"""
Pruebas de los comandos de `manage.py`.

El comando `probar_ia` llama a la API real cuando se ejecuta a mano, pero
aquí se simula la respuesta: las pruebas no deben depender de la red ni
gastar crédito.
"""

from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase, override_settings


def _modelo(identificador: str):
    """Imita un objeto de la lista que devuelve `client.models.list()`."""
    objeto = MagicMock()
    objeto.id = identificador
    return objeto


class CargarDatosDemoTests(TestCase):
    fixtures = ["catalogo_alimentos.json"]

    def test_crea_el_usuario_demo_con_comidas(self):
        salida = StringIO()
        call_command("cargar_datos_demo", "--dias", "3", stdout=salida)

        from django.contrib.auth.models import User

        demo = User.objects.get(username="demo")
        self.assertTrue(demo.comidas.exists())
        self.assertEqual(demo.perfil.meta_calorias_diaria, 2200)
        self.assertIn("demo", salida.getvalue())

    def test_es_idempotente(self):
        """Ejecutarlo dos veces no duplica las comidas."""
        call_command("cargar_datos_demo", "--dias", "2", stdout=StringIO())
        from django.contrib.auth.models import User

        primera = User.objects.get(username="demo").comidas.count()
        call_command("cargar_datos_demo", "--dias", "2", stdout=StringIO())
        self.assertEqual(User.objects.get(username="demo").comidas.count(), primera)


class ProbarIaSinCatalogoTests(TestCase):
    """Sin catálogo no tiene sentido seguir: lo dice y se detiene."""

    def test_avisa_de_que_falta_el_catalogo(self):
        salida = StringIO()
        call_command("probar_ia", stdout=salida)
        self.assertIn("catálogo está vacío", salida.getvalue())


@override_settings(OPENAI_API_KEY="")
class ProbarIaSinClaveTests(TestCase):
    fixtures = ["catalogo_alimentos.json"]

    def test_explica_como_conseguir_la_clave(self):
        salida = StringIO()
        call_command("probar_ia", stdout=salida)
        texto = salida.getvalue()
        self.assertIn("No hay OPENAI_API_KEY configurada", texto)
        self.assertIn("platform.openai.com", texto)
        # Debe dejar claro que la API se paga aparte de ChatGPT.
        self.assertIn("ChatGPT", texto)


@override_settings(OPENAI_API_KEY="sk-clave-de-prueba-1234", OPENAI_MODEL="gpt-4o-mini")
class ProbarIaConClaveTests(TestCase):
    fixtures = ["catalogo_alimentos.json"]

    def _respuesta_de_analisis(self):
        import json

        mensaje = MagicMock()
        mensaje.content = json.dumps(
            {
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
        )
        opcion = MagicMock()
        opcion.message = mensaje
        respuesta = MagicMock()
        respuesta.choices = [opcion]
        return respuesta

    @patch("openai.OpenAI")
    def test_nunca_imprime_la_clave_completa(self, cliente_falso):
        """La clave solo se muestra recortada, nunca entera."""
        cliente_falso.return_value.models.list.return_value = [_modelo("gpt-4o-mini")]
        cliente_falso.return_value.chat.completions.create.return_value = (
            self._respuesta_de_analisis()
        )
        salida = StringIO()
        call_command("probar_ia", stdout=salida)
        self.assertNotIn("sk-clave-de-prueba-1234", salida.getvalue())

    @patch("openai.OpenAI")
    def test_flujo_completo_correcto(self, cliente_falso):
        cliente_falso.return_value.models.list.return_value = [_modelo("gpt-4o-mini")]
        cliente_falso.return_value.chat.completions.create.return_value = (
            self._respuesta_de_analisis()
        )
        salida = StringIO()
        call_command("probar_ia", stdout=salida)
        texto = salida.getvalue()
        self.assertIn("está disponible", texto)
        self.assertIn("TOTAL CALCULADO", texto)
        # La arepa frita pesa 100 g y aporta 280 kcal/100 g.
        self.assertIn("280.0 kcal", texto)

    @patch("openai.OpenAI")
    def test_avisa_si_el_modelo_no_existe_y_sugiere_otros(self, cliente_falso):
        cliente_falso.return_value.models.list.return_value = [
            _modelo("gpt-otro-modelo"),
            _modelo("un-modelo-sin-gpt"),
        ]
        salida = StringIO()
        call_command("probar_ia", stdout=salida)
        texto = salida.getvalue()
        self.assertIn("NO está en tu cuenta", texto)
        self.assertIn("gpt-otro-modelo", texto)

    @patch("openai.OpenAI")
    def test_clave_rechazada(self, cliente_falso):
        import openai

        respuesta_http = MagicMock()
        respuesta_http.status_code = 401
        respuesta_http.headers = {}
        cliente_falso.return_value.models.list.side_effect = openai.AuthenticationError(
            "no autorizado", response=respuesta_http, body=None
        )
        salida = StringIO()
        call_command("probar_ia", stdout=salida)
        self.assertIn("rechazada por OpenAI", salida.getvalue())

    @patch("openai.OpenAI")
    def test_sin_conexion(self, cliente_falso):
        import openai

        cliente_falso.return_value.models.list.side_effect = openai.APIConnectionError(
            request=MagicMock()
        )
        salida = StringIO()
        call_command("probar_ia", stdout=salida)
        self.assertIn("No se pudo conectar", salida.getvalue())

    @patch("openai.OpenAI")
    def test_solo_modelos_no_analiza_texto(self, cliente_falso):
        cliente_falso.return_value.models.list.return_value = [_modelo("gpt-4o-mini")]
        salida = StringIO()
        call_command("probar_ia", "--solo-modelos", stdout=salida)
        self.assertNotIn("TOTAL CALCULADO", salida.getvalue())
        cliente_falso.return_value.chat.completions.create.assert_not_called()
