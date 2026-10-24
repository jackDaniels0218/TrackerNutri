"""RF7 (Registro de comidas) y RF10 (Correcciones y retroalimentación)."""

import uuid
from decimal import Decimal

from django.urls import reverse

from core.models import Alimento, Comida, Correccion, EstadoComida, MetodoCoccion, Notificacion
from core.services import comidas, curacion, reportes

from .base import BaseNutri


class RegistroPorTextoTests(BaseNutri):
    def test_flujo_completo_texto_aclarar_confirmar(self):
        usuario = self.crear_usuario()
        self.entrar(usuario)
        r = self.client.post(reverse("comida_nueva"), {"texto": "una arepa y una gaseosa", "fecha": "2026-10-20",
                                                       "hora": "13:00", "tipo": ""})
        comida = Comida.objects.get(usuario=usuario)
        self.assertEqual(comida.estado, EstadoComida.INTERPRETADA)
        self.assertRedirects(r, reverse("comida_aclarar", args=[comida.pk]))
        # Nada cuenta hasta confirmar.
        self.assertEqual(reportes.kcal_del_dia(usuario, comida.fecha), 0)

        respuestas = {f"pregunta_{p['item']}_{p['tipo']}": p["opciones"][0]["valor"] for p in comida.preguntas}
        self.assertLessEqual(len(comida.preguntas), 2)
        self.client.post(reverse("comida_aclarar", args=[comida.pk]), respuestas)
        r = self.client.get(reverse("comida_confirmar", args=[comida.pk]))
        self.assertContains(r, "Arepa")
        # Los campos numéricos llevan punto decimal: con coma el navegador los deja vacíos.
        item = comida.items.first()
        self.assertContains(r, f'name="item-{item.pk}-cantidad" value="{item.cantidad_g}"')
        self.assertContains(r, "confianza")
        self.client.post(reverse("comida_confirmar", args=[comida.pk]), {"accion": "confirmar"})
        comida.refresh_from_db()
        self.assertEqual(comida.estado, EstadoComida.CONFIRMADA)
        self.assertGreater(reportes.kcal_del_dia(usuario, comida.fecha), 0)

    def test_no_se_confirma_con_componentes_sin_reconocer(self):
        usuario = self.crear_usuario()
        comida = comidas.crear_desde_texto(usuario, "un plato de xqzwv")
        with self.assertRaises(comidas.ComidaNoConfirmable):
            comidas.confirmar(comida)

    def test_doble_confirmacion_es_idempotente(self):
        usuario = self.crear_usuario()
        comida = comidas.crear_desde_texto(usuario, "200 g de arroz blanco")
        comidas.confirmar(comida)
        comidas.confirmar(comida)
        self.assertEqual(Comida.objects.filter(usuario=usuario).count(), 1)


class RegistroManualTests(BaseNutri):
    def datos(self, clave, **cambios):
        datos = {"fecha": "2026-10-20", "hora": "12:30", "tipo": "almuerzo", "clave": str(clave),
                 "fila-TOTAL_FORMS": "1", "fila-INITIAL_FORMS": "0", "fila-MIN_NUM_FORMS": "0", "fila-MAX_NUM_FORMS": "20",
                 "fila-0-alimento": "Arroz blanco cocido", "fila-0-cantidad": "150", "fila-0-unidad": "g", "fila-0-metodo": ""}
        datos.update(cambios)
        return datos

    def test_registro_manual_siempre_disponible(self):
        usuario = self.crear_usuario()
        clave = uuid.uuid4()
        r = self.entrar(usuario).post(reverse("comida_manual"), self.datos(clave))
        self.assertEqual(r.status_code, 302)
        comida = Comida.objects.get(usuario=usuario)
        self.assertEqual(comida.estado, EstadoComida.CONFIRMADA)
        arroz = Alimento.objects.get(nombre="Arroz blanco cocido")
        self.assertEqual(comida.kcal, (arroz.kcal * Decimal("1.5")).quantize(Decimal("0.1")))

    def test_doble_envio_no_duplica(self):
        usuario = self.crear_usuario()
        clave = uuid.uuid4()
        self.entrar(usuario)
        self.client.post(reverse("comida_manual"), self.datos(clave))
        self.client.post(reverse("comida_manual"), self.datos(clave))
        self.assertEqual(Comida.objects.filter(usuario=usuario).count(), 1)

    def test_cantidad_invalida(self):
        usuario = self.crear_usuario()
        r = self.entrar(usuario).post(reverse("comida_manual"), self.datos(uuid.uuid4(), **{"fila-0-cantidad": "-5"}))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Comida.objects.filter(usuario=usuario).exists())


