"""
Comprueba de extremo a extremo que la integración con la IA funciona de verdad.

    python manage.py probar_ia
    python manage.py probar_ia --texto "dos huevos fritos y una arepa asada"
    python manage.py probar_ia --solo-modelos

A diferencia de las pruebas automatizadas (que simulan la respuesta), este
comando SÍ llama a la API real. Por eso no forma parte de `manage.py test`:
gasta crédito y necesita conexión.

Hace cuatro comprobaciones, en orden, y se detiene en la primera que falle:

  1. ¿Hay una clave configurada?
  2. ¿La clave es válida y el modelo de `OPENAI_MODEL` existe en esta cuenta?
  3. ¿El modelo devuelve el JSON con la estructura esperada?
  4. ¿Los alimentos se emparejan con el catálogo y los nutrientes se calculan?

Sirve para dos cosas: verificar la configuración al instalar el proyecto y
demostrar en vivo, durante la sustentación, que la IA está realmente conectada.
"""

from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand

from core.models import Alimento
from core.services import ai_service
from core.services.nutrition import calcular

TEXTO_POR_DEFECTO = (
    "Hoy almorcé una arepa frita mediana, 150 gramos de carne de res asada, "
    "una porción de arroz y una gaseosa de 400 ml"
)


class Command(BaseCommand):
    help = "Prueba la integración real con la API de IA (consume crédito)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--texto",
            default=TEXTO_POR_DEFECTO,
            help="Descripción de comida que se enviará a la IA.",
        )
        parser.add_argument(
            "--solo-modelos",
            action="store_true",
            help="Solo verifica la clave y lista los modelos, sin analizar texto.",
        )

    # --- Utilidades de presentación -----------------------------------------

    def _titulo(self, texto):
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(texto))

    def _ok(self, texto):
        self.stdout.write(self.style.SUCCESS(f"  OK  {texto}"))

    def _fallo(self, texto):
        self.stdout.write(self.style.ERROR(f"  --  {texto}"))

    def _nota(self, texto):
        self.stdout.write(f"      {texto}")

    # --- Paso 1: clave configurada ------------------------------------------

    def _comprobar_clave(self) -> bool:
        self._titulo("1. Clave de la API")

        if not ai_service.ia_configurada():
            self._fallo("No hay OPENAI_API_KEY configurada.")
            self._nota("")
            self._nota("Para conseguirla:")
            self._nota("  1. Entra en https://platform.openai.com/api-keys")
            self._nota("  2. Crea una clave nueva (empieza por 'sk-').")
            self._nota("  3. Necesitas saldo de API: es un producto aparte de")
            self._nota("     la suscripción de ChatGPT y se paga por separado.")
            self._nota("  4. Ponla en tu archivo .env:   OPENAI_API_KEY=sk-...")
            self._nota("")
            self._nota("Sin clave, la aplicación sigue funcionando con el")
            self._nota("registro manual: python manage.py runserver")
            return False

        clave = settings.OPENAI_API_KEY
        # Nunca se imprime la clave completa.
        self._ok(f"Configurada ({clave[:6]}…{clave[-4:]}, {len(clave)} caracteres).")
        return True

    # --- Paso 2: la clave sirve y el modelo existe --------------------------

    def _comprobar_modelo(self) -> bool:
        self._titulo("2. Validez de la clave y del modelo")
        import openai

        cliente = openai.OpenAI(
            api_key=settings.OPENAI_API_KEY, timeout=settings.OPENAI_TIMEOUT
        )
        try:
            disponibles = sorted(m.id for m in cliente.models.list())
        except openai.AuthenticationError:
            self._fallo("La clave fue rechazada por OpenAI.")
            self._nota("Revisa que la copiaste completa y que sigue activa.")
            return False
        except openai.APIConnectionError:
            self._fallo("No se pudo conectar con la API.")
            self._nota("Revisa tu conexión o si hay un proxy o cortafuegos.")
            return False
        except openai.APIError as exc:
            self._fallo(f"Error de la API: {type(exc).__name__}")
            return False

        self._ok(f"Clave válida. {len(disponibles)} modelos disponibles.")

        configurado = settings.OPENAI_MODEL
        if configurado in disponibles:
            self._ok(f"El modelo configurado «{configurado}» está disponible.")
        else:
            self._fallo(f"El modelo «{configurado}» NO está en tu cuenta.")
            sugerencias = [m for m in disponibles if "gpt" in m][:12]
            if sugerencias:
                self._nota("Modelos con 'gpt' disponibles para ti:")
                for m in sugerencias:
                    self._nota(f"  · {m}")
            self._nota("")
            self._nota("Cambia OPENAI_MODEL en tu .env por uno de la lista.")
            return False
        return True

    # --- Paso 3 y 4: análisis real y cálculo --------------------------------

    def _analizar(self, texto: str) -> bool:
        self._titulo("3. Interpretación del texto")
        self._nota(f'Enviando: "{texto}"')

        try:
            items = ai_service.analizar_texto(texto)
        except ai_service.ErrorIA as exc:
            self._fallo(f"{type(exc).__name__}: {exc}")
            self._nota(f"Mensaje que vería el usuario: {exc.mensaje_usuario}")
            return False

        self._ok(f"La IA identificó {len(items)} alimento(s).")

        self._titulo("4. Emparejamiento con el catálogo y cálculo")
        total = Decimal("0")
        sin_datos = 0

        for item in items:
            alimento: Alimento | None = item["alimento"]
            etiqueta = item["nombre"]
            cantidad = item["cantidad"]
            unidad = item["unidad"]
            preparacion = item["metodo_preparacion"]

            self.stdout.write("")
            self.stdout.write(f'  «{etiqueta}»  {cantidad} {unidad}  [{preparacion}]')

            if alimento is None:
                self._fallo("Sin coincidencia en el catálogo: no se calcula nada.")
                sin_datos += 1
                continue

            self._ok(f"Catálogo: {alimento}")

            if cantidad is None:
                self._fallo("La IA no dio una cantidad: el usuario debe indicarla.")
                sin_datos += 1
                continue

            resultado = calcular(
                alimento, cantidad, unidad, metodo_declarado=preparacion
            )
            if not resultado.calculado:
                self._fallo(f"No se pudo calcular: {resultado.motivo}")
                sin_datos += 1
                continue

            total += resultado.calorias
            self._nota(
                f"{resultado.calorias} kcal · "
                f"P {resultado.proteinas} g · "
                f"C {resultado.carbohidratos} g · "
                f"G {resultado.grasas} g"
                + ("  (estimado)" if resultado.es_estimado else "")
            )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"  TOTAL CALCULADO: {total} kcal"))
        if sin_datos:
            self.stdout.write(
                self.style.WARNING(
                    f"  {sin_datos} alimento(s) quedaron sin datos. "
                    "No se cuentan como cero."
                )
            )
        return True

    # --- Orquestación --------------------------------------------------------

    def handle(self, *args, **opciones):
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "Prueba de la integración real con la API de IA"
            )
        )
        self.stdout.write(
            "Esto hace llamadas reales y consume crédito de tu cuenta."
        )

        if not Alimento.objects.exists():
            self._fallo("El catálogo está vacío.")
            self._nota("Ejecuta antes: python manage.py loaddata catalogo_alimentos")
            return

        if not self._comprobar_clave():
            return
        if not self._comprobar_modelo():
            return
        if opciones["solo_modelos"]:
            self.stdout.write("")
            self._ok("Configuración correcta. Omitido el análisis (--solo-modelos).")
            return
        if not self._analizar(opciones["texto"]):
            return

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "La integración con la IA funciona de extremo a extremo."
            )
        )
