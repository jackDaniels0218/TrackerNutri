"""
RF21: servicios externos compatibles con la API de OpenAI (Groq, OpenRouter,
Google AI Studio…) y modelos locales.

Las pruebas de integración levantan un servidor HTTP local que habla el
protocolo de OpenAI y se comporta como un modelo gratuito que NO admite el
esquema estricto. Así se ejercita el cliente real (cabeceras, cuerpo, errores
y reintento con JSON simple) sin salir a internet. No sustituye la prueba con
el servicio real: para eso está `python manage.py probar_ia`.
"""

import json
import threading
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from django.test import override_settings

from core.models import Parametro, UsoIA
from core.services import ia
from core.services.interpretacion import interpretar
from core.services.parametros import limpiar_cache

from .base import BaseNutri

CLAVE_OPENAI = "sk-openai-que-no-debe-salir"
CLAVE_COMPATIBLE = "gsk-clave-del-servicio-gratuito"


class ServidorCompatible(ThreadingHTTPServer):
    """Imita /v1/chat/completions de un servicio compatible con OpenAI."""

    def __init__(self, admite_esquema=False, estado_forzado=None):
        super().__init__(("127.0.0.1", 0), ManejadorCompatible)
        self.admite_esquema = admite_esquema
        self.estado_forzado = estado_forzado
        self.peticiones = []

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server_address[1]}/v1"


