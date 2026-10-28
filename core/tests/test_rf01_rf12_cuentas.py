"""RF1 (CRUD Usuarios) y RF12 (Acceso y registro)."""

from datetime import timedelta

from django.contrib.auth.models import User
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from core.models import Bitacora, Consentimiento, Cuenta, EstadoCuenta, MetaCalorica, Rol, TipoConsentimiento
from core.services import cuentas

from .base import CLAVE, BaseNutri


class RegistroEnTresPasosTests(BaseNutri):
    def datos_paso1(self, **cambios):
        datos = {"nombres": "Laura", "apellidos": "Gómez", "correo": "Laura@Correo.co", "password1": CLAVE,
                 "password2": CLAVE, "acepta_datos": "on", "entiende_aviso": "on"}
        datos.update(cambios)
        return datos

    def test_registro_completo_crea_cuenta_perfil_y_meta(self):
        r = self.client.post(reverse("registro"), self.datos_paso1())
        self.assertRedirects(r, reverse("registro_perfil"))
        usuario = User.objects.get(email="laura@correo.co")
        self.assertEqual(usuario.cuenta.rol, Rol.USUARIO)
        self.assertEqual(usuario.cuenta.paso_registro, Cuenta.PASO_PERFIL)

        # Sin terminar el registro, cualquier pantalla devuelve al paso pendiente.
        self.assertRedirects(self.client.get(reverse("panel")), reverse("registro_perfil"))

        perfil = self.perfil_base()
        perfil["fecha_nacimiento"] = perfil["fecha_nacimiento"].isoformat()
        perfil["fecha_peso_inicial"] = perfil["fecha_peso_inicial"].isoformat()
        r = self.client.post(reverse("registro_perfil"), perfil)
        self.assertRedirects(r, reverse("registro_meta"))
        meta = MetaCalorica.objects.get(usuario=usuario, vigente=True)
        r = self.client.get(reverse("registro_meta"))
        self.assertContains(r, "Mifflin-St Jeor")
        self.assertContains(r, f"{meta.kcal_dia:.0f}")
        self.assertRedirects(self.client.post(reverse("registro_meta")), reverse("panel"))
        usuario.cuenta.refresh_from_db()
        self.assertTrue(usuario.cuenta.registro_completo)

    def test_autorizaciones_separadas_y_datos_obligatoria(self):
        r = self.client.post(reverse("registro"), self.datos_paso1(acepta_datos=""))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(email="laura@correo.co").exists())

        self.client.post(reverse("registro"), self.datos_paso1(acepta_ia="on"))
        usuario = User.objects.get(email="laura@correo.co")
        tipos = dict(Consentimiento.objects.filter(usuario=usuario).values_list("tipo", "otorgado"))
        self.assertEqual(tipos, {TipoConsentimiento.DATOS: True, TipoConsentimiento.IA: True})

    def test_correo_unico(self):
        self.crear_usuario("laura@correo.co")
        r = self.client.post(reverse("registro"), self.datos_paso1())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(User.objects.filter(email="laura@correo.co").count(), 1)

    def test_menor_de_edad_no_puede_registrar_perfil(self):
        usuario = self.crear_usuario(perfil=False)
        self.entrar(usuario)
        hoy = timezone.localdate()
        perfil = self.perfil_base(fecha_nacimiento=hoy.replace(year=hoy.year - 16))
        perfil = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in perfil.items()}
        r = self.client.post(reverse("registro_perfil"), perfil)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(hasattr(User.objects.get(pk=usuario.pk), "perfil"))


class IngresoYBloqueoTests(BaseNutri):
    def test_ingreso_con_correo(self):
        self.crear_usuario("ana@prueba.co")
        r = self.client.post(reverse("login"), {"username": "ANA@prueba.co", "password": CLAVE})
        self.assertRedirects(r, reverse("inicio"), fetch_redirect_response=False)
        self.assertTrue(Bitacora.objects.filter(accion="ingreso").exists())

    def test_cinco_intentos_fallidos_bloquean_la_cuenta(self):
        usuario = self.crear_usuario("ana@prueba.co")
        for _ in range(5):
            self.client.post(reverse("login"), {"username": "ana@prueba.co", "password": "equivocada"})
        usuario.cuenta.refresh_from_db()
        self.assertTrue(usuario.cuenta.esta_bloqueada)
        r = self.client.post(reverse("login"), {"username": "ana@prueba.co", "password": CLAVE})
        self.assertContains(r, "bloqueada temporalmente")

    def test_recuperacion_de_contrasena_envia_enlace(self):
        self.crear_usuario("ana@prueba.co")
        self.client.post(reverse("password_reset"), {"email": "ana@prueba.co"})
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/cuentas/reset/", mail.outbox[0].body)

    def test_cerrar_sesion_en_todos_los_dispositivos(self):
        usuario = self.crear_usuario()
        otro_dispositivo = self.client_class()
        otro_dispositivo.force_login(usuario)
        self.entrar(usuario)
        self.client.post(reverse("cerrar_sesiones"))
        self.assertRedirects(otro_dispositivo.get(reverse("panel")), f"{reverse('login')}?next=/panel/")

    def test_aviso_medico_visible_sin_sesion(self):
        r = self.client.get(reverse("aviso_medico"))
        self.assertContains(r, "no es un servicio médico", status_code=200)


