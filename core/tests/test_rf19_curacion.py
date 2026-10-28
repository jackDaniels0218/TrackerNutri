"""RF19 (Curación del catálogo y mejora continua)."""

from decimal import Decimal

from django.urls import reverse

from core.datos.frases import FRASES
from core.models import (
    Alimento,
    EjecucionExactitud,
    FraseReferencia,
    HistorialCatalogo,
    TerminoLexico,
    TerminoPendiente,
    VersionCatalogo,
)
from core.services import curacion
from core.services.interpretacion import interpretar

from .base import BaseNutri


class BandejaTests(BaseNutri):
    def test_bandeja_muestra_terminos_por_frecuencia(self):
        for _ in range(3):
            interpretar("un vaso de borojo", permitir_ia=False)
        interpretar("un plato de xqzwv", permitir_ia=False)
        terminos = list(curacion.bandeja()["terminos"])
        self.assertGreaterEqual(terminos[0].veces, 3)
        r = self.entrar(self.crear_curador()).get(reverse("curacion"))
        self.assertContains(r, "borojo")

    def test_resolver_termino_desde_la_bandeja(self):
        interpretar("un vaso de borojo", permitir_ia=False)
        pendiente = TerminoPendiente.objects.get(termino__contains="borojo")
        self.entrar(self.crear_curador()).post(reverse("termino_resolver", args=[pendiente.pk]),
                                               {"destino": "Jugo de naranja natural"})
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estado, TerminoPendiente.Estado.RESUELTO)
        self.assertTrue(TerminoLexico.objects.filter(termino=pendiente.termino).exists())
        # Cada cambio queda en la versión en borrador.
        self.assertTrue(HistorialCatalogo.objects.filter(version__estado=VersionCatalogo.Estado.BORRADOR).exists())

    def test_usuario_no_entra_a_la_bandeja(self):
        self.assertEqual(self.entrar(self.crear_usuario()).get(reverse("curacion")).status_code, 403)


class VersionesYExactitudTests(BaseNutri):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        FraseReferencia.objects.bulk_create(
            [FraseReferencia(texto=f["texto"], componentes_esperados=f["componentes"]) for f in FRASES]
        )

    def test_publicar_version_ejecuta_el_conjunto_de_prueba(self):
        curador = self.crear_curador()
        lulo = Alimento.objects.get(nombre="Lulo")
        antes = curacion.instantanea(lulo)
        lulo.fuente_detalle = "Verificado"
        lulo.save()
        curacion.registrar_cambio(lulo, "Edición de prueba", antes, curador)
        borrador = VersionCatalogo.objects.get(estado=VersionCatalogo.Estado.BORRADOR)
        self.entrar(curador).post(reverse("version_publicar"), {"notas": "Versión de prueba"})
        borrador.refresh_from_db()
        self.assertEqual(borrador.estado, VersionCatalogo.Estado.PUBLICADA)
        self.assertTrue(EjecucionExactitud.objects.filter(version=borrador, aprobada=True).exists())

    def test_publicacion_bloqueada_si_baja_la_exactitud(self):
        curador = self.crear_curador()
        curacion.ejecutar_exactitud(self.version)  # línea base aprobada de la versión publicada
        # Se rompe el léxico: el término "arepa" deja de existir.
        TerminoLexico.objects.filter(termino__startswith="arepa").delete()
        borrador = VersionCatalogo.borrador()
        ejecucion = curacion.publicar_version(borrador, curador)
        self.assertFalse(ejecucion.aprobada)
        borrador.refresh_from_db()
        self.assertEqual(borrador.estado, VersionCatalogo.Estado.BORRADOR)

    def test_revertir_un_cambio(self):
        curador = self.crear_curador()
        lulo = Alimento.objects.get(nombre="Lulo")
        kcal_original = lulo.kcal
        antes = curacion.instantanea(lulo)
        lulo.kcal = lulo.kcal + Decimal("1")
        lulo.save()
        cambio = curacion.registrar_cambio(lulo, "Edición de prueba", antes, curador)
        self.entrar(curador).post(reverse("cambio_revertir", args=[cambio.pk]))
        lulo.refresh_from_db()
        self.assertEqual(lulo.kcal, kcal_original)

    def test_pantalla_de_exactitud(self):
        curador = self.crear_curador()
        self.entrar(curador).post(reverse("exactitud_ejecutar"))
        r = self.client.get(reverse("exactitud"))
        self.assertContains(r, "%")

    def test_validar_registro_contra_la_fuente(self):
        curador = self.crear_curador()
        lulo = Alimento.objects.get(nombre="Lulo")
        self.entrar(curador).post(reverse("catalogo_verificar", args=["alimento", lulo.pk]))
        lulo.refresh_from_db()
        self.assertTrue(lulo.verificado)

    def test_indicadores_agregados(self):
        r = self.entrar(self.crear_curador()).get(reverse("indicadores"))
        self.assertEqual(r.status_code, 200)
