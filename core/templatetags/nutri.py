"""
Filtros de plantilla de NutriRegional.

    {% load nutri %}
    {{ valor|cifra:ocultar_cifras }}      → "—" si el usuario ocultó las cifras
    {{ item.confianza|confianza }}        → "alta", "media" o "baja"
    {{ numero|entero }}                   → número sin decimales
"""

from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def cifra(valor, ocultar=False):
    """Respeta la preferencia de ocultar el peso y las calorías (RF2, RF17)."""
    if ocultar:
        return "—"
    if valor is None or valor == "":
        return "—"
    return valor


@register.filter
def entero(valor):
    try:
        return f"{Decimal(str(valor)):.0f}"
    except (InvalidOperation, ValueError, TypeError):
        return valor


@register.filter
def confianza(valor):
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, ValueError, TypeError):
        return ""
    if numero >= Decimal("0.8"):
        return "alta"
    if numero >= Decimal("0.6"):
        return "media"
    return "baja"


@register.filter
def porcentaje(valor):
    try:
        return f"{Decimal(str(valor)) * 100:.0f} %"
    except (InvalidOperation, ValueError, TypeError):
        return ""


@register.filter
def obtener(diccionario, clave):
    try:
        return diccionario.get(clave)
    except AttributeError:
        return None
