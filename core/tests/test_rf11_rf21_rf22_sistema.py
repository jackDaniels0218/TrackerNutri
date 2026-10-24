"""RF11 (Parámetros), RF21 (Integración con IA) y RF22 (Trazabilidad y auditoría)."""

import json
import uuid
from decimal import Decimal
from unittest import mock

from django.test import override_settings
from django.urls import reverse

from core.models import Alimento, Bitacora, CacheInterpretacion, Comida, Parametro, UsoIA
from core.services import ia
from core.services.parametros import limpiar_cache, parametro

from .base import BaseNutri


class ParametrosTests(BaseNutri):
    def test_parametros_iniciales_cargados(self):
        self.assertGreaterEqual(Parametro.objects.count(), 40)
        self.assertEqual(parametro("piso_calorico_femenino"), Decimal("1200"))

    def test_admin_cambia_un_parametro_y_queda_en_bitacora(self):
        admin = self.crear_admin()
        umbral = Parametro.objects.get(clave="umbral_confianza")
        self.entrar(admin).post(reverse("parametro_editar", args=[umbral.pk]), {"valor": "0.7"})
        limpiar_cache()
        self.assertEqual(parametro("umbral_confianza"), Decimal("0.7"))
        registro = Bitacora.objects.get(accion="parametro_cambiado")
        self.assertIn("0.6", registro.detalle)
        self.assertIn("0.7", registro.detalle)

    def test_valor_invalido_se_rechaza(self):
        admin = self.crear_admin()
        umbral = Parametro.objects.get(clave="umbral_confianza")
        r = self.entrar(admin).post(reverse("parametro_editar", args=[umbral.pk]), {"valor": "no es número"})
        self.assertEqual(r.status_code, 200)
        umbral.refresh_from_db()
        self.assertEqual(umbral.valor, "0.6")

    def test_curador_solo_ve_y_cambia_los_nutricionales(self):
        curador = self.crear_curador()
        self.entrar(curador)
        r = self.client.get(reverse("parametros"))
        self.assertContains(r, "factores_actividad")
        self.assertNotContains(r, "ia_presupuesto_mensual_usd")
        presupuesto = Parametro.objects.get(clave="ia_presupuesto_mensual_usd")
        self.client.post(reverse("parametro_editar", args=[presupuesto.pk]), {"valor": "999"})
        presupuesto.refresh_from_db()
        self.assertEqual(presupuesto.valor, "5")

    def test_usuario_no_ve_parametros(self):
        self.assertEqual(self.entrar(self.crear_usuario()).get(reverse("parametros")).status_code, 403)


@override_settings(OPENAI_API_KEY="sk-prueba")
class IntegracionIATests(BaseNutri):
    TEXTO = "un platado de arroz bien graneadito"

    def respuesta(self):
        datos = {"items": [{"fragmento": 0, "name": "arroz blanco cocido", "quantity": 1, "unit": "plato",
                            "preparation": "", "needs_confirmation": False}]}
        return json.dumps(datos), 150, 40

    def test_registra_uso_tokens_y_costo(self):
        usuario = self.crear_usuario(acepta_ia=True)
        with mock.patch.object(ia.ProveedorOpenAI, "llamar", return_value=self.respuesta()):
            ia.interpretar_fragmentos(usuario, [self.TEXTO])
        uso = UsoIA.objects.get(resultado=UsoIA.Resultado.EXITO)
        self.assertEqual((uso.tokens_entrada, uso.tokens_salida), (150, 40))
        self.assertGreater(uso.costo_usd, 0)

    def test_cache_evita_llamadas_repetidas(self):
        usuario = self.crear_usuario(acepta_ia=True)
        with mock.patch.object(ia.ProveedorOpenAI, "llamar", return_value=self.respuesta()) as llamada:
            ia.interpretar_fragmentos(usuario, [self.TEXTO])
            resultado = ia.interpretar_fragmentos(usuario, [self.TEXTO])
        self.assertEqual(llamada.call_count, 1)
        self.assertTrue(resultado.usado)
        self.assertEqual(CacheInterpretacion.objects.get().usos, 1)

    def test_limite_diario_por_usuario(self):
        usuario = self.crear_usuario(acepta_ia=True)
        Parametro.objects.filter(clave="ia_limite_diario_usuario").update(valor="1")
        limpiar_cache()
        with mock.patch.object(ia.ProveedorOpenAI, "llamar", return_value=self.respuesta()) as llamada:
            ia.interpretar_fragmentos(usuario, [self.TEXTO])
            resultado = ia.interpretar_fragmentos(usuario, ["otro texto distinto"])
        self.assertEqual(llamada.call_count, 1)
        self.assertFalse(resultado.usado)
        self.assertTrue(UsoIA.objects.filter(resultado=UsoIA.Resultado.LIMITE).exists())

    def test_presupuesto_agotado_degrada_a_reglas_y_avisa(self):
        usuario = self.crear_usuario(acepta_ia=True)
        admin = self.crear_admin()
        UsoIA.objects.create(proveedor="openai", modelo="m", resultado=UsoIA.Resultado.EXITO, costo_usd=Decimal("6"))
        with mock.patch.object(ia.ProveedorOpenAI, "llamar") as llamada:
            resultado = ia.interpretar_fragmentos(usuario, [self.TEXTO])
        llamada.assert_not_called()
        self.assertFalse(resultado.usado)
        self.assertTrue(admin.notificaciones.filter(titulo__icontains="presupuesto").exists())

    def test_falla_del_proveedor_no_impide_registrar(self):
        usuario = self.crear_usuario(acepta_ia=True)
        with mock.patch.object(ia.ProveedorOpenAI, "llamar", side_effect=ia.ProveedorNoDisponible("sin_conexion")):
            r = self.entrar(usuario).post(reverse("comida_nueva"), {"texto": self.TEXTO, "fecha": "2026-10-20",
                                                                    "hora": "12:00", "tipo": ""})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(UsoIA.objects.filter(resultado=UsoIA.Resultado.FALLO, tipo_error="sin_conexion").exists())

    def test_proveedor_ninguno(self):
        Parametro.objects.filter(clave="ia_proveedor").update(valor="ninguno")
        limpiar_cache()
        self.assertFalse(ia.ia_disponible())

    def test_proveedor_local_no_requiere_autorizacion_externa(self):
        Parametro.objects.filter(clave="ia_proveedor").update(valor="local")
        limpiar_cache()
        usuario = self.crear_usuario(acepta_ia=False)
        with mock.patch.object(ia.ProveedorLocal, "llamar", return_value=self.respuesta()) as llamada:
            resultado = ia.interpretar_fragmentos(usuario, [self.TEXTO])
        llamada.assert_called_once()
        self.assertEqual(resultado.motor, "modelo_local")

    def test_pantalla_de_ia_para_el_administrador(self):
        r = self.entrar(self.crear_admin()).get(reverse("ia_admin"))
        self.assertContains(r, "Plantilla")


