"""
RF8 Metas calóricas y RF16 Cálculo de metas y ajuste automático semanal.

META INICIAL
    TMB (Mifflin-St Jeor) = 10 × peso + 6,25 × estatura − 5 × edad + 5 (hombres)
                                                                 − 161 (mujeres)
    GET  = TMB × factor de actividad
    Meta = GET × (1 − déficit), con el déficit según el ritmo, limitado al
           máximo y nunca por debajo del piso calórico.
    Macros: proteína por kg de peso, grasa como % de la energía, el resto en
            carbohidratos.

AJUSTE SEMANAL (si hay al menos 5 días completos y 2 pesajes)
    GET observado = ingesta media + (pérdida de peso × 7700 kcal/kg) / días
    GET nuevo     = mezcla suavizada del estimado y el observado
    Meta nueva    = GET nuevo × (1 − déficit), con un cambio máximo semanal,
                    sin bajar del piso ni superar el déficit máximo.
    El usuario puede revertirlo durante 48 horas.

Todo cálculo queda en la tabla de metas con su motivo y sus datos de entrada.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from core.models import DiaRegistro, MetaCalorica, Notificacion, Objetivo, OrigenMeta, Pesaje, Sexo
from core.services import auditoria, salvaguardas
from core.services.calculo import r1
from core.services.parametros import parametro

CERO = Decimal("0")


def tmb_mifflin(peso_kg, estatura_cm, edad: int, sexo: str) -> Decimal:
    base = Decimal("10") * Decimal(peso_kg) + Decimal("6.25") * Decimal(estatura_cm) - Decimal("5") * edad
    return base + (Decimal("5") if sexo == Sexo.MASCULINO else Decimal("-161"))


def peso_actual(usuario) -> Decimal:
    ultimo = Pesaje.objects.filter(usuario=usuario).order_by("-fecha").first()
    if ultimo:
        return ultimo.peso_kg
    return usuario.perfil.peso_inicial_kg


@dataclass
class CalculoMeta:
    tmb: Decimal
    gasto_total: Decimal
    kcal: Decimal
    deficit_pct: Decimal
    proteinas_g: Decimal
    carbohidratos_g: Decimal
    grasas_g: Decimal
    solo_informativa: bool
    pasos: list[str]


def macros_para(kcal: Decimal, peso_kg: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    proteina = parametro("proteina_g_por_kg") * Decimal(peso_kg)
    grasa = kcal * parametro("grasa_pct_energia") / 100 / 9
    carbohidratos = max(CERO, (kcal - proteina * 4 - grasa * 9) / 4)
    return r1(proteina), r1(carbohidratos), r1(grasa)


def calcular_meta(perfil, *, peso_kg=None, gasto_total=None) -> CalculoMeta:
    """Meta según el perfil. Si se pasa `gasto_total`, se usa en vez del estimado."""
    peso = Decimal(peso_kg if peso_kg is not None else perfil.peso_inicial_kg)
    edad = perfil.edad
    tmb = tmb_mifflin(peso, perfil.estatura_cm, edad, perfil.sexo)
    factor = Decimal(str(parametro("factores_actividad")[perfil.nivel_actividad]))
    gasto = Decimal(gasto_total) if gasto_total is not None else tmb * factor
    signo = "+ 5" if perfil.sexo == Sexo.MASCULINO else "− 161"
    pasos = [
        f"Tasa metabólica basal (Mifflin-St Jeor): 10 × {peso} kg + 6,25 × {perfil.estatura_cm} cm − 5 × {edad} años {signo} = {r1(tmb)} kcal.",
    ]
    if gasto_total is None:
        pasos.append(f"Gasto energético total: {r1(tmb)} × {factor} (actividad {perfil.get_nivel_actividad_display().lower()}) = {r1(gasto)} kcal.")
    else:
        pasos.append(f"Gasto energético total observado con tus registros: {r1(gasto)} kcal.")

    eleg = salvaguardas.elegibilidad(perfil)
    if not eleg.elegible:
        deficit = CERO
        pasos.append(
            "No se aplica déficit porque " + ", ".join(eleg.motivos) +
            ". Tu seguimiento es informativo; te recomendamos consultar a un profesional."
        )
    elif perfil.objetivo == Objetivo.MANTENER:
        deficit = CERO
        pasos.append("Tu objetivo es mantener el peso: la meta es igual a tu gasto.")
    else:
        deficit = Decimal(str(parametro("deficit_por_ritmo")[perfil.ritmo]))
        maximo = parametro("deficit_maximo_pct")
        if deficit > maximo:
            deficit = maximo
        pasos.append(f"Déficit para un ritmo {perfil.get_ritmo_display().lower()}: {deficit} %.")

    kcal = gasto * (1 - deficit / 100)
    kcal, avisos = salvaguardas.aplicar_limites(kcal, gasto, perfil.sexo) if deficit > 0 else (kcal, [])
    pasos += avisos
    pasos.append(f"Meta diaria: {r1(kcal):.0f} kcal.")
    proteina, carbohidratos, grasa = macros_para(kcal, peso)
    pasos.append(
        f"Reparto: {proteina:.0f} g de proteína ({parametro('proteina_g_por_kg')} g por kg), "
        f"{grasa:.0f} g de grasa ({parametro('grasa_pct_energia')} % de la energía) y {carbohidratos:.0f} g de carbohidratos."
    )
    efectivo = (1 - kcal / gasto) * 100 if gasto else CERO
    return CalculoMeta(r1(tmb), r1(gasto), r1(kcal), r1(efectivo), proteina, carbohidratos, grasa, not eleg.elegible, pasos)


def meta_vigente(usuario) -> MetaCalorica | None:
    return MetaCalorica.objects.filter(usuario=usuario, vigente=True).first()


@transaction.atomic
def registrar_meta(usuario, calculo: CalculoMeta, *, origen: str, motivo: str, datos_entrada: dict | None = None,
                   revertible: bool = False) -> MetaCalorica:
    """Cierra la meta vigente y crea la nueva. Solo una vigente por usuario."""
    anterior = meta_vigente(usuario)
    hoy = timezone.localdate()
    if anterior:
        anterior.vigente = False
        anterior.fecha_fin = hoy
        anterior.save(update_fields=["vigente", "fecha_fin"])
    meta = MetaCalorica.objects.create(
        usuario=usuario, fecha_inicio=hoy, vigente=True, tmb=calculo.tmb, gasto_total=calculo.gasto_total,
        kcal_dia=calculo.kcal, deficit_pct=calculo.deficit_pct, proteinas_g=calculo.proteinas_g,
        carbohidratos_g=calculo.carbohidratos_g, grasas_g=calculo.grasas_g, origen=origen, motivo=motivo,
        explicacion={"pasos": calculo.pasos, "entrada": datos_entrada or {}},
        solo_informativa=calculo.solo_informativa, meta_anterior=anterior,
        revertible_hasta=(timezone.now() + timedelta(hours=parametro("horas_para_revertir"))) if revertible else None,
    )
    auditoria.registrar("meta_registrada", usuario=usuario, entidad="MetaCalorica", entidad_id=meta.pk,
                        detalle=f"{meta.get_origen_display()}: {meta.kcal_dia:.0f} kcal.")
    return meta


def meta_inicial(usuario) -> MetaCalorica:
    perfil = usuario.perfil
    calculo = calcular_meta(perfil)
    return registrar_meta(usuario, calculo, origen=OrigenMeta.INICIAL, motivo="Meta inicial calculada con tu perfil.",
                          datos_entrada=_entrada_perfil(perfil))


def recalcular_por_perfil(usuario) -> MetaCalorica:
    """Un cambio de peso, actividad u objetivo dispara el recálculo (RF2)."""
    perfil = usuario.perfil
    calculo = calcular_meta(perfil, peso_kg=peso_actual(usuario))
    return registrar_meta(usuario, calculo, origen=OrigenMeta.RECALCULO,
                          motivo="Recalculada porque cambiaste datos de tu perfil.",
                          datos_entrada=_entrada_perfil(perfil))


def _entrada_perfil(perfil) -> dict:
    return {
        "peso_kg": str(perfil.peso_inicial_kg), "estatura_cm": perfil.estatura_cm, "edad": perfil.edad,
        "sexo": perfil.sexo, "actividad": perfil.nivel_actividad, "objetivo": perfil.objetivo, "ritmo": perfil.ritmo,
    }


class AjusteNoPermitido(ValueError):
    pass


def ajuste_manual(usuario, kcal_propuestas) -> MetaCalorica:
    """El usuario propone su meta; se acepta solo dentro de los límites de seguridad."""
    perfil = usuario.perfil
    vigente = meta_vigente(usuario)
    if vigente is None:
        raise AjusteNoPermitido("Todavía no tienes una meta calculada.")
    propuesta = Decimal(str(kcal_propuestas))
    ajustada, avisos = salvaguardas.aplicar_limites(propuesta, vigente.gasto_total, perfil.sexo)
    if vigente.solo_informativa and propuesta < vigente.gasto_total:
        raise AjusteNoPermitido("Con tu perfil actual no se aplica déficit. Consulta a un profesional.")
    if avisos:
        raise AjusteNoPermitido(
            f"Esa meta queda fuera de los límites de seguridad. {' '.join(avisos)} El mínimo para ti es {ajustada:.0f} kcal."
        )
    proteina, carbohidratos, grasa = macros_para(propuesta, peso_actual(usuario))
    deficit = (1 - propuesta / vigente.gasto_total) * 100
    calculo = CalculoMeta(vigente.tmb, vigente.gasto_total, r1(propuesta), r1(deficit), proteina, carbohidratos, grasa,
                          False, [f"Meta propuesta por ti: {propuesta:.0f} kcal (déficit {r1(deficit)} %).",
                                  "Está dentro de los límites de seguridad."])
    return registrar_meta(usuario, calculo, origen=OrigenMeta.MANUAL, motivo="Ajuste manual dentro de los límites.",
                          datos_entrada={"propuesta": str(propuesta)})


# --- Ajuste automático semanal ---------------------------------------------------


@dataclass
class ResultadoAjuste:
    aplicado: bool
    mensaje: str
    meta: MetaCalorica | None = None


def evaluar_ajuste_semanal(usuario, hasta=None) -> ResultadoAjuste:
    """
    Evalúa y, si corresponde, aplica el ajuste de la semana. Siempre devuelve
    un mensaje en lenguaje sencillo que explica qué pasó.
    """
    from core.services.reportes import kcal_del_dia

    hasta = hasta or timezone.localdate()
    perfil = getattr(usuario, "perfil", None)
    vigente = meta_vigente(usuario)
    cuenta = getattr(usuario, "cuenta", None)
    if perfil is None or vigente is None:
        return ResultadoAjuste(False, "Aún no tienes perfil o meta.")
    if cuenta and cuenta.seguimiento_pausado:
        return ResultadoAjuste(False, "Tu seguimiento está en pausa: no se ajusta la meta.")
    if vigente.solo_informativa:
        return ResultadoAjuste(False, "Tu seguimiento es informativo: no se aplican ajustes de déficit.")

    inicio = hasta - timedelta(days=6)
    completos = list(DiaRegistro.objects.filter(usuario=usuario, completo=True, fecha__gte=inicio, fecha__lte=hasta)
                     .values_list("fecha", flat=True))
    pesajes = Pesaje.objects.filter(usuario=usuario, fecha__gte=hasta - timedelta(days=13), fecha__lte=hasta).count()
    if len(completos) < parametro("dias_completos_minimos") or pesajes < parametro("pesajes_minimos"):
        return ResultadoAjuste(False,
            f"No ajustamos tu meta esta semana: hacen falta al menos {parametro('dias_completos_minimos')} días "
            f"marcados como completos y {parametro('pesajes_minimos')} pesajes (tienes {len(completos)} y {pesajes}).")

    if salvaguardas.detectar_riesgos(usuario, hasta):
        salvaguardas.notificar_riesgos(usuario, hasta)
        return ResultadoAjuste(False, "Detectamos una señal de cuidado: no reducimos tu meta y te recomendamos hablar con un profesional.")

    actual = peso_actual(usuario)
    if perfil.peso_meta_kg and actual <= perfil.peso_meta_kg and perfil.objetivo == Objetivo.PERDER:
        from core.services.notificaciones import notificar

        notificar(usuario, Notificacion.Tipo.META, "Alcanzaste tu peso meta",
                  "Puedes pasar a mantenimiento cuando quieras desde tu página de metas.", url="/metas/")
        return ResultadoAjuste(False, "Alcanzaste tu peso meta: te proponemos pasar a mantenimiento.")

    ingesta_media = sum((kcal_del_dia(usuario, d) for d in completos), CERO) / len(completos)
    serie = salvaguardas.peso_tendencial(usuario, hasta)
    recientes = [s for s in serie if (hasta - s[0]).days <= 13]
    dias = max(1, (recientes[-1][0] - recientes[0][0]).days)
    cambio_kg = recientes[-1][2] - recientes[0][2]
    gasto_observado = ingesta_media - cambio_kg * parametro("kcal_por_kg") / dias
    suavizado = parametro("suavizado_gasto")
    gasto_nuevo = vigente.gasto_total * (1 - suavizado) + gasto_observado * suavizado

    calculo = calcular_meta(perfil, peso_kg=actual, gasto_total=gasto_nuevo)
    cambio_max = min(parametro("ajuste_semanal_max_kcal"), vigente.kcal_dia * parametro("ajuste_max_pct_meta") / 100)
    diferencia = calculo.kcal - vigente.kcal_dia
    if abs(diferencia) > cambio_max:
        limitada = vigente.kcal_dia + (cambio_max if diferencia > 0 else -cambio_max)
        limitada, _ = salvaguardas.aplicar_limites(limitada, gasto_nuevo, perfil.sexo)
        proteina, carbohidratos, grasa = macros_para(limitada, actual)
        calculo.pasos.append(f"El cambio se limitó a {cambio_max:.0f} kcal por semana para evitar saltos bruscos.")
        calculo.kcal, calculo.proteinas_g, calculo.carbohidratos_g, calculo.grasas_g = r1(limitada), proteina, carbohidratos, grasa
    if abs(calculo.kcal - vigente.kcal_dia) < 20:
        return ResultadoAjuste(False, "Tu meta actual sigue siendo adecuada: no hace falta cambiarla.")

    entrada = {"ingesta_media": str(r1(ingesta_media)), "dias_completos": len(completos),
               "cambio_peso_kg": str(r1(cambio_kg)), "dias_peso": dias, "gasto_observado": str(r1(gasto_observado))}
    calculo.pasos.insert(0, f"Comiste en promedio {ingesta_media:.0f} kcal en {len(completos)} días completos y tu peso "
                            f"tendencial cambió {cambio_kg:+.1f} kg en {dias} días.")
    direccion = "subimos" if calculo.kcal > vigente.kcal_dia else "bajamos"
    motivo = (f"Con tus registros de la semana {direccion} tu meta de {vigente.kcal_dia:.0f} a {calculo.kcal:.0f} kcal. "
              f"Puedes revertir este cambio durante {parametro('horas_para_revertir')} horas.")
    meta = registrar_meta(usuario, calculo, origen=OrigenMeta.AUTOMATICO, motivo=motivo, datos_entrada=entrada, revertible=True)

    from core.services.notificaciones import notificar

    notificar(usuario, Notificacion.Tipo.META, "Ajustamos tu meta de la semana", motivo, url="/metas/", correo=True)
    return ResultadoAjuste(True, motivo, meta)


@transaction.atomic
def revertir(meta: MetaCalorica) -> MetaCalorica:
    if not meta.puede_revertirse:
        raise AjusteNoPermitido("Este ajuste ya no se puede revertir.")
    anterior = meta.meta_anterior
    meta.vigente = False
    meta.revertida = True
    meta.fecha_fin = timezone.localdate()
    meta.save(update_fields=["vigente", "revertida", "fecha_fin"])
    restaurada = MetaCalorica.objects.create(
        usuario=meta.usuario, fecha_inicio=timezone.localdate(), vigente=True, tmb=anterior.tmb,
        gasto_total=anterior.gasto_total, kcal_dia=anterior.kcal_dia, deficit_pct=anterior.deficit_pct,
        proteinas_g=anterior.proteinas_g, carbohidratos_g=anterior.carbohidratos_g, grasas_g=anterior.grasas_g,
        origen=OrigenMeta.REVERSION, motivo=f"Revertiste el ajuste del {meta.fecha_inicio:%d/%m/%Y}.",
        explicacion=anterior.explicacion, solo_informativa=anterior.solo_informativa, meta_anterior=meta,
    )
    auditoria.registrar("meta_revertida", usuario=meta.usuario, entidad="MetaCalorica", entidad_id=meta.pk)
    return restaurada


def pasar_a_mantenimiento(usuario) -> MetaCalorica:
    perfil = usuario.perfil
    perfil.objetivo = Objetivo.MANTENER
    perfil.save(update_fields=["objetivo", "actualizado_en"])
    calculo = calcular_meta(perfil, peso_kg=peso_actual(usuario))
    return registrar_meta(usuario, calculo, origen=OrigenMeta.MANTENIMIENTO, motivo="Pasaste a mantenimiento.")


def ajuste_semanal_todos(hasta=None) -> dict:
    """Proceso en lote para todos los usuarios (`manage.py procesos ajuste_semanal`)."""
    from django.contrib.auth import get_user_model

    from core.models import EstadoCuenta, Rol

    resumen = {"evaluados": 0, "ajustados": 0}
    usuarios = get_user_model().objects.filter(cuenta__rol=Rol.USUARIO, cuenta__estado=EstadoCuenta.ACTIVO, perfil__isnull=False)
    for usuario in usuarios:
        resultado = evaluar_ajuste_semanal(usuario, hasta)
        resumen["evaluados"] += 1
        resumen["ajustados"] += int(resultado.aplicado)
    return resumen
