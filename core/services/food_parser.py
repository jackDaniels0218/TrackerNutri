"""
Normalización de alimentos y emparejamiento con el catálogo.

La IA devuelve texto libre normalizado a medias: "arepa frita", "Coca-Cola",
"gramos", "fritas". Este módulo traduce eso al vocabulario del catálogo antes
de que el motor de cálculo toque un solo número.

Está separado de ai_service.py a propósito: aquí no hay llamadas de red, así
que estas funciones se prueban sin simular nada (ver core/tests/test_parser.py).
"""

from __future__ import annotations

import unicodedata
from typing import Optional

from core.models import Alimento, MetodoPreparacion, Unidad

# --- Vocabulario -------------------------------------------------------------

# Cómo escribe la gente las unidades frente a las que admite el modelo.
SINONIMOS_UNIDAD = {
    "g": Unidad.GRAMOS,
    "gr": Unidad.GRAMOS,
    "grs": Unidad.GRAMOS,
    "gramo": Unidad.GRAMOS,
    "gramos": Unidad.GRAMOS,
    "ml": Unidad.MILILITROS,
    "mililitro": Unidad.MILILITROS,
    "mililitros": Unidad.MILILITROS,
    "cc": Unidad.MILILITROS,
    "unidad": Unidad.UNIDAD,
    "unidades": Unidad.UNIDAD,
    "und": Unidad.UNIDAD,
    "u": Unidad.UNIDAD,
    "porcion": Unidad.PORCION,
    "porciones": Unidad.PORCION,
    "plato": Unidad.PORCION,
    "vaso": Unidad.PORCION,
}

# Métodos de preparación tal como los nombra el usuario.
SINONIMOS_PREPARACION = {
    "frito": MetodoPreparacion.FRITO,
    "frita": MetodoPreparacion.FRITO,
    "fritos": MetodoPreparacion.FRITO,
    "fritas": MetodoPreparacion.FRITO,
    "apanado": MetodoPreparacion.FRITO,
    "asado": MetodoPreparacion.ASADO,
    "asada": MetodoPreparacion.ASADO,
    "asados": MetodoPreparacion.ASADO,
    "asadas": MetodoPreparacion.ASADO,
    "a la plancha": MetodoPreparacion.ASADO,
    "a la parrilla": MetodoPreparacion.ASADO,
    "cocido": MetodoPreparacion.COCIDO,
    "cocida": MetodoPreparacion.COCIDO,
    "cocinado": MetodoPreparacion.COCIDO,
    "hervido": MetodoPreparacion.COCIDO,
    "hervida": MetodoPreparacion.COCIDO,
    "sancochado": MetodoPreparacion.COCIDO,
    "crudo": MetodoPreparacion.CRUDO,
    "cruda": MetodoPreparacion.CRUDO,
    "horneado": MetodoPreparacion.HORNEADO,
    "horneada": MetodoPreparacion.HORNEADO,
    "al horno": MetodoPreparacion.HORNEADO,
    "no aplica": MetodoPreparacion.NO_APLICA,
    "no especificada": MetodoPreparacion.NO_ESPECIFICADA,
    "no especificado": MetodoPreparacion.NO_ESPECIFICADA,
    "ninguna": MetodoPreparacion.NO_ESPECIFICADA,
}

# Nombres coloquiales o marcas que apuntan a una entrada del catálogo.
SINONIMOS_ALIMENTO = {
    "coca cola": "gaseosa azucarada",
    "cocacola": "gaseosa azucarada",
    "coca-cola": "gaseosa azucarada",
    "gaseosa": "gaseosa azucarada",
    "pepsi": "gaseosa azucarada",
    "refresco": "gaseosa azucarada",
    "carne": "carne de res",
    "res": "carne de res",
    "bistec": "carne de res",
    "pollo": "pechuga de pollo",
    "pechuga": "pechuga de pollo",
    "arroz": "arroz blanco",
    "papa": "papa",
    "papas": "papa",
    "platano": "platano maduro",
    "platano maduro": "platano maduro",
    "maduro": "platano maduro",
    "patacon": "patacon",
    "patacones": "patacon",
    "frijol": "frijoles",
    "frijoles": "frijoles",
    "frisoles": "frijoles",
    "huevos": "huevo",
    "arepas": "arepa de maiz",
    "arepa": "arepa de maiz",
    "empanada": "empanada de carne",
    "jugo": "jugo de fruta natural",
    "leche": "leche entera",
    "aguacate": "aguacate",
    "yuca": "yuca",
    "bandeja": "bandeja paisa",
}


def quitar_tildes(texto: str) -> str:
    """Convierte 'plátano' en 'platano' para poder comparar nombres."""
    descompuesto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def normalizar_texto(texto: Optional[str]) -> str:
    """Minúsculas, sin tildes y sin espacios sobrantes."""
    if not texto:
        return ""
    return " ".join(quitar_tildes(str(texto)).lower().split())


def normalizar_unidad(unidad: Optional[str]) -> str:
    """
    Traduce la unidad escrita por el usuario a una de las admitidas.

    Si no se reconoce, devuelve 'unidad' sin inventar una equivalencia en
    gramos: el motor de cálculo pedirá confirmación si no hay peso documentado.
    """
    clave = normalizar_texto(unidad)
    return SINONIMOS_UNIDAD.get(clave, Unidad.UNIDAD)


