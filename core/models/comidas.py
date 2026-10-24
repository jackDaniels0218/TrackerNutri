"""
RF7 CRUD Registro de comidas y RF10 Correcciones.

Una comida nace en estado "interpretada" (lo que propuso el sistema), pasa a
"confirmada" cuando el usuario la aprueba y a "editada" si la corrige. Solo
las confirmadas o editadas cuentan en los totales. "Eliminar" es una baja
lógica: estado "descartada".
"""

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models.catalogo import Alimento, MetodoCoccion, Preparacion

CERO = Decimal("0")


class TipoComida(models.TextChoices):
    DESAYUNO = "desayuno", "Desayuno"
    ALMUERZO = "almuerzo", "Almuerzo"
    CENA = "cena", "Cena"
    MERIENDA = "merienda", "Merienda"
    BEBIDA = "bebida", "Bebida"
    OTRO = "otro", "Otro"


class OrigenComida(models.TextChoices):
    TEXTO = "texto", "Texto libre"
    MANUAL = "manual", "Búsqueda manual"
    FAVORITA = "favorita", "Favorita"


class EstadoComida(models.TextChoices):
    INTERPRETADA = "interpretada", "Interpretada (sin confirmar)"
    CONFIRMADA = "confirmada", "Confirmada"
    EDITADA = "editada", "Editada"
    DESCARTADA = "descartada", "Descartada"


class MotorInterpretacion(models.TextChoices):
    IA_EXTERNA = "ia_externa", "IA externa"
    MODELO_LOCAL = "modelo_local", "Modelo local"
    REGLAS = "reglas", "Reglas y léxico"
    MANUAL = "manual", "Búsqueda manual"


ESTADOS_QUE_CUENTAN = (EstadoComida.CONFIRMADA, EstadoComida.EDITADA)


class ComidaQuerySet(models.QuerySet):
    def que_cuentan(self):
        return self.filter(estado__in=ESTADOS_QUE_CUENTAN)


class Comida(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comidas")
    texto_original = models.CharField(max_length=500, blank=True)
    fecha_hora = models.DateTimeField(default=timezone.now)
    tipo = models.CharField(max_length=10, choices=TipoComida.choices, default=TipoComida.OTRO)
    origen = models.CharField(max_length=10, choices=OrigenComida.choices)
    estado = models.CharField(max_length=15, choices=EstadoComida.choices, default=EstadoComida.INTERPRETADA)

    # Totales (copia de lo calculado: el historial no cambia si cambia el catálogo).
    kcal = models.DecimalField(max_digits=7, decimal_places=1, default=CERO)
    proteinas = models.DecimalField(max_digits=6, decimal_places=1, default=CERO)
    carbohidratos = models.DecimalField(max_digits=6, decimal_places=1, default=CERO)
    azucares = models.DecimalField(max_digits=6, decimal_places=1, default=CERO)
    grasas = models.DecimalField(max_digits=6, decimal_places=1, default=CERO)
    aceite_g = models.DecimalField(max_digits=6, decimal_places=1, default=CERO)
    kcal_min = models.DecimalField(max_digits=7, decimal_places=1, default=CERO)
    kcal_max = models.DecimalField(max_digits=7, decimal_places=1, default=CERO)
    confianza = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal("1"))

    motor = models.CharField(max_length=15, choices=MotorInterpretacion.choices)
    version_motor = models.CharField(max_length=20)
    version_catalogo = models.PositiveIntegerField(null=True, blank=True)
    version_plantilla_ia = models.CharField(max_length=20, blank=True)
    sin_conexion = models.BooleanField(default=False)

    es_favorita = models.BooleanField(default=False)
    nombre_favorita = models.CharField(max_length=80, blank=True)
    preguntas = models.JSONField(
        default=list, blank=True, help_text="Preguntas de aclaración pendientes (máximo dos)."
    )

    clave_idempotencia = models.UUIDField(
        default=uuid.uuid4, help_text="Evita duplicar la comida por un doble envío."
    )
    creada_en = models.DateTimeField(auto_now_add=True)
    editada_en = models.DateTimeField(auto_now=True)

    objects = ComidaQuerySet.as_manager()

    class Meta:
        ordering = ["-fecha_hora"]
        indexes = [
            models.Index(fields=["usuario", "fecha_hora"], name="idx_comida_usuario_fecha"),
            models.Index(fields=["usuario", "estado"], name="idx_comida_usuario_estado"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["usuario", "clave_idempotencia"], name="comida_idempotente"
            )
        ]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} {timezone.localtime(self.fecha_hora):%Y-%m-%d %H:%M}"

    @property
    def fecha(self):
        return timezone.localtime(self.fecha_hora).date()

    @property
    def cuenta_en_totales(self) -> bool:
        return self.estado in ESTADOS_QUE_CUENTAN

    @property
    def items_activos(self):
        return self.items.filter(descartado=False)


