"""RF2 (Perfil nutricional), RF8 (Metas) y RF16 (Cálculo de metas y ajuste semanal)."""

from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from core.models import Alimento, DiaRegistro, MetaCalorica, OrigenMeta, Pesaje
from core.services import comidas, cuentas, metas
from core.services.parametros import parametro

from .base import BaseNutri


class PerfilTests(BaseNutri):
    def test_rangos_del_srs(self):
        usuario = self.crear_usuario()
        perfil = usuario.perfil
        for campo, valor in (("estatura_cm", 90), ("estatura_cm", 260), ("peso_inicial_kg", Decimal("20"))):
            setattr(perfil, campo, valor)
            with self.assertRaises(ValidationError, msg=campo):
                perfil.full_clean()
            perfil.refresh_from_db()

    def test_peso_meta_fuera_de_imc_saludable_se_rechaza(self):
        usuario = self.crear_usuario()
        usuario.perfil.peso_meta_kg = Decimal("40")  # IMC 14,7 para 1,65 m
        with self.assertRaises(ValidationError):
            usuario.perfil.full_clean()

    def test_cambiar_actividad_recalcula_la_meta(self):
        usuario = self.crear_usuario()
        antes = metas.meta_vigente(usuario).kcal_dia
        datos = self.perfil_base(nivel_actividad="alto")
        _, recalculo = cuentas.guardar_perfil(usuario, datos)
        self.assertTrue(recalculo)
        nueva = metas.meta_vigente(usuario)
        self.assertEqual(nueva.origen, OrigenMeta.RECALCULO)
        self.assertGreater(nueva.kcal_dia, antes)

    def test_editar_perfil_desde_la_pantalla(self):
        usuario = self.crear_usuario()
        datos = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in self.perfil_base(ritmo="lento").items()}
        r = self.entrar(usuario).post(reverse("perfil"), datos)
        self.assertEqual(r.status_code, 302)
        usuario.perfil.refresh_from_db()
        self.assertEqual(usuario.perfil.ritmo, "lento")


class CalculoDeMetaTests(BaseNutri):
    def test_mifflin_st_jeor(self):
        # 10×70 + 6,25×165 − 5×30 − 161 = 1420,25
        self.assertEqual(metas.tmb_mifflin(70, 165, 30, "femenino"), Decimal("1420.25"))
        # 10×80 + 6,25×180 − 5×25 + 5 = 1805
        self.assertEqual(metas.tmb_mifflin(80, 180, 25, "masculino"), Decimal("1805"))

    def test_meta_inicial_con_deficit_por_ritmo(self):
        usuario = self.crear_usuario()
        meta = metas.meta_vigente(usuario)
        tmb = metas.tmb_mifflin(70, 165, usuario.perfil.edad, "femenino")
        gasto = tmb * Decimal("1.375")
        self.assertAlmostEqual(float(meta.gasto_total), float(gasto), delta=0.1)
        self.assertAlmostEqual(float(meta.kcal_dia), float(gasto * Decimal("0.8")), delta=0.1)
        self.assertEqual(meta.proteinas_g, Decimal("112.0"))  # 1,6 g × 70 kg
        self.assertTrue(meta.explicacion["pasos"])

    def test_nunca_baja_del_piso(self):
        usuario = self.crear_usuario(estatura_cm=150, peso_inicial_kg=Decimal("45"), peso_meta_kg=Decimal("43"),
                                     nivel_actividad="sedentario", fecha_nacimiento=timezone.localdate().replace(year=timezone.localdate().year - 60))
        self.assertGreaterEqual(metas.meta_vigente(usuario).kcal_dia, parametro("piso_calorico_femenino"))

    def test_mantener_no_aplica_deficit(self):
        usuario = self.crear_usuario(objetivo="mantener", peso_meta_kg=None)
        meta = metas.meta_vigente(usuario)
        self.assertEqual(meta.kcal_dia, meta.gasto_total)


class MetasCrudTests(BaseNutri):
    def test_una_sola_meta_vigente_e_historial(self):
        usuario = self.crear_usuario()
        metas.ajuste_manual(usuario, metas.meta_vigente(usuario).kcal_dia + 50)
        self.assertEqual(MetaCalorica.objects.filter(usuario=usuario, vigente=True).count(), 1)
        self.assertEqual(MetaCalorica.objects.filter(usuario=usuario).count(), 2)

    def test_ajuste_manual_bajo_el_piso_se_rechaza(self):
        usuario = self.crear_usuario()
        r = self.entrar(usuario).post(reverse("metas"), {"kcal": "1000"})
        self.assertContains(r, "fuera de los límites de seguridad")
        self.assertEqual(MetaCalorica.objects.filter(usuario=usuario).count(), 1)

    def test_el_historial_de_metas_no_se_borra(self):
        usuario = self.crear_usuario()
        with self.assertRaises(Exception):
            metas.meta_vigente(usuario).delete()

    def test_pantalla_de_metas_explica_el_calculo(self):
        usuario = self.crear_usuario()
        r = self.entrar(usuario).get(reverse("metas"))
        self.assertContains(r, "Mifflin-St Jeor")
        self.assertContains(r, "Inicial")


