"""
Pruebas de la API REST.

Repite sobre los endpoints las garantías que ya se comprobaron en la web:
autenticación obligatoria, aislamiento entre usuarios y validación de
cantidades. Un agujero en la API sería tan grave como uno en las páginas.
"""

import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import Alimento, MetodoPreparacion, RegistroComida, Unidad
from core.services.comidas import guardar_comida

CLAVE = "clave-de-prueba-123"


class BaseAPI(TestCase):
    fixtures = ["catalogo_alimentos.json"]

    def setUp(self):
        self.ana = User.objects.create_user("ana", password=CLAVE)
        self.luis = User.objects.create_user("luis", password=CLAVE)
        self.hoy = timezone.localdate()
        self.arroz = Alimento.objects.get(nombre="Arroz blanco")

    def _comida_de(self, usuario, descripcion="Almuerzo"):
        return guardar_comida(
            usuario,
            descripcion=descripcion,
            fecha=self.hoy,
            filas=[
                {
                    "alimento": self.arroz,
                    "nombre_mostrado": "Arroz blanco",
                    "cantidad": Decimal("150"),
                    "unidad": Unidad.GRAMOS,
                    "metodo_preparacion": MetodoPreparacion.COCIDO,
                }
            ],
        )


class AutenticacionAPITests(BaseAPI):
    """Ningún endpoint responde sin sesión iniciada."""

    def test_endpoints_protegidos(self):
        for nombre in ["api_alimentos", "api_perfil", "api_comidas", "api_resumen"]:
            with self.subTest(endpoint=nombre):
                respuesta = self.client.get(reverse(nombre))
                self.assertIn(respuesta.status_code, (401, 403))


class CatalogoAPITests(BaseAPI):
    def setUp(self):
        super().setUp()
        self.client.login(username="ana", password=CLAVE)

    def test_lista_el_catalogo(self):
        respuesta = self.client.get(reverse("api_alimentos"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.json()), Alimento.objects.count())

    def test_busca_por_nombre(self):
        respuesta = self.client.get(reverse("api_alimentos"), {"buscar": "arepa"})
        nombres = {a["nombre"] for a in respuesta.json()}
        self.assertEqual(nombres, {"Arepa de maíz"})

    def test_incluye_la_fuente_y_el_aviso_de_aproximacion(self):
        """La interfaz debe poder decir de dónde salen los valores."""
        primero = self.client.get(reverse("api_alimentos")).json()[0]
        self.assertIn("fuente", primero)
        self.assertIn("valores_aproximados", primero)


class PerfilAPITests(BaseAPI):
    def setUp(self):
        super().setUp()
        self.client.login(username="ana", password=CLAVE)

    def test_lee_el_perfil_propio(self):
        respuesta = self.client.get(reverse("api_perfil"))
        self.assertEqual(respuesta.json()["usuario"], "ana")

    def test_actualiza_la_meta(self):
        respuesta = self.client.patch(
            reverse("api_perfil"),
            json.dumps({"meta_calorias_diaria": 2200}),
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code, 200)
        self.ana.perfil.refresh_from_db()
        self.assertEqual(self.ana.perfil.meta_calorias_diaria, 2200)

    def test_rechaza_una_meta_fuera_de_rango(self):
        respuesta = self.client.patch(
            reverse("api_perfil"),
            json.dumps({"meta_calorias_diaria": 50}),
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code, 400)


