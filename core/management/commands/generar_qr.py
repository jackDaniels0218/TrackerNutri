"""
Genera el código QR de la aplicación como imagen PNG, para diapositivas o
para imprimir:

    python manage.py generar_qr --url https://nutriregional.onrender.com

La página /qr/ de la aplicación muestra el mismo código sin necesidad de
este comando, con la dirección desde la que se abre.
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core.services.qr import qr_png


class Command(BaseCommand):
    help = "Guarda un PNG con el código QR que abre la URL indicada."

    def add_arguments(self, parser):
        parser.add_argument("--url", required=True)
        parser.add_argument("--salida", default="nutriregional-qr.png")

    def handle(self, *args, url, salida, **opciones):
        if not url.startswith(("http://", "https://")):
            raise CommandError("La URL debe empezar por http:// o https://")
        archivo = Path(salida)
        archivo.write_bytes(qr_png(url))
        self.stdout.write(self.style.SUCCESS(f"Código QR de {url} guardado en {archivo.resolve()}"))