class AjusteSemanalTests(BaseNutri):
    def preparar_semana(self, usuario, kcal_por_dia=1300, peso_inicio="70.0", peso_fin="70.6"):
        hoy = timezone.localdate()
        arroz = Alimento.objects.get(nombre="Arroz blanco cocido")
        gramos = Decimal(kcal_por_dia) / arroz.kcal * 100
        for i in range(6):
            dia = hoy - timedelta(days=i)
            momento = timezone.make_aware(timezone.datetime.combine(dia, timezone.datetime.min.time().replace(hour=12)))
            comidas.crear_manual(usuario, [{"destino": arroz, "cantidad_g": gramos}], fecha_hora=momento)
            DiaRegistro.objects.create(usuario=usuario, fecha=dia, completo=True)
        Pesaje.objects.create(usuario=usuario, fecha=hoy - timedelta(days=10), peso_kg=Decimal(peso_inicio))
        Pesaje.objects.create(usuario=usuario, fecha=hoy, peso_kg=Decimal(peso_fin))

    def test_sin_datos_suficientes_no_ajusta_y_explica(self):
        usuario = self.crear_usuario()
        resultado = metas.evaluar_ajuste_semanal(usuario)
        self.assertFalse(resultado.aplicado)
        self.assertIn("días", resultado.mensaje)

    def test_ajuste_limitado_y_revertible(self):
        usuario = self.crear_usuario()
        anterior = metas.meta_vigente(usuario)
        self.preparar_semana(usuario)  # come poco y aun así sube de peso → el gasto real es menor
        resultado = metas.evaluar_ajuste_semanal(usuario)
        self.assertTrue(resultado.aplicado, resultado.mensaje)
        nueva = resultado.meta
        self.assertEqual(nueva.origen, OrigenMeta.AUTOMATICO)
        limite = min(Decimal("150"), anterior.kcal_dia * Decimal("0.10"))
        self.assertLessEqual(abs(nueva.kcal_dia - anterior.kcal_dia), limite + Decimal("0.1"))
        self.assertTrue(nueva.puede_revertirse)
        self.assertTrue(usuario.notificaciones.filter(titulo__icontains="meta").exists())

        restaurada = metas.revertir(nueva)
        self.assertEqual(restaurada.kcal_dia, anterior.kcal_dia)
        self.assertEqual(restaurada.origen, OrigenMeta.REVERSION)

    def test_no_se_revierte_despues_de_48_horas(self):
        usuario = self.crear_usuario()
        self.preparar_semana(usuario)
        nueva = metas.evaluar_ajuste_semanal(usuario).meta
        MetaCalorica.objects.filter(pk=nueva.pk).update(revertible_hasta=timezone.now() - timedelta(minutes=1))
        nueva.refresh_from_db()
        with self.assertRaises(metas.AjusteNoPermitido):
            metas.revertir(nueva)

    def test_seguimiento_en_pausa_no_ajusta(self):
        usuario = self.crear_usuario()
        self.preparar_semana(usuario)
        usuario.cuenta.seguimiento_pausado = True
        usuario.cuenta.save()
        self.assertFalse(metas.evaluar_ajuste_semanal(usuario).aplicado)

    def test_alcanzar_el_peso_meta_propone_mantenimiento(self):
        usuario = self.crear_usuario(estatura_cm=175, peso_meta_kg=Decimal("69.0"))
        self.preparar_semana(usuario, peso_fin="68.8")
        resultado = metas.evaluar_ajuste_semanal(usuario)
        self.assertIn("mantenimiento", resultado.mensaje)
        meta = metas.pasar_a_mantenimiento(usuario)
        self.assertEqual(meta.origen, OrigenMeta.MANTENIMIENTO)

    def test_evaluar_desde_la_pantalla(self):
        usuario = self.crear_usuario()
        self.preparar_semana(usuario)
        r = self.entrar(usuario).post(reverse("meta_evaluar"), follow=True)
        self.assertContains(r, "Puedes revertir este cambio")
