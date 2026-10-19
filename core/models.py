"""
Modelos de datos del tracker nutricional.

Las cuatro entidades del dominio son:

* PerfilNutricional : datos opcionales del usuario y su meta diaria de calorías.
* Alimento          : catálogo de alimentos y preparaciones colombianas.
* RegistroComida    : una comida que un usuario registró en una fecha.
* DetalleComida     : cada alimento concreto dentro de esa comida.

El usuario se toma del sistema de autenticación de Django
(django.contrib.auth.models.User); no se implementa un login propio.
"""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Unidad(models.TextChoices):
    """Unidades admitidas al registrar una cantidad."""

    GRAMOS = "g", "gramos"
    MILILITROS = "ml", "mililitros"
    UNIDAD = "unidad", "unidad"
    PORCION = "porcion", "porción"


class UnidadReferencia(models.TextChoices):
    """Base sobre la que están expresados los valores nutricionales."""

    GRAMOS_100 = "g", "por 100 g"
    MILILITROS_100 = "ml", "por 100 ml"


class MetodoPreparacion(models.TextChoices):
    """
    Distinguir la preparación es clave en el proyecto: una arepa frita y una
    arepa asada son dos filas distintas del catálogo, no el mismo alimento.
    """

    NO_APLICA = "no_aplica", "No aplica"
    NO_ESPECIFICADA = "no_especificada", "No especificada"
    ASADO = "asado", "Asado"
    FRITO = "frito", "Frito"
    COCIDO = "cocido", "Cocido"
    CRUDO = "crudo", "Crudo"
    HORNEADO = "horneado", "Horneado"


class OrigenRegistro(models.TextChoices):
    """Cómo se creó la comida: interpretada por la IA o escrita a mano."""

    IA = "ia", "Interpretado por IA"
    MANUAL = "manual", "Registro manual"


class PerfilNutricional(models.Model):
    """
    Datos nutricionales del usuario. Se crea automáticamente al registrarse
    (ver core/signals.py) con una meta por defecto que el usuario puede cambiar
    desde la página de perfil.

    Solo se guardan los campos que la aplicación realmente usa. El peso y la
    estatura son opcionales e informativos: la meta calórica se configura a
    mano, no se calcula con fórmulas clínicas.
    """

    META_CALORIAS_POR_DEFECTO = 2000

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="perfil",
        verbose_name="usuario",
    )
    edad = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name="edad (años)"
    )
    peso_kg = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("1"))],
        verbose_name="peso (kg)",
    )
    estatura_cm = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name="estatura (cm)"
    )
    meta_calorias_diaria = models.PositiveIntegerField(
        default=META_CALORIAS_POR_DEFECTO,
        validators=[MinValueValidator(1)],
        verbose_name="meta diaria de calorías (kcal)",
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "perfil nutricional"
        verbose_name_plural = "perfiles nutricionales"

    def __str__(self) -> str:
        return f"Perfil de {self.usuario.username}"


class Alimento(models.Model):
    """
    Un alimento o preparación del catálogo.

    Los valores nutricionales se guardan siempre por 100 g o por 100 ml
    (campo `unidad_referencia`), que es la forma en que vienen publicados en
    las tablas de composición de alimentos. El motor de cálculo
    (core/services/nutrition.py) hace la regla de tres a partir de ahí.

    `gramos_por_unidad` guarda la equivalencia documentada de "1 unidad"
    (por ejemplo, una arepa mediana). Si está vacío, el sistema no inventa un
    peso: pide confirmación al usuario.
    """

    nombre = models.CharField(max_length=120, verbose_name="nombre")
    categoria = models.CharField(max_length=60, verbose_name="categoría")
    unidad_referencia = models.CharField(
        max_length=4,
        choices=UnidadReferencia.choices,
        default=UnidadReferencia.GRAMOS_100,
        verbose_name="los valores están expresados",
    )
    calorias = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        verbose_name="kcal por 100 g/ml",
    )
    proteinas = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        verbose_name="proteínas (g) por 100 g/ml",
    )
    carbohidratos = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        verbose_name="carbohidratos (g) por 100 g/ml",
    )
    grasas = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        verbose_name="grasas (g) por 100 g/ml",
    )
    metodo_preparacion = models.CharField(
        max_length=20,
        choices=MetodoPreparacion.choices,
        default=MetodoPreparacion.NO_APLICA,
        verbose_name="método de preparación",
    )
    gramos_por_unidad = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
        verbose_name="equivalencia de 1 unidad (g o ml)",
        help_text="Peso o volumen documentado de una unidad o porción habitual.",
    )
    descripcion_porcion = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="porción de referencia",
        help_text="Ej.: 'arepa mediana de 100 g'.",
    )
    fuente = models.CharField(
        max_length=200,
        verbose_name="fuente de los valores",
        help_text="Tabla de composición o estimación documentada de la que provienen.",
    )
    valores_aproximados = models.BooleanField(
        default=True,
        verbose_name="los valores son aproximados",
        help_text="Marcado cuando la receta o la porción varían de forma importante.",
    )
    notas = models.TextField(blank=True, verbose_name="notas")
    activo = models.BooleanField(default=True, verbose_name="activo")

    class Meta:
        verbose_name = "alimento"
        verbose_name_plural = "alimentos"
        ordering = ["nombre", "metodo_preparacion"]
        constraints = [
            # Un mismo alimento puede repetirse solo si cambia la preparación:
            # "arepa de maíz" asada y frita son dos registros válidos.
            models.UniqueConstraint(
                fields=["nombre", "metodo_preparacion"],
                name="alimento_unico_por_preparacion",
            )
        ]

    def __str__(self) -> str:
        if self.metodo_preparacion in (
            MetodoPreparacion.NO_APLICA,
            MetodoPreparacion.NO_ESPECIFICADA,
        ):
            return self.nombre
        return f"{self.nombre} ({self.get_metodo_preparacion_display().lower()})"

    @property
    def es_liquido(self) -> bool:
        """True cuando los valores están expresados por 100 ml."""
        return self.unidad_referencia == UnidadReferencia.MILILITROS_100


