"""
RF8 CRUD Metas calóricas y RF9 Seguimiento de peso.

Solo puede haber una meta vigente por usuario (restricción de la base de
datos). Las metas anteriores se conservan como historial: nunca se borran.
"""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class OrigenMeta(models.TextChoices):
    INICIAL = "inicial", "Inicial"
    AUTOMATICO = "ajuste_automatico", "Ajuste automático semanal"
    MANUAL = "ajuste_manual", "Ajuste manual"
    MANTENIMIENTO = "mantenimiento", "Paso a mantenimiento"
    RECALCULO = "recalculo", "Recálculo por cambio de perfil"
    REVERSION = "reversion", "Reversión de un ajuste"


class MetaCalorica(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="metas")
    fecha_inicio = models.DateField(default=timezone.localdate)
    fecha_fin = models.DateField(null=True, blank=True)
    vigente = models.BooleanField(default=True)
    tmb = models.DecimalField(max_digits=6, decimal_places=1, verbose_name="TMB (kcal)")
    gasto_total = models.DecimalField(max_digits=6, decimal_places=1, verbose_name="gasto energético total, GET (kcal)")
    kcal_dia = models.DecimalField(max_digits=6, decimal_places=1, verbose_name="meta diaria (kcal)")
    deficit_pct = models.DecimalField(max_digits=4, decimal_places=1)
    proteinas_g = models.DecimalField(max_digits=5, decimal_places=1)
    carbohidratos_g = models.DecimalField(max_digits=5, decimal_places=1)
    grasas_g = models.DecimalField(max_digits=5, decimal_places=1)
    origen = models.CharField(max_length=20, choices=OrigenMeta.choices)
    motivo = models.TextField()
    explicacion = models.JSONField(default=dict, help_text="Pasos del cálculo, para mostrarlos al usuario.")
    solo_informativa = models.BooleanField(
        default=False, help_text="Salvaguarda activa: no se aplica déficit."
    )
    revertida = models.BooleanField(default=False)
    revertible_hasta = models.DateTimeField(null=True, blank=True)
    meta_anterior = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creada_en"]
        verbose_name = "meta calórica"
        verbose_name_plural = "metas calóricas"
        constraints = [
            models.UniqueConstraint(
                fields=["usuario"],
                condition=models.Q(vigente=True),
                name="una_meta_vigente_por_usuario",
            )
        ]

    def __str__(self) -> str:
        return f"{self.kcal_dia:.0f} kcal ({self.get_origen_display()})"

    @property
    def puede_revertirse(self) -> bool:
        return (
            self.vigente
            and not self.revertida
            and self.meta_anterior_id is not None
            and self.revertible_hasta is not None
            and self.revertible_hasta > timezone.now()
        )

    def delete(self, *args, **kwargs):
        raise ValidationError("El historial de metas no se puede borrar.")


class Pesaje(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pesajes")
    fecha = models.DateField(default=timezone.localdate)
    peso_kg = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        validators=[MinValueValidator(Decimal("30")), MaxValueValidator(Decimal("300"))],
    )
    observacion = models.CharField(max_length=200, blank=True)
    registrado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha"]
        constraints = [models.UniqueConstraint(fields=["usuario", "fecha"], name="un_pesaje_por_dia")]

    def __str__(self) -> str:
        return f"{self.fecha}: {self.peso_kg} kg"
