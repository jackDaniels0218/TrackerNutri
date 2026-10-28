"""
RF18 Gráficos de tendencias y reportes.

Series para Chart.js con filtros de 7, 30 y 90 días, exportación a CSV y
paneles agregados y anonimizados para el Administrador y el Curador.

Todas las cifras salen de los registros guardados (confirmados o editados):
nunca se muestran datos de ejemplo a un usuario real.
"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone

from core.models import (
    Alimento,
    Comida,
    Correccion,
    DiaRegistro,
    EjecucionExactitud,
    ItemComida,
    MetaCalorica,
    MotorInterpretacion,
    Pesaje,
    Rol,
    TerminoPendiente,
)
from core.services.calculo import r1

CERO = Decimal("0")
PERIODOS = (7, 30, 90)


def comidas_del_dia(usuario, fecha):
    return Comida.objects.filter(usuario=usuario, fecha_hora__date=fecha).que_cuentan()


def kcal_del_dia(usuario, fecha) -> Decimal:
    return Decimal(comidas_del_dia(usuario, fecha).aggregate(t=Sum("kcal"))["t"] or 0)


def meta_en(usuario, fecha):
    return (
        MetaCalorica.objects.filter(usuario=usuario, fecha_inicio__lte=fecha)
        .filter(Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=fecha))
        .exclude(revertida=True)
        .order_by("-creada_en")
        .first()
    )


def resumen_dia(usuario, fecha) -> dict:
    """Lo que muestra el tablero del día."""
    comidas = comidas_del_dia(usuario, fecha)
    agregados = comidas.aggregate(
        kcal=Sum("kcal"), kcal_min=Sum("kcal_min"), kcal_max=Sum("kcal_max"), proteinas=Sum("proteinas"),
        carbohidratos=Sum("carbohidratos"), grasas=Sum("grasas"), azucares=Sum("azucares"), aceite=Sum("aceite_g"),
        confianza=Avg("confianza"),
    )
    datos = {k: Decimal(v or 0) for k, v in agregados.items()}
    meta = meta_en(usuario, fecha)
    meta_kcal = meta.kcal_dia if meta else None
    restantes = exceso = None
    if meta_kcal:
        diferencia = meta_kcal - datos["kcal"]
        restantes = r1(max(diferencia, CERO))
        exceso = r1(max(-diferencia, CERO))
    dia = DiaRegistro.objects.filter(usuario=usuario, fecha=fecha).first()
    return {
        "fecha": fecha,
        "comidas": comidas.prefetch_related("items"),
        "numero_comidas": comidas.count(),
        **{k: r1(v) for k, v in datos.items()},
        "meta": meta,
        "meta_kcal": meta_kcal,
        "restantes": restantes,
        "exceso": exceso,
        "meta_superada": bool(exceso),
        "porcentaje": r1(datos["kcal"] / meta_kcal * 100) if meta_kcal else None,
        "dia_completo": bool(dia and dia.completo),
        "baja_confianza": datos["confianza"] and datos["confianza"] < Decimal("0.6"),
    }


def _media_movil(valores: list, ventana: int = 7) -> list:
    resultado = []
    for i in range(len(valores)):
        tramo = [v for v in valores[max(0, i - ventana + 1): i + 1] if v is not None]
        resultado.append(round(sum(tramo) / len(tramo), 1) if tramo else None)
    return resultado


def series(usuario, dias: int = 30, hasta=None) -> dict:
    """Datos para los seis gráficos del módulo de reportes."""
    if dias not in PERIODOS:
        dias = 30
    hasta = hasta or timezone.localdate()
    inicio = hasta - timedelta(days=dias - 1)
    fechas = [inicio + timedelta(days=i) for i in range(dias)]

    comidas = Comida.objects.filter(usuario=usuario, fecha_hora__date__gte=inicio, fecha_hora__date__lte=hasta).que_cuentan()
    por_dia = defaultdict(lambda: defaultdict(lambda: CERO))
    for c in comidas:
        f = timezone.localtime(c.fecha_hora).date()
        for campo in ("kcal", "kcal_min", "kcal_max", "proteinas", "carbohidratos", "grasas", "azucares", "aceite_g"):
            por_dia[f][campo] += getattr(c, campo)
        por_dia[f]["registros"] += 1

    kcal = [float(por_dia[f]["kcal"]) if por_dia[f]["registros"] else None for f in fechas]
    metas = []
    for f in fechas:
        meta = meta_en(usuario, f)
        metas.append(float(meta.kcal_dia) if meta else None)

    pesajes = {p.fecha: p.peso_kg for p in Pesaje.objects.filter(usuario=usuario, fecha__gte=inicio, fecha__lte=hasta)}
    from core.services.salvaguardas import peso_tendencial

    tendencial = {f: t for f, _, t in peso_tendencial(usuario, hasta)}

    # Agregados semanales: aceite y cumplimiento.
    semanas = defaultdict(lambda: {"aceite": CERO, "dias": 0, "cumplidos": 0})
    completos = set(DiaRegistro.objects.filter(usuario=usuario, completo=True, fecha__gte=inicio).values_list("fecha", flat=True))
    for f, valor, meta in zip(fechas, kcal, metas):
        clave = f - timedelta(days=f.weekday())
        semanas[clave]["aceite"] += por_dia[f]["aceite_g"]
        if f in completos and valor is not None and meta:
            semanas[clave]["dias"] += 1
            if abs(valor - meta) <= meta * 0.1:
                semanas[clave]["cumplidos"] += 1
    semanas_ordenadas = sorted(semanas)

    items = ItemComida.objects.filter(comida__in=comidas, descartado=False)
    fuentes_azucar = (items.values("nombre_mostrado").annotate(total=Sum("azucares")).filter(total__gt=0).order_by("-total")[:5])
    fuentes_aceite = (items.values("nombre_mostrado").annotate(total=Sum("aceite_g")).filter(total__gt=0).order_by("-total")[:5])

    return {
        "dias": dias,
        "etiquetas": [f.strftime("%d/%m") for f in fechas],
        "ingesta": {
            "kcal": kcal,
            "min": [float(por_dia[f]["kcal_min"]) if por_dia[f]["registros"] else None for f in fechas],
            "max": [float(por_dia[f]["kcal_max"]) if por_dia[f]["registros"] else None for f in fechas],
            "media_movil": _media_movil(kcal),
            "meta": metas,
        },
        "peso": {
            "real": [float(pesajes[f]) if f in pesajes else None for f in fechas],
            "tendencial": [float(tendencial[f]) if f in tendencial and f in pesajes else None for f in fechas],
        },
        "macros": {
            "proteinas": [float(por_dia[f]["proteinas"]) for f in fechas],
            "carbohidratos": [float(por_dia[f]["carbohidratos"]) for f in fechas],
            "grasas": [float(por_dia[f]["grasas"]) for f in fechas],
        },
        "azucares": [float(por_dia[f]["azucares"]) for f in fechas],
        "fuentes_azucar": [{"nombre": x["nombre_mostrado"], "g": float(x["total"])} for x in fuentes_azucar],
        "aceite_semanal": {
            "etiquetas": [f"Semana del {s:%d/%m}" for s in semanas_ordenadas],
            "g": [float(semanas[s]["aceite"]) for s in semanas_ordenadas],
        },
        "fuentes_aceite": [{"nombre": x["nombre_mostrado"], "g": float(x["total"])} for x in fuentes_aceite],
        "cumplimiento": {
            "etiquetas": [f"Semana del {s:%d/%m}" for s in semanas_ordenadas],
            "pct": [round(semanas[s]["cumplidos"] / semanas[s]["dias"] * 100) if semanas[s]["dias"] else None for s in semanas_ordenadas],
        },
        "evolucion_meta": [
            {"fecha": m.fecha_inicio.strftime("%d/%m/%Y"), "kcal": float(m.kcal_dia), "origen": m.get_origen_display()}
            for m in MetaCalorica.objects.filter(usuario=usuario).order_by("creada_en")
        ],
        "tiene_datos": any(v is not None for v in kcal) or bool(pesajes),
    }


# --- Exportación ---------------------------------------------------------------


def exportar_csv(usuario) -> str:
    """Todas las comidas confirmadas y los pesajes del usuario en CSV (UTF-8)."""
    salida = io.StringIO()
    escritor = csv.writer(salida)
    escritor.writerow(["fecha", "hora", "tipo", "origen", "componente", "cantidad_g", "metodo", "kcal", "kcal_min",
                       "kcal_max", "proteinas_g", "carbohidratos_g", "azucares_g", "grasas_g", "aceite_g", "confianza", "editado"])
    comidas = Comida.objects.filter(usuario=usuario).que_cuentan().order_by("fecha_hora").prefetch_related("items__metodo")
    for c in comidas:
        momento = timezone.localtime(c.fecha_hora)
        for i in c.items.all():
            if i.descartado:
                continue
            escritor.writerow([momento.date(), momento.strftime("%H:%M"), c.get_tipo_display(), c.get_origen_display(),
                               i.nombre_mostrado, i.cantidad_g, i.metodo.nombre if i.metodo else "", i.kcal, i.kcal_min,
                               i.kcal_max, i.proteinas, i.carbohidratos, i.azucares, i.grasas, i.aceite_g, i.confianza,
                               "sí" if i.editado else "no"])
    escritor.writerow([])
    escritor.writerow(["fecha", "peso_kg", "observacion"])
    for p in Pesaje.objects.filter(usuario=usuario).order_by("fecha"):
        escritor.writerow([p.fecha, p.peso_kg, p.observacion])
    return salida.getvalue()


def exportar_todo(usuario) -> dict:
    """Portabilidad de datos (Ley 1581): todo lo del titular en JSON."""
    perfil = getattr(usuario, "perfil", None)
    cuenta = getattr(usuario, "cuenta", None)
    return {
        "cuenta": {
            "correo": usuario.email, "nombres": usuario.first_name, "apellidos": usuario.last_name,
            "fecha_registro": usuario.date_joined.isoformat(),
            "acepta_datos": cuenta.acepta_datos if cuenta else None, "acepta_ia": cuenta.acepta_ia if cuenta else None,
        },
        "perfil": None if perfil is None else {
            "fecha_nacimiento": perfil.fecha_nacimiento.isoformat(), "sexo": perfil.sexo, "estatura_cm": perfil.estatura_cm,
            "peso_inicial_kg": str(perfil.peso_inicial_kg), "nivel_actividad": perfil.nivel_actividad,
            "objetivo": perfil.objetivo, "peso_meta_kg": str(perfil.peso_meta_kg or ""), "ritmo": perfil.ritmo,
        },
        "consentimientos": [
            {"tipo": c.tipo, "otorgado": c.otorgado, "version": c.version_texto, "fecha": c.fecha.isoformat()}
            for c in usuario.consentimientos.all()
        ],
        "metas": [
            {"desde": m.fecha_inicio.isoformat(), "kcal": str(m.kcal_dia), "origen": m.origen, "motivo": m.motivo}
            for m in usuario.metas.order_by("creada_en")
        ],
        "pesajes": [{"fecha": p.fecha.isoformat(), "kg": str(p.peso_kg)} for p in usuario.pesajes.order_by("fecha")],
        "comidas": [
            {
                "fecha_hora": c.fecha_hora.isoformat(), "texto": c.texto_original, "tipo": c.tipo, "estado": c.estado,
                "kcal": str(c.kcal), "items": [
                    {"nombre": i.nombre_mostrado, "cantidad_g": str(i.cantidad_g or ""), "kcal": str(i.kcal or "")}
                    for i in c.items.all()
                ],
            }
            for c in usuario.comidas.order_by("fecha_hora").prefetch_related("items")
        ],
    }


# --- Paneles agregados (Administrador y Curador) ----------------------------------


def panel_agregado() -> dict:
    """Indicadores sin datos personales: solo conteos y promedios."""
    User = get_user_model()
    comidas = Comida.objects.que_cuentan()
    items = ItemComida.objects.filter(comida__in=comidas, descartado=False)
    total_items = items.count()
    texto = comidas.filter(origen="texto")
    ultima = EjecucionExactitud.objects.first()
    return {
        "usuarios_por_rol": {r.label: User.objects.filter(cuenta__rol=r).count() for r in Rol},
        "comidas": comidas.count(),
        "comidas_texto": texto.count(),
        "sin_ia_pct": r1(texto.exclude(motor=MotorInterpretacion.IA_EXTERNA).count() / texto.count() * 100) if texto.count() else None,
        "items": total_items,
        "corregidos_pct": r1(items.filter(editado=True).count() / total_items * 100) if total_items else None,
        "correcciones": Correccion.objects.count(),
        "tasa_correccion_pct": r1(Correccion.objects.count() / total_items * 100) if total_items else None,
        "estimados_pct": r1(items.filter(estimado=True).count() / total_items * 100) if total_items else None,
        "confianza_media": items.aggregate(m=Avg("confianza"))["m"],
        "terminos_pendientes": TerminoPendiente.objects.filter(estado=TerminoPendiente.Estado.PENDIENTE).order_by("-veces")[:10],
        "alimentos_personales_pendientes": Alimento.objects.filter(ambito="personal", verificado=False).count(),
        "ultima_exactitud": ultima,
        "comidas_por_origen": list(comidas.values("origen").annotate(n=Count("id")).order_by("-n")),
    }