class RegistroComida(models.Model):
    """
    Una comida registrada por un usuario en una fecha concreta.

    El campo `confirmado` separa los borradores (lo que la IA propuso y el
    usuario aún no aprobó) de lo que cuenta para el resumen diario: el panel
    solo suma comidas confirmadas.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="comidas",
        verbose_name="usuario",
    )
    fecha = models.DateField(default=timezone.localdate, verbose_name="fecha")
    hora = models.TimeField(null=True, blank=True, verbose_name="hora")
    descripcion = models.CharField(
        max_length=300,
        verbose_name="descripción",
        help_text="Texto que escribió el usuario o nombre que le dio a la comida.",
    )
    origen = models.CharField(
        max_length=10,
        choices=OrigenRegistro.choices,
        default=OrigenRegistro.MANUAL,
        verbose_name="origen del registro",
    )
    confirmado = models.BooleanField(default=False, verbose_name="confirmado")
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "registro de comida"
        verbose_name_plural = "registros de comidas"
        ordering = ["-fecha", "-creado_en"]
        indexes = [
            # El panel y el historial consultan siempre por usuario + fecha.
            models.Index(fields=["usuario", "fecha"], name="idx_comida_usuario_fecha"),
        ]

    def __str__(self) -> str:
        return f"{self.descripcion} ({self.fecha})"

    def totales(self) -> dict:
        """
        Suma los nutrientes de todos sus detalles.

        Se delega en el motor de cálculo para que la fórmula viva en un solo
        sitio. Devuelve un diccionario con kcal, proteínas, carbohidratos,
        grasas y la cantidad de detalles sin datos nutricionales.
        """
        from core.services.nutrition import sumar_detalles

        return sumar_detalles(self.detalles.all())


class DetalleComida(models.Model):
    """
    Un alimento concreto dentro de una comida.

    Guarda una INSTANTÁNEA de los valores nutricionales usados en el momento
    del registro (campos `*_ref`). Así, si mañana se corrige la ficha de la
    arepa frita en el catálogo, el historial del usuario no cambia solo.

    Cuando la IA menciona un alimento que no existe en el catálogo, el detalle
    se guarda con `alimento = None` y los campos nutricionales en NULL: el
    sistema no inventa calorías. Esos detalles se reportan aparte como
    "pendientes de datos".
    """

    registro = models.ForeignKey(
        RegistroComida,
        on_delete=models.CASCADE,
        related_name="detalles",
        verbose_name="registro de comida",
    )
    alimento = models.ForeignKey(
        Alimento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="detalles",
        verbose_name="alimento del catálogo",
        help_text="Puede quedar vacío si no hubo coincidencia en el catálogo.",
    )
    nombre_mostrado = models.CharField(
        max_length=120,
        verbose_name="nombre mostrado",
        help_text="Lo que ve el usuario, aunque no coincida con el catálogo.",
    )
    cantidad = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        verbose_name="cantidad",
    )
    unidad = models.CharField(
        max_length=10,
        choices=Unidad.choices,
        default=Unidad.GRAMOS,
        verbose_name="unidad",
    )
    metodo_preparacion = models.CharField(
        max_length=20,
        choices=MetodoPreparacion.choices,
        default=MetodoPreparacion.NO_ESPECIFICADA,
        verbose_name="método de preparación",
    )

    # --- Instantánea de la referencia nutricional aplicada ------------------
    cantidad_base = models.DecimalField(
        max_digits=9,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="cantidad convertida (g o ml)",
        help_text="Resultado de convertir cantidad + unidad a la base del alimento.",
    )
    unidad_referencia_ref = models.CharField(
        max_length=4,
        choices=UnidadReferencia.choices,
        blank=True,
        verbose_name="base de la referencia aplicada",
    )
    calorias_ref = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True,
        verbose_name="kcal por 100 aplicadas",
    )
    proteinas_ref = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        verbose_name="proteínas por 100 aplicadas",
    )
    carbohidratos_ref = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        verbose_name="carbohidratos por 100 aplicados",
    )
    grasas_ref = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        verbose_name="grasas por 100 aplicadas",
    )

    # --- Resultado del cálculo ---------------------------------------------
    calorias = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name="kcal",
    )
    proteinas = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True,
        verbose_name="proteínas (g)",
    )
    carbohidratos = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True,
        verbose_name="carbohidratos (g)",
    )
    grasas = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True,
        verbose_name="grasas (g)",
    )

    es_estimado = models.BooleanField(
        default=False,
        verbose_name="valores estimados",
        help_text="La cantidad se infirió o los valores del catálogo son aproximados.",
    )
    necesita_confirmacion = models.BooleanField(
        default=False,
        verbose_name="necesita confirmación del usuario",
    )
    observacion = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="observación",
        help_text="Por qué faltan datos o por qué el valor es aproximado.",
    )

    class Meta:
        verbose_name = "detalle de comida"
        verbose_name_plural = "detalles de comida"
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.nombre_mostrado} - {self.cantidad} {self.unidad}"

    @property
    def tiene_datos_nutricionales(self) -> bool:
        """False cuando no se pudo calcular (alimento fuera del catálogo)."""
        return self.calorias is not None
