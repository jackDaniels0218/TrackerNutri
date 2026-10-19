"""
Pruebas de las páginas web.

Cubre los escenarios 1, 2, 3, 9, 14 y 15 de la lista obligatoria.

Son pruebas de integración: usan el cliente de pruebas de Django, que recorre
el mismo camino que un navegador (URL, vista, formulario, base de datos y
plantilla).
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import (
    Alimento,
    MetodoPreparacion,
    OrigenRegistro,
    PerfilNutricional,
    RegistroComida,
    Unidad,
)
from core.services.comidas import guardar_comida

CLAVE = "clave-de-prueba-123"


class RegistroEInicioDeSesionTests(TestCase):
    """Escenario 1."""

    def test_se_puede_crear_una_cuenta(self):
        respuesta = self.client.post(
            reverse("registro"),
            {
                "username": "nuevo",
                "email": "nuevo@ejemplo.com",
                "password1": CLAVE,
                "password2": CLAVE,
            },
        )
        self.assertRedirects(respuesta, reverse("panel"))
        self.assertTrue(User.objects.filter(username="nuevo").exists())

    def test_al_crear_la_cuenta_se_crea_el_perfil(self):
        self.client.post(
            reverse("registro"),
            {"username": "nuevo", "password1": CLAVE, "password2": CLAVE},
        )
        usuario = User.objects.get(username="nuevo")
        self.assertTrue(PerfilNutricional.objects.filter(usuario=usuario).exists())
        self.assertEqual(usuario.perfil.meta_calorias_diaria, 2000)

    def test_no_se_crea_la_cuenta_si_las_contrasenas_no_coinciden(self):
        self.client.post(
            reverse("registro"),
            {"username": "nuevo", "password1": CLAVE, "password2": "otra-cosa-999"},
        )
        self.assertFalse(User.objects.filter(username="nuevo").exists())

    def test_inicio_de_sesion(self):
        User.objects.create_user("ana", password=CLAVE)
        respuesta = self.client.post(
            reverse("login"), {"username": "ana", "password": CLAVE}
        )
        self.assertRedirects(respuesta, reverse("panel"))

    def test_inicio_de_sesion_con_clave_incorrecta(self):
        User.objects.create_user("ana", password=CLAVE)
        respuesta = self.client.post(
            reverse("login"), {"username": "ana", "password": "incorrecta"}
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(respuesta.wsgi_request.user.is_authenticated)

    def test_cierre_de_sesion(self):
        User.objects.create_user("ana", password=CLAVE)
        self.client.login(username="ana", password=CLAVE)
        respuesta = self.client.post(reverse("logout"))
        self.assertRedirects(respuesta, reverse("login"))


class AccesoAPaginasPrivadasTests(TestCase):
    """Escenario 2: sin sesión no se entra a ninguna página privada."""

    RUTAS = ["panel", "perfil", "nueva_comida", "comida_manual", "historial"]

    def test_sin_sesion_redirige_al_login(self):
        for nombre in self.RUTAS:
            with self.subTest(ruta=nombre):
                respuesta = self.client.get(reverse(nombre))
                self.assertEqual(respuesta.status_code, 302)
                self.assertIn(reverse("login"), respuesta.url)

    def test_con_sesion_se_accede(self):
        User.objects.create_user("ana", password=CLAVE)
        self.client.login(username="ana", password=CLAVE)
        for nombre in self.RUTAS:
            with self.subTest(ruta=nombre):
                self.assertEqual(self.client.get(reverse(nombre)).status_code, 200)


class BaseConComidas(TestCase):
    """Datos compartidos por las pruebas que necesitan comidas guardadas."""

    fixtures = ["catalogo_alimentos.json"]

    def setUp(self):
        self.ana = User.objects.create_user("ana", password=CLAVE)
        self.luis = User.objects.create_user("luis", password=CLAVE)
        self.hoy = timezone.localdate()
        self.arroz = Alimento.objects.get(nombre="Arroz blanco")

    def _comida_de(self, usuario, descripcion="Almuerzo", cantidad=150):
        return guardar_comida(
            usuario,
            descripcion=descripcion,
            fecha=self.hoy,
            filas=[
                {
                    "alimento": self.arroz,
                    "nombre_mostrado": "Arroz blanco",
                    "cantidad": Decimal(cantidad),
                    "unidad": Unidad.GRAMOS,
                    "metodo_preparacion": MetodoPreparacion.COCIDO,
                }
            ],
        )


class SeparacionEntreUsuariosTests(BaseConComidas):
    """
    Escenario 3: lo de cada quien es suyo.

    Es la prueba de seguridad más importante del proyecto: un usuario no puede
    ver, editar ni borrar las comidas de otro.
    """

    def test_el_panel_solo_muestra_lo_propio(self):
        self._comida_de(self.ana, "Almuerzo de Ana")
        self.client.login(username="luis", password=CLAVE)
        respuesta = self.client.get(reverse("panel"))
        self.assertNotContains(respuesta, "Almuerzo de Ana")

    def test_el_historial_solo_muestra_lo_propio(self):
        self._comida_de(self.ana, "Almuerzo de Ana")
        self.client.login(username="luis", password=CLAVE)
        respuesta = self.client.get(reverse("historial"))
        self.assertNotContains(respuesta, "Almuerzo de Ana")

    def test_no_se_puede_ver_la_comida_de_otro(self):
        comida = self._comida_de(self.ana)
        self.client.login(username="luis", password=CLAVE)
        respuesta = self.client.get(reverse("detalle_comida", args=[comida.pk]))
        self.assertEqual(respuesta.status_code, 404)

    def test_no_se_puede_editar_la_comida_de_otro(self):
        comida = self._comida_de(self.ana)
        self.client.login(username="luis", password=CLAVE)
        respuesta = self.client.get(reverse("editar_comida", args=[comida.pk]))
        self.assertEqual(respuesta.status_code, 404)

    def test_no_se_puede_eliminar_la_comida_de_otro(self):
        comida = self._comida_de(self.ana)
        self.client.login(username="luis", password=CLAVE)
        respuesta = self.client.post(reverse("eliminar_comida", args=[comida.pk]))
        self.assertEqual(respuesta.status_code, 404)
        self.assertTrue(RegistroComida.objects.filter(pk=comida.pk).exists())

    def test_el_resumen_de_cada_usuario_es_independiente(self):
        self._comida_de(self.ana, cantidad=150)
        self.client.login(username="luis", password=CLAVE)
        respuesta = self.client.get(reverse("panel"))
        self.assertEqual(respuesta.context["resumen"]["consumido"], Decimal("0.0"))


class RegistroManualTests(BaseConComidas):
    """Escenario 14: el camino que funciona siempre, sin IA."""

    def setUp(self):
        super().setUp()
        self.client.login(username="ana", password=CLAVE)

    def _datos(self, cantidad="150", alimento=None):
        return {
            "descripcion": "Almuerzo",
            "fecha": self.hoy.isoformat(),
            "hora": "13:00",
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-alimento": str(alimento if alimento is not None else self.arroz.pk),
            "form-0-nombre_mostrado": "Arroz blanco",
            "form-0-cantidad": cantidad,
            "form-0-unidad": Unidad.GRAMOS,
            "form-0-metodo_preparacion": MetodoPreparacion.COCIDO,
        }

    def test_se_guarda_una_comida_manual(self):
        respuesta = self.client.post(reverse("comida_manual"), self._datos())
        self.assertEqual(respuesta.status_code, 302)

        comida = RegistroComida.objects.get(usuario=self.ana)
        self.assertEqual(comida.origen, OrigenRegistro.MANUAL)
        self.assertTrue(comida.confirmado)

        detalle = comida.detalles.get()
        # 130 kcal/100 g x 150 g = 195 kcal
        self.assertEqual(detalle.calorias, Decimal("195.0"))

    def test_rechaza_una_cantidad_negativa(self):
        """Escenario 10, ahora desde la interfaz."""
        respuesta = self.client.post(reverse("comida_manual"), self._datos(cantidad="-5"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(RegistroComida.objects.exists())

    def test_rechaza_una_cantidad_cero(self):
        respuesta = self.client.post(reverse("comida_manual"), self._datos(cantidad="0"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(RegistroComida.objects.exists())

    def test_un_alimento_fuera_del_catalogo_se_guarda_sin_valores(self):
        """Escenario 11 desde la interfaz: no se inventan calorías."""
        datos = self._datos(alimento="")
        datos["form-0-nombre_mostrado"] = "Sushi"
        respuesta = self.client.post(reverse("comida_manual"), datos)
        self.assertEqual(respuesta.status_code, 302)

        detalle = RegistroComida.objects.get().detalles.get()
        self.assertIsNone(detalle.calorias)
        self.assertTrue(detalle.necesita_confirmacion)
        self.assertIn("catálogo", detalle.observacion)


class CicloDeVidaDeComidasTests(BaseConComidas):
    """Escenario 9: crear, modificar y eliminar."""

    def setUp(self):
        super().setUp()
        self.client.login(username="ana", password=CLAVE)
        self.comida = self._comida_de(self.ana, "Almuerzo", cantidad=150)

    def test_ver_el_detalle(self):
        respuesta = self.client.get(reverse("detalle_comida", args=[self.comida.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Arroz blanco")

    def test_editar_recalcula_los_valores(self):
        datos = {
            "descripcion": "Almuerzo corregido",
            "fecha": self.hoy.isoformat(),
            "hora": "",
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-alimento": str(self.arroz.pk),
            "form-0-nombre_mostrado": "Arroz blanco",
            "form-0-cantidad": "300",
            "form-0-unidad": Unidad.GRAMOS,
            "form-0-metodo_preparacion": MetodoPreparacion.COCIDO,
        }
        respuesta = self.client.post(
            reverse("editar_comida", args=[self.comida.pk]), datos
        )
        self.assertEqual(respuesta.status_code, 302)

        self.comida.refresh_from_db()
        self.assertEqual(self.comida.descripcion, "Almuerzo corregido")
        # 130 kcal/100 g x 300 g = 390 kcal
        self.assertEqual(self.comida.detalles.get().calorias, Decimal("390.0"))

    def test_eliminar_pide_confirmacion_antes(self):
        """Un GET muestra la confirmación; no borra nada."""
        respuesta = self.client.get(reverse("eliminar_comida", args=[self.comida.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(RegistroComida.objects.filter(pk=self.comida.pk).exists())

    def test_eliminar_con_post_borra_la_comida_y_sus_detalles(self):
        respuesta = self.client.post(reverse("eliminar_comida", args=[self.comida.pk]))
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(RegistroComida.objects.filter(pk=self.comida.pk).exists())
        self.assertEqual(self.comida.detalles.count(), 0)

    def test_el_panel_refleja_el_total(self):
        respuesta = self.client.get(reverse("panel"))
        self.assertEqual(respuesta.context["resumen"]["consumido"], Decimal("195.0"))


class DatosDeLosGraficosTests(BaseConComidas):
    """
    Los gráficos se alimentan de datos reales y con la forma que espera
    Chart.js.

    La comprobación de que `datos_grafico` es un diccionario (y no una cadena)
    es una prueba de regresión: al serializarlo con json.dumps en la vista, el
    filtro json_script lo codificaba por segunda vez y el JavaScript recibía
    texto en lugar de un objeto, así que los gráficos salían en blanco.
    """

    def setUp(self):
        super().setUp()
        self.client.login(username="ana", password=CLAVE)
        self._comida_de(self.ana, cantidad=150)

    def test_los_datos_se_pasan_como_diccionario(self):
        datos = self.client.get(reverse("panel")).context["datos_grafico"]
        self.assertIsInstance(datos, dict)
        self.assertIn("tendencia", datos)
        self.assertIn("macros", datos)

    def test_la_tendencia_cubre_siete_dias_y_termina_en_la_fecha_vista(self):
        datos = self.client.get(reverse("panel")).context["datos_grafico"]
        etiquetas = datos["tendencia"]["etiquetas"]
        self.assertEqual(len(etiquetas), 7)
        self.assertEqual(etiquetas[-1], self.hoy.isoformat())
        self.assertEqual(datos["tendencia"]["valores"][-1], 195.0)

    def test_los_macros_reflejan_lo_consumido(self):
        datos = self.client.get(reverse("panel")).context["datos_grafico"]
        # 150 g de arroz: 2.7 g de proteína/100 g -> 4.1 g (redondeado).
        self.assertEqual(datos["macros"]["valores"][0], 4.1)

    def test_el_grafico_de_otro_usuario_no_se_mezcla(self):
        self._comida_de(self.luis, cantidad=300)
        datos = self.client.get(reverse("panel")).context["datos_grafico"]
        self.assertEqual(datos["tendencia"]["valores"][-1], 195.0)


class EstadosVaciosTests(TestCase):
    """Escenario 15: historial y panel sin datos, sin inventar nada."""

    def setUp(self):
        User.objects.create_user("ana", password=CLAVE)
        self.client.login(username="ana", password=CLAVE)

    def test_historial_vacio(self):
        respuesta = self.client.get(reverse("historial"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(respuesta.context["tiene_registros"])
        self.assertContains(respuesta, "Tu historial está vacío")

    def test_panel_vacio_no_muestra_datos_ficticios(self):
        respuesta = self.client.get(reverse("panel"))
        self.assertFalse(respuesta.context["tiene_registros"])
        self.assertEqual(respuesta.context["resumen"]["consumido"], Decimal("0.0"))
        self.assertContains(respuesta, "Todavía no has registrado nada")


class PerfilTests(TestCase):
    """La meta diaria se puede configurar y se valida."""

    def setUp(self):
        self.ana = User.objects.create_user("ana", password=CLAVE)
        self.client.login(username="ana", password=CLAVE)

    def test_cambiar_la_meta(self):
        respuesta = self.client.post(
            reverse("perfil"), {"meta_calorias_diaria": "2500", "edad": "", "peso_kg": "", "estatura_cm": ""}
        )
        self.assertEqual(respuesta.status_code, 302)
        self.ana.perfil.refresh_from_db()
        self.assertEqual(self.ana.perfil.meta_calorias_diaria, 2500)

    def test_rechaza_una_meta_absurda(self):
        self.client.post(
            reverse("perfil"), {"meta_calorias_diaria": "50", "edad": "", "peso_kg": "", "estatura_cm": ""}
        )
        self.ana.perfil.refresh_from_db()
        self.assertEqual(self.ana.perfil.meta_calorias_diaria, 2000)


class SeleccionDeFechaTests(BaseConComidas):
    """El panel permite moverse entre días sin romperse con entradas raras."""

    def setUp(self):
        super().setUp()
        self.client.login(username="ana", password=CLAVE)

    def test_una_fecha_invalida_no_rompe_el_panel(self):
        respuesta = self.client.get(reverse("panel"), {"fecha": "no-es-una-fecha"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["fecha"], self.hoy)
