"""
Comprueba de extremo a extremo que la integración con la IA funciona de verdad.

    python manage.py probar_ia
    python manage.py probar_ia --texto "un sudado de pescado bien sabroso"

A diferencia de las pruebas automatizadas (que simulan la respuesta), este
comando SÍ llama al proveedor configurado. Por eso no forma parte de
`manage.py test`: gasta crédito y necesita conexión.

Pasos:
  1. ¿Hay un proveedor activo y configurado? (parámetro ia_proveedor y la
     clave OPENAI_API_KEY o IA_COMPATIBLE_API_KEY, o ia_url_local)
  2. ¿El proveedor responde con el JSON del esquema? (RF13, sin pasar por
     caché ni límites, para ver la respuesta cruda validada)
  3. ¿La interpretación completa (léxico → IA → catálogo) produce ítems
     calculables? Lo hace sin guardar nada.
"""

import time

from django.core.management.base import BaseCommand, CommandError

from core.services import ia
from core.services.interpretacion import interpretar
from core.services.parametros import parametro

TEXTO_POR_DEFECTO = "un plato de sancocho trifásico, un pedazo de bollo limpio y un jugo de lulo"


class Command(BaseCommand):
    help = "Prueba la integración real con el proveedor de IA (puede consumir crédito)."

    def add_arguments(self, parser):
        parser.add_argument("--texto", default=TEXTO_POR_DEFECTO)

    def handle(self, *args, **opciones):
        proveedor = ia.proveedor_activo()
        self.stdout.write(f"1. Proveedor: {parametro('ia_proveedor')}")
        if proveedor is None:
            raise CommandError("La IA está desactivada (parámetro ia_proveedor = 'ninguno').")
        if not proveedor.disponible:
            faltante = {"openai": "OPENAI_API_KEY en .env", "compatible": "IA_COMPATIBLE_API_KEY en .env y los parámetros "
                        "ia_url_compatible e ia_modelo_compatible", "local": "el parámetro ia_url_local"}[proveedor.nombre]
            raise CommandError(f"Falta {faltante}.")
        destino = f" en {proveedor.base_url}" if proveedor.base_url else ""
        self.stdout.write(self.style.SUCCESS(f"   Configurado · modelo {proveedor.modelo}{destino}"))

        texto = opciones["texto"]
        self.stdout.write(f"2. Llamada directa con: «{texto}»")
        inicio = time.monotonic()
        try:
            contenido, entrada, salida = proveedor.llamar([texto], ia.PLANTILLA_VIGENTE)
            items = ia.validar_respuesta(contenido, 1)
        except ia.ProveedorNoDisponible as exc:
            raise CommandError(f"El proveedor no respondió: {exc}") from exc
        except ia.RespuestaInvalida as exc:
            raise CommandError(f"Respuesta fuera del esquema: {exc}") from exc
        ms = int((time.monotonic() - inicio) * 1000)
        self.stdout.write(self.style.SUCCESS(
            f"   Respuesta válida en {ms} ms · {entrada}+{salida} tokens · ~{ia.costo(entrada, salida):.6f} USD"
        ))
        self.stdout.write(f"   {items[0]}")

        self.stdout.write("3. Interpretación completa (sin guardar):")
        resultado = interpretar(texto, registrar_pendientes=False)
        self.stdout.write(f"   motor: {resultado.motor}")
        for item in resultado.items:
            destino = item.destino.nombre if item.destino else "— sin identificar"
            self.stdout.write(f"   · «{item.fragmento}» → {destino} ({item.cantidad_g} g, {item.origen_resolucion})")
        for aviso in resultado.avisos:
            self.stdout.write(self.style.WARNING(f"   {aviso}"))
        self.stdout.write(self.style.SUCCESS("La integración con la IA funciona."))