class AuditoriaTests(BaseNutri):
    def test_la_bitacora_no_se_modifica_ni_se_borra(self):
        self.crear_usuario()
        registro = Bitacora.objects.first()
        registro.detalle = "alterado"
        with self.assertRaises(Exception):
            registro.save()
        with self.assertRaises(Exception):
            registro.delete()

    def test_ingresos_y_cambios_quedan_registrados(self):
        usuario = self.crear_usuario()
        self.client.post(reverse("login"), {"username": usuario.email, "password": "ClaveSegura2026"})
        acciones = set(Bitacora.objects.values_list("accion", flat=True))
        self.assertTrue({"cuenta_creada", "perfil_actualizado", "meta_registrada", "ingreso"} <= acciones)

    def test_la_comida_guarda_las_versiones_usadas(self):
        usuario = self.crear_usuario()
        from core.services import comidas

        comida = comidas.crear_desde_texto(usuario, "una arepa con huevo")
        self.assertTrue(comida.version_motor)
        self.assertEqual(comida.version_catalogo, self.version.numero)
        self.assertEqual(comida.motor, "reglas")

    def test_pantalla_de_auditoria_con_filtro(self):
        admin = self.crear_admin()
        self.crear_usuario()
        r = self.entrar(admin).get(reverse("auditoria"), {"accion": "cuenta_creada"})
        self.assertContains(r, "cuenta_creada")
        self.assertEqual(self.entrar(self.crear_usuario("otro@prueba.co")).get(reverse("auditoria")).status_code, 403)


class ApiTests(BaseNutri):
    def test_requiere_sesion(self):
        self.assertIn(self.client.get(reverse("api_resumen")).status_code, (401, 403))

    def test_interpretar_confirmar_y_resumen(self):
        usuario = self.crear_usuario()
        self.entrar(usuario)
        r = self.client.post(reverse("api_interpretar"), {"texto": "200 g de arroz blanco"}, content_type="application/json")
        self.assertEqual(r.status_code, 201)
        pk = r.json()["id"]
        self.assertEqual(self.client.post(reverse("api_comida_confirmar", args=[pk])).status_code, 200)
        resumen = self.client.get(reverse("api_resumen")).json()
        self.assertGreater(resumen["kcal"], 0)

    def test_registro_manual_idempotente(self):
        usuario = self.crear_usuario()
        self.entrar(usuario)
        arroz = Alimento.objects.get(nombre="Arroz blanco cocido")
        cuerpo = {"tipo": "almuerzo", "clave_idempotencia": str(uuid.uuid4()),
                  "filas": [{"alimento_id": arroz.pk, "cantidad_g": "150"}]}
        for _ in range(2):
            self.assertEqual(self.client.post(reverse("api_comidas"), cuerpo, content_type="application/json").status_code, 201)
        self.assertEqual(Comida.objects.filter(usuario=usuario).count(), 1)

    def test_aislamiento_en_la_api(self):
        ana = self.crear_usuario("ana@prueba.co")
        self.entrar(ana)
        pk = self.client.post(reverse("api_interpretar"), {"texto": "un huevo"}, content_type="application/json").json()["id"]
        self.entrar(self.crear_usuario("luis@prueba.co"))
        self.assertEqual(self.client.get(reverse("api_comida", args=[pk])).status_code, 404)

    def test_esquema_openapi(self):
        self.entrar(self.crear_usuario())
        self.assertEqual(self.client.get("/api/v1/esquema/").status_code, 200)