class AdministracionDeCuentasTests(BaseNutri):
    def test_bloquear_cuenta_cierra_su_sesion(self):
        admin = self.crear_admin()
        usuario = self.crear_usuario()
        sesion_usuario = self.client_class()
        sesion_usuario.force_login(usuario)
        self.entrar(admin).post(reverse("cuenta_estado", args=[usuario.cuenta.pk]), {"estado": "bloqueado"})
        usuario.cuenta.refresh_from_db()
        self.assertEqual(usuario.cuenta.estado, EstadoCuenta.BLOQUEADO)
        self.assertEqual(sesion_usuario.get(reverse("panel")).status_code, 302)
        self.assertTrue(Bitacora.objects.filter(accion="cuenta_estado").exists())

    def test_admin_no_cambia_su_propia_cuenta(self):
        admin = self.crear_admin()
        with self.assertRaises(cuentas.OperacionNoPermitida):
            cuentas.cambiar_estado(admin.cuenta, EstadoCuenta.BLOQUEADO, administrador=admin)

    def test_el_rol_no_se_puede_cambiar(self):
        usuario = self.crear_usuario()
        usuario.cuenta.rol = Rol.ADMINISTRADOR
        with self.assertRaises(Exception):
            usuario.cuenta.save()

    def test_solo_admin_crea_cuentas_internas(self):
        usuario = self.crear_usuario()
        self.assertEqual(self.entrar(usuario).get(reverse("cuenta_interna_nueva")).status_code, 403)
        admin = self.crear_admin()
        self.entrar(admin).post(reverse("cuenta_interna_nueva"), {
            "correo": "cura@prueba.co", "nombres": "Cura", "apellidos": "Dor", "rol": Rol.CURADOR, "password": CLAVE,
        })
        self.assertEqual(User.objects.get(email="cura@prueba.co").cuenta.rol, Rol.CURADOR)

    def test_soporte_requiere_autorizacion_del_titular(self):
        admin = self.crear_admin()
        usuario = self.crear_usuario()
        self.entrar(admin)
        self.assertEqual(self.client.get(reverse("cuenta_soporte", args=[usuario.cuenta.pk])).status_code, 302)
        cuentas.autorizar_soporte(usuario, 24)
        r = self.client.get(reverse("cuenta_soporte", args=[usuario.cuenta.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(Bitacora.objects.filter(accion="acceso_soporte").exists())


class EdicionYSupresionTests(BaseNutri):
    def test_editar_datos_de_contacto(self):
        usuario = self.crear_usuario()
        self.entrar(usuario).post(reverse("cuenta"), {"first_name": "Ana María", "last_name": "Prueba",
                                                       "email": "ana@prueba.co"})
        usuario.refresh_from_db()
        self.assertEqual(usuario.first_name, "Ana María")

    def test_retirar_autorizacion_de_ia_queda_en_historial(self):
        usuario = self.crear_usuario(acepta_ia=True)
        self.entrar(usuario).post(reverse("privacidad"), {"accion": "ia"})
        usuario.cuenta.refresh_from_db()
        self.assertFalse(usuario.cuenta.acepta_ia)
        self.assertEqual(Consentimiento.objects.filter(usuario=usuario, tipo=TipoConsentimiento.IA).count(), 2)

    def test_los_consentimientos_no_se_modifican(self):
        usuario = self.crear_usuario()
        registro = Consentimiento.objects.filter(usuario=usuario).first()
        registro.otorgado = not registro.otorgado
        with self.assertRaises(Exception):
            registro.save()

    def test_eliminar_cuenta_suprime_los_datos(self):
        usuario = self.crear_usuario()
        self.entrar(usuario).post(reverse("eliminar_cuenta"), {"confirmacion": "ELIMINAR"})
        usuario.refresh_from_db()
        self.assertFalse(usuario.is_active)
        self.assertEqual(usuario.email, "")
        self.assertFalse(MetaCalorica.objects.filter(usuario=usuario).exists())
        self.assertFalse(hasattr(User.objects.get(pk=usuario.pk), "perfil"))

    def test_cuentas_internas_no_se_eliminan(self):
        with self.assertRaises(cuentas.OperacionNoPermitida):
            cuentas.eliminar_cuenta(self.crear_curador())

    def test_exportar_mis_datos(self):
        usuario = self.crear_usuario()
        r = self.entrar(usuario).get(reverse("exportar_datos"))
        self.assertEqual(r.status_code, 200)
        self.assertIn("perfil", r.json())

    def test_sesion_expira_por_inactividad(self):
        from django.conf import settings

        self.assertEqual(settings.SESSION_COOKIE_AGE, 60 * 60)
        self.assertTrue(settings.SESSION_SAVE_EVERY_REQUEST)
        self.assertLessEqual(settings.PASSWORD_RESET_TIMEOUT, timedelta(hours=2).total_seconds())
