"""
RF14 Deconstrucción de recetas y cálculo nutricional.

Motor DETERMINISTA: con los mismos datos siempre da el mismo resultado, y la
IA no interviene en ningún número. Para cada ítem:

1. Si es una preparación, la descompone en sus ingredientes crudos y escala
   las cantidades al peso consumido.
2. Aplica el método de cocción: convierte el peso cocinado a crudo con el
   factor de agua y, en carnes asadas, descuenta la grasa que gotea.
3. Si el método es una fritura, suma el aceite absorbido (RF15).
4. Calcula energía y macronutrientes desde la composición por 100 g y
   comprueba la coherencia con los factores de Atwater.
5. Calcula un rango mínimo–máximo según la incertidumbre de la porción y de
   la absorción de aceite.

Cada resultado guarda VERSION_MOTOR y el desglose completo, para poder
explicarlo y reproducirlo (RNF25).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP

from core.models import (
    Alimento,
    EstadoFisico,
    Matriz,
    MetodoCoccion,
    Preparacion,
    RolComponente,
)
from core.services.aceite import calcular_aceite
from core.services.parametros import parametro

VERSION_MOTOR = "2.0.0"

CERO = Decimal("0")
CIEN = Decimal("100")
UN_DECIMAL = Decimal("0.1")
NUTRIENTES = ("kcal", "proteinas", "carbohidratos", "azucares", "grasas")
MATRICES_QUE_GOTEAN = (Matriz.CARNE, Matriz.PESCADO)


def r1(valor) -> Decimal:
    """Política de redondeo del proyecto: 1 decimal, ROUND_HALF_UP."""
    return Decimal(valor).quantize(UN_DECIMAL, rounding=ROUND_HALF_UP)


class CantidadInvalida(ValueError):
    pass


def validar_cantidad(valor) -> Decimal:
    try:
        cantidad = Decimal(str(valor))
    except Exception as exc:  # noqa: BLE001
        raise CantidadInvalida("La cantidad debe ser un número.") from exc
    if not cantidad.is_finite() or cantidad <= 0:
        raise CantidadInvalida("La cantidad debe ser un número mayor que cero.")
    if cantidad > 5000:
        raise CantidadInvalida("La cantidad es demasiado grande para una comida (máx. 5 kg).")
    return cantidad


@dataclass
class Solicitud:
    """Qué se comió y cuánto, ya resuelto contra el catálogo."""

    destino: Alimento | Preparacion
    cantidad_g: Decimal
    metodo: MetodoCoccion | None = None
    fuente_cantidad: str = "gramos"  # gramos | medida | unidad | defecto
    tamano: str = ""
    tiempo: str = ""
    escurrido: bool = False
    aceite_agregado_g: Decimal | None = None
    aplicar_rendimiento: bool = False


@dataclass
class Resultado:
    kcal: Decimal = CERO
    proteinas: Decimal = CERO
    carbohidratos: Decimal = CERO
    azucares: Decimal = CERO
    grasas: Decimal = CERO
    aceite_g: Decimal = CERO
    aceite_min_g: Decimal = CERO
    aceite_max_g: Decimal = CERO
    kcal_min: Decimal = CERO
    kcal_max: Decimal = CERO
    metodo: MetodoCoccion | None = None
    estimado: bool = False
    lineas: list[dict] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    azucares_incompletos: bool = False

    def detalle(self) -> dict:
        """Desglose serializable para guardar en ItemComida.detalle_calculo."""
        return {
            "version_motor": VERSION_MOTOR,
            "lineas": self.lineas,
            "avisos": self.avisos,
            "aceite": {"tipico": str(self.aceite_g), "min": str(self.aceite_min_g), "max": str(self.aceite_max_g)},
            "rango": {"min": str(self.kcal_min), "max": str(self.kcal_max)},
        }


def _metodo_efectivo_alimento(alimento: Alimento, declarado: MetodoCoccion | None):
    return declarado or alimento.metodo_defecto


def _calcular_ingrediente(
    alimento: Alimento,
    peso_crudo: Decimal,
    metodo: MetodoCoccion | None,
    *,
    con_aceite: bool,
    tamano: str,
    tiempo: str,
    escurrido: bool,
    aceite_agregado_g,
    permitir_matriz_otro: bool,
) -> dict:
    """Nutrientes de un ingrediente a partir de su peso CRUDO."""
    factor = peso_crudo / CIEN
    valores = {
        "kcal": alimento.kcal * factor,
        "proteinas": alimento.proteinas * factor,
        "carbohidratos": alimento.carbohidratos * factor,
        "azucares": (alimento.azucares or CERO) * factor,
        "grasas": alimento.grasas * factor,
    }
    pasos = []
    kcal_grasa = parametro("kcal_por_gramo_grasa")

    if metodo and metodo.perdida_grasa > 0 and alimento.matriz in MATRICES_QUE_GOTEAN:
        perdida = valores["grasas"] * metodo.perdida_grasa / CIEN
        valores["grasas"] -= perdida
        valores["kcal"] -= perdida * kcal_grasa
        pasos.append(f"pierde {r1(perdida)} g de grasa al {metodo.nombre.lower()}")

    aceite = None
    if (
        con_aceite
        and metodo is not None
        and metodo.es_fritura
        and (permitir_matriz_otro or alimento.matriz != Matriz.OTRO)
    ):
        aceite = calcular_aceite(
            peso_crudo_g=peso_crudo, matriz=alimento.matriz, metodo=metodo,
            tamano=tamano, tiempo=tiempo, escurrido=escurrido, aceite_agregado_g=aceite_agregado_g,
        )
        if aceite.aplica:
            valores["grasas"] += aceite.tipico_g
            valores["kcal"] += aceite.kcal_tipico
            pasos.append(f"absorbe {aceite.tipico_g} g de aceite")

    # Solo importa la falta del dato si el ingrediente aporta carbohidratos.
    azucar_desconocido = alimento.azucares is None and alimento.carbohidratos >= 5
    return {"valores": valores, "aceite": aceite, "pasos": pasos, "azucar_desconocido": azucar_desconocido}


def calcular(solicitud: Solicitud) -> Resultado:
    """Punto de entrada del motor. Devuelve un Resultado redondeado."""
    cantidad = validar_cantidad(solicitud.cantidad_g)
    resultado = Resultado()
    totales = {n: CERO for n in NUTRIENTES}
    aceite_tip = aceite_min = aceite_max = CERO
    kcal_aceite = CERO

    def acumular(datos: dict, linea: dict):
        nonlocal aceite_tip, aceite_min, aceite_max, kcal_aceite
        for n in NUTRIENTES:
            totales[n] += datos["valores"][n]
        if datos["azucar_desconocido"]:
            resultado.azucares_incompletos = True
        aceite = datos["aceite"]
        if aceite and aceite.aplica:
            aceite_tip += aceite.tipico_g
            aceite_min += aceite.minimo_g
            aceite_max += aceite.maximo_g
            kcal_aceite += aceite.kcal_tipico
            linea["aceite_g"] = str(aceite.tipico_g)
            linea["aceite_detalle"] = aceite.pasos
        linea["kcal"] = str(r1(datos["valores"]["kcal"]))
        linea["pasos"] = datos["pasos"]
        resultado.lineas.append(linea)

    destino = solicitud.destino

    if isinstance(destino, Preparacion):
        metodo_prep = solicitud.metodo or destino.metodo_defecto
        resultado.metodo = metodo_prep
        escala = cantidad / destino.peso_porcion_g
        componentes = list(destino.componentes.filter(opcional=False).select_related("alimento", "metodo"))
        tiene_grasa_receta = any(c.rol == RolComponente.GRASA for c in componentes)
        override = solicitud.metodo if solicitud.metodo and solicitud.metodo != destino.metodo_defecto else None
        if override:
            resultado.avisos.append(
                f"Se aplicó «{override.nombre.lower()}» en lugar de «{destino.metodo_defecto.nombre.lower()}» "
                "a los ingredientes base."
            )

        for c in componentes:
            if c.metodo:
                metodo = c.metodo
                propio = True
            elif override and c.rol == RolComponente.BASE:
                metodo = override
                propio = True
            else:
                metodo = destino.metodo_defecto
                propio = False
            peso_crudo = c.cantidad_g * escala
            # El aceite de la receta ya está contado: no se suma absorción a
            # los ingredientes que siguen el método de la preparación.
            con_aceite = c.rol != RolComponente.GRASA and not (tiene_grasa_receta and not propio)
            datos = _calcular_ingrediente(
                c.alimento, peso_crudo, metodo, con_aceite=con_aceite,
                tamano=solicitud.tamano, tiempo=solicitud.tiempo, escurrido=solicitud.escurrido,
                aceite_agregado_g=None, permitir_matriz_otro=False,
            )
            acumular(datos, {
                "ingrediente": c.alimento.nombre,
                "rol": c.get_rol_display(),
                "gramos_crudos": str(r1(peso_crudo)),
                "metodo": metodo.nombre if metodo else "",
            })
            if not c.alimento.verificado:
                resultado.estimado = True
        if not destino.verificada:
            resultado.estimado = True
        resultado.lineas.insert(0, {
            "resumen": f"{destino.nombre}: {r1(cantidad)} g = {r1(escala * 100)} % de la porción típica "
                       f"({r1(destino.peso_porcion_g)} g), descompuesta en {len(componentes)} ingredientes."
        })

    else:
        alimento: Alimento = destino
        metodo = _metodo_efectivo_alimento(alimento, solicitud.metodo)
        resultado.metodo = metodo
        comestible = cantidad
        pasos_previos = []
        if solicitud.aplicar_rendimiento and alimento.rendimiento_pct:
            comestible = cantidad * alimento.rendimiento_pct / CIEN
            pasos_previos.append(f"parte comestible {alimento.rendimiento_pct} % → {r1(comestible)} g")
        peso_crudo = comestible
        if alimento.estado_fisico == EstadoFisico.CRUDO and metodo and metodo.factor_agua:
            divisor = 1 + metodo.factor_agua / CIEN
            if divisor > 0:
                peso_crudo = comestible / divisor
                pasos_previos.append(
                    f"{r1(comestible)} g cocinados ({metodo.nombre.lower()}, {metodo.factor_agua:+} % de peso) "
                    f"≈ {r1(peso_crudo)} g en crudo"
                )
        datos = _calcular_ingrediente(
            alimento, peso_crudo, metodo, con_aceite=True,
            tamano=solicitud.tamano, tiempo=solicitud.tiempo, escurrido=solicitud.escurrido,
            aceite_agregado_g=solicitud.aceite_agregado_g, permitir_matriz_otro=True,
        )
        datos["pasos"] = pasos_previos + datos["pasos"]
        acumular(datos, {
            "ingrediente": alimento.nombre,
            "gramos_consumidos": str(r1(cantidad)),
            "gramos_crudos": str(r1(peso_crudo)),
            "metodo": metodo.nombre if metodo else "sin cocción indicada",
        })
        if not alimento.verificado:
            resultado.estimado = True

    # Redondeo y rango.
    for n in NUTRIENTES:
        setattr(resultado, n, r1(totales[n]))
    resultado.aceite_g, resultado.aceite_min_g, resultado.aceite_max_g = r1(aceite_tip), r1(aceite_min), r1(aceite_max)

    margen = Decimal(str(parametro("incertidumbre_porcion_pct").get(solicitud.fuente_cantidad, 30))) / CIEN
    kcal_g = parametro("kcal_por_gramo_grasa")
    base = totales["kcal"] - kcal_aceite
    resultado.kcal_min = r1(max(CERO, base * (1 - margen) + aceite_min * kcal_g))
    resultado.kcal_max = r1(base * (1 + margen) + aceite_max * kcal_g)
    if solicitud.fuente_cantidad != "gramos" or aceite_tip > 0:
        resultado.estimado = True

    # Coherencia con Atwater (proteínas y carbohidratos 4 kcal/g, grasas 9).
    atwater = resultado.proteinas * 4 + resultado.carbohidratos * 4 + resultado.grasas * 9
    tolerancia = parametro("tolerancia_atwater_pct") / CIEN
    if abs(resultado.kcal - atwater) > max(resultado.kcal, Decimal("20")) * tolerancia:
        resultado.avisos.append(
            f"La energía ({resultado.kcal} kcal) difiere de la calculada por Atwater ({r1(atwater)} kcal)."
        )
    if resultado.azucares_incompletos:
        resultado.avisos.append("Algún ingrediente no tiene dato de azúcares: el valor de azúcares es parcial.")

    return resultado
