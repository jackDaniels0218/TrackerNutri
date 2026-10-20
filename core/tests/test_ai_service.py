"""
Pruebas de la integración con la IA.

Cubre los escenarios 12 (respuesta inválida) y 13 (API no disponible).

NINGUNA de estas pruebas llama a la API real: todas simulan la respuesta con
unittest.mock. Así las pruebas son rápidas, deterministas y no gastan créditos.
"""

import json
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase, override_settings

from core.services import ai_service


class ValidacionDeRespuestaTests(SimpleTestCase):
    """
    La función que de verdad protege al sistema: aunque el modelo devuelva
    cualquier cosa, aquí se filtra antes de tocar la base de datos.
    """

    def test_respuesta_valida(self):
        datos = {
            "items": [
                {
                    "name": "arepa",
                    "quantity": 1,
                    "unit": "unidad",
                    "preparation": "frita",
                    "portion_description": "mediana",
                    "needs_confirmation": True,
                }
            ]
        }
        items = ai_service.validar_respuesta(datos)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["name"], "arepa")

    def test_acepta_una_cadena_json(self):
        items = ai_service.validar_respuesta(
            json.dumps({"items": [{"name": "huevo", "quantity": 2, "unit": "unidad"}]})
        )
        self.assertEqual(items[0]["quantity"], 2.0)

    def test_json_mal_formado(self):
        with self.assertRaises(ai_service.RespuestaIAInvalida):
            ai_service.validar_respuesta("{no es json")

    def test_respuesta_que_no_es_un_objeto(self):
        with self.assertRaises(ai_service.RespuestaIAInvalida):
            ai_service.validar_respuesta([1, 2, 3])

    def test_respuesta_sin_lista_items(self):
        with self.assertRaises(ai_service.RespuestaIAInvalida):
            ai_service.validar_respuesta({"resultado": "ok"})

    def test_items_vacios(self):
        with self.assertRaises(ai_service.TextoNoInterpretable):
            ai_service.validar_respuesta({"items": []})

    def test_descarta_items_sin_nombre(self):
        with self.assertRaises(ai_service.TextoNoInterpretable):
            ai_service.validar_respuesta({"items": [{"quantity": 2, "unit": "g"}]})

    def test_cantidad_negativa_se_anula_y_pide_confirmacion(self):
        """Una cantidad negativa no se guarda: se convierte en 'por confirmar'."""
        items = ai_service.validar_respuesta(
            {"items": [{"name": "arroz", "quantity": -50, "unit": "g"}]}
        )
        self.assertIsNone(items[0]["quantity"])
        self.assertTrue(items[0]["needs_confirmation"])

    def test_cantidad_en_texto_se_convierte(self):
        items = ai_service.validar_respuesta(
            {"items": [{"name": "arroz", "quantity": "150", "unit": "g"}]}
        )
        self.assertEqual(items[0]["quantity"], 150.0)

    def test_cantidad_absurda_se_descarta(self):
        items = ai_service.validar_respuesta(
            {"items": [{"name": "arroz", "quantity": "mucho", "unit": "g"}]}
        )
        self.assertIsNone(items[0]["quantity"])

    def test_se_ignoran_claves_desconocidas(self):
        """El modelo no puede colar campos extra (p. ej. calorías inventadas)."""
        items = ai_service.validar_respuesta(
            {
                "items": [
                    {"name": "arroz", "quantity": 100, "unit": "g", "calorias": 999}
                ]
            }
        )
        self.assertNotIn("calorias", items[0])

    def test_se_corta_la_lista_en_el_maximo(self):
        muchos = [{"name": f"alimento {i}", "quantity": 1, "unit": "g"} for i in range(50)]
        items = ai_service.validar_respuesta({"items": muchos})
        self.assertEqual(len(items), ai_service.MAX_ITEMS)


@override_settings(OPENAI_API_KEY="")
class SinClaveConfiguradaTests(SimpleTestCase):
    """Escenario 13, primera mitad: la aplicación sin clave de API."""

    def test_ia_configurada_es_falso(self):
        self.assertFalse(ai_service.ia_configurada())

    def test_interpretar_lanza_error_controlado(self):
        with self.assertRaises(ai_service.IANoConfigurada) as ctx:
            ai_service.interpretar_comida("una arepa frita")
        self.assertIn("manual", ctx.exception.mensaje_usuario)

    def test_texto_vacio(self):
        with self.assertRaises(ai_service.TextoNoInterpretable):
            ai_service.interpretar_comida("   ")


