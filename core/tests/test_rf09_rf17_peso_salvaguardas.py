"""RF9 (Seguimiento de peso) y RF17 (Salvaguardas de salud y seguridad)."""

import re
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from core.models import Alimento, DiaRegistro, Pesaje
from core.services import comidas, metas, salvaguardas

from .base import BaseNutri


class PesoTests(BaseNutri):
    def test_registrar_editar_y_eliminar_pesaje(self):
        usuario = self.crear_usuario()
        self.entrar(usuario)
        hoy = timezone.localdate()
        self.client.post(reverse("peso"), {"fecha": hoy.isoformat(), "peso_kg": "69.5", "observacion": ""})
        pesaje = Pesaje.objects.get(usuario=usuario)
        self.client.post(reverse("peso_editar", args=[pesaje.pk]), {"fecha": hoy.isoformat(), "peso_kg": "69.8", "observacion": ""})
        pesaje.refresh_from_db()
        self.assertEqual(pesaje.peso_kg, Decimal("69.8"))
        self.client.post(reverse("peso_eliminar", args=[pesaje.pk]))
        self.assertFalse(Pesaje.objects.filter(usuario=usuario).exists())

    def test_peso_fuera_de_rango_y_fecha_futura(self):
        usuario = self.crear_usuario()
        self.entrar(usuario)
        hoy = timezone.localdate()
        self.client.post(reverse("peso"), {"fecha": hoy.isoformat(), "peso_kg": "10", "observacion": ""})
        self.client.post(reverse("peso"), {"fecha": (hoy + timedelta(days=2)).isoformat(), "peso_kg": "70", "observacion": ""})
        self.assertFalse(Pesaje.objects.filter(usuario=usuario).exists())

    def test_cambio_brusco_advierte_sin_bloquear(self):
        usuario = self.crear_usuario()
        hoy = timezone.localdate()
        Pesaje.objects.create(usuario=usuario, fecha=hoy - timedelta(days=1), peso_kg=Decimal("70"))
        r = self.entrar(usuario).post(reverse("peso"), {"fecha": hoy.isoformat(), "peso_kg": "74", "observacion": ""}, follow=True)
        self.assertContains(r, "cambió 4.0 kg en un día")
        self.assertEqual(Pesaje.objects.filter(usuario=usuario).count(), 2)

    def test_peso_tendencial_es_media_movil(self):
        usuario = self.crear_usuario()
        hoy = timezone.localdate()
        for i, peso in enumerate(("70.0", "71.0", "69.0")):
            Pesaje.objects.create(usuario=usuario, fecha=hoy - timedelta(days=2 - i), peso_kg=Decimal(peso))
        serie = salvaguardas.peso_tendencial(usuario)
        self.assertEqual(serie[-1][2], Decimal("70.0"))

    def test_un_pesaje_por_dia(self):
        usuario = self.crear_usuario()
        hoy = timezone.localdate()
        Pesaje.objects.create(usuario=usuario, fecha=hoy, peso_kg=Decimal("70"))
        self.entrar(usuario).post(reverse("peso"), {"fecha": hoy.isoformat(), "peso_kg": "70.2", "observacion": ""})
        self.assertEqual(Pesaje.objects.filter(usuario=usuario).count(), 1)


class SalvaguardasTests(BaseNutri):
    def test_gestante_recibe_meta_informativa_sin_deficit(self):
        usuario = self.crear_usuario(gestante_lactante=True)
        meta = metas.meta_vigente(usuario)
        self.assertTrue(meta.solo_informativa)
        self.assertEqual(meta.kcal_dia, meta.gasto_total)
        r = self.entrar(usuario).get(reverse("panel"))
        self.assertContains(r, "informativo")

    def test_acompanamiento_profesional_desactiva_el_deficit(self):
        usuario = self.crear_usuario(requiere_acompanamiento=True)
        self.assertTrue(metas.meta_vigente(usuario).solo_informativa)
        with self.assertRaises(metas.AjusteNoPermitido):
            metas.ajuste_manual(usuario, 1400)

    def test_deficit_maximo(self):
        kcal, avisos = salvaguardas.aplicar_limites(Decimal("1300"), Decimal("2400"), "masculino")
        self.assertEqual(kcal, Decimal("1800"))  # 25 % de déficit máximo
        self.assertTrue(avisos)

    def test_alerta_por_dias_bajo_el_piso(self):
        usuario = self.crear_usuario()
        hoy = timezone.localdate()
        tinto = Alimento.objects.get(nombre="Café tinto (sin azúcar)")
        for i in range(3):
            dia = hoy - timedelta(days=i)
            momento = timezone.make_aware(timezone.datetime.combine(dia, timezone.datetime.min.time().replace(hour=9)))
            comidas.crear_manual(usuario, [{"destino": tinto, "cantidad_g": 200}], fecha_hora=momento)
            DiaRegistro.objects.create(usuario=usuario, fecha=dia, completo=True)
        alertas = salvaguardas.notificar_riesgos(usuario)
        self.assertEqual([a.clave for a in alertas], ["bajo_piso"])
        self.assertTrue(usuario.notificaciones.filter(tipo="cuidado").exists())
        # Con riesgo no se reduce la meta.
        Pesaje.objects.create(usuario=usuario, fecha=hoy - timedelta(days=8), peso_kg=Decimal("70"))
        Pesaje.objects.create(usuario=usuario, fecha=hoy, peso_kg=Decimal("69.8"))
        DiaRegistro.objects.bulk_create([DiaRegistro(usuario=usuario, fecha=hoy - timedelta(days=i), completo=True) for i in (3, 4)])
        self.assertFalse(metas.evaluar_ajuste_semanal(usuario).aplicado)

    def test_dia_incompleto_no_dispara_alertas(self):
        usuario = self.crear_usuario()
        tinto = Alimento.objects.get(nombre="Café tinto (sin azúcar)")
        for i in range(3):
            dia = timezone.localdate() - timedelta(days=i)
            momento = timezone.make_aware(timezone.datetime.combine(dia, timezone.datetime.min.time().replace(hour=9)))
            comidas.crear_manual(usuario, [{"destino": tinto, "cantidad_g": 200}], fecha_hora=momento)
        self.assertEqual(salvaguardas.detectar_riesgos(usuario), [])

    def test_ocultar_cifras(self):
        usuario = self.crear_usuario()
        comidas.crear_manual(usuario, [{"destino": Alimento.objects.get(nombre="Arroz blanco cocido"), "cantidad_g": 150}])
        self.entrar(usuario).post(reverse("privacidad"), {"accion": "ocultar"})
        r = self.client.get(reverse("panel"))
        meta = metas.meta_vigente(usuario)
        self.assertNotContains(r, f"{meta.kcal_dia:.0f} <small>kcal")

    def test_pausar_seguimiento(self):
        usuario = self.crear_usuario()
        self.entrar(usuario).post(reverse("privacidad"), {"accion": "pausa"})
        usuario.cuenta.refresh_from_db()
        self.assertTrue(usuario.cuenta.seguimiento_pausado)

    def test_la_interfaz_no_usa_lenguaje_moralizante(self):
        """Ninguna plantilla califica alimentos como buenos, malos, trampa o pecado."""
        encontrados = []
        for plantilla in Path(settings.BASE_DIR, "templates").rglob("*.html"):
            texto = re.sub(r"{%.*?%}|{{.*?}}|<[^>]+>", " ", plantilla.read_text(encoding="utf-8"), flags=re.S)
            for palabra in salvaguardas.contiene_lenguaje_prohibido(texto):
                encontrados.append(f"{plantilla.name}: {palabra}")
        self.assertEqual(encontrados, [])
