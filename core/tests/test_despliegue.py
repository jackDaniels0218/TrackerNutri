"""Despliegue: código QR de acceso y parámetros fijados al arrancar (Render)."""

import io

from django.core.management import CommandError, call_command
from django.test import override_settings
from django.urls import reverse

from core.services.parametros import parametro

from .base import BaseNutri


class QrTests(BaseNutri):
    @override_settings(ALLOWED_HOSTS=["nutriregional.onrender.com"])
    def test_pagina_qr_publica_con_la_direccion_del_sitio(self):
        r = self.client.get(reverse("qr"), HTTP_HOST="nutriregional.onrender.com", secure=True)
        self.assertContains(r, "https://nutriregional.onrender.com/")
        self.assertContains(r, "<svg")

    def test_qr_png(self):
        r = self.client.get(reverse("qr_png"))
        self.assertEqual(r["Content-Type"], "image/png")
        self.assertTrue(r.content.startswith(b"\x89PNG"))

    def test_qr_disponible_con_sesion_y_registro_incompleto(self):
        self.entrar(self.crear_usuario(perfil=False))
        self.assertEqual(self.client.get(reverse("qr")).status_code, 200)

    def test_comando_generar_qr(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as carpeta:
            archivo = Path(carpeta, "qr.png")
            call_command("generar_qr", url="https://nutriregional.onrender.com", salida=str(archivo), stdout=io.StringIO())
            self.assertTrue(archivo.read_bytes().startswith(b"\x89PNG"))
        with self.assertRaises(CommandError):
            call_command("generar_qr", url="nutriregional.onrender.com", stdout=io.StringIO())


class ParametrosAlArrancarTests(BaseNutri):
    def test_inicializar_fija_parametros(self):
        call_command("inicializar_sistema", parametro=["ia_proveedor=compatible", "ia_modelo_compatible=openai/gpt-oss-20b"],
                     stdout=io.StringIO())
        self.assertEqual(parametro("ia_proveedor"), "compatible")
        self.assertEqual(parametro("ia_modelo_compatible"), "openai/gpt-oss-20b")

    def test_parametro_inexistente_o_invalido(self):
        for par in ("no_existe=1", "umbral_confianza=abc", "sin_signo_igual"):
            with self.assertRaises(CommandError, msg=par):
                call_command("inicializar_sistema", parametro=[par], stdout=io.StringIO())