@override_settings(OPENAI_API_KEY="clave-de-prueba")
class LlamadaSimuladaTests(TestCase):
    """Escenarios 12 y 13: la API responde mal o no responde."""

    fixtures = ["catalogo_alimentos.json"]

    def _respuesta_falsa(self, contenido: str):
        """Construye un objeto con la misma forma que devuelve el SDK."""
        mensaje = MagicMock()
        mensaje.content = contenido
        opcion = MagicMock()
        opcion.message = mensaje
        respuesta = MagicMock()
        respuesta.choices = [opcion]
        return respuesta

    @patch("openai.OpenAI")
    def test_flujo_completo_con_respuesta_valida(self, cliente_falso):
        contenido = json.dumps(
            {
                "items": [
                    {
                        "name": "arepa",
                        "quantity": 1,
                        "unit": "unidad",
                        "preparation": "frita",
                        "portion_description": "mediana",
                        "needs_confirmation": True,
                    },
                    {
                        "name": "Coca-Cola",
                        "quantity": 400,
                        "unit": "ml",
                        "preparation": "no aplica",
                        "portion_description": "",
                        "needs_confirmation": False,
                    },
                ]
            }
        )
        cliente_falso.return_value.chat.completions.create.return_value = (
            self._respuesta_falsa(contenido)
        )

        items = ai_service.analizar_texto("una arepa frita y una Coca-Cola de 400 ml")

        self.assertEqual(len(items), 2)
        # La arepa frita se emparejó con la ficha correcta del catálogo.
        self.assertIsNotNone(items[0]["alimento"])
        self.assertEqual(items[0]["metodo_preparacion"], "frito")
        # La bebida quedó en mililitros, no en gramos.
        self.assertEqual(items[1]["unidad"], "ml")

    @patch("openai.OpenAI")
    def test_respuesta_invalida_de_la_ia(self, cliente_falso):
        """Escenario 12: el modelo devuelve texto que no es el JSON esperado."""
        cliente_falso.return_value.chat.completions.create.return_value = (
            self._respuesta_falsa("Claro, te ayudo con eso :)")
        )
        with self.assertRaises(ai_service.RespuestaIAInvalida):
            ai_service.interpretar_comida("una arepa")

    @patch("openai.OpenAI")
    def test_la_ia_no_puede_inventar_calorias(self, cliente_falso):
        """Aunque el modelo devuelva calorías, el backend las descarta."""
        contenido = json.dumps(
            {"items": [{"name": "arepa", "quantity": 1, "unit": "unidad",
                        "calories": 9999, "protein": 500}]}
        )
        cliente_falso.return_value.chat.completions.create.return_value = (
            self._respuesta_falsa(contenido)
        )
        items = ai_service.interpretar_comida("una arepa")
        self.assertNotIn("calories", items[0])
        self.assertNotIn("protein", items[0])

    @patch("openai.OpenAI")
    def test_tiempo_de_espera_agotado(self, cliente_falso):
        """Escenario 13: la API no responde a tiempo."""
        import openai

        cliente_falso.return_value.chat.completions.create.side_effect = (
            openai.APITimeoutError(request=MagicMock())
        )
        with self.assertRaises(ai_service.IANoDisponible):
            ai_service.interpretar_comida("una arepa")

    @patch("openai.OpenAI")
    def test_sin_conexion(self, cliente_falso):
        import openai

        cliente_falso.return_value.chat.completions.create.side_effect = (
            openai.APIConnectionError(request=MagicMock())
        )
        with self.assertRaises(ai_service.IANoDisponible) as ctx:
            ai_service.interpretar_comida("una arepa")
        self.assertIn("manual", ctx.exception.mensaje_usuario)

    def _error_429(self, cuerpo=None, mensaje="limite"):
        """Construye un RateLimitError como el que devuelve el SDK."""
        import openai

        respuesta_http = MagicMock()
        respuesta_http.status_code = 429
        respuesta_http.headers = {}
        return openai.RateLimitError(
            mensaje, response=respuesta_http, body=cuerpo
        )

    @patch("openai.OpenAI")
    def test_limite_de_uso_alcanzado(self, cliente_falso):
        """Un 429 por exceso de peticiones: tiene sentido reintentar."""
        cliente_falso.return_value.chat.completions.create.side_effect = (
            self._error_429()
        )
        with self.assertRaises(ai_service.IANoDisponible):
            ai_service.interpretar_comida("una arepa")

    @patch("openai.OpenAI")
    def test_falta_de_saldo_no_se_confunde_con_el_limite_de_uso(self, cliente_falso):
        """
        OpenAI devuelve 429 tanto por exceso de peticiones como por falta de
        saldo. Son problemas distintos: reintentar solo sirve en el primero.
        """
        cliente_falso.return_value.chat.completions.create.side_effect = (
            self._error_429(
                cuerpo={
                    "error": {
                        "code": "insufficient_quota",
                        "message": "You exceeded your current quota.",
                    }
                },
                mensaje="You exceeded your current quota.",
            )
        )
        with self.assertRaises(ai_service.IASinSaldo) as ctx:
            ai_service.interpretar_comida("una arepa")
        self.assertIn("saldo", ctx.exception.mensaje_usuario)
        # Y sigue ofreciendo la salida manual.
        self.assertIn("manual", ctx.exception.mensaje_usuario)

    @patch("openai.OpenAI")
    def test_falta_de_saldo_detectada_por_el_atributo_code(self, cliente_falso):
        """El SDK puede exponer el código como atributo en lugar de en el cuerpo."""
        error = self._error_429()
        error.code = "insufficient_quota"
        cliente_falso.return_value.chat.completions.create.side_effect = error
        with self.assertRaises(ai_service.IASinSaldo):
            ai_service.interpretar_comida("una arepa")
