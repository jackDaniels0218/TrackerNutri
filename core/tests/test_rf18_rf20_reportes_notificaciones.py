"""RF18 (Gráficos y reportes) y RF20 (Notificaciones y recordatorios)."""

from datetime import time, timedelta

from django.core import mail
from django.urls import reverse
from django.utils import timezone

from core.models import Alimento, Notificacion, RecordatorioUsuario
from core.services import comidas, notificaciones, reportes

from .base import BaseNutri


class ReportesTests(BaseNutri):
    def setUp(self):
        super().setUp()
        self.usuario = self.crear_usuario()
        comidas.crear_manual(self.usuario, [{"destino": Alimento.objects.get(nombre="Arroz blanco cocido"), "cantidad_g": 150}])

    def test_series_por_periodo(self):
        for dias in (7, 30, 90):
            series = reportes.series(self.usuario, dias)
            self.assertEqual(len(series["etiquetas"]), dias)
            self.assertEqual(len(series["ingesta"]["kcal"]), dias)
            self.assertIsNotNone(series["ingesta"]["kcal"][-1])
            self.assertIsNone(series["ingesta"]["kcal"][0])  # día sin registros: vacío, no cero

    def test_pantalla_de_reportes(self):
        self.entrar(self.usuario)
        for dias in (7, 30, 90):
            r = self.client.get(reverse("reportes"), {"dias": dias})
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, "datos-series")

    def test_exportar_csv(self):
        r = self.entrar(self.usuario).get(reverse("reporte_csv"))
        self.assertEqual(r["Content-Type"], "text/csv; charset=utf-8")
        contenido = r.content.decode()
        self.assertIn("Arroz blanco cocido", contenido)

    def test_informe_para_imprimir(self):
        r = self.entrar(self.usuario).get(reverse("reporte_imprimir"))
        self.assertContains(r, "estimaciones")

    def test_panel_agregado_sin_datos_personales(self):
        datos = reportes.panel_agregado()
        self.assertEqual(datos["comidas"], 1)
        r = self.entrar(self.crear_admin()).get(reverse("indicadores"))
        self.assertNotContains(r, self.usuario.email)


class NotificacionesTests(BaseNutri):
    def test_hasta_tres_recordatorios(self):
        usuario = self.crear_usuario()
        self.entrar(usuario).post(reverse("recordatorios"), {"hora_1": "08:00", "hora_2": "13:00", "hora_3": "19:00"})
        self.assertEqual(RecordatorioUsuario.objects.filter(usuario=usuario, activo=True).count(), 3)

    def test_generar_recordatorios_una_vez_al_dia(self):
        usuario = self.crear_usuario()
        RecordatorioUsuario.objects.create(usuario=usuario, hora=time(12, 0))
        momento = timezone.make_aware(timezone.datetime.combine(timezone.localdate(), time(12, 10)))
        self.assertEqual(notificaciones.generar_recordatorios(momento), 1)
        self.assertEqual(notificaciones.generar_recordatorios(momento), 0)

    def test_ventana_que_cruza_la_medianoche(self):
        usuario = self.crear_usuario()
        RecordatorioUsuario.objects.create(usuario=usuario, hora=time(23, 55))
        momento = timezone.make_aware(timezone.datetime.combine(timezone.localdate(), time(0, 10)))
        self.assertEqual(notificaciones.generar_recordatorios(momento), 1)

    def test_sin_recordatorios_con_seguimiento_en_pausa(self):
        usuario = self.crear_usuario()
        usuario.cuenta.seguimiento_pausado = True
        usuario.cuenta.save()
        RecordatorioUsuario.objects.create(usuario=usuario, hora=time(12, 0))
        momento = timezone.make_aware(timezone.datetime.combine(timezone.localdate(), time(12, 10)))
        self.assertEqual(notificaciones.generar_recordatorios(momento), 0)

    def test_resumen_semanal_por_correo(self):
        usuario = self.crear_usuario()
        usuario.cuenta.recibir_resumen_semanal = True
        usuario.cuenta.save()
        comidas.crear_manual(usuario, [{"destino": Alimento.objects.get(nombre="Arroz blanco cocido"), "cantidad_g": 150}])
        self.assertEqual(notificaciones.resumen_semanal(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_marcar_como_leida(self):
        usuario = self.crear_usuario()
        aviso = notificaciones.notificar(usuario, Notificacion.Tipo.RECORDATORIO, "Hola", "Mensaje")
        self.entrar(usuario)
        self.assertContains(self.client.get(reverse("notificaciones")), "Hola")
        self.client.post(reverse("notificacion_leer", args=[aviso.pk]))
        aviso.refresh_from_db()
        self.assertTrue(aviso.leida)

    def test_no_se_leen_notificaciones_ajenas(self):
        ana = self.crear_usuario("ana@prueba.co")
        luis = self.crear_usuario("luis@prueba.co")
        aviso = notificaciones.notificar(ana, Notificacion.Tipo.RECORDATORIO, "Privado", "Mensaje")
        self.assertEqual(self.entrar(luis).post(reverse("notificacion_leer", args=[aviso.pk])).status_code, 404)

    def test_proceso_de_recordatorios_desde_administracion(self):
        usuario = self.crear_usuario()
        RecordatorioUsuario.objects.create(usuario=usuario, hora=(timezone.localtime() - timedelta(minutes=5)).time())
        r = self.entrar(self.crear_admin()).post(reverse("procesos"), {"proceso": "recordatorios"}, follow=True)
        self.assertContains(r, "Recordatorios generados: 1")