class EdicionFavoritasYBajaTests(BaseNutri):
    def comida(self, usuario):
        return comidas.crear_manual(usuario, [{"destino": Alimento.objects.get(nombre="Huevo de gallina"),
                                               "cantidad_g": 100, "metodo": MetodoCoccion.objects.get(clave="fritura_sarten")}])

    def test_editar_un_item_marca_la_comida_como_editada(self):
        usuario = self.crear_usuario()
        comida = self.comida(usuario)
        item = comida.items.first()
        comidas.editar_item(item, cantidad_g=Decimal("120"))
        comida.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(comida.estado, EstadoComida.EDITADA)
        self.assertTrue(item.editado)

    def test_valores_congelados_no_cambian_si_cambia_el_catalogo(self):
        usuario = self.crear_usuario()
        comida = self.comida(usuario)
        kcal = comida.kcal
        Alimento.objects.filter(nombre="Huevo de gallina").update(kcal=500)
        comida.refresh_from_db()
        self.assertEqual(comida.kcal, kcal)

    def test_favorita_y_repetir(self):
        usuario = self.crear_usuario()
        comida = self.comida(usuario)
        self.entrar(usuario).post(reverse("comida_favorita", args=[comida.pk]), {"nombre": "Desayuno de siempre"})
        comida.refresh_from_db()
        self.assertTrue(comida.es_favorita)
        self.client.post(reverse("favorita_repetir", args=[comida.pk]), {"clave": str(uuid.uuid4())})
        self.assertEqual(Comida.objects.filter(usuario=usuario, origen="favorita").count(), 1)

    def test_eliminar_es_baja_logica(self):
        usuario = self.crear_usuario()
        comida = self.comida(usuario)
        self.entrar(usuario).post(reverse("comida_eliminar", args=[comida.pk]))
        comida.refresh_from_db()
        self.assertEqual(comida.estado, EstadoComida.DESCARTADA)
        self.assertEqual(reportes.kcal_del_dia(usuario, comida.fecha), 0)

    def test_aislamiento_entre_usuarios(self):
        ana = self.crear_usuario("ana@prueba.co")
        luis = self.crear_usuario("luis@prueba.co")
        comida = self.comida(ana)
        self.entrar(luis)
        for nombre in ("comida_detalle", "comida_confirmar", "comida_eliminar"):
            self.assertEqual(self.client.get(reverse(nombre, args=[comida.pk])).status_code, 404, nombre)
        self.assertEqual(self.client.get(reverse("item_corregir", args=[comida.items.first().pk])).status_code, 404)

    def test_historial_muestra_las_comidas(self):
        usuario = self.crear_usuario()
        comida = self.comida(usuario)
        r = self.entrar(usuario).get(reverse("historial") + f"?hasta={comida.fecha:%Y-%m-%d}")
        self.assertContains(r, "Huevo de gallina")


class CorreccionesTests(BaseNutri):
    def test_correccion_de_cantidad_se_aplica_de_inmediato(self):
        usuario = self.crear_usuario()
        comida = comidas.crear_manual(usuario, [{"destino": Alimento.objects.get(nombre="Arroz blanco cocido"), "cantidad_g": 100}])
        item = comida.items.first()
        self.entrar(usuario).post(reverse("item_corregir", args=[item.pk]), {
            "tipo": Correccion.Tipo.CANTIDAD, "valor_sugerido": "200 g", "comentario": "Era un plato grande",
        })
        correccion = Correccion.objects.get(item=item)
        item.refresh_from_db()
        self.assertTrue(correccion.aplicada_a_comida)
        self.assertEqual(item.cantidad_g, Decimal("200.0"))
        self.assertEqual(correccion.estado, Correccion.Estado.PENDIENTE)

    def test_curador_acepta_y_el_usuario_recibe_la_respuesta(self):
        usuario = self.crear_usuario()
        curador = self.crear_curador()
        comida = comidas.crear_desde_texto(usuario, "una arepa asada")
        comidas.confirmar(comida)
        item = comida.items.first()
        correccion = curacion.crear_correccion(item, usuario, Correccion.Tipo.METODO, "frita")
        self.assertTrue(Notificacion.objects.filter(destinatario=curador).exists())
        self.entrar(curador).post(reverse("correccion_revisar", args=[correccion.pk]),
                                  {"decision": "aceptar", "resolucion": "Gracias, ajustamos el método."})
        correccion.refresh_from_db()
        self.assertEqual(correccion.estado, Correccion.Estado.ACEPTADA)
        self.assertTrue(Notificacion.objects.filter(destinatario=usuario, tipo=Notificacion.Tipo.CORRECCION).exists())
        r = self.entrar(usuario).get(reverse("mis_correcciones"))
        self.assertContains(r, "Aceptada")
