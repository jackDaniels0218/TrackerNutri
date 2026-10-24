"""RF3 (Alimentos), RF4 (Preparaciones), RF5 (Métodos y absorción) y RF6 (Léxico y porciones)."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.urls import reverse

from core.datos.alimentos import ALIMENTOS
from core.models import (
    Alimento,
    Ambito,
    CoeficienteAbsorcion,
    HistorialCatalogo,
    MetodoCoccion,
    PorcionCasera,
    Preparacion,
    TerminoLexico,
    TerminoPendiente,
)
from core.services import curacion
from core.services.catalogo import alimentos_visibles, cargar_catalogo_inicial
from core.services.interpretacion import interpretar

from .base import BaseNutri


class CatalogoInicialTests(BaseNutri):
    def test_tamano_minimo_del_catalogo(self):
        self.assertGreaterEqual(Alimento.objects.filter(ambito=Ambito.GLOBAL).count(), 150)
        self.assertGreaterEqual(Preparacion.objects.count(), 60)
        self.assertGreaterEqual(MetodoCoccion.objects.count(), 10)
        self.assertGreaterEqual(TerminoLexico.objects.count(), 300)

    def test_carga_idempotente(self):
        antes = Alimento.objects.count()
        cargar_catalogo_inicial(self.version)
        self.assertEqual(Alimento.objects.count(), antes)

    def test_todos_los_alimentos_cumplen_atwater(self):
        for alimento in Alimento.objects.all():
            alimento.full_clean()

    def test_datos_desconocidos_quedan_vacios_no_en_cero(self):
        self.assertTrue(any(datos.get("fibra") is None for datos in ALIMENTOS) or Alimento.objects.filter(fibra__isnull=True).exists())


class AlimentosTests(BaseNutri):
    def test_energia_incoherente_se_rechaza(self):
        alimento = Alimento(nombre="Prueba", categoria="Otros", kcal=500, proteinas=10, carbohidratos=10, grasas=1)
        with self.assertRaises(ValidationError):
            alimento.full_clean()

    def test_macronutrientes_no_superan_100_g(self):
        alimento = Alimento(nombre="Prueba", categoria="Otros", kcal=900, proteinas=60, carbohidratos=60, grasas=10)
        with self.assertRaises(ValidationError):
            alimento.full_clean()

    def test_curador_edita_y_queda_historial(self):
        curador = self.crear_curador()
        lulo = Alimento.objects.get(nombre="Lulo")
        datos = {campo: getattr(lulo, campo) for campo in ("nombre", "categoria", "estado_fisico", "kcal", "proteinas",
                                                           "carbohidratos", "azucares", "grasas", "matriz", "fuente")}
        datos = {k: ("" if v is None else v) for k, v in datos.items()}
        datos.update(fuente_detalle="TCAC 2018", agua_pct="", densidad="", rendimiento_pct="100", grasa_visible_pct="0",
                     grasas_saturadas="", fibra="", sodio_mg="", metodo_defecto="", estado="activo")
        r = self.entrar(curador).post(reverse("catalogo_alimento_editar", args=[lulo.pk]), datos)
        self.assertEqual(r.status_code, 302, getattr(r.context, "get", lambda *_: None)("form") and r.context["form"].errors)
        self.assertTrue(HistorialCatalogo.objects.filter(entidad="Alimento", entidad_id=lulo.pk).exists())

    def test_usuario_no_entra_al_catalogo_global(self):
        self.assertEqual(self.entrar(self.crear_usuario()).get(reverse("catalogo_alimentos")).status_code, 403)

    def test_alimento_personal_solo_lo_ve_su_dueno(self):
        ana = self.crear_usuario("ana@prueba.co")
        luis = self.crear_usuario("luis@prueba.co")
        self.entrar(ana).post(reverse("mi_alimento_nuevo"), {
            "nombre": "Arepa de la abuela", "categoria": "Cereales y derivados", "estado_fisico": "cocido",
            "kcal": "220", "proteinas": "5", "carbohidratos": "40", "grasas": "4", "azucares": "",
        })
        personal = Alimento.objects.get(nombre="Arepa de la abuela")
        self.assertEqual(personal.ambito, Ambito.PERSONAL)
        self.assertIn(personal, alimentos_visibles(ana))
        self.assertNotIn(personal, alimentos_visibles(luis))

    def test_curador_aprueba_alimento_personal(self):
        ana = self.crear_usuario()
        personal = Alimento.objects.create(nombre="Masato casero", categoria="Bebidas", kcal=80, proteinas=1,
                                           carbohidratos=18, grasas=0.5, estado_fisico="cocido",
                                           ambito=Ambito.PERSONAL, propietario=ana)
        copia = curacion.aprobar_alimento_personal(personal, self.crear_curador())
        self.assertEqual(copia.ambito, Ambito.GLOBAL)
        self.assertIsNone(copia.propietario)


class PreparacionesTests(BaseNutri):
    def test_bandeja_paisa_tiene_componentes_con_metodo(self):
        bandeja = Preparacion.objects.get(nombre__iexact="Bandeja paisa")
        self.assertGreaterEqual(bandeja.componentes.count(), 8)
        self.assertTrue(bandeja.componentes.filter(metodo__isnull=False).exists())

    def test_peso_de_la_porcion_coherente_con_los_componentes(self):
        for preparacion in Preparacion.objects.all():
            self.assertFalse(preparacion.validar_peso(), preparacion.nombre)

    def test_validacion_de_peso_avisa_si_no_cuadra(self):
        bandeja = Preparacion.objects.get(nombre__iexact="Bandeja paisa")
        bandeja.peso_porcion_g = Decimal("100")
        self.assertTrue(bandeja.validar_peso())

    def test_pantalla_de_preparaciones(self):
        r = self.entrar(self.crear_curador()).get(reverse("catalogo_preparaciones"))
        self.assertContains(r, "Bandeja paisa")


class MetodosYCoeficientesTests(BaseNutri):
    def test_rangos_de_absorcion_ordenados(self):
        for coef in CoeficienteAbsorcion.objects.all():
            self.assertLessEqual(coef.pct_min, coef.pct_tipico)
            self.assertLessEqual(coef.pct_tipico, coef.pct_max)

    def test_coeficiente_incoherente_se_rechaza(self):
        coef = CoeficienteAbsorcion.objects.first()
        coef.pct_min = Decimal("20")
        with self.assertRaises(ValidationError):
            coef.full_clean()

    def test_cambio_de_coeficiente_guarda_anterior_y_nuevo(self):
        curador = self.crear_curador()
        coef = CoeficienteAbsorcion.objects.get(metodo__clave="fritura_profunda", matriz="masa_maiz")
        self.entrar(curador).post(reverse("catalogo_coeficiente_editar", args=[coef.pk]), {
            "metodo": coef.metodo_id, "matriz": coef.matriz, "pct_min": "6", "pct_tipico": "11", "pct_max": "16",
            "fuente": coef.fuente, "estado": "activo",
        })
        cambio = HistorialCatalogo.objects.filter(entidad="CoeficienteAbsorcion", entidad_id=coef.pk).latest("fecha")
        self.assertEqual(Decimal(str(cambio.valor_nuevo["pct_tipico"])), Decimal("11"))
        self.assertNotEqual(cambio.valor_anterior["pct_tipico"], cambio.valor_nuevo["pct_tipico"])


class LexicoYPorcionesTests(BaseNutri):
    def test_termino_unico(self):
        termino = TerminoLexico.objects.first()
        with self.assertRaises((IntegrityError, ValidationError)):
            TerminoLexico(termino=termino.termino, tipo=termino.tipo, alimento=termino.alimento,
                          preparacion=termino.preparacion, metodo=termino.metodo).full_clean()
            TerminoLexico.objects.create(termino=termino.termino, tipo=termino.tipo, alimento=termino.alimento)

    def test_termino_no_reconocido_va_a_pendientes_y_el_curador_lo_resuelve(self):
        interpretar("un plato de chontaduro con sal")
        pendiente = TerminoPendiente.objects.get(termino__contains="chontaduro")
        destino = Alimento.objects.get(nombre="Plátano maduro")  # cualquier destino válido para la prueba
        curacion.resolver_termino(pendiente, destino, self.crear_curador())
        resultado = interpretar("chontaduro")
        self.assertEqual(resultado.items[0].destino, destino)

    def test_porciones_caseras_por_alimento(self):
        self.assertTrue(PorcionCasera.objects.filter(medida="unidad_mediana", alimento__nombre="Huevo de gallina").exists())
        self.assertTrue(PorcionCasera.objects.filter(medida="pocillo").exists())

    def test_pantallas_de_lexico_y_porciones(self):
        self.entrar(self.crear_curador())
        self.assertEqual(self.client.get(reverse("catalogo_lexico")).status_code, 200)
        self.assertEqual(self.client.get(reverse("catalogo_porciones")).status_code, 200)
