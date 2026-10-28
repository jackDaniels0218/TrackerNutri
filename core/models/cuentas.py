"""
RF1 CRUD Usuarios, RF2 CRUD Perfil nutricional y registro de consentimientos.

El usuario se apoya en django.contrib.auth.models.User, que ya resuelve el
correo, el nombre, la contraseña con hash y sal (PBKDF2), la fecha de registro
y el último acceso. `Cuenta` añade lo que el SRS pide y Django no trae: rol,
estado, autorizaciones, intentos fallidos y avance del registro.
"""

from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Rol(models.TextChoices):
    USUARIO = "usuario", "Usuario"
    CURADOR = "curador", "Curador nutricional"
    ADMINISTRADOR = "administrador", "Administrador"


class EstadoCuenta(models.TextChoices):
    ACTIVO = "activo", "Activo"
    INACTIVO = "inactivo", "Inactivo"
    BLOQUEADO = "bloqueado", "Bloqueado"


class Cuenta(models.Model):
    """
    Datos de la cuenta que complementan al User de Django (usu_*).

    El rol no cambia después de creada la cuenta (regla del SRS, actividad 1):
    `save()` lo impide.
    """

    # Pasos del registro en tres etapas (actividad 12).
    PASO_CUENTA = 1
    PASO_PERFIL = 2
    PASO_META = 3
    REGISTRO_COMPLETO = 4

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cuenta"
    )
    rol = models.CharField(max_length=15, choices=Rol.choices, default=Rol.USUARIO)
    estado = models.CharField(
        max_length=10, choices=EstadoCuenta.choices, default=EstadoCuenta.ACTIVO
    )
    acepta_datos = models.BooleanField(
        default=False, verbose_name="autoriza el tratamiento de datos personales"
    )
    fecha_acepta_datos = models.DateTimeField(null=True, blank=True)
    acepta_ia = models.BooleanField(
        default=False, verbose_name="autoriza enviar el texto de sus comidas a una IA externa"
    )
    fecha_acepta_ia = models.DateTimeField(null=True, blank=True)
    intentos_fallidos = models.PositiveSmallIntegerField(default=0)
    bloqueado_hasta = models.DateTimeField(null=True, blank=True)
    paso_registro = models.PositiveSmallIntegerField(default=PASO_CUENTA)
    seguimiento_pausado = models.BooleanField(
        default=False, verbose_name="seguimiento en pausa"
    )
    recibir_resumen_semanal = models.BooleanField(default=True)
    autoriza_soporte_hasta = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Mientras esté vigente, el Administrador puede ver sus datos para soporte.",
    )

    class Meta:
        verbose_name = "cuenta"
        verbose_name_plural = "cuentas"

    def __str__(self) -> str:
        return f"{self.usuario.email or self.usuario.username} ({self.get_rol_display()})"

    def save(self, *args, **kwargs):
        if self.pk:
            rol_original = Cuenta.objects.filter(pk=self.pk).values_list("rol", flat=True).first()
            if rol_original and rol_original != self.rol:
                raise ValidationError("El rol de una cuenta no cambia después de creada.")
        super().save(*args, **kwargs)

    @property
    def es_interna(self) -> bool:
        """Curador y Administrador: se desactivan, nunca se eliminan."""
        return self.rol in (Rol.CURADOR, Rol.ADMINISTRADOR)

    @property
    def esta_bloqueada(self) -> bool:
        if self.estado == EstadoCuenta.BLOQUEADO:
            return True
        return bool(self.bloqueado_hasta and self.bloqueado_hasta > timezone.now())

    @property
    def registro_completo(self) -> bool:
        return self.rol != Rol.USUARIO or self.paso_registro >= self.REGISTRO_COMPLETO

    @property
    def soporte_autorizado(self) -> bool:
        return bool(self.autoriza_soporte_hasta and self.autoriza_soporte_hasta > timezone.now())


class TipoConsentimiento(models.TextChoices):
    DATOS = "datos", "Tratamiento de datos personales"
    IA = "ia", "Envío del texto de comidas a IA externa"


