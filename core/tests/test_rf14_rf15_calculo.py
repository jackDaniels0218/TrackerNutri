"""RF14 (Deconstrucción de recetas y cálculo) y RF15 (Calculadora de absorción de aceite)."""

from decimal import Decimal

from django.urls import reverse

from core.models import Alimento, MetodoCoccion, Preparacion
from core.services import comidas
from core.services.aceite import calcular_aceite
from core.services.calculo import CantidadInvalida, Solicitud, calcular, validar_cantidad

from .base import BaseNutri


def metodo(clave):
    return MetodoCoccion.objects.get(clave=clave)


class CalculoTests(BaseNutri):
    def test_alimento_simple_por_100_g(self):
        arroz = Alimento.objects.get(nombre="Arroz blanco cocido")
        resultado = calcular(Solicitud(destino=arroz, cantidad_g=Decimal("150")))
        self.assertEqual(resultado.kcal, (arroz.kcal * Decimal("1.5")).quantize(Decimal("0.1")))
        self.assertEqual(resultado.aceite_g, 0)

    def test_fritura_suma_aceite_y_da_rango(self):
        platano = Alimento.objects.get(nombre="Plátano verde")
        cocido = calcular(Solicitud(destino=platano, cantidad_g=Decimal("100"), metodo=metodo("hervido")))
        frito = calcular(Solicitud(destino=platano, cantidad_g=Decimal("100"), metodo=metodo("fritura_profunda")))
        self.assertGreater(frito.aceite_g, 0)
        self.assertGreater(frito.kcal, cocido.kcal)
        self.assertLessEqual(frito.kcal_min, frito.kcal)
        self.assertLessEqual(frito.kcal, frito.kcal_max)

    def test_preparacion_se_deconstruye_en_ingredientes(self):
        bandeja = Preparacion.objects.get(nombre__iexact="Bandeja paisa")
        resultado = calcular(Solicitud(destino=bandeja, cantidad_g=bandeja.peso_porcion_g))
        # Una línea por ingrediente (más la del aceite de cocción, si aplica).
        self.assertGreaterEqual(len(resultado.lineas), bandeja.componentes.filter(opcional=False).count())
        self.assertGreater(resultado.kcal, Decimal("900"))
        self.assertTrue(any(Decimal(str(l.get("aceite_g", 0))) > 0 for l in resultado.lineas))

    def test_porcion_escala_los_componentes(self):
        bandeja = Preparacion.objects.get(nombre__iexact="Bandeja paisa")
        entera = calcular(Solicitud(destino=bandeja, cantidad_g=bandeja.peso_porcion_g))
        media = calcular(Solicitud(destino=bandeja, cantidad_g=bandeja.peso_porcion_g / 2))
        self.assertAlmostEqual(float(media.kcal), float(entera.kcal) / 2, delta=2)

    def test_nutrientes_desconocidos_no_se_cuentan_como_cero(self):
        resultado = calcular(Solicitud(destino=Alimento.objects.get(nombre="Arroz blanco cocido"), cantidad_g=Decimal("100")))
        self.assertIsInstance(resultado.azucares_incompletos, bool)

    def test_cantidades_invalidas(self):
        for valor in ("0", "-3", "abc", "6000"):
            with self.assertRaises(CantidadInvalida, msg=valor):
                validar_cantidad(valor)

    def test_desglose_guardado_en_el_item(self):
        usuario = self.crear_usuario()
        comida = comidas.crear_manual(usuario, [{"destino": Preparacion.objects.get(nombre__iexact="Bandeja paisa"),
                                                 "cantidad_g": 500}])
        item = comida.items.first()
        self.assertIn("lineas", item.detalle_calculo)
        self.assertEqual(item.detalle_calculo["version_motor"], comida.version_motor)
        r = self.entrar(usuario).get(reverse("comida_detalle", args=[comida.pk]))
        self.assertContains(r, "Huevo")
        self.assertContains(r, "aceite")


class AceiteTests(BaseNutri):
    def test_ejemplo_del_srs_platano_verde(self):
        # 65 g crudos, tubérculo 5/10/15 % → 6,5 g típico (3,3 a 9,8 g)
        resultado = calcular_aceite(peso_crudo_g=65, matriz="tuberculo", metodo=metodo("fritura_profunda"))
        self.assertEqual(resultado.tipico_g, Decimal("6.5"))
        self.assertEqual(resultado.minimo_g, Decimal("3.3"))
        self.assertEqual(resultado.maximo_g, Decimal("9.8"))
        self.assertEqual(resultado.kcal_tipico, Decimal("58.5"))

    def test_factores_de_pieza_y_escurrido(self):
        base = calcular_aceite(peso_crudo_g=65, matriz="tuberculo", metodo=metodo("fritura_profunda"))
        pequena = calcular_aceite(peso_crudo_g=65, matriz="tuberculo", metodo=metodo("fritura_profunda"), tamano="pequena")
        escurrido = calcular_aceite(peso_crudo_g=65, matriz="tuberculo", metodo=metodo("fritura_profunda"), escurrido=True)
        self.assertGreater(pequena.tipico_g, base.tipico_g)
        self.assertLess(escurrido.tipico_g, base.tipico_g)

    def test_sarten_con_aceite_agregado(self):
        resultado = calcular_aceite(peso_crudo_g=50, matriz="huevo", metodo=metodo("fritura_sarten"), aceite_agregado_g=10)
        self.assertGreater(resultado.tipico_g, 0)
        self.assertLess(resultado.tipico_g, Decimal("10"))

    def test_sin_fritura_no_hay_aceite(self):
        self.assertFalse(calcular_aceite(peso_crudo_g=100, matriz="carne", metodo=metodo("asado")).aplica)

    def test_pantalla_de_la_calculadora(self):
        platano = Alimento.objects.get(nombre="Plátano verde")
        r = self.entrar(self.crear_usuario()).get(reverse("calculadora_aceite"), {
            "alimento": platano.pk, "peso_crudo_g": "65", "metodo": metodo("fritura_profunda").pk,
            "tamano": "", "tiempo": "", "aceite_agregado_g": "",
        })
        self.assertContains(r, "6.5")