class ComidasAPITests(BaseAPI):
    def setUp(self):
        super().setUp()
        self.client.login(username="ana", password=CLAVE)

    def _cuerpo(self, cantidad="150"):
        return json.dumps(
            {
                "descripcion": "Almuerzo",
                "fecha": self.hoy.isoformat(),
                "filas": [
                    {
                        "alimento": self.arroz.pk,
                        "nombre_mostrado": "Arroz blanco",
                        "cantidad": cantidad,
                        "unidad": "g",
                        "metodo_preparacion": "cocido",
                    }
                ],
            }
        )

    def test_crea_una_comida(self):
        respuesta = self.client.post(
            reverse("api_comidas"), self._cuerpo(), content_type="application/json"
        )
        self.assertEqual(respuesta.status_code, 201)
        datos = respuesta.json()
        self.assertEqual(datos["totales"]["calorias"], 195.0)

    def test_rechaza_cantidades_invalidas(self):
        respuesta = self.client.post(
            reverse("api_comidas"),
            self._cuerpo(cantidad="-20"),
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(RegistroComida.objects.exists())

    def test_rechaza_una_comida_sin_alimentos(self):
        respuesta = self.client.post(
            reverse("api_comidas"),
            json.dumps(
                {"descripcion": "Vacía", "fecha": self.hoy.isoformat(), "filas": []}
            ),
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_lista_solo_las_comidas_propias(self):
        self._comida_de(self.ana, "De Ana")
        self._comida_de(self.luis, "De Luis")
        respuesta = self.client.get(reverse("api_comidas"), {"fecha": self.hoy.isoformat()})
        descripciones = [c["descripcion"] for c in respuesta.json()]
        self.assertEqual(descripciones, ["De Ana"])

    def test_no_se_lee_la_comida_de_otro(self):
        comida = self._comida_de(self.luis)
        respuesta = self.client.get(reverse("api_comida", args=[comida.pk]))
        self.assertEqual(respuesta.status_code, 404)

    def test_no_se_borra_la_comida_de_otro(self):
        comida = self._comida_de(self.luis)
        respuesta = self.client.delete(reverse("api_comida", args=[comida.pk]))
        self.assertEqual(respuesta.status_code, 404)
        self.assertTrue(RegistroComida.objects.filter(pk=comida.pk).exists())

    def test_borra_la_comida_propia(self):
        comida = self._comida_de(self.ana)
        respuesta = self.client.delete(reverse("api_comida", args=[comida.pk]))
        self.assertEqual(respuesta.status_code, 204)
        self.assertFalse(RegistroComida.objects.filter(pk=comida.pk).exists())

    def test_fecha_con_formato_invalido(self):
        respuesta = self.client.get(reverse("api_comidas"), {"fecha": "ayer"})
        self.assertEqual(respuesta.status_code, 400)


class ResumenAPITests(BaseAPI):
    def setUp(self):
        super().setUp()
        self.client.login(username="ana", password=CLAVE)

    def test_resumen_del_dia(self):
        self._comida_de(self.ana)
        respuesta = self.client.get(reverse("api_resumen"), {"fecha": self.hoy.isoformat()})
        datos = respuesta.json()
        self.assertEqual(datos["consumido"], 195.0)
        self.assertEqual(datos["meta"], 2000)

    def test_tendencia_de_varios_dias(self):
        self._comida_de(self.ana)
        respuesta = self.client.get(reverse("api_tendencia"), {"dias": "7"})
        dias = respuesta.json()["dias"]
        self.assertEqual(len(dias), 7)
        self.assertEqual(dias[-1]["calorias"], 195.0)

    def test_la_tendencia_limita_el_numero_de_dias(self):
        respuesta = self.client.get(reverse("api_tendencia"), {"dias": "999"})
        self.assertLessEqual(len(respuesta.json()["dias"]), 31)


@override_settings(OPENAI_API_KEY="")
class AnalizarAPISinClaveTests(BaseAPI):
    """Sin clave, el endpoint responde 503 con el modo manual como salida."""

    def setUp(self):
        super().setUp()
        self.client.login(username="ana", password=CLAVE)

    def test_responde_503_y_ofrece_el_modo_manual(self):
        respuesta = self.client.post(
            reverse("api_analizar"),
            json.dumps({"texto": "una arepa frita"}),
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code, 503)
        self.assertTrue(respuesta.json()["modo_manual_disponible"])


@override_settings(OPENAI_API_KEY="clave-de-prueba")
class AnalizarAPIConClaveTests(BaseAPI):
    """Con la API simulada, el endpoint devuelve los items emparejados."""

    def setUp(self):
        super().setUp()
        self.client.login(username="ana", password=CLAVE)

    @patch("openai.OpenAI")
    def test_devuelve_los_items_detectados(self, cliente_falso):
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
        respuesta_falsa = MagicMock()
        respuesta_falsa.choices = [opcion]
        cliente_falso.return_value.chat.completions.create.return_value = respuesta_falsa

        respuesta = self.client.post(
            reverse("api_analizar"),
            json.dumps({"texto": "una arepa frita"}),
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code, 200)
        item = respuesta.json()["items"][0]
        self.assertEqual(item["metodo_preparacion"], "frito")
        self.assertIn("frito", item["alimento_etiqueta"].lower())
        # El endpoint no guarda nada: solo propone.
        self.assertFalse(RegistroComida.objects.exists())

    def test_rechaza_un_texto_demasiado_corto(self):
        respuesta = self.client.post(
            reverse("api_analizar"),
            json.dumps({"texto": "x"}),
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code, 400)
