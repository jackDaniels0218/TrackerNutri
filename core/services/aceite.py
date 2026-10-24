"""
RF15 Calculadora dinámica de absorción de aceite.

En lugar de un valor fijo, estima cuánto aceite queda en un alimento frito a
partir de:

* el peso en crudo,
* el coeficiente de absorción según la matriz del alimento (masa de maíz,
  tubérculo, carne...) y el método (fritura profunda o sartén),
* el tamaño de la pieza (más superficie respecto al peso → más aceite),
* el tiempo de fritura, si se conoce,
* si se escurrió sobre papel absorbente,
* en sartén, la cantidad de aceite que el usuario dice haber agregado.

Entrega un valor típico y un rango mínimo–máximo. Solo cuenta el aceite que
queda en el alimento, no el que se queda en la sartén.

Todos los factores son parámetros (RF11), no constantes del código.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP

from core.models import CoeficienteAbsorcion, EstadoRegistro, Matriz, MetodoCoccion
from core.services.parametros import parametro

CERO = Decimal("0")
UN_DECIMAL = Decimal("0.1")


def _r(valor: Decimal) -> Decimal:
    return Decimal(valor).quantize(UN_DECIMAL, rounding=ROUND_HALF_UP)


@dataclass
class ResultadoAceite:
    tipico_g: Decimal = CERO
    minimo_g: Decimal = CERO
    maximo_g: Decimal = CERO
    kcal_tipico: Decimal = CERO
    kcal_minimo: Decimal = CERO
    kcal_maximo: Decimal = CERO
    pasos: list[str] = field(default_factory=list)

    @property
    def aplica(self) -> bool:
        return self.tipico_g > 0


def coeficiente_para(metodo: MetodoCoccion, matriz: str) -> CoeficienteAbsorcion | None:
    activos = CoeficienteAbsorcion.objects.filter(metodo=metodo, estado=EstadoRegistro.ACTIVO)
    return activos.filter(matriz=matriz).first() or activos.filter(matriz=Matriz.OTRO).first()


def calcular_aceite(
    *,
    peso_crudo_g,
    matriz: str,
    metodo: MetodoCoccion | None,
    tamano: str = "",
    tiempo: str = "",
    escurrido: bool = False,
    aceite_agregado_g=None,
) -> ResultadoAceite:
    """
    Aceite absorbido (g) y su energía, con rango.

    Ejemplo: 65 g de plátano verde en fritura profunda (tubérculo 5/10/15 %)
    → 6,5 g de aceite típico, entre 3,3 y 9,8 g → 58,5 kcal típicas.
    """
    resultado = ResultadoAceite()
    if metodo is None or not metodo.es_fritura:
        return resultado

    peso = Decimal(str(peso_crudo_g))
    kcal_g = parametro("kcal_por_gramo_grasa")

    if aceite_agregado_g and metodo.clave == "fritura_sarten":
        proporcion = parametro("proporcion_aceite_sarten")
        agregado = Decimal(str(aceite_agregado_g))
        minimo = agregado * Decimal(str(proporcion["min"]))
        tipico = agregado * Decimal(str(proporcion["tipico"]))
        maximo = agregado * Decimal(str(proporcion["max"]))
        resultado.pasos.append(
            f"Aceite agregado a la sartén: {_r(agregado)} g; se estima que el alimento "
            f"retiene el {Decimal(str(proporcion['tipico'])) * 100:.0f} %."
        )
    else:
        coef = coeficiente_para(metodo, matriz)
        if coef is None:
            resultado.pasos.append("No hay coeficiente de absorción para este método y tipo de alimento.")
            return resultado
        minimo = peso * coef.pct_min / 100
        tipico = peso * coef.pct_tipico / 100
        maximo = peso * coef.pct_max / 100
        resultado.pasos.append(
            f"{_r(peso)} g crudos × {coef.pct_tipico} % ({coef.get_matriz_display().lower()}, "
            f"{metodo.nombre.lower()}) = {_r(tipico)} g de aceite."
        )

        factores = []
        if tamano:
            f = Decimal(str(parametro("factor_tamano_pieza").get(tamano, 1)))
            if f != 1:
                factores.append((f, f"pieza {tamano}"))
        if tiempo:
            f = Decimal(str(parametro("factor_tiempo_fritura").get(tiempo, 1)))
            if f != 1:
                factores.append((f, f"fritura {tiempo}"))
        if escurrido:
            factores.append((parametro("factor_escurrido"), "escurrido en papel"))
        for f, motivo in factores:
            minimo, tipico, maximo = minimo * f, tipico * f, maximo * f
            resultado.pasos.append(f"Ajuste por {motivo}: × {f}.")

    resultado.minimo_g, resultado.tipico_g, resultado.maximo_g = _r(minimo), _r(tipico), _r(maximo)
    resultado.kcal_minimo = _r(resultado.minimo_g * kcal_g)
    resultado.kcal_tipico = _r(resultado.tipico_g * kcal_g)
    resultado.kcal_maximo = _r(resultado.maximo_g * kcal_g)
    resultado.pasos.append(
        f"Aceite estimado {resultado.tipico_g} g (entre {resultado.minimo_g} y {resultado.maximo_g} g) "
        f"= {resultado.kcal_tipico} kcal."
    )
    return resultado
