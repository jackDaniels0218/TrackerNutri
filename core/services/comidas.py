"""
RF7 Registro de comidas: flujo completo de una comida.

    texto libre ──► crear_desde_texto() ──► estado "interpretada"
                         │  (preguntas de aclaración, si hacen falta)
                         ▼
                    responder_preguntas() / editar_item() / agregar_item()
                         │
                         ▼
                    confirmar() ──► estado "confirmada"  (cuenta en los totales)
                         │
                    editar_item() ──► estado "editada"
                    descartar()   ──► estado "descartada" (baja lógica)

    búsqueda manual ──► crear_manual() ──► "confirmada" directamente
    favorita        ──► repetir_favorita() ──► "confirmada"

Todas las operaciones que tocan varias tablas son atómicas (RNF28).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from core.models import (
    Alimento,
    Comida,
    EstadoComida,
    ItemComida,
    MetodoCoccion,
    MotorInterpretacion,
    OrigenComida,
    OrigenDato,
    PorcionCasera,
    Preparacion,
    TipoComida,
    VersionCatalogo,
)
from core.services import calculo
from core.services.calculo import CantidadInvalida, Solicitud, r1
from core.services.interpretacion import (
    calcular_confianza,
    interpretar,
    preguntas_para,
)

CERO = Decimal("0")


class ComidaNoConfirmable(ValueError):
    pass


def _version_catalogo():
    version = VersionCatalogo.publicada_vigente()
    return version.numero if version else None


def _es_liquido(destino) -> bool:
    if isinstance(destino, Alimento):
        return destino.es_liquido
    if isinstance(destino, Preparacion):
        return destino.es_bebida
    return False


# --- Cálculo de un ítem ----------------------------------------------------------


def calcular_item(item: ItemComida) -> ItemComida:
    """Recalcula un ítem con el motor determinista y guarda la instantánea."""
    destino = item.destino
    if destino is None or item.descartado or not item.cantidad_g:
        for campo in ("kcal", "proteinas", "carbohidratos", "azucares", "grasas", "kcal_min", "kcal_max"):
            setattr(item, campo, None)
        item.aceite_g = item.aceite_min_g = item.aceite_max_g = CERO
        return item
    resultado = calculo.calcular(Solicitud(
        destino=destino, cantidad_g=item.cantidad_g, metodo=item.metodo,
        fuente_cantidad=item.fuente_cantidad, tamano=item.tamano, escurrido=item.escurrido,
        aceite_agregado_g=item.aceite_agregado_g, aplicar_rendimiento=item.aplicar_rendimiento,
    ))
    for campo in ("kcal", "proteinas", "carbohidratos", "azucares", "grasas", "kcal_min", "kcal_max"):
        setattr(item, campo, getattr(resultado, campo))
    item.aceite_g, item.aceite_min_g, item.aceite_max_g = resultado.aceite_g, resultado.aceite_min_g, resultado.aceite_max_g
    if item.metodo is None and resultado.metodo is not None:
        item.metodo = resultado.metodo
    item.estimado = resultado.estimado or item.origen_dato in (OrigenDato.SIMILITUD, OrigenDato.IA)
    interpretacion = item.detalle_calculo.get("interpretacion", {}) if item.detalle_calculo else {}
    item.detalle_calculo = {**resultado.detalle(), "interpretacion": interpretacion}
    return item


def actualizar_totales(comida: Comida) -> Comida:
    items = [i for i in comida.items.all() if not i.descartado and i.kcal is not None]
    for campo in ("kcal", "proteinas", "carbohidratos", "azucares", "grasas", "aceite_g", "kcal_min", "kcal_max"):
        setattr(comida, campo, r1(sum((getattr(i, campo) or CERO for i in items), CERO)))
    total_kcal = sum((i.kcal for i in items), CERO)
    if items and total_kcal > 0:
        ponderada = sum((i.confianza * i.kcal for i in items), CERO) / total_kcal
        comida.confianza = ponderada.quantize(Decimal("0.01"))
    elif items:
        comida.confianza = min(i.confianza for i in items)
    comida.save()
    return comida


# --- Desde texto libre (RF13) ----------------------------------------------------


def _origen_dato(origen_resolucion: str) -> str:
    return {
        "lexico": OrigenDato.CATALOGO,
        "similitud": OrigenDato.SIMILITUD,
        "semantica": OrigenDato.SIMILITUD,
        "ia": OrigenDato.IA,
    }.get(origen_resolucion, OrigenDato.CATALOGO)


@transaction.atomic
def crear_desde_texto(usuario, texto: str, *, fecha_hora=None, tipo: str | None = None) -> Comida:
    """
    Interpreta el texto y guarda una comida en estado "interpretada".

    Todavía no cuenta en los totales: el usuario tiene que confirmarla.
    """
    texto = (texto or "").strip()
    if len(texto) < 3:
        raise ComidaNoConfirmable("Describe lo que comiste con un poco más de detalle.")

    # Si quedó una interpretación sin confirmar de antes, se descarta para no acumular borradores.
    Comida.objects.filter(usuario=usuario, estado=EstadoComida.INTERPRETADA).update(estado=EstadoComida.DESCARTADA)

    resultado = interpretar(texto, usuario=usuario)
    motor = {
        "ia_externa": MotorInterpretacion.IA_EXTERNA,
        "modelo_local": MotorInterpretacion.MODELO_LOCAL,
    }.get(resultado.motor, MotorInterpretacion.REGLAS)
    comida = Comida.objects.create(
        usuario=usuario, texto_original=texto[:500], fecha_hora=fecha_hora or timezone.now(),
        tipo=tipo or resultado.tipo_comida, origen=OrigenComida.TEXTO, estado=EstadoComida.INTERPRETADA,
        motor=motor, version_motor=calculo.VERSION_MOTOR, version_catalogo=_version_catalogo(),
        version_plantilla_ia=resultado.version_plantilla_ia,
    )

    pares = []
    for interpretado in resultado.items:
        destino = interpretado.destino
        item = ItemComida(
            comida=comida,
            alimento=destino if isinstance(destino, Alimento) else None,
            preparacion=destino if isinstance(destino, Preparacion) else None,
            nombre_mostrado=destino.nombre if destino else interpretado.texto_alimento or interpretado.fragmento,
            fragmento_texto=interpretado.fragmento[:200],
            cantidad_original=interpretado.cantidad_original or interpretado.cuenta,
            unidad_original=interpretado.unidad_original[:30],
            cantidad_g=r1(interpretado.cantidad_g) if interpretado.cantidad_g else None,
            medida=interpretado.medida,
            fuente_cantidad=interpretado.fuente_cantidad,
            metodo=interpretado.metodo,
            origen_metodo=interpretado.origen_metodo,
            tamano=interpretado.tamano,
            escurrido=interpretado.escurrido,
            aceite_agregado_g=interpretado.aceite_agregado_g,
            aplicar_rendimiento=interpretado.aplicar_rendimiento,
            confianza=interpretado.confianza,
            origen_dato=_origen_dato(interpretado.origen_resolucion),
            pendiente=destino is None,
            notas="\n".join(interpretado.notas),
            detalle_calculo={"interpretacion": {
                "resolucion": str(interpretado.puntaje_resolucion),
                "origen": interpretado.origen_resolucion,
                "candidatos": [f"{'p' if isinstance(c, Preparacion) else 'a'}{c.pk}" for c in interpretado.candidatos],
            }},
        )
        calcular_item(item)
        item.save()
        interpretado.nombre_mostrado = item.nombre_mostrado
        pares.append((item.pk, interpretado, item.kcal or CERO))

    comida.preguntas = preguntas_para(pares)
    actualizar_totales(comida)
    # Avisos para mostrar una sola vez (por ejemplo, por qué no se usó la IA).
    comida.avisos_interpretacion = resultado.avisos
    return comida


def _resolucion(item: ItemComida) -> Decimal:
    datos = (item.detalle_calculo or {}).get("interpretacion", {})
    return Decimal(datos.get("resolucion", "1"))


def recalcular_confianza(item: ItemComida) -> None:
    item.confianza = calcular_confianza(
        _resolucion(item), item.fuente_cantidad, bool(item.tamano), _es_liquido(item.destino), item.origen_metodo
    )


def _destino_desde_valor(valor: str):
    """'a12' → Alimento 12; 'p5' → Preparación 5."""
    if not valor or valor[0] not in "ap" or not valor[1:].isdigit():
        return None
    modelo = Alimento if valor[0] == "a" else Preparacion
    return modelo.objects.filter(pk=int(valor[1:])).first()


def _cantidad_por_porcion(item: ItemComida, medida: str) -> bool:
    destino = item.destino
    filtro = {"preparacion": destino} if isinstance(destino, Preparacion) else {"alimento": destino}
    porcion = PorcionCasera.objects.filter(medida=medida, **filtro).first()
    if porcion is None:
        return False
    cuenta = item.cantidad_original if (item.cantidad_original and item.unidad_original not in ("g", "ml", "gramos")) else Decimal("1")
    densidad = destino.densidad if isinstance(destino, Alimento) and destino.densidad and _es_liquido(destino) else Decimal("1")
    item.cantidad_g = r1(porcion.cantidad * densidad * (cuenta or 1))
    item.medida = medida
    item.fuente_cantidad = "medida" if not medida.startswith("unidad_") else "unidad"
    item.tamano = medida.replace("unidad_", "") if medida.startswith("unidad_") else item.tamano
    item.unidad_original = porcion.get_medida_display().lower()
    return True


@transaction.atomic
def responder_preguntas(comida: Comida, respuestas: dict) -> Comida:
    """Aplica las respuestas a las preguntas de aclaración y recalcula."""
    pendientes = []
    for pregunta in comida.preguntas or []:
        clave = f"pregunta_{pregunta['item']}_{pregunta['tipo']}"
        valor = respuestas.get(clave)
        validos = {o["valor"] for o in pregunta["opciones"]}
        if not valor or valor not in validos:
            pendientes.append(pregunta)
            continue
        item = comida.items.filter(pk=pregunta["item"]).first()
        if item is None:
            continue
        if pregunta["tipo"] == "metodo":
            item.metodo = MetodoCoccion.objects.get(clave=valor)
            item.origen_metodo = "explicito"
        elif pregunta["tipo"] in ("presentacion", "tamano"):
            _cantidad_por_porcion(item, valor)
        elif pregunta["tipo"] == "candidato":
            destino = _destino_desde_valor(valor)
            if destino is not None:
                _cambiar_destino(item, destino)
                item.detalle_calculo.setdefault("interpretacion", {})["resolucion"] = "0.95"
        recalcular_confianza(item)
        calcular_item(item)
        item.save()
    comida.preguntas = []  # como máximo una ronda de preguntas
    comida.save(update_fields=["preguntas"])
    return actualizar_totales(comida)


def _cambiar_destino(item: ItemComida, destino) -> None:
    from core.services.catalogo import porcion_defecto

    item.alimento = destino if isinstance(destino, Alimento) else None
    item.preparacion = destino if isinstance(destino, Preparacion) else None
    item.nombre_mostrado = destino.nombre
    item.pendiente = False
    if isinstance(destino, Preparacion):
        item.metodo = destino.metodo_defecto
        item.origen_metodo = "implicito"
    else:
        item.metodo = destino.metodo_defecto
        item.origen_metodo = "no_aplica" if destino.estado_fisico == "cocido" else "defecto"
    if not item.cantidad_g:
        porcion = porcion_defecto(destino)
        item.cantidad_g = porcion.cantidad if porcion else Decimal("100")
        item.fuente_cantidad = "defecto"


# --- Edición en la pantalla de confirmación --------------------------------------


@transaction.atomic
def editar_item(item: ItemComida, *, destino=None, cantidad_g=None, metodo=None, descartar: bool | None = None,
                marcar_editado: bool = True) -> ItemComida:
    """Corrige un ítem. Lo que el usuario cambia queda marcado como editado."""
    cambio = False
    if descartar is not None and descartar != item.descartado:
        item.descartado = descartar
        cambio = True
    if destino is not None and destino != item.destino:
        _cambiar_destino(item, destino)
        item.origen_dato = OrigenDato.USUARIO
        item.detalle_calculo.setdefault("interpretacion", {})["resolucion"] = "1"
        cambio = True
    if cantidad_g is not None:
        cantidad = calculo.validar_cantidad(cantidad_g)
        if item.cantidad_g is None or r1(cantidad) != r1(item.cantidad_g):
            item.cantidad_g = r1(cantidad)
            item.fuente_cantidad = "gramos"
            item.aplicar_rendimiento = False
            item.medida = ""
            cambio = True
    if metodo is not None and metodo != item.metodo:
        item.metodo = metodo
        item.origen_metodo = "explicito"
        cambio = True
    if not cambio:
        return item
    if marcar_editado:
        item.editado = True
    recalcular_confianza(item)
    calcular_item(item)
    item.save()
    comida = item.comida
    if comida.estado == EstadoComida.CONFIRMADA:
        comida.estado = EstadoComida.EDITADA
    actualizar_totales(comida)
    return item


@transaction.atomic
def agregar_item(comida: Comida, destino, cantidad_g, metodo: MetodoCoccion | None = None) -> ItemComida:
    cantidad = calculo.validar_cantidad(cantidad_g)
    item = ItemComida(
        comida=comida,
        alimento=destino if isinstance(destino, Alimento) else None,
        preparacion=destino if isinstance(destino, Preparacion) else None,
        nombre_mostrado=destino.nombre, cantidad_g=r1(cantidad), fuente_cantidad="gramos",
        metodo=metodo, origen_metodo="explicito" if metodo else "implicito",
        origen_dato=OrigenDato.USUARIO, editado=True, confianza=Decimal("1"),
        detalle_calculo={"interpretacion": {"resolucion": "1", "origen": "usuario"}},
    )
    calcular_item(item)
    item.save()
    if comida.estado == EstadoComida.CONFIRMADA:
        comida.estado = EstadoComida.EDITADA
    actualizar_totales(comida)
    return item


@transaction.atomic
def confirmar(comida: Comida) -> Comida:
    """
    Pasa una comida interpretada a confirmada. No se puede confirmar con
    componentes sin reconocer: hay que elegirlos del catálogo o descartarlos.
    """
    if comida.estado != EstadoComida.INTERPRETADA:
        return comida  # idempotente: un doble clic no hace nada
    activos = comida.items.filter(descartado=False)
    if activos.filter(pendiente=True).exists():
        raise ComidaNoConfirmable(
            "Hay componentes sin reconocer: búscalos en el catálogo, créalos como alimento personal o descártalos."
        )
    if not activos.exists():
        raise ComidaNoConfirmable("La comida no tiene ningún componente.")
    comida.estado = EstadoComida.CONFIRMADA
    comida.preguntas = []
    comida.save(update_fields=["estado", "preguntas", "editada_en"])
    return comida


# --- Búsqueda manual y favoritas --------------------------------------------------


@transaction.atomic
def crear_manual(usuario, filas: list[dict], *, fecha_hora=None, tipo: str = TipoComida.OTRO,
                 clave_idempotencia=None, origen: str = OrigenComida.MANUAL, texto: str = "") -> Comida:
    """
    Registro manual (siempre disponible, también sin IA).

    `filas`: [{"destino": Alimento|Preparacion, "cantidad_g": ..., "metodo": MetodoCoccion|None}]
    Si llega la misma `clave_idempotencia` dos veces, devuelve la comida ya creada.
    """
    if not filas:
        raise CantidadInvalida("Agrega al menos un alimento.")
    clave = clave_idempotencia or uuid.uuid4()
    existente = Comida.objects.filter(usuario=usuario, clave_idempotencia=clave).first()
    if existente:
        return existente
    try:
        with transaction.atomic():
            comida = Comida.objects.create(
                usuario=usuario, fecha_hora=fecha_hora or timezone.now(), tipo=tipo, origen=origen,
                estado=EstadoComida.CONFIRMADA, motor=MotorInterpretacion.MANUAL, texto_original=texto[:500],
                version_motor=calculo.VERSION_MOTOR, version_catalogo=_version_catalogo(),
                clave_idempotencia=clave,
            )
    except IntegrityError:
        return Comida.objects.get(usuario=usuario, clave_idempotencia=clave)
    for fila in filas:
        destino = fila["destino"]
        metodo = fila.get("metodo")
        item = ItemComida(
            comida=comida,
            alimento=destino if isinstance(destino, Alimento) else None,
            preparacion=destino if isinstance(destino, Preparacion) else None,
            nombre_mostrado=destino.nombre, cantidad_g=r1(calculo.validar_cantidad(fila["cantidad_g"])),
            fuente_cantidad=fila.get("fuente_cantidad", "gramos"), medida=fila.get("medida", ""),
            metodo=metodo, origen_metodo="explicito" if metodo else "implicito",
            origen_dato=OrigenDato.USUARIO, confianza=Decimal("1"),
            detalle_calculo={"interpretacion": {"resolucion": "1", "origen": "usuario"}},
        )
        calcular_item(item)
        item.save()
    return actualizar_totales(comida)


def marcar_favorita(comida: Comida, nombre: str, favorita: bool = True) -> Comida:
    comida.es_favorita = favorita
    comida.nombre_favorita = (nombre or comida.get_tipo_display())[:80] if favorita else ""
    comida.save(update_fields=["es_favorita", "nombre_favorita"])
    return comida


def repetir_favorita(comida: Comida, *, fecha_hora=None, clave_idempotencia=None) -> Comida:
    """Registra de nuevo una comida favorita, recalculada con el catálogo actual."""
    filas = [
        {"destino": i.destino, "cantidad_g": i.cantidad_g, "metodo": i.metodo}
        for i in comida.items.filter(descartado=False)
        if i.destino is not None and i.cantidad_g
    ]
    return crear_manual(
        comida.usuario, filas, fecha_hora=fecha_hora, tipo=comida.tipo, origen=OrigenComida.FAVORITA,
        clave_idempotencia=clave_idempotencia, texto=comida.nombre_favorita,
    )


@transaction.atomic
def descartar(comida: Comida) -> Comida:
    """Baja lógica: la comida deja de contar pero se conserva."""
    comida.estado = EstadoComida.DESCARTADA
    comida.save(update_fields=["estado", "editada_en"])
    return comida
