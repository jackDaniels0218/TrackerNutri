"""RF13 (Interpretación de texto libre)."""

import json
from decimal import Decimal
from unittest import mock

from django.test import override_settings

from core.datos.frases import FRASES
from core.models import FraseReferencia, TerminoPendiente
from core.services import comidas, ia
from core.services.curacion import ejecutar_exactitud
from core.services.interpretacion import calcular_confianza, interpretar
from core.services.texto import normalizar

from .base import BaseNutri


def nombres(resultado):
    return [i.destino.nombre if i.destino else None for i in resultado.items]


class SegmentacionYLexicoTests(BaseNutri):
    def test_varios_alimentos_en_una_frase(self):
        resultado = interpretar("Hoy almorcé arroz, fríjoles y una tajada de maduro, y un jugo de lulo", permitir_ia=False)
        self.assertGreaterEqual(len([n for n in nombres(resultado) if n]), 3)

    def test_jerga_regional(self):
        resultado = interpretar("un tinto y un pandebono", permitir_ia=False)
        self.assertTrue(all(nombres(resultado)), nombres(resultado))

    def test_errores_ortograficos(self):
        resultado = interpretar("chicarron con aripa", permitir_ia=False)
        self.assertTrue(all(nombres(resultado)), nombres(resultado))
        self.assertTrue(any("arepa" in normalizar(n) for n in nombres(resultado)))

    def test_cantidades_numericas_y_caseras(self):
        resultado = interpretar("200 g de arroz blanco y dos huevos", permitir_ia=False)
        arroz, huevos = resultado.items
        self.assertEqual(arroz.cantidad_g, Decimal("200"))
        self.assertEqual(arroz.fuente_cantidad, "gramos")
        self.assertGreater(huevos.cantidad_g, Decimal("90"))

    def test_metodo_explicito(self):
        resultado = interpretar("una arepa frita", permitir_ia=False)
        self.assertEqual(resultado.items[0].metodo.clave, "fritura_profunda")
        self.assertEqual(resultado.items[0].origen_metodo, "explicito")

    def test_tipo_de_comida_detectado(self):
        self.assertEqual(interpretar("en el desayuno comí un huevo", permitir_ia=False).tipo_comida, "desayuno")

    def test_no_reconocido_queda_pendiente_y_no_se_inventa(self):
        resultado = interpretar("un plato de xqzwv", permitir_ia=False)
        self.assertIsNone(resultado.items[0].destino)
        self.assertTrue(TerminoPendiente.objects.filter(termino__contains="xqzwv").exists())


class ConfianzaYPreguntasTests(BaseNutri):
    def test_confianza_combina_resolucion_cantidad_y_metodo(self):
        alta = calcular_confianza(Decimal("1"), "gramos", False, False, "explicito")
        baja = calcular_confianza(Decimal("0.8"), "defecto", False, False, "defecto")
        self.assertGreater(alta, baja)
        self.assertLessEqual(alta, Decimal("1"))

    def test_preguntas_de_aclaracion_como_maximo_dos(self):
        usuario = self.crear_usuario()
        comida = comidas.crear_desde_texto(usuario, "una arepa, una empanada, una gaseosa y un buñuelo")
        self.assertLessEqual(len(comida.preguntas), 2)
        self.assertTrue(comida.preguntas)
        for pregunta in comida.preguntas:
            self.assertIn(pregunta["tipo"], ("metodo", "presentacion", "tamano", "candidato"))
            self.assertGreaterEqual(len(pregunta["opciones"]), 2)

    def test_umbral_configurable(self):
        from core.models import Parametro

        usuario = self.crear_usuario()
        Parametro.objects.filter(clave="umbral_confianza").update(valor="0")
        from core.services.parametros import limpiar_cache

        limpiar_cache()
        comida = comidas.crear_desde_texto(usuario, "una arepa y una gaseosa")
        self.assertEqual(comida.preguntas, [])


class ExactitudTests(BaseNutri):
    def test_conjunto_de_referencia_cumple_los_umbrales(self):
        for frase in FRASES:
            FraseReferencia.objects.create(texto=frase["texto"], componentes_esperados=frase["componentes"])
        ejecucion = ejecutar_exactitud()
        self.assertGreaterEqual(ejecucion.identificacion_pct, Decimal("85"))
        self.assertGreaterEqual(ejecucion.coccion_pct, Decimal("80"))
        self.assertTrue(ejecucion.aprobada)


@override_settings(OPENAI_API_KEY="sk-prueba")
class InterpretacionConIATests(BaseNutri):
    def respuesta(self, nombre="arroz blanco cocido", cantidad=1, unidad="plato"):
        datos = {"items": [{"fragmento": 0, "name": nombre, "quantity": cantidad, "unit": unidad,
                            "preparation": "", "needs_confirmation": False}]}
        return json.dumps(datos), 120, 30

    def test_la_ia_estructura_y_el_catalogo_calcula(self):
        usuario = self.crear_usuario(acepta_ia=True)
        with mock.patch.object(ia.ProveedorOpenAI, "llamar", return_value=self.respuesta()) as llamada:
            resultado = interpretar("un platado de arroz bien graneadito", usuario=usuario)
        llamada.assert_called_once()
        item = resultado.items[0]
        self.assertEqual(item.destino.nombre, "Arroz blanco cocido")
        self.assertEqual(item.origen_resolucion, "ia")
        self.assertEqual(resultado.motor, "ia_externa")

    def test_sin_autorizacion_no_se_envia_nada(self):
        usuario = self.crear_usuario(acepta_ia=False)
        with mock.patch.object(ia.ProveedorOpenAI, "llamar") as llamada:
            resultado = interpretar("un platado de arroz bien graneadito", usuario=usuario)
        llamada.assert_not_called()
        self.assertTrue(resultado.avisos)

    def test_respuesta_invalida_se_descarta(self):
        usuario = self.crear_usuario(acepta_ia=True)
        with mock.patch.object(ia.ProveedorOpenAI, "llamar", return_value=("no es json", 10, 5)):
            resultado = interpretar("un platado de arroz bien graneadito", usuario=usuario)
        self.assertIsNone(resultado.items[0].destino)
        self.assertEqual(resultado.motor, "reglas")

    def test_la_ia_no_puede_aportar_calorias(self):
        datos = {"items": [{"fragmento": 0, "name": "arroz", "quantity": 1, "unit": "", "preparation": "",
                            "needs_confirmation": False, "kcal": 9999}]}
        self.assertNotIn("kcal", ia.validar_respuesta(datos, 1)[0])

    def test_lo_que_resuelve_el_lexico_no_va_a_la_ia(self):
        usuario = self.crear_usuario(acepta_ia=True)
        with mock.patch.object(ia.ProveedorOpenAI, "llamar") as llamada:
            interpretar("una arepa con huevo", usuario=usuario)
        llamada.assert_not_called()
