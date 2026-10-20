"""
Integración con la API de IA.

Responsabilidad única: convertir el texto libre del usuario ("me comí una
arepa frita y dos huevos") en una lista de elementos estructurados.

PRINCIPIO DEL PROYECTO
----------------------
La IA solo INTERPRETA. No calcula calorías y su respuesta nunca se guarda tal
cual: el backend valida la estructura (`validar_respuesta`), empareja con el
catálogo (food_parser) y calcula los nutrientes en Python (nutrition).

Si no hay clave configurada o la API falla, se lanza un error controlado y la
aplicación sigue funcionando con el registro manual. Nunca se cae el servidor
ni se inventan valores.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)

# Límites defensivos: evitan enviar textos enormes y recibir listas absurdas.
MAX_CARACTERES_TEXTO = 500
MAX_ITEMS = 20

INSTRUCCIONES = """\
Eres un asistente que identifica alimentos en descripciones de comidas \
colombianas. Devuelves únicamente datos estructurados.

Reglas obligatorias:
1. No inventes alimentos que el usuario no haya mencionado.
2. Distingue cantidades explícitas ("150 gramos") de inferidas ("una porción").
3. "1 unidad" NO son gramos. Si el usuario no dio peso, usa unit="unidad".
4. No asumas pesos: no todas las arepas pesan lo mismo.
5. Diferencia la preparación: frito, asado, cocido, crudo, horneado o \
no especificada.
6. Marca needs_confirmation=true cuando la cantidad sea inferida o ambigua.
7. No calcules calorías ni nutrientes: no es tu tarea.
8. Si el texto no describe comida, devuelve una lista vacía.
9. Responde solo con el JSON pedido, sin texto adicional.
"""

# Esquema que se le exige al modelo y que además se valida en el backend.
ESQUEMA_RESPUESTA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "quantity": {"type": ["number", "null"]},
                    "unit": {"type": "string"},
                    "preparation": {"type": "string"},
                    "portion_description": {"type": "string"},
                    "needs_confirmation": {"type": "boolean"},
                },
                "required": [
                    "name",
                    "quantity",
                    "unit",
                    "preparation",
                    "portion_description",
                    "needs_confirmation",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


# --- Errores controlados -----------------------------------------------------


class ErrorIA(Exception):
    """Base de todos los fallos de la integración con IA."""

    mensaje_usuario = "No se pudo interpretar la comida. Usa el registro manual."


class IANoConfigurada(ErrorIA):
    """No hay OPENAI_API_KEY definida."""

    mensaje_usuario = (
        "El análisis con IA no está configurado. Registra la comida manualmente."
    )


class IANoDisponible(ErrorIA):
    """Error de red, tiempo de espera agotado o límite de uso alcanzado."""

    mensaje_usuario = (
        "El servicio de IA no respondió. Inténtalo de nuevo o usa el "
        "registro manual."
    )


class IASinSaldo(ErrorIA):
    """
    La cuenta no tiene crédito de API disponible.

    OpenAI responde 429 tanto cuando se hacen demasiadas peticiones como
    cuando se agotó el saldo, y el SDK convierte ambos casos en el mismo
    RateLimitError. Conviene separarlos: ante un límite de velocidad tiene
    sentido reintentar, pero sin saldo el reintento no servirá nunca.
    """

    mensaje_usuario = (
        "La cuenta de OpenAI no tiene saldo de API disponible. "
        "Registra la comida manualmente mientras se recarga."
    )


class RespuestaIAInvalida(ErrorIA):
    """La respuesta no cumple el esquema esperado."""

    mensaje_usuario = (
        "La IA devolvió una respuesta que no se pudo entender. "
        "Revisa el texto o usa el registro manual."
    )


class TextoNoInterpretable(ErrorIA):
    """El texto no describe ninguna comida reconocible."""

    mensaje_usuario = (
        "No se identificó ningún alimento en el texto. "
        "Descríbelo con más detalle o usa el registro manual."
    )


# --- API pública del módulo --------------------------------------------------


def _es_falta_de_saldo(error) -> bool:
    """
    ¿Este 429 es por falta de saldo o por exceso de peticiones?

    OpenAI marca el primero con el código `insufficient_quota`. Se busca en
    el atributo `code`, en el cuerpo de la respuesta y, como último recurso,
    en el texto del error, porque la forma exacta cambia entre versiones del
    SDK.
    """
    if getattr(error, "code", None) == "insufficient_quota":
        return True

    cuerpo = getattr(error, "body", None)
    if isinstance(cuerpo, dict):
        detalle = cuerpo.get("error")
        if isinstance(detalle, dict) and detalle.get("code") == "insufficient_quota":
            return True

    return "insufficient_quota" in str(error)


def ia_configurada() -> bool:
    """
    ¿Hay una clave de API disponible?

    Las vistas la usan para mostrar u ocultar el botón "Analizar con IA" y para
    explicarle al usuario por qué solo está el modo manual.
    """
    return bool(getattr(settings, "OPENAI_API_KEY", ""))


def validar_respuesta(datos: Any) -> list[dict]:
    """
    Valida la estructura devuelta por el modelo ANTES de usarla.

    Esta función es pura (no toca la red) y es la que de verdad protege al
    sistema: aunque el modelo devuelva basura, aquí se descarta.

    Reglas aplicadas:
    * La raíz debe ser un objeto con la lista "items".
    * Cada item necesita un nombre no vacío.
    * La cantidad, si viene, debe ser un número positivo y finito.
    * Se ignoran las claves que no estén en el esquema.
    * Se corta la lista en MAX_ITEMS.

    Lanza RespuestaIAInvalida si la forma general no sirve.
    """
    if isinstance(datos, str):
        try:
            datos = json.loads(datos)
        except json.JSONDecodeError as exc:
            raise RespuestaIAInvalida("La respuesta no es JSON válido.") from exc

    if not isinstance(datos, dict):
        raise RespuestaIAInvalida("La respuesta no es un objeto JSON.")

    items = datos.get("items")
    if not isinstance(items, list):
        raise RespuestaIAInvalida("La respuesta no contiene una lista 'items'.")

    validados: list[dict] = []
    for item in items[:MAX_ITEMS]:
        if not isinstance(item, dict):
            continue
        nombre = item.get("name") or item.get("nombre")
        if not isinstance(nombre, str) or not nombre.strip():
            continue

        cantidad = item.get("quantity", item.get("cantidad"))
        if isinstance(cantidad, bool):  # True no es una cantidad
            cantidad = None
        elif isinstance(cantidad, (int, float)):
            cantidad = float(cantidad)
            if cantidad != cantidad or cantidad in (float("inf"), float("-inf")):
                cantidad = None  # descarta NaN e infinitos
            elif cantidad <= 0:
                cantidad = None
        elif isinstance(cantidad, str):
            try:
                cantidad = float(cantidad.replace(",", "."))
                cantidad = cantidad if cantidad > 0 else None
            except ValueError:
                cantidad = None
        else:
            cantidad = None

        def _texto(clave_en: str, clave_es: str) -> str:
            valor = item.get(clave_en, item.get(clave_es, ""))
            return valor.strip() if isinstance(valor, str) else ""

        validados.append(
            {
                "name": nombre.strip()[:120],
                "quantity": cantidad,
                "unit": _texto("unit", "unidad"),
                "preparation": _texto("preparation", "preparacion"),
                "portion_description": _texto("portion_description", "porcion"),
                # Si no vino cantidad, hay que confirmarla sí o sí.
                "needs_confirmation": bool(
                    item.get("needs_confirmation", item.get("necesita_confirmacion"))
                )
                or cantidad is None,
            }
        )

    if not validados:
        raise TextoNoInterpretable("No se identificó ningún alimento.")
    return validados


def interpretar_comida(texto: str) -> list[dict]:
    """
    Envía el texto del usuario al modelo y devuelve los items ya validados.

    Recibe  : texto libre, por ejemplo "una arepa frita y 150 g de carne asada".
    Devuelve: lista de dicts con name, quantity, unit, preparation,
              portion_description y needs_confirmation.
    Lanza   : IANoConfigurada, IANoDisponible, RespuestaIAInvalida o
              TextoNoInterpretable. Todos se traducen a un mensaje legible
              mediante el atributo `mensaje_usuario`.

    Solo se envía la descripción de la comida: ni el nombre, ni el correo, ni
    el perfil del usuario salen del servidor.
    """
    texto = (texto or "").strip()
    if not texto:
        raise TextoNoInterpretable("El texto está vacío.")
    texto = texto[:MAX_CARACTERES_TEXTO]

    if not ia_configurada():
        raise IANoConfigurada("OPENAI_API_KEY no está definida.")

    # La importación va aquí dentro para que el proyecto arranque aunque el
    # paquete no esté instalado y solo se use el modo manual.
    import openai

    cliente = openai.OpenAI(
        api_key=settings.OPENAI_API_KEY,
        timeout=settings.OPENAI_TIMEOUT,
        max_retries=1,
    )

    try:
        respuesta = cliente.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": INSTRUCCIONES},
                {"role": "user", "content": texto},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "alimentos_detectados",
                    "schema": ESQUEMA_RESPUESTA,
                    "strict": True,
                },
            },
            temperature=0,
        )
    except openai.APITimeoutError as exc:
        logger.warning("Tiempo de espera agotado al llamar a la API de IA.")
        raise IANoDisponible("Tiempo de espera agotado.") from exc
    except openai.RateLimitError as exc:
        if _es_falta_de_saldo(exc):
            logger.error("La cuenta de la API de IA se quedó sin saldo.")
            raise IASinSaldo("Sin saldo de API disponible.") from exc
        logger.warning("Límite de uso de la API de IA alcanzado.")
        raise IANoDisponible("Límite de uso alcanzado.") from exc
    except openai.AuthenticationError as exc:
        logger.error("La clave de la API de IA fue rechazada.")
        raise IANoConfigurada("La clave de la API no es válida.") from exc
    except openai.APIConnectionError as exc:
        logger.warning("No se pudo conectar con la API de IA.")
        raise IANoDisponible("Sin conexión con el servicio de IA.") from exc
    except openai.APIError as exc:
        # Se registra el tipo de error, nunca el texto del usuario.
        logger.error("Error de la API de IA: %s", type(exc).__name__)
        raise IANoDisponible("El servicio de IA devolvió un error.") from exc

    try:
        contenido = respuesta.choices[0].message.content
    except (AttributeError, IndexError, TypeError) as exc:
        logger.error("Respuesta de la API de IA con forma inesperada.")
        raise RespuestaIAInvalida("Respuesta sin contenido.") from exc

    return validar_respuesta(contenido)


def analizar_texto(texto: str) -> list[dict]:
    """
    Flujo completo: interpreta con IA y empareja con el catálogo.

    Devuelve la lista de items ya normalizados por food_parser, lista para
    mostrarse en el formulario de confirmación. Es lo que usa la vista
    `analizar_comida`.
    """
    from core.services.food_parser import normalizar_item

    items = interpretar_comida(texto)
    return [normalizar_item(item) for item in items]
