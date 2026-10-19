"""
Pruebas de la normalización y el emparejamiento con el catálogo.

Trabaja sobre el catálogo real (fixture catalogo_alimentos.json) porque lo que
se está comprobando es precisamente que los sinónimos del parser coincidan con
los nombres que hay cargados.
"""

from django.test import TestCase

from core.models import MetodoPreparacion, Unidad
from core.services.food_parser import (
    buscar_alimento,
    normalizar_item,
    normalizar_nombre,
    normalizar_preparacion,
    normalizar_texto,
    normalizar_unidad,
)


class NormalizacionTextoTests(TestCase):
    """Funciones puras: no tocan la base de datos."""

    def test_quita_tildes_y_mayusculas(self):
        self.assertEqual(normalizar_texto("Plátano Maduro"), "platano maduro")

    def test_texto_vacio(self):
        self.assertEqual(normalizar_texto(None), "")

    def test_unidades_equivalentes(self):
        self.assertEqual(normalizar_unidad("gramos"), Unidad.GRAMOS)
        self.assertEqual(normalizar_unidad("gr"), Unidad.GRAMOS)
        self.assertEqual(normalizar_unidad("ML"), Unidad.MILILITROS)
        self.assertEqual(normalizar_unidad("unidades"), Unidad.UNIDAD)

    def test_unidad_desconocida_no_se_convierte_en_gramos(self):
        """Confundir una unidad con gramos es uno de los errores prohibidos."""
        self.assertNotEqual(normalizar_unidad("puñado"), Unidad.GRAMOS)

    def test_preparaciones(self):
        self.assertEqual(normalizar_preparacion("frita"), MetodoPreparacion.FRITO)
        self.assertEqual(normalizar_preparacion("Asada"), MetodoPreparacion.ASADO)
        self.assertEqual(normalizar_preparacion("hervida"), MetodoPreparacion.COCIDO)
        self.assertEqual(normalizar_preparacion("a la plancha"), MetodoPreparacion.ASADO)

    def test_preparacion_desconocida_queda_sin_especificar(self):
        self.assertEqual(
            normalizar_preparacion("al vapor con limón"),
            MetodoPreparacion.NO_ESPECIFICADA,
        )

    def test_sinonimos_de_alimento(self):
        self.assertEqual(normalizar_nombre("Coca-Cola"), "gaseosa azucarada")
        self.assertEqual(normalizar_nombre("arepa frita"), "arepa de maiz")


class BusquedaEnCatalogoTests(TestCase):
    """Emparejamiento contra el catálogo cargado."""

    fixtures = ["catalogo_alimentos.json"]

    def test_la_preparacion_decide_la_ficha(self):
        """Arepa frita y arepa asada deben dar fichas distintas."""
        frita = buscar_alimento("arepa", "frita")
        asada = buscar_alimento("arepa", "asada")
        self.assertIsNotNone(frita)
        self.assertIsNotNone(asada)
        self.assertNotEqual(frita.pk, asada.pk)
        self.assertEqual(frita.metodo_preparacion, MetodoPreparacion.FRITO)
        self.assertGreater(frita.calorias, asada.calorias)

    def test_carne_frita_y_asada_son_distintas(self):
        self.assertNotEqual(
            buscar_alimento("carne de res", "frita").pk,
            buscar_alimento("carne de res", "asada").pk,
        )

    def test_una_marca_se_resuelve_al_alimento_generico(self):
        alimento = buscar_alimento("Coca-Cola")
        self.assertIsNotNone(alimento)
        self.assertEqual(alimento.nombre, "Gaseosa azucarada")

    def test_alimento_inexistente_devuelve_none(self):
        self.assertIsNone(buscar_alimento("sushi de atún"))

    def test_nombre_vacio_devuelve_none(self):
        self.assertIsNone(buscar_alimento(""))

    def test_la_preparacion_incrustada_en_el_nombre_se_detecta(self):
        alimento = buscar_alimento("arepa frita")
        self.assertEqual(alimento.metodo_preparacion, MetodoPreparacion.FRITO)


class NormalizacionDeItemsTests(TestCase):
    """Traducción del JSON de la IA al vocabulario del proyecto."""

    fixtures = ["catalogo_alimentos.json"]

    def test_item_completo(self):
        item = normalizar_item(
            {
                "name": "arepa",
                "quantity": 1,
                "unit": "unidad",
                "preparation": "frita",
                "needs_confirmation": True,
            }
        )
        self.assertEqual(item["unidad"], Unidad.UNIDAD)
        self.assertEqual(item["metodo_preparacion"], MetodoPreparacion.FRITO)
        self.assertIsNotNone(item["alimento_id"])
        self.assertTrue(item["necesita_confirmacion"])

    def test_item_sin_coincidencia_queda_sin_alimento(self):
        item = normalizar_item({"name": "ramen", "quantity": 1, "unit": "unidad"})
        self.assertIsNone(item["alimento_id"])

    def test_preparacion_no_dicha_pide_confirmacion(self):
        """
        Si el usuario no dijo cómo estaba preparado y el catálogo solo tiene
        versiones preparadas, el sistema eligió por él: hay que avisarle.
        """
        item = normalizar_item({"name": "huevo", "quantity": 2, "unit": "unidad"})
        self.assertTrue(item["necesita_confirmacion"])

    def test_bebida_en_mililitros(self):
        item = normalizar_item(
            {"name": "Coca-Cola", "quantity": 400, "unit": "ml"}
        )
        self.assertEqual(item["unidad"], Unidad.MILILITROS)
        self.assertEqual(item["cantidad"], 400)