class OrigenDato(models.TextChoices):
    CATALOGO = "catalogo", "Catálogo"
    SIMILITUD = "similitud", "Estimado por similitud"
    IA = "ia", "Inferido por IA"
    USUARIO = "usuario", "Ingresado por el usuario"


class ItemComida(models.Model):
    """
    Un componente de la comida, con su cálculo completo guardado.

    `detalle_calculo` conserva el desglose (ingredientes, agua, grasa perdida,
    aceite) para que cada número se pueda explicar (RNF25).
    """

    comida = models.ForeignKey(Comida, on_delete=models.CASCADE, related_name="items")
    alimento = models.ForeignKey(Alimento, on_delete=models.PROTECT, null=True, blank=True)
    preparacion = models.ForeignKey(Preparacion, on_delete=models.PROTECT, null=True, blank=True)
    nombre_mostrado = models.CharField(max_length=120)
    fragmento_texto = models.CharField(max_length=200, blank=True)
    cantidad_original = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    unidad_original = models.CharField(max_length=30, blank=True)
    cantidad_g = models.DecimalField(max_digits=8, decimal_places=1, null=True, blank=True)
    medida = models.CharField(max_length=20, blank=True, help_text="Medida casera usada, si la hubo.")
    fuente_cantidad = models.CharField(
        max_length=10, default="gramos",
        help_text="De dónde salió la cantidad: gramos, medida, unidad o defecto (porción por defecto).",
    )
    metodo = models.ForeignKey(MetodoCoccion, on_delete=models.PROTECT, null=True, blank=True)
    origen_metodo = models.CharField(
        max_length=10, default="explicito",
        help_text="explicito, implicito, defecto, ambiguo o no_aplica.",
    )
    tamano = models.CharField(max_length=10, blank=True)
    escurrido = models.BooleanField(default=False)
    aceite_agregado_g = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        help_text="Aceite que el usuario dijo agregar a la sartén.",
    )
    aplicar_rendimiento = models.BooleanField(
        default=False, help_text="Descontar hueso o parte no comestible (porciones caseras)."
    )
    aceite_g = models.DecimalField(max_digits=6, decimal_places=1, default=CERO)
    aceite_min_g = models.DecimalField(max_digits=6, decimal_places=1, default=CERO)
    aceite_max_g = models.DecimalField(max_digits=6, decimal_places=1, default=CERO)

    kcal = models.DecimalField(max_digits=7, decimal_places=1, null=True, blank=True)
    proteinas = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    carbohidratos = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    azucares = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    grasas = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    kcal_min = models.DecimalField(max_digits=7, decimal_places=1, null=True, blank=True)
    kcal_max = models.DecimalField(max_digits=7, decimal_places=1, null=True, blank=True)

    confianza = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal("1"))
    origen_dato = models.CharField(max_length=10, choices=OrigenDato.choices, default=OrigenDato.CATALOGO)
    editado = models.BooleanField(default=False, verbose_name="editado por el usuario")
    estimado = models.BooleanField(default=True)
    pendiente = models.BooleanField(
        default=False, help_text="No se reconoció: el usuario debe elegirlo o descartarlo."
    )
    descartado = models.BooleanField(default=False)
    notas = models.TextField(blank=True)
    detalle_calculo = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return self.nombre_mostrado

    @property
    def destino(self):
        return self.alimento or self.preparacion

    @property
    def tiene_valores(self) -> bool:
        return self.kcal is not None


class DiaRegistro(models.Model):
    """
    El usuario marca un día como completo cuando registró todo lo que comió.

    Evita falsas alertas de las salvaguardas y es un requisito para el ajuste
    semanal de la meta (actividades 16 y 17).
    """

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="dias")
    fecha = models.DateField()
    completo = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["usuario", "fecha"], name="dia_unico")]
        ordering = ["-fecha"]


class Correccion(models.Model):
    """Un usuario reporta que una estimación está mal (actividad 10)."""

    class Tipo(models.TextChoices):
        COMPONENTE = "componente", "Componente equivocado"
        CANTIDAD = "cantidad", "Cantidad"
        METODO = "metodo", "Método de cocción"
        VALOR = "valor_nutricional", "Valor nutricional"
        OTRO = "otro", "Otro"

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        EN_REVISION = "en_revision", "En revisión"
        ACEPTADA = "aceptada", "Aceptada"
        RECHAZADA = "rechazada", "Rechazada"

    item = models.ForeignKey(ItemComida, on_delete=models.SET_NULL, null=True, related_name="correcciones")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="correcciones"
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    valor_original = models.CharField(max_length=200)
    valor_sugerido = models.CharField(max_length=200)
    comentario = models.TextField(blank=True)
    aplicada_a_comida = models.BooleanField(default=False)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.PENDIENTE)
    revisor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    resolucion = models.TextField(blank=True)
    fecha_reporte = models.DateTimeField(auto_now_add=True)
    fecha_revision = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-fecha_reporte"]
        verbose_name = "corrección"
        verbose_name_plural = "correcciones"

    def __str__(self) -> str:
        return f"{self.get_tipo_display()}: {self.valor_original} → {self.valor_sugerido}"
