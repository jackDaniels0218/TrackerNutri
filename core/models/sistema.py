"""
Modelos transversales:

* RF11 Parametro              — valores configurables del sistema.
* RF20 Notificacion           — avisos dentro de la app (y copia por correo).
* RF21 UsoIA, CacheInterpretacion — consumo, costo y caché del proveedor de IA.
* RF22 Bitacora               — auditoría de acciones relevantes (solo inserción).
* RF19 FraseReferencia, EjecucionExactitud — conjunto de prueba de exactitud.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.models.catalogo import VersionCatalogo


class Parametro(models.Model):
    class Tipo(models.TextChoices):
        ENTERO = "entero", "Entero"
        DECIMAL = "decimal", "Decimal"
        TEXTO = "texto", "Texto"
        BOOLEANO = "booleano", "Sí / No"
        JSON = "json", "Lista o tabla (JSON)"

    class Grupo(models.TextChoices):
        NUTRICIONAL = "nutricional", "Nutricional (lo edita el Curador)"
        SEGURIDAD_USUARIO = "salvaguardas", "Salvaguardas de salud"
        IA = "ia", "Proveedor de IA"
        SISTEMA = "sistema", "Sistema"

    clave = models.SlugField(max_length=60, unique=True)
    valor = models.TextField()
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    grupo = models.CharField(max_length=15, choices=Grupo.choices)
    descripcion = models.CharField(max_length=250)
    modificado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    modificado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["grupo", "clave"]
        verbose_name = "parámetro"
        verbose_name_plural = "parámetros del sistema"

    def __str__(self) -> str:
        return f"{self.clave} = {self.valor}"

    def delete(self, *args, **kwargs):
        raise ValidationError("Los parámetros no se eliminan, solo se modifican.")


class Notificacion(models.Model):
    class Tipo(models.TextChoices):
        RECORDATORIO = "recordatorio", "Recordatorio"
        RESUMEN = "resumen", "Resumen semanal"
        META = "meta", "Ajuste de meta"
        CUIDADO = "cuidado", "Alerta de cuidado"
        CORRECCION = "correccion", "Respuesta a una corrección"
        CURACION = "curacion", "Pendientes de curación"
        EXACTITUD = "exactitud", "Pruebas de exactitud"
        SISTEMA = "sistema", "Sistema"

    destinatario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notificaciones"
    )
    tipo = models.CharField(max_length=15, choices=Tipo.choices)
    titulo = models.CharField(max_length=120)
    mensaje = models.TextField()
    url = models.CharField(max_length=200, blank=True, help_text="Registro relacionado (opcional).")
    leida = models.BooleanField(default=False)
    enviada_por_correo = models.BooleanField(default=False)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creada_en"]
        indexes = [models.Index(fields=["destinatario", "leida"], name="idx_notif_destinatario")]

    def __str__(self) -> str:
        return self.titulo


class UsoIA(models.Model):
    """
    Una llamada (o un intento) al proveedor de IA.

    No guarda el texto enviado ni la respuesta: solo métricas. El usuario se
    conserva para aplicar el límite diario, pero los paneles solo muestran
    agregados.
    """

    class Resultado(models.TextChoices):
        EXITO = "exito", "Éxito"
        CACHE = "cache", "Resuelto desde caché"
        FALLO = "fallo", "Fallo del proveedor"
        INVALIDA = "invalida", "Respuesta inválida"
        LIMITE = "limite_diario", "Límite diario alcanzado"
        PRESUPUESTO = "presupuesto", "Presupuesto agotado"
        SIN_CONSENTIMIENTO = "sin_consentimiento", "Sin autorización del usuario"

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    fecha = models.DateTimeField(auto_now_add=True)
    proveedor = models.CharField(max_length=20)
    modelo = models.CharField(max_length=60, blank=True)
    version_plantilla = models.CharField(max_length=20, blank=True)
    resultado = models.CharField(max_length=20, choices=Resultado.choices)
    tipo_error = models.CharField(max_length=60, blank=True)
    latencia_ms = models.PositiveIntegerField(default=0)
    tokens_entrada = models.PositiveIntegerField(default=0)
    tokens_salida = models.PositiveIntegerField(default=0)
    costo_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0)

    class Meta:
        ordering = ["-fecha"]
        indexes = [models.Index(fields=["usuario", "fecha"], name="idx_usoia_usuario_fecha")]
        verbose_name = "uso de IA"
        verbose_name_plural = "uso de IA"


class CacheInterpretacion(models.Model):
    """Interpretaciones de frases ya vistas, para no pagar dos veces."""

    clave = models.CharField(max_length=64, unique=True, help_text="SHA-256 del texto normalizado.")
    version_plantilla = models.CharField(max_length=20)
    resultado = models.JSONField()
    usos = models.PositiveIntegerField(default=0)
    creada_en = models.DateTimeField(auto_now_add=True)


class Bitacora(models.Model):
    """Auditoría funcional. Solo inserción: no se edita ni se borra."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    accion = models.CharField(max_length=60)
    entidad = models.CharField(max_length=60, blank=True)
    entidad_id = models.CharField(max_length=40, blank=True)
    detalle = models.TextField(blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha"]
        verbose_name = "registro de auditoría"
        verbose_name_plural = "bitácora de auditoría"
        indexes = [models.Index(fields=["fecha"], name="idx_bitacora_fecha")]

    def __str__(self) -> str:
        return f"{self.fecha:%Y-%m-%d %H:%M} {self.accion}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("La bitácora es de solo inserción.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("La bitácora no se puede borrar.")


class FraseReferencia(models.Model):
    """
    Frase regional con su resultado esperado, validado por un nutricionista.

    `componentes_esperados` es una lista de {"nombre": ..., "metodo": ...}
    donde "nombre" es el nombre exacto de un alimento o preparación del
    catálogo y "metodo" la clave del método de cocción.
    """

    class Origen(models.TextChoices):
        INICIAL = "inicial", "Conjunto inicial"
        CORRECCION = "correccion", "Derivada de una corrección aceptada"

    texto = models.CharField(max_length=500)
    componentes_esperados = models.JSONField()
    kcal_referencia = models.DecimalField(max_digits=7, decimal_places=1, null=True, blank=True)
    validada = models.BooleanField(default=False, help_text="Validada por un nutricionista.")
    origen = models.CharField(max_length=12, choices=Origen.choices, default=Origen.INICIAL)
    activa = models.BooleanField(default=True)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "frase de referencia"
        verbose_name_plural = "conjunto de prueba de exactitud"

    def __str__(self) -> str:
        return self.texto


class EjecucionExactitud(models.Model):
    version = models.ForeignKey(VersionCatalogo, on_delete=models.SET_NULL, null=True, related_name="ejecuciones")
    fecha = models.DateTimeField(auto_now_add=True)
    total_frases = models.PositiveIntegerField()
    identificacion_pct = models.DecimalField(max_digits=5, decimal_places=1)
    coccion_pct = models.DecimalField(max_digits=5, decimal_places=1)
    error_energia_pct = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    aprobada = models.BooleanField()
    detalle = models.JSONField(default=list)
    ejecutada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-fecha"]
