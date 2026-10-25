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
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.models import Parametro
from core.services import auditoria, ia
from core.services.interpretacion import interpretar
from core.services.parametros import limpiar_cache, parametro

TEXTO_POR_DEFECTO = "un plato de sancocho trifásico, un pedazo de bollo limpio y un jugo de lulo"


class Command(BaseCommand):
    help = "Prueba la integración real con el proveedor de IA (puede consumir crédito)."

    def add_arguments(self, parser):
        parser.add_argument("--texto", default=TEXTO_POR_DEFECTO)
        parser.add_argument("--modelo", help="Prueba este modelo en lugar del configurado.")
        parser.add_argument("--guardar", action="store_true",
                            help="Si la prueba funciona, guarda --modelo en los parámetros del sistema.")

    def _listar_modelos(self, proveedor) -> None:
        """Muestra los modelos que la clave puede usar, para elegir uno que exista."""
        try:
            modelos = sorted(m.id for m in proveedor._cliente().models.list())
        except Exception as exc:  # noqa: BLE001 - solo es una ayuda para el diagnóstico
            self.stdout.write(self.style.WARNING(f"   No se pudo obtener la lista de modelos ({type(exc).__name__})."))
            return
        self.stdout.write(self.style.WARNING(f"   El modelo «{proveedor.modelo}» no existe para esta clave. Modelos disponibles:"))
        for modelo in modelos:
            self.stdout.write(f"     - {modelo}")
        self.stdout.write("   Prueba uno y guárdalo con:  python manage.py probar_ia --modelo NOMBRE --guardar")

    @staticmethod
    def _que_falta(proveedor) -> str:
        """Dice exactamente qué falta, sin mostrar nunca el valor de una clave."""
        faltas = []
        variable = {"openai": "OPENAI_API_KEY", "compatible": "IA_COMPATIBLE_API_KEY"}.get(proveedor.nombre)
        if variable and not proveedor.clave:
            archivo = Path(settings.BASE_DIR, ".env")
            if not archivo.exists():
                detalle = f"no existe el archivo {archivo}"
            elif not any(linea.strip().startswith(f"{variable}=") for linea in archivo.read_text(encoding="utf-8", errors="ignore").splitlines()):
                detalle = f"{archivo} no tiene una línea que empiece por {variable}="
            else:
                detalle = f"la línea {variable}= de {archivo} está vacía"
            faltas.append(f"la clave {variable} ({detalle})")
        parametros = {"compatible": ("ia_url_compatible", "ia_modelo_compatible"), "local": ("ia_url_local",)}
        for clave in parametros.get(proveedor.nombre, ()):
            if not parametro(clave):
                faltas.append(f"el parámetro {clave} (Administrador → Parámetros)")
        return "Falta " + " y ".join(faltas) + "."

    def handle(self, *args, **opciones):
        proveedor = ia.proveedor_activo()
        self.stdout.write(f"1. Proveedor: {parametro('ia_proveedor')}")
        if proveedor is None:
            raise CommandError("La IA está desactivada (parámetro ia_proveedor = 'ninguno').")
        if not proveedor.disponible:
            raise CommandError(self._que_falta(proveedor))
        if opciones["modelo"]:
            proveedor.modelo = opciones["modelo"]
        destino = f" en {proveedor.base_url}" if proveedor.base_url else ""
        self.stdout.write(self.style.SUCCESS(f"   Configurado · modelo {proveedor.modelo}{destino}"))

        texto = opciones["texto"]
        self.stdout.write(f"2. Llamada directa con: «{texto}»")
        inicio = time.monotonic()
        try:
            contenido, entrada, salida = proveedor.llamar([texto], ia.PLANTILLA_VIGENTE)
            items = ia.validar_respuesta(contenido, 1)
        except ia.ProveedorNoDisponible as exc:
            if str(exc) == "modelo_no_encontrado":
                self._listar_modelos(proveedor)
            raise CommandError(f"El proveedor no respondió: {exc}") from exc
        except ia.RespuestaInvalida as exc:
            raise CommandError(f"Respuesta fuera del esquema: {exc}") from exc
        ms = int((time.monotonic() - inicio) * 1000)
        precio = f"~{ia.costo(entrada, salida):.6f} USD" if proveedor.cobra else "sin costo (nivel gratuito)"
        self.stdout.write(self.style.SUCCESS(f"   Respuesta válida en {ms} ms · {entrada}+{salida} tokens · {precio}"))
        self.stdout.write(f"   {items[0]}")

        if opciones["modelo"]:
            if not opciones["guardar"]:
                self.stdout.write(self.style.SUCCESS(
                    f"El modelo {proveedor.modelo} funciona. Para usarlo en la aplicación: "
                    f"python manage.py probar_ia --modelo {proveedor.modelo} --guardar"))
                return
            clave = "ia_modelo_compatible" if proveedor.nombre == "compatible" else "ia_modelo"
            Parametro.objects.filter(clave=clave).update(valor=proveedor.modelo)
            limpiar_cache()
            auditoria.registrar("parametro_cambiado", entidad="Parametro", entidad_id=clave,
                                detalle=f"{proveedor.modelo} (desde probar_ia)")
            self.stdout.write(self.style.SUCCESS(f"   Guardado: {clave} = {proveedor.modelo}"))

        self.stdout.write("3. Interpretación completa (sin guardar):")
        resultado = interpretar(texto, registrar_pendientes=False)
        self.stdout.write(f"   motor: {resultado.motor}")
        for item in resultado.items:
            destino = item.destino.nombre if item.destino else "— sin identificar"
            self.stdout.write(f"   · «{item.fragmento}» → {destino} ({item.cantidad_g} g, {item.origen_resolucion})")
        for aviso in resultado.avisos:
            self.stdout.write(self.style.WARNING(f"   {aviso}"))
        self.stdout.write(self.style.SUCCESS("La integración con la IA funciona."))
