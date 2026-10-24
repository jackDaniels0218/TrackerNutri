"""
Prepara una instalación nueva de NutriRegional.

    python manage.py migrate
    python manage.py inicializar_sistema

Carga los parámetros del sistema, el catálogo inicial (alimentos,
preparaciones, métodos de cocción, coeficientes, léxico y porciones), el
conjunto de frases de referencia, y publica la versión 1 del catálogo tras
ejecutar las pruebas de exactitud. Es idempotente: se puede ejecutar varias
veces sin duplicar nada.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from core.datos.frases import FRASES
from core.models import FraseReferencia, VersionCatalogo
from core.services.catalogo import cargar_catalogo_inicial
from core.services.curacion import publicar_version
from core.services.parametros import sembrar_parametros


class Command(BaseCommand):
    help = "Carga parámetros, catálogo inicial y frases de referencia; publica la versión 1."

    @transaction.atomic
    def handle(self, *args, **opciones):
        creados = sembrar_parametros()
        self.stdout.write(f"Parámetros nuevos: {creados}")

        version = VersionCatalogo.objects.filter(numero=1).first() or VersionCatalogo.objects.create(
            numero=1, notas="Catálogo inicial del prototipo (estimaciones pendientes de validación)."
        )
        conteo = cargar_catalogo_inicial(version)
        for clave, valor in conteo.items():
            self.stdout.write(f"  {clave}: {valor} nuevos")

        nuevas = 0
        for frase in FRASES:
            _, creada = FraseReferencia.objects.get_or_create(
                texto=frase["texto"], defaults={"componentes_esperados": frase["componentes"]}
            )
            nuevas += int(creada)
        self.stdout.write(f"Frases de referencia nuevas: {nuevas}")

        if version.estado != VersionCatalogo.Estado.PUBLICADA:
            ejecucion = publicar_version(version, None, version.notas)
            estado = "publicada" if ejecucion.aprobada else "BLOQUEADA"
            self.stdout.write(
                f"Versión 1 {estado}: identificación {ejecucion.identificacion_pct} %, "
                f"método de cocción {ejecucion.coccion_pct} % ({ejecucion.total_frases} frases)."
            )
        self.stdout.write(self.style.SUCCESS("Sistema inicializado."))
