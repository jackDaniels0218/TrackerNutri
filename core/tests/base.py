"""
Base común de las pruebas: parámetros y catálogo inicial cargados una vez
por clase, y ayudas para crear cuentas con su perfil.

La IA externa queda apagada (sin clave): las pruebas nunca llaman a la red.
Las que prueban la integración sustituyen el proveedor por uno simulado.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import Cuenta, Rol, VersionCatalogo
from core.services import cuentas
from core.services.catalogo import cargar_catalogo_inicial
from core.services.parametros import limpiar_cache, sembrar_parametros

CLAVE = "ClaveSegura2026"


@override_settings(OPENAI_API_KEY="")
class BaseNutri(TestCase):
    @classmethod
    def setUpTestData(cls):
        limpiar_cache()
        sembrar_parametros()
        cls.version = VersionCatalogo.objects.create(
            numero=1, estado=VersionCatalogo.Estado.PUBLICADA, publicada_en=timezone.now()
        )
        cargar_catalogo_inicial(cls.version)

    def setUp(self):
        limpiar_cache()

    # --- Ayudas ---------------------------------------------------------------------

    @staticmethod
    def perfil_base(**cambios) -> dict:
        hoy = timezone.localdate()
        datos = {
            "fecha_nacimiento": date(hoy.year - 30, 1, 15), "sexo": "femenino", "estatura_cm": 165,
            "peso_inicial_kg": Decimal("70.0"), "fecha_peso_inicial": hoy - timedelta(days=21),
            "nivel_actividad": "ligero", "objetivo": "perder", "peso_meta_kg": Decimal("60.0"), "ritmo": "moderado",
        }
        datos.update(cambios)
        return datos

    def crear_usuario(self, correo="ana@prueba.co", *, perfil=True, acepta_ia=False, **cambios_perfil):
        usuario = cuentas.crear_usuario(correo=correo, password=CLAVE, nombres="Ana", apellidos="Prueba",
                                        acepta_datos=True, acepta_ia=acepta_ia)
        if perfil:
            cuentas.guardar_perfil(usuario, self.perfil_base(**cambios_perfil))
            cuentas.avanzar_registro(usuario, Cuenta.REGISTRO_COMPLETO)
        usuario.refresh_from_db()
        return usuario

    def crear_interno(self, rol, correo=None):
        correo = correo or f"{rol}@prueba.co"
        return cuentas.crear_usuario(correo=correo, password=CLAVE, nombres=rol.title(), apellidos="Prueba",
                                     rol=rol, acepta_datos=True)

    def crear_curador(self):
        return self.crear_interno(Rol.CURADOR)

    def crear_admin(self):
        return self.crear_interno(Rol.ADMINISTRADOR)

    def entrar(self, usuario):
        self.client.force_login(usuario)
        return self.client