class ManejadorCompatible(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _responder(self, estado, cuerpo):
        datos = json.dumps(cuerpo).encode()
        self.send_response(estado)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def do_POST(self):
        cuerpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.peticiones.append({"autorizacion": self.headers.get("Authorization"), "cuerpo": cuerpo})
        if self.server.estado_forzado:
            estado, codigo = self.server.estado_forzado
            return self._responder(estado, {"error": {"message": codigo, "type": codigo, "code": codigo}})
        formato = cuerpo["response_format"]["type"]
        if formato == "json_schema" and not self.server.admite_esquema:
            return self._responder(400, {"error": {"message": "response_format json_schema is not supported by this model",
                                                   "type": "invalid_request_error"}})
        fragmentos = json.loads(cuerpo["messages"][-1]["content"])["fragmentos"]
        items = [{"fragmento": i, "name": "arroz blanco cocido", "quantity": 1, "unit": "plato",
                  "preparation": "", "needs_confirmation": False} for i, _ in enumerate(fragmentos)]
        self._responder(200, {
            "id": "x", "object": "chat.completion", "created": 0, "model": cuerpo["model"],
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": json.dumps({"items": items})}}],
            "usage": {"prompt_tokens": 210, "completion_tokens": 35, "total_tokens": 245},
        })


@override_settings(OPENAI_API_KEY=CLAVE_OPENAI, IA_COMPATIBLE_API_KEY=CLAVE_COMPATIBLE)
class ProveedorCompatibleTests(BaseNutri):
    TEXTO = "un platado de arroz bien graneadito"

    def servidor(self, **opciones):
        servidor = ServidorCompatible(**opciones)
        hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
        hilo.start()
        self.addCleanup(servidor.server_close)
        self.addCleanup(servidor.shutdown)
        self.usar("compatible", ia_url_compatible=servidor.url, ia_modelo_compatible="llama-3.3-70b-versatile")
        return servidor

    def usar(self, proveedor, **parametros):
        Parametro.objects.filter(clave="ia_proveedor").update(valor=proveedor)
        for clave, valor in parametros.items():
            Parametro.objects.filter(clave=clave).update(valor=valor)
        limpiar_cache()

    def test_modelo_sin_esquema_estricto_reintenta_con_json_simple(self):
        servidor = self.servidor(admite_esquema=False)
        usuario = self.crear_usuario(acepta_ia=True)
        resultado = interpretar(self.TEXTO, usuario=usuario)
        self.assertEqual(resultado.items[0].destino.nombre, "Arroz blanco cocido")
        self.assertEqual(resultado.motor, "ia_externa")
        formatos = [p["cuerpo"]["response_format"]["type"] for p in servidor.peticiones]
        self.assertEqual(formatos, ["json_schema", "json_object"])
        self.assertIn("esquema", servidor.peticiones[1]["cuerpo"]["messages"][0]["content"])

    def test_modelo_con_esquema_estricto_lo_usa(self):
        servidor = self.servidor(admite_esquema=True)
        interpretar(self.TEXTO, usuario=self.crear_usuario(acepta_ia=True))
        self.assertEqual([p["cuerpo"]["response_format"]["type"] for p in servidor.peticiones], ["json_schema"])

    def test_usa_su_propia_clave_y_nunca_la_de_openai(self):
        servidor = self.servidor()
        interpretar(self.TEXTO, usuario=self.crear_usuario(acepta_ia=True))
        for peticion in servidor.peticiones:
            self.assertEqual(peticion["autorizacion"], f"Bearer {CLAVE_COMPATIBLE}")
        self.assertEqual(servidor.peticiones[0]["cuerpo"]["model"], "llama-3.3-70b-versatile")

    def test_solo_se_envia_el_fragmento_no_resuelto(self):
        servidor = self.servidor()
        interpretar("una arepa con huevo y " + self.TEXTO, usuario=self.crear_usuario(acepta_ia=True))
        enviado = json.loads(servidor.peticiones[0]["cuerpo"]["messages"][-1]["content"])
        self.assertEqual(enviado, {"fragmentos": ["un platado de arroz bien graneadito"]})

    def test_requiere_la_autorizacion_de_ia(self):
        servidor = self.servidor()
        resultado = interpretar(self.TEXTO, usuario=self.crear_usuario(acepta_ia=False))
        self.assertEqual(servidor.peticiones, [])
        self.assertIsNone(resultado.items[0].destino)
        self.assertTrue(resultado.avisos)

    def test_nivel_gratuito_registra_tokens_sin_costo(self):
        self.servidor()
        interpretar(self.TEXTO, usuario=self.crear_usuario(acepta_ia=True))
        uso = UsoIA.objects.get(resultado=UsoIA.Resultado.EXITO)
        self.assertEqual((uso.proveedor, uso.tokens_entrada, uso.tokens_salida), ("compatible", 210, 35))
        self.assertEqual(uso.costo_usd, Decimal("0"))

    def test_no_lo_detiene_el_presupuesto_de_openai(self):
        self.servidor()
        UsoIA.objects.create(proveedor="openai", modelo="m", resultado=UsoIA.Resultado.EXITO, costo_usd=Decimal("50"))
        resultado = ia.interpretar_fragmentos(self.crear_usuario(acepta_ia=True), [self.TEXTO])
        self.assertTrue(resultado.usado)

    def test_cuota_agotada_degrada_a_reglas(self):
        self.servidor(estado_forzado=(429, "rate_limit_exceeded"))
        resultado = interpretar(self.TEXTO, usuario=self.crear_usuario(acepta_ia=True))
        self.assertEqual(resultado.motor, "reglas")
        self.assertTrue(UsoIA.objects.filter(resultado=UsoIA.Resultado.FALLO, tipo_error="limite_proveedor").exists())

    def test_clave_invalida_y_modelo_inexistente(self):
        for estado, motivo in ((401, "clave_invalida"), (404, "modelo_no_encontrado")):
            UsoIA.objects.all().delete()
            self.servidor(estado_forzado=(estado, "error"))
            ia.interpretar_fragmentos(self.crear_usuario(f"u{estado}@prueba.co", acepta_ia=True), [self.TEXTO])
            self.assertTrue(UsoIA.objects.filter(tipo_error=motivo).exists(), motivo)

    def test_sin_clave_no_esta_disponible(self):
        self.usar("compatible")
        with override_settings(IA_COMPATIBLE_API_KEY=""):
            self.assertFalse(ia.ia_disponible())


@override_settings(OPENAI_API_KEY=CLAVE_OPENAI)
class ProveedorLocalTests(BaseNutri):
    def test_el_modelo_local_no_recibe_la_clave_de_openai(self):
        Parametro.objects.filter(clave="ia_proveedor").update(valor="local")
        limpiar_cache()
        proveedor = ia.proveedor_activo()
        self.assertEqual(proveedor.clave, "")
        self.assertNotEqual(proveedor._cliente().api_key, CLAVE_OPENAI)
