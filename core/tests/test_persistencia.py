"""
Escenario 17: los registros sobreviven al reinicio del servidor.

Lo que se comprueba de verdad es que los datos están en SQLite y no en memoria
ni en la sesión: se cierra la conexión a la base de datos (que es lo que ocurre
cuando el proceso de Django muere), se abre una nueva y se vuelve a consultar.

Se usa TransactionTestCase en lugar de TestCase porque TestCase envuelve cada
prueba en una transacción que se revierte, lo que impediría ver el efecto real
de cerrar la conexión.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.db import connection
from django.test import TransactionTestCase
from django.utils import timezone

from core.models import Alimento, MetodoPreparacion, RegistroComida, Unidad
from core.services.comidas import guardar_comida
from core.services.nutrition import resumen_diario


class PersistenciaTrasReinicioTests(TransactionTestCase):
    fixtures = ["catalogo_alimentos.json"]

    def test_la_comida_sigue_ahi_despues_de_cerrar_la_conexion(self):
        usuario = User.objects.create_user("ana", password="clave-de-prueba-123")
        arroz = Alimento.objects.get(nombre="Arroz blanco")
        hoy = timezone.localdate()

        comida = guardar_comida(
            usuario,
            descripcion="Almuerzo",
            fecha=hoy,
            filas=[
                {
                    "alimento": arroz,
                    "nombre_mostrado": "Arroz blanco",
                    "cantidad": Decimal("150"),
                    "unidad": Unidad.GRAMOS,
                    "metodo_preparacion": MetodoPreparacion.COCIDO,
                }
            ],
        )
        pk = comida.pk

        # Simula el reinicio: se cierra la conexión y se abre otra nueva.
        connection.close()

        recuperada = RegistroComida.objects.get(pk=pk)
        self.assertEqual(recuperada.descripcion, "Almuerzo")
        self.assertEqual(recuperada.detalles.count(), 1)
        self.assertEqual(recuperada.detalles.get().calorias, Decimal("195.0"))

        resumen = resumen_diario(usuario, hoy)
        self.assertEqual(resumen["consumido"], Decimal("195.0"))

    def test_la_instantanea_sobrevive_a_un_cambio_del_catalogo(self):
        """
        Si mañana se corrige la ficha del arroz, el historial no debe cambiar
        solo: el detalle guarda los valores que se aplicaron en su momento.
        """
        usuario = User.objects.create_user("luis", password="clave-de-prueba-123")
        arroz = Alimento.objects.get(nombre="Arroz blanco")

        comida = guardar_comida(
            usuario,
            descripcion="Almuerzo",
            fecha=timezone.localdate(),
            filas=[
                {
                    "alimento": arroz,
                    "nombre_mostrado": "Arroz blanco",
                    "cantidad": Decimal("100"),
                    "unidad": Unidad.GRAMOS,
                    "metodo_preparacion": MetodoPreparacion.COCIDO,
                }
            ],
        )
        calorias_originales = comida.detalles.get().calorias

        # Alguien corrige el catálogo.
        arroz.calorias = Decimal("500")
        arroz.save()
        connection.close()

        detalle = RegistroComida.objects.get(pk=comida.pk).detalles.get()
        self.assertEqual(detalle.calorias, calorias_originales)
        self.assertEqual(detalle.calorias_ref, Decimal("130.00"))

    def test_el_catalogo_cargado_persiste(self):
        """El fixture queda realmente escrito en la base de datos."""
        total = Alimento.objects.count()
        connection.close()
        self.assertEqual(Alimento.objects.count(), total)
        self.assertGreaterEqual(total, 20)
