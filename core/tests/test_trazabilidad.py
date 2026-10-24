"""
Trazabilidad SRS → aplicación: cada requerimiento del mapa tiene pantallas
que existen, pruebas que existen y aparece en la página /requerimientos/.
"""

import importlib

from django.urls import NoReverseMatch, reverse

from core.requerimientos import NO_FUNCIONALES, REQUERIMIENTOS

from .base import BaseNutri


class TrazabilidadTests(BaseNutri):
    def test_estan_los_22_requerimientos_funcionales(self):
        self.assertEqual([r["id"] for r in REQUERIMIENTOS], list(range(1, 23)))

    def test_todas_las_pantallas_existen(self):
        for req in REQUERIMIENTOS:
            for nombre, _ in req["pantallas"]:
                try:
                    reverse(nombre)
                except NoReverseMatch:
                    self.fail(f"RF{req['id']}: la ruta «{nombre}» no existe")
        for nfr in NO_FUNCIONALES:
            reverse(nfr["pantalla"])

    def test_todas_las_pruebas_mencionadas_existen(self):
        for req in REQUERIMIENTOS:
            for modulo in req["pruebas"]:
                importlib.import_module(f"core.tests.{modulo}")

    def test_pagina_de_requerimientos(self):
        r = self.client.get(reverse("requerimientos"))
        for req in REQUERIMIENTOS:
            self.assertContains(r, req["nombre"])

    def test_cada_pantalla_responde_para_su_rol(self):
        """La pantalla principal de cada requerimiento abre sin errores con el rol que lo demuestra."""
        cuentas = {"Usuario": self.crear_usuario(), "Curador": self.crear_curador(), "Administrador": self.crear_admin()}
        for req in REQUERIMIENTOS:
            for nombre, _ in req["pantallas"]:
                url = reverse(nombre)
                for rol in req["roles"]:
                    self.client.force_login(cuentas[rol])
                    codigo = self.client.get(url).status_code
                    if codigo in (200, 302):
                        break
                else:
                    self.fail(f"RF{req['id']}: {url} no abre con {req['roles']} (último código {codigo})")
