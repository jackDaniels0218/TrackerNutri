"""
Respaldo de la base de datos (RNF34).

    python manage.py respaldar                # copia en respaldos/
    python manage.py respaldar --conservar 14 # deja solo los 14 más recientes

Usa la API de respaldo de SQLite, que copia la base aunque la aplicación
esté en uso. Para restaurar, se detiene el servidor y se reemplaza
db.sqlite3 por el archivo de respaldo. En producción (PostgreSQL) este
comando se sustituye por pg_dump programado.
"""

import sqlite3
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.services import auditoria


class Command(BaseCommand):
    help = "Copia la base de datos SQLite a la carpeta respaldos/."

    def add_arguments(self, parser):
        parser.add_argument("--destino", default=str(Path(settings.BASE_DIR, "respaldos")))
        parser.add_argument("--conservar", type=int, default=7)

    def handle(self, *args, destino, conservar, **opciones):
        base = settings.DATABASES["default"]
        if base["ENGINE"] != "django.db.backends.sqlite3":
            raise CommandError("Este comando es para SQLite; con PostgreSQL usa pg_dump.")
        carpeta = Path(destino)
        carpeta.mkdir(parents=True, exist_ok=True)
        archivo = carpeta / f"nutriregional-{timezone.localtime():%Y%m%d-%H%M%S}.sqlite3"
        with sqlite3.connect(base["NAME"]) as origen, sqlite3.connect(archivo) as copia:
            origen.backup(copia)
        respaldos = sorted(carpeta.glob("nutriregional-*.sqlite3"))
        for viejo in respaldos[:-conservar] if conservar > 0 else []:
            viejo.unlink()
        auditoria.registrar("respaldo", detalle=archivo.name)
        self.stdout.write(self.style.SUCCESS(f"Respaldo creado: {archivo}"))