def normalizar_preparacion(preparacion: Optional[str]) -> str:
    """Traduce 'frita', 'a la plancha'… al método de preparación del modelo."""
    clave = normalizar_texto(preparacion)
    if not clave:
        return MetodoPreparacion.NO_ESPECIFICADA
    if clave in SINONIMOS_PREPARACION:
        return SINONIMOS_PREPARACION[clave]
    # Permite frases como "carne frita en aceite".
    for palabra, metodo in SINONIMOS_PREPARACION.items():
        if palabra in clave:
            return metodo
    return MetodoPreparacion.NO_ESPECIFICADA


def normalizar_nombre(nombre: Optional[str]) -> str:
    """Aplica los sinónimos de alimentos sobre el nombre normalizado."""
    clave = normalizar_texto(nombre)
    if not clave:
        return ""
    if clave in SINONIMOS_ALIMENTO:
        return SINONIMOS_ALIMENTO[clave]
    # Quita la preparación del nombre: "arepa frita" -> "arepa".
    for palabra in SINONIMOS_PREPARACION:
        if clave.endswith(" " + palabra):
            clave = clave[: -(len(palabra) + 1)].strip()
            break
    return SINONIMOS_ALIMENTO.get(clave, clave)


def _candidatos(nombre_normalizado: str) -> list[Alimento]:
    """
    Busca en el catálogo por nombre, de lo más preciso a lo más laxo.

    Se compara contra el nombre sin tildes y en minúsculas; el catálogo es
    pequeño (decenas de filas), así que se puede recorrer en memoria sin
    penalización apreciable y sin añadir dependencias de búsqueda.
    """
    if not nombre_normalizado:
        return []

    catalogo = list(Alimento.objects.filter(activo=True))
    normalizados = [(normalizar_texto(a.nombre), a) for a in catalogo]

    exactos = [a for n, a in normalizados if n == nombre_normalizado]
    if exactos:
        return exactos

    contenidos = [
        a
        for n, a in normalizados
        if nombre_normalizado in n or n in nombre_normalizado
    ]
    if contenidos:
        return contenidos

    # Último intento: que compartan al menos una palabra significativa.
    palabras = {p for p in nombre_normalizado.split() if len(p) > 3}
    if not palabras:
        return []
    return [a for n, a in normalizados if palabras & set(n.split())]


def buscar_alimento(
    nombre: Optional[str], preparacion: Optional[str] = None
) -> Optional[Alimento]:
    """
    Devuelve el alimento del catálogo que mejor corresponde, o None.

    La preparación manda: si el usuario dijo "arepa frita" y el catálogo tiene
    la arepa asada y la frita, devuelve la frita. Si pidió una preparación que
    no existe en el catálogo, devuelve la variante neutra en lugar de una
    preparación distinta, para no atribuirle al usuario algo que no comió.

    Devolver None es una respuesta válida y esperada: significa "no está en el
    catálogo", y el motor de cálculo lo tratará como dato faltante.
    """
    metodo = normalizar_preparacion(preparacion)
    # El nombre puede traer la preparación incrustada ("arepa frita").
    if metodo == MetodoPreparacion.NO_ESPECIFICADA:
        metodo = normalizar_preparacion(nombre)

    candidatos = _candidatos(normalizar_nombre(nombre))
    if not candidatos:
        return None

    if metodo not in (
        MetodoPreparacion.NO_ESPECIFICADA,
        MetodoPreparacion.NO_APLICA,
    ):
        con_preparacion = [a for a in candidatos if a.metodo_preparacion == metodo]
        if con_preparacion:
            return con_preparacion[0]

    neutros = [
        a
        for a in candidatos
        if a.metodo_preparacion
        in (MetodoPreparacion.NO_APLICA, MetodoPreparacion.NO_ESPECIFICADA)
    ]
    if neutros:
        return neutros[0]

    return candidatos[0]


def normalizar_item(item: dict) -> dict:
    """
    Normaliza un elemento del JSON que devuelve la IA.

    Entrada  : {"name": "arepa", "quantity": 1, "unit": "unidad",
                "preparation": "frita", ...}
    Salida   : {"nombre": "arepa", "cantidad": 1, "unidad": "unidad",
                "metodo_preparacion": "frito", "alimento": <Alimento|None>, ...}

    No calcula nutrientes: de eso se encarga core/services/nutrition.py.
    """
    nombre = (item.get("name") or item.get("nombre") or "").strip()
    cantidad = item.get("quantity", item.get("cantidad"))
    unidad = normalizar_unidad(item.get("unit") or item.get("unidad"))
    preparacion = normalizar_preparacion(
        item.get("preparation") or item.get("preparacion")
    )
    alimento = buscar_alimento(nombre, preparacion)

    necesita_confirmacion = bool(
        item.get("needs_confirmation", item.get("necesita_confirmacion", False))
    )
    # Si el usuario no dijo cómo estaba preparado pero el catálogo solo tiene
    # versiones preparadas, se eligió una por él: que lo revise.
    if (
        alimento is not None
        and preparacion == MetodoPreparacion.NO_ESPECIFICADA
        and alimento.metodo_preparacion
        not in (MetodoPreparacion.NO_APLICA, MetodoPreparacion.NO_ESPECIFICADA)
    ):
        necesita_confirmacion = True

    return {
        "nombre": nombre,
        "cantidad": cantidad,
        "unidad": unidad,
        "metodo_preparacion": preparacion,
        "descripcion_porcion": (
            item.get("portion_description") or item.get("porcion") or ""
        ),
        "necesita_confirmacion": necesita_confirmacion,
        "alimento": alimento,
        "alimento_id": alimento.id if alimento else None,
    }