class Consentimiento(models.Model):
    """
    Registro inmutable de autorizaciones otorgadas o retiradas (actividad 22).

    Cada cambio crea una fila nueva; las anteriores nunca se modifican.
    """

    VERSION_TEXTO_ACTUAL = "1.0"

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="consentimientos"
    )
    tipo = models.CharField(max_length=10, choices=TipoConsentimiento.choices)
    otorgado = models.BooleanField()
    version_texto = models.CharField(max_length=10, default=VERSION_TEXTO_ACTUAL)
    ip = models.GenericIPAddressField(null=True, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "consentimiento"
        verbose_name_plural = "registro de consentimientos"
        ordering = ["-fecha"]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("El registro de consentimientos es de solo inserción.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("El registro de consentimientos no se puede borrar.")


class Sexo(models.TextChoices):
    FEMENINO = "femenino", "Femenino"
    MASCULINO = "masculino", "Masculino"


class NivelActividad(models.TextChoices):
    SEDENTARIO = "sedentario", "Sedentario"
    LIGERO = "ligero", "Ligero"
    MODERADO = "moderado", "Moderado"
    ALTO = "alto", "Alto"
    MUY_ALTO = "muy_alto", "Muy alto"


class Objetivo(models.TextChoices):
    PERDER = "perder", "Perder peso"
    MANTENER = "mantener", "Mantener peso"


class Ritmo(models.TextChoices):
    LENTO = "lento", "Lento"
    MODERADO = "moderado", "Moderado"


class PerfilNutricional(models.Model):
    """
    Datos con los que se calcula la meta (per_*). Solo los ve su dueño.

    Las validaciones de rango vienen literalmente del SRS (actividad 2).
    """

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil"
    )
    fecha_nacimiento = models.DateField()
    sexo = models.CharField(max_length=10, choices=Sexo.choices)
    estatura_cm = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(120), MaxValueValidator(230)]
    )
    peso_inicial_kg = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        validators=[MinValueValidator(Decimal("30")), MaxValueValidator(Decimal("300"))],
    )
    fecha_peso_inicial = models.DateField(default=timezone.localdate)
    nivel_actividad = models.CharField(
        max_length=12, choices=NivelActividad.choices, default=NivelActividad.LIGERO
    )
    objetivo = models.CharField(max_length=10, choices=Objetivo.choices, default=Objetivo.PERDER)
    peso_meta_kg = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("30")), MaxValueValidator(Decimal("300"))],
    )
    ritmo = models.CharField(max_length=10, choices=Ritmo.choices, default=Ritmo.LENTO)
    gestante_lactante = models.BooleanField(
        default=False, verbose_name="en gestación o lactancia"
    )
    requiere_acompanamiento = models.BooleanField(
        default=False,
        verbose_name="tiene una condición de salud o alimentación que requiere acompañamiento profesional",
    )
    ocultar_cifras = models.BooleanField(
        default=False, verbose_name="ocultar el peso y las cifras de calorías"
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "perfil nutricional"
        verbose_name_plural = "perfiles nutricionales"

    def __str__(self) -> str:
        return f"Perfil de {self.usuario}"

    @staticmethod
    def calcular_edad(fecha_nacimiento: date, hoy: date | None = None) -> int:
        hoy = hoy or timezone.localdate()
        cumplio = (hoy.month, hoy.day) >= (fecha_nacimiento.month, fecha_nacimiento.day)
        return hoy.year - fecha_nacimiento.year - (0 if cumplio else 1)

    @property
    def edad(self) -> int:
        return self.calcular_edad(self.fecha_nacimiento)

    def imc_para(self, peso_kg) -> Decimal:
        metros = Decimal(self.estatura_cm) / 100
        return (Decimal(peso_kg) / (metros * metros)).quantize(Decimal("0.1"))

    def clean(self):
        errores = {}
        if self.fecha_nacimiento and self.calcular_edad(self.fecha_nacimiento) < 18:
            errores["fecha_nacimiento"] = "Debes ser mayor de 18 años para usar NutriRegional."
        if self.peso_meta_kg and self.estatura_cm:
            from core.services.parametros import parametro

            imc = self.imc_para(self.peso_meta_kg)
            minimo = parametro("imc_meta_minimo")
            maximo = parametro("imc_meta_maximo")
            if not (minimo <= imc <= maximo):
                errores["peso_meta_kg"] = (
                    f"Ese peso meta da un índice de masa corporal de {imc}, fuera del "
                    f"rango saludable ({minimo}–{maximo}) para tu estatura."
                )
        if errores:
            raise ValidationError(errores)


class RecordatorioUsuario(models.Model):
    """Horas a las que el usuario quiere que le recuerden registrar (máx. 3)."""

    MAXIMO_POR_USUARIO = 3

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recordatorios"
    )
    hora = models.TimeField()
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["hora"]
        constraints = [
            models.UniqueConstraint(fields=["usuario", "hora"], name="recordatorio_hora_unica")
        ]

    def __str__(self) -> str:
        return f"{self.hora:%H:%M}"
