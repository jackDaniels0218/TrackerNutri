"""
Pruebas del motor de cálculo nutricional.

Cubre los escenarios 4, 5, 6, 7, 8, 10, 11 y 16 de la lista de pruebas
obligatorias del enunciado.

Se usan alimentos creados dentro de la prueba (no el catálogo real) para que
los números esperados estén a la vista y la prueba no dependa de que alguien
corrija una ficha del fixture.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from core.models import (
    Alimento,
    DetalleComida,
    MetodoPreparacion,
    RegistroComida,
    Unidad,
    UnidadReferencia,
)
from core.services.nutrition import (
    CantidadInvalida,
    calcular,
    convertir_a_base,
    redondear,
    resumen_diario,
    sumar_detalles,
    validar_cantidad,
)


class CreacionDeAlimentosTests(TestCase):
    """Escenario 4: crear alimentos en el catálogo."""

    def test_se_crea_un_alimento_con_sus_valores(self):
        alimento = Alimento.objects.create(
            nombre="Alimento de prueba",
            categoria="Pruebas",
            calorias=Decimal("200"),
            proteinas=Decimal("10"),
            carbohidratos=Decimal("20"),
            grasas=Decimal("5"),
            fuente="Valores inventados para la prueba",
        )
        self.assertEqual(Alimento.objects.count(), 1)
        self.assertEqual(alimento.unidad_referencia, UnidadReferencia.GRAMOS_100)
        self.assertTrue(alimento.valores_aproximados)

    def test_un_alimento_puede_repetirse_si_cambia_la_preparacion(self):
        """Arepa asada y arepa frita son dos fichas distintas y válidas."""
        comunes = dict(
            nombre="Arepa",
            categoria="Cereales",
            calorias=Decimal("180"),
            proteinas=Decimal("4"),
            carbohidratos=Decimal("38"),
            grasas=Decimal("1.5"),
            fuente="Prueba",
        )
        Alimento.objects.create(metodo_preparacion=MetodoPreparacion.ASADO, **comunes)
        Alimento.objects.create(metodo_preparacion=MetodoPreparacion.FRITO, **comunes)
        self.assertEqual(Alimento.objects.filter(nombre="Arepa").count(), 2)


class CalculoPorCantidadTests(TestCase):
    """Escenario 5: la regla de tres sobre los valores por 100 g."""

    def setUp(self):
        self.alimento = Alimento.objects.create(
            nombre="Alimento base",
            categoria="Pruebas",
            calorias=Decimal("200"),
            proteinas=Decimal("10"),
            carbohidratos=Decimal("20"),
            grasas=Decimal("5"),
            fuente="Prueba",
            valores_aproximados=False,
        )

    def test_doscientas_kcal_por_cien_gramos_en_ciento_cincuenta_gramos(self):
        """200 kcal/100 g x 150 g = 300 kcal (el ejemplo del enunciado)."""
        resultado = calcular(self.alimento, 150, Unidad.GRAMOS)
        self.assertEqual(resultado.calorias, Decimal("300.0"))
        self.assertEqual(resultado.proteinas, Decimal("15.0"))
        self.assertEqual(resultado.carbohidratos, Decimal("30.0"))
        self.assertEqual(resultado.grasas, Decimal("7.5"))

    def test_cien_gramos_devuelve_los_valores_de_la_ficha(self):
        resultado = calcular(self.alimento, 100, Unidad.GRAMOS)
        self.assertEqual(resultado.calorias, Decimal("200.0"))

    def test_guarda_la_instantanea_de_la_referencia_usada(self):
        """El historial debe poder reconstruirse aunque cambie el catálogo."""
        resultado = calcular(self.alimento, 50, Unidad.GRAMOS)
        self.assertEqual(resultado.referencia["calorias"], Decimal("200"))
        self.assertEqual(resultado.cantidad_base, Decimal("50.0"))

    def test_el_redondeo_es_a_un_decimal(self):
        self.assertEqual(redondear(Decimal("12.345")), Decimal("12.3"))
        self.assertEqual(redondear(Decimal("12.35")), Decimal("12.4"))


class ConversionDeUnidadesTests(TestCase):
    """Escenario 6: solo se convierten unidades con equivalencia documentada."""

    def setUp(self):
        self.arepa = Alimento.objects.create(
            nombre="Arepa",
            categoria="Cereales",
            calorias=Decimal("180"),
            proteinas=Decimal("4"),
            carbohidratos=Decimal("38"),
            grasas=Decimal("1.5"),
            gramos_por_unidad=Decimal("100"),
            fuente="Prueba",
        )
        self.gaseosa = Alimento.objects.create(
            nombre="Gaseosa",
            categoria="Bebidas",
            unidad_referencia=UnidadReferencia.MILILITROS_100,
            calorias=Decimal("42"),
            proteinas=Decimal("0"),
            carbohidratos=Decimal("10.6"),
            grasas=Decimal("0"),
            fuente="Prueba",
        )
        self.sin_equivalencia = Alimento.objects.create(
            nombre="Preparación sin peso conocido",
            categoria="Pruebas",
            calorias=Decimal("100"),
            proteinas=Decimal("1"),
            carbohidratos=Decimal("1"),
            grasas=Decimal("1"),
            gramos_por_unidad=None,
            fuente="Prueba",
        )

    def test_una_unidad_usa_la_equivalencia_documentada(self):
        cantidad, motivo = convertir_a_base(Decimal("2"), Unidad.UNIDAD, self.arepa)
        self.assertEqual(cantidad, Decimal("200"))
        self.assertEqual(motivo, "")

    def test_mililitros_sobre_un_alimento_en_mililitros(self):
        resultado = calcular(self.gaseosa, 400, Unidad.MILILITROS)
        # 42 kcal/100 ml x 400 ml = 168 kcal
        self.assertEqual(resultado.calorias, Decimal("168.0"))

    def test_no_se_convierten_gramos_a_mililitros(self):
        """Sin densidad conocida, convertir g a ml sería inventar."""
        resultado = calcular(self.gaseosa, 400, Unidad.GRAMOS)
        self.assertFalse(resultado.calculado)
        self.assertTrue(resultado.necesita_confirmacion)
        self.assertIn("ml", resultado.motivo)

    def test_sin_equivalencia_de_unidad_pide_confirmacion(self):
        """Escenario clave: no todas las arepas pesan lo mismo."""
        resultado = calcular(self.sin_equivalencia, 1, Unidad.UNIDAD)
        self.assertFalse(resultado.calculado)
        self.assertTrue(resultado.necesita_confirmacion)
        self.assertIn("equivalencia", resultado.motivo.lower())

    def test_una_unidad_se_marca_como_estimacion(self):
        resultado = calcular(self.arepa, 1, Unidad.UNIDAD)
        self.assertTrue(resultado.calculado)
        self.assertTrue(resultado.es_estimado)


class CantidadesInvalidasTests(TestCase):
    """Escenario 10: cantidades negativas, cero o no numéricas."""

    def setUp(self):
        self.alimento = Alimento.objects.create(
            nombre="Alimento base",
            categoria="Pruebas",
            calorias=Decimal("200"),
            proteinas=Decimal("10"),
            carbohidratos=Decimal("20"),
            grasas=Decimal("5"),
            fuente="Prueba",
        )

    def test_cantidad_negativa(self):
        with self.assertRaises(CantidadInvalida):
            validar_cantidad(-100)

    def test_cantidad_cero(self):
        with self.assertRaises(CantidadInvalida):
            validar_cantidad(0)

    def test_cantidad_no_numerica(self):
        with self.assertRaises(CantidadInvalida):
            validar_cantidad("mucho")

    def test_el_calculo_rechaza_una_cantidad_negativa(self):
        with self.assertRaises(CantidadInvalida):
            calcular(self.alimento, -50, Unidad.GRAMOS)


class AlimentoNoIdentificadoTests(TestCase):
    """Escenario 11: lo que no está en el catálogo no vale cero."""

    def test_sin_alimento_no_se_calculan_valores(self):
        resultado = calcular(None, 100, Unidad.GRAMOS, nombre_mostrado="sushi")
        self.assertIsNone(resultado.calorias)
        self.assertIsNone(resultado.proteinas)
        self.assertFalse(resultado.calculado)
        self.assertTrue(resultado.necesita_confirmacion)
        self.assertIn("sushi", resultado.motivo)


class SumaDeAlimentosTests(TestCase):
    """Escenario 7: sumar los nutrientes de varios alimentos."""

    def setUp(self):
        self.usuario = User.objects.create_user("ana", password="clave-de-prueba-1")
        self.alimento = Alimento.objects.create(
            nombre="Alimento base",
            categoria="Pruebas",
            calorias=Decimal("200"),
            proteinas=Decimal("10"),
            carbohidratos=Decimal("20"),
            grasas=Decimal("5"),
            fuente="Prueba",
            valores_aproximados=False,
        )
        self.comida = RegistroComida.objects.create(
            usuario=self.usuario,
            descripcion="Almuerzo",
            fecha=timezone.localdate(),
            confirmado=True,
        )

    def _detalle(self, gramos, calorias, proteinas):
        return DetalleComida.objects.create(
            registro=self.comida,
            alimento=self.alimento,
            nombre_mostrado="Alimento base",
            cantidad=Decimal(gramos),
            unidad=Unidad.GRAMOS,
            calorias=Decimal(calorias),
            proteinas=Decimal(proteinas),
            carbohidratos=Decimal("0"),
            grasas=Decimal("0"),
        )

    def test_suma_dos_alimentos(self):
        self._detalle(100, "200", "10")
        self._detalle(150, "300", "15")
        totales = sumar_detalles(self.comida.detalles.all())
        self.assertEqual(totales["calorias"], Decimal("500.0"))
        self.assertEqual(totales["proteinas"], Decimal("25.0"))
        self.assertEqual(totales["sin_datos"], 0)

    def test_un_detalle_sin_datos_no_suma_cero_sino_que_se_reporta(self):
        self._detalle(100, "200", "10")
        DetalleComida.objects.create(
            registro=self.comida,
            alimento=None,
            nombre_mostrado="Sushi",
            cantidad=Decimal("1"),
            unidad=Unidad.UNIDAD,
        )
        totales = sumar_detalles(self.comida.detalles.all())
        self.assertEqual(totales["calorias"], Decimal("200.0"))
        self.assertEqual(totales["sin_datos"], 1)

    def test_lista_vacia_da_cero(self):
        totales = sumar_detalles([])
        self.assertEqual(totales["calorias"], Decimal("0.0"))


class ResumenDiarioTests(TestCase):
    """Escenarios 8 y 16: resumen del día y calorías restantes."""

    def setUp(self):
        self.usuario = User.objects.create_user("luis", password="clave-de-prueba-1")
        self.usuario.perfil.meta_calorias_diaria = 2000
        self.usuario.perfil.save()
        self.hoy = timezone.localdate()
        self.alimento = Alimento.objects.create(
            nombre="Alimento base",
            categoria="Pruebas",
            calorias=Decimal("200"),
            proteinas=Decimal("10"),
            carbohidratos=Decimal("20"),
            grasas=Decimal("5"),
            fuente="Prueba",
            valores_aproximados=False,
        )

    def _comida(self, calorias, confirmado=True, fecha=None):
        comida = RegistroComida.objects.create(
            usuario=self.usuario,
            descripcion="Comida",
            fecha=fecha or self.hoy,
            confirmado=confirmado,
        )
        DetalleComida.objects.create(
            registro=comida,
            alimento=self.alimento,
            nombre_mostrado="Alimento base",
            cantidad=Decimal("100"),
            unidad=Unidad.GRAMOS,
            calorias=Decimal(calorias),
            proteinas=Decimal("10"),
            carbohidratos=Decimal("20"),
            grasas=Decimal("5"),
        )
        return comida

    def test_resumen_sin_registros(self):
        resumen = resumen_diario(self.usuario, self.hoy)
        self.assertEqual(resumen["consumido"], Decimal("0.0"))
        self.assertEqual(resumen["restantes"], Decimal("2000.0"))
        self.assertFalse(resumen["meta_superada"])

    def test_calorias_restantes(self):
        self._comida("500")
        self._comida("300")
        resumen = resumen_diario(self.usuario, self.hoy)
        self.assertEqual(resumen["consumido"], Decimal("800.0"))
        self.assertEqual(resumen["restantes"], Decimal("1200.0"))
        self.assertEqual(resumen["porcentaje"], Decimal("40.0"))

    def test_al_superar_la_meta_no_hay_restantes_negativas(self):
        """Nunca se muestran calorías negativas como si estuvieran disponibles."""
        self._comida("2500")
        resumen = resumen_diario(self.usuario, self.hoy)
        self.assertTrue(resumen["meta_superada"])
        self.assertEqual(resumen["restantes"], Decimal("0.0"))
        self.assertEqual(resumen["exceso"], Decimal("500.0"))

    def test_las_comidas_sin_confirmar_no_cuentan(self):
        self._comida("500", confirmado=False)
        resumen = resumen_diario(self.usuario, self.hoy)
        self.assertEqual(resumen["consumido"], Decimal("0.0"))

    def test_solo_cuentan_las_comidas_de_la_fecha(self):
        self._comida("500", fecha=self.hoy - timedelta(days=1))
        resumen = resumen_diario(self.usuario, self.hoy)
        self.assertEqual(resumen["consumido"], Decimal("0.0"))

    def test_los_macronutrientes_se_suman(self):
        self._comida("500")
        resumen = resumen_diario(self.usuario, self.hoy)
        self.assertEqual(resumen["proteinas"], Decimal("10.0"))
        self.assertEqual(resumen["carbohidratos"], Decimal("20.0"))
        self.assertEqual(resumen["grasas"], Decimal("5.0"))
