"""
Motor de cálculos nutricionales.

Este módulo es el único sitio donde se calculan calorías y macronutrientes.
No sabe nada de HTTP, de plantillas ni de la IA: recibe números y devuelve
números, por lo que se puede probar de forma aislada con pruebas unitarias
(ver core/tests/test_nutrition.py).

FÓRMULA BASE
------------
Los valores del catálogo vienen por 100 g (o por 100 ml). Para una cantidad
consumida se aplica una regla de tres:

    nutriente_consumido = valor_por_100 * cantidad_base / 100

Ejemplo de comprobación (solo aritmético): 200 kcal/100 g con 150 g
    200 * 150 / 100 = 300 kcal

POLÍTICA DE REDONDEO
--------------------
Todos los resultados se redondean a 1 decimal con ROUND_HALF_UP en el momento
de calcular cada detalle. Las sumas (comida y día) suman valores ya
redondeados, de modo que lo que muestra el panel coincide exactamente con la
suma de las filas que ve el usuario.

DATOS FALTANTES
---------------
Si no se puede calcular (alimento fuera del catálogo o unidad sin equivalencia
documentada), el resultado NO vale cero: vale None y se marca el motivo. El
resumen diario informa de cuántos detalles quedaron sin datos en lugar de
ocultarlos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Iterable, Optional

from core.models import (
    Alimento,
    MetodoPreparacion,
    Unidad,
    UnidadReferencia,
)

# Cuántos decimales conserva cada valor nutricional.
DECIMALES = Decimal("0.1")

# Base sobre la que están expresados los valores del catálogo.
BASE_REFERENCIA = Decimal("100")

# Mejora opcional y desactivada por defecto: gramos de aceite que se estiman
# absorbidos por cada 100 g de alimento frito cuando el catálogo NO describe ya
# la versión frita. No pretende medir la absorción real; es un parámetro
# configurable y documentado (ver README, sección "Limitaciones conocidas").
GRAMOS_ACEITE_POR_100G_FRITO = Decimal("8")
KCAL_POR_GRAMO_DE_ACEITE = Decimal("9")


def redondear(valor: Optional[Decimal]) -> Optional[Decimal]:
    """Aplica la política de redondeo del proyecto (1 decimal, HALF_UP)."""
    if valor is None:
        return None
    return Decimal(valor).quantize(DECIMALES, rounding=ROUND_HALF_UP)


class CantidadInvalida(ValueError):
    """La cantidad recibida no es un número positivo utilizable."""


def validar_cantidad(cantidad) -> Decimal:
    """
    Convierte la cantidad a Decimal y rechaza valores no positivos.

    Se usa tanto en los formularios como en la API para que una cantidad
    negativa o un texto no numérico nunca llegue al cálculo.
    """
    try:
        valor = Decimal(str(cantidad))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise CantidadInvalida("La cantidad debe ser un número.") from exc
    if not valor.is_finite():
        raise CantidadInvalida("La cantidad debe ser un número finito.")
    if valor <= 0:
        raise CantidadInvalida("La cantidad debe ser mayor que cero.")
    return valor


@dataclass
class ResultadoCalculo:
    """
    Resultado de calcular un alimento con una cantidad.

    `calorias` y los macros valen None cuando no se pudo calcular; en ese caso
    `motivo` explica por qué y `necesita_confirmacion` queda en True para que
    la interfaz le pida el dato al usuario.
    """

    calorias: Optional[Decimal] = None
    proteinas: Optional[Decimal] = None
    carbohidratos: Optional[Decimal] = None
    grasas: Optional[Decimal] = None
    cantidad_base: Optional[Decimal] = None
    unidad_referencia: str = ""
    es_estimado: bool = False
    necesita_confirmacion: bool = False
    motivo: str = ""
    # Instantánea de los valores por 100 que se aplicaron.
    referencia: dict = field(default_factory=dict)

    @property
    def calculado(self) -> bool:
        return self.calorias is not None


def convertir_a_base(
    cantidad: Decimal, unidad: str, alimento: Alimento
) -> tuple[Optional[Decimal], str]:
    """
    Convierte `cantidad` + `unidad` a la base del alimento (g o ml).

    Devuelve (cantidad_convertida, motivo). Si no hay una equivalencia
    documentada devuelve (None, motivo) en lugar de inventar un peso.

    Reglas:
    * g  -> solo sirve para alimentos expresados por 100 g.
    * ml -> solo sirve para alimentos expresados por 100 ml.
    * unidad / porción -> usa `gramos_por_unidad` del catálogo.

    No se convierten gramos a mililitros (ni al revés) porque eso exigiría
    conocer la densidad del alimento, que el catálogo no almacena.
    """
    base = alimento.unidad_referencia

    if unidad in (Unidad.UNIDAD, Unidad.PORCION):
        if alimento.gramos_por_unidad is None:
            return None, (
                f"No hay una equivalencia documentada para 1 {unidad} de "
                f"{alimento.nombre}. Indica la cantidad en "
                f"{'ml' if base == UnidadReferencia.MILILITROS_100 else 'g'}."
            )
        return cantidad * alimento.gramos_por_unidad, ""

    if unidad == Unidad.GRAMOS:
        if base != UnidadReferencia.GRAMOS_100:
            return None, (
                f"{alimento.nombre} se mide en mililitros. "
                "Indica la cantidad en ml."
            )
        return cantidad, ""

    if unidad == Unidad.MILILITROS:
        if base != UnidadReferencia.MILILITROS_100:
            return None, (
                f"{alimento.nombre} se mide en gramos. Indica la cantidad en g."
            )
        return cantidad, ""

    return None, f"Unidad no admitida: {unidad}."


def calcular(
    alimento: Optional[Alimento],
    cantidad,
    unidad: str,
    *,
    nombre_mostrado: str = "",
    sumar_aceite_de_fritura: bool = False,
    metodo_declarado: str = MetodoPreparacion.NO_ESPECIFICADA,
) -> ResultadoCalculo:
    """
    Calcula los nutrientes de un alimento para una cantidad dada.

    Parámetros
    ----------
    alimento : Alimento o None
        None significa "no hubo coincidencia en el catálogo". En ese caso no se
        calcula nada: se devuelve un resultado vacío con el motivo.
    cantidad, unidad
        Lo que el usuario (o la IA) indicó. La cantidad se valida antes.
    sumar_aceite_de_fritura
        Mejora opcional. Solo tiene efecto si el alimento del catálogo NO es ya
        una preparación frita, para no contar el aceite dos veces.

    Devuelve
    --------
    ResultadoCalculo con los cuatro nutrientes redondeados y la instantánea de
    los valores por 100 que se usaron.
    """
    cantidad = validar_cantidad(cantidad)

    if alimento is None:
        etiqueta = nombre_mostrado or "el alimento"
        return ResultadoCalculo(
            necesita_confirmacion=True,
            motivo=(
                f"No se encontró «{etiqueta}» en el catálogo. "
                "Elige un alimento equivalente o añádelo al catálogo."
            ),
        )

    cantidad_base, motivo = convertir_a_base(cantidad, unidad, alimento)
    if cantidad_base is None:
        return ResultadoCalculo(necesita_confirmacion=True, motivo=motivo)

    factor = cantidad_base / BASE_REFERENCIA

    calorias = alimento.calorias * factor
    proteinas = alimento.proteinas * factor
    carbohidratos = alimento.carbohidratos * factor
    grasas = alimento.grasas * factor

    observacion = ""
    # El catálogo ya incluye el aceite cuando el alimento es "frito"; solo se
    # suma cuando el usuario declara fritura sobre un alimento no frito.
    aplica_aceite = (
        sumar_aceite_de_fritura
        and metodo_declarado == MetodoPreparacion.FRITO
        and alimento.metodo_preparacion != MetodoPreparacion.FRITO
        and alimento.unidad_referencia == UnidadReferencia.GRAMOS_100
    )
    if aplica_aceite:
        gramos_aceite = GRAMOS_ACEITE_POR_100G_FRITO * factor
        grasas += gramos_aceite
        calorias += gramos_aceite * KCAL_POR_GRAMO_DE_ACEITE
        observacion = (
            f"Incluye una estimación de {redondear(gramos_aceite)} g de aceite "
            "absorbido al freír."
        )

    es_estimado = (
        alimento.valores_aproximados
        or unidad in (Unidad.UNIDAD, Unidad.PORCION)
        or aplica_aceite
    )

    return ResultadoCalculo(
        calorias=redondear(calorias),
        proteinas=redondear(proteinas),
        carbohidratos=redondear(carbohidratos),
        grasas=redondear(grasas),
        cantidad_base=redondear(cantidad_base),
        unidad_referencia=alimento.unidad_referencia,
        es_estimado=es_estimado,
        necesita_confirmacion=False,
        motivo=observacion,
        referencia={
            "calorias": alimento.calorias,
            "proteinas": alimento.proteinas,
            "carbohidratos": alimento.carbohidratos,
            "grasas": alimento.grasas,
        },
    )


def aplicar_calculo(detalle, resultado: ResultadoCalculo):
    """
    Copia un ResultadoCalculo sobre un DetalleComida (sin guardarlo).

    Mantiene la instantánea de los valores por 100 aplicados, de modo que
    editar luego el catálogo no altere el historial.
    """
    detalle.calorias = resultado.calorias
    detalle.proteinas = resultado.proteinas
    detalle.carbohidratos = resultado.carbohidratos
    detalle.grasas = resultado.grasas
    detalle.cantidad_base = resultado.cantidad_base
    detalle.unidad_referencia_ref = resultado.unidad_referencia
    detalle.calorias_ref = resultado.referencia.get("calorias")
    detalle.proteinas_ref = resultado.referencia.get("proteinas")
    detalle.carbohidratos_ref = resultado.referencia.get("carbohidratos")
    detalle.grasas_ref = resultado.referencia.get("grasas")
    detalle.es_estimado = resultado.es_estimado
    detalle.necesita_confirmacion = resultado.necesita_confirmacion
    detalle.observacion = resultado.motivo[:200]
    return detalle


def sumar_detalles(detalles: Iterable) -> dict:
    """
    Suma los nutrientes de una lista de DetalleComida.

    Los detalles sin datos nutricionales no se cuentan como cero: se informan
    aparte en `sin_datos` para que la interfaz pueda avisar al usuario.
    """
    totales = {
        "calorias": Decimal("0"),
        "proteinas": Decimal("0"),
        "carbohidratos": Decimal("0"),
        "grasas": Decimal("0"),
        "sin_datos": 0,
        "estimado": False,
    }
    for detalle in detalles:
        if detalle.calorias is None:
            totales["sin_datos"] += 1
            continue
        totales["calorias"] += detalle.calorias
        totales["proteinas"] += detalle.proteinas or Decimal("0")
        totales["carbohidratos"] += detalle.carbohidratos or Decimal("0")
        totales["grasas"] += detalle.grasas or Decimal("0")
        if detalle.es_estimado:
            totales["estimado"] = True

    for clave in ("calorias", "proteinas", "carbohidratos", "grasas"):
        totales[clave] = redondear(totales[clave])
    return totales


def resumen_diario(usuario, fecha, meta_calorias: Optional[int] = None) -> dict:
    """
    Construye el resumen que muestra el panel principal para una fecha.

    Solo suma las comidas CONFIRMADAS del usuario: los borradores pendientes de
    aprobar no contaminan el total del día.

    Devuelve, entre otros:
    * consumido / meta / porcentaje
    * `restantes`: nunca negativo. Cuando se supera la meta, `exceso` lo indica
      y `meta_superada` queda en True, para no presentar un número negativo
      como si fueran calorías disponibles.
    """
    from core.models import DetalleComida, RegistroComida

    if meta_calorias is None:
        perfil = getattr(usuario, "perfil", None)
        meta_calorias = (
            perfil.meta_calorias_diaria
            if perfil
            else PerfilPorDefecto.META_CALORIAS
        )

    comidas = RegistroComida.objects.filter(
        usuario=usuario, fecha=fecha, confirmado=True
    )
    detalles = DetalleComida.objects.filter(registro__in=comidas)
    totales = sumar_detalles(detalles)

    consumido = totales["calorias"] or Decimal("0")
    meta = Decimal(meta_calorias)
    diferencia = meta - consumido
    porcentaje = (consumido / meta * 100) if meta > 0 else Decimal("0")

    return {
        "fecha": fecha,
        "meta": int(meta),
        "consumido": redondear(consumido),
        "restantes": redondear(diferencia if diferencia > 0 else Decimal("0")),
        "exceso": redondear(-diferencia if diferencia < 0 else Decimal("0")),
        "meta_superada": diferencia < 0,
        "porcentaje": redondear(porcentaje),
        "proteinas": totales["proteinas"],
        "carbohidratos": totales["carbohidratos"],
        "grasas": totales["grasas"],
        "detalles_sin_datos": totales["sin_datos"],
        "contiene_estimaciones": totales["estimado"],
        "numero_comidas": comidas.count(),
    }


class PerfilPorDefecto:
    """Valores usados cuando un usuario todavía no tiene perfil creado."""

    META_CALORIAS = 2000
