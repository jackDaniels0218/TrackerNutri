"""
Normalización de texto, compartida por el léxico, la interpretación y la
búsqueda manual: minúsculas, sin tildes, sin signos y sin espacios dobles.
"""

import re
import unicodedata

_SIGNOS = re.compile(r"[^\w\s,./+-]", re.UNICODE)
_ESPACIOS = re.compile(r"\s+")


def quitar_tildes(texto: str) -> str:
    """
    Elimina tildes y diéresis. La ñ también pasa a n: muchos teclados no la
    tienen, y "pina" debe encontrar "piña".
    """
    descompuesto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def normalizar(texto) -> str:
    """'Arepa  FRITA, con Coca-Cola!' -> 'arepa frita, con coca cola'"""
    if not texto:
        return ""
    texto = quitar_tildes(str(texto)).lower()
    texto = texto.replace("-", " ").replace("_", " ")
    texto = _SIGNOS.sub(" ", texto)
    return _ESPACIOS.sub(" ", texto).strip()


def singular(palabra: str) -> str:
    """Singular aproximado en español: 'arepas' -> 'arepa', 'panes' -> 'pan'."""
    if len(palabra) > 4 and palabra.endswith("es") and palabra[-3] not in "aeiou":
        return palabra[:-2]
    if len(palabra) > 3 and palabra.endswith("s"):
        return palabra[:-1]
    return palabra


def singular_frase(frase: str) -> str:
    return " ".join(singular(p) for p in frase.split())
