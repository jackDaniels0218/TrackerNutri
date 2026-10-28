"""
Señales del sistema.

* Crear la Cuenta al crear un usuario.
* Bloqueo temporal tras varios intentos fallidos de ingreso (actividad 12).
* Registrar ingresos y salidas en la bitácora (actividad 22).
* Vaciar la caché de parámetros cuando cambian o al empezar cada petición.
"""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.core.signals import request_started
from django.db.models import Q
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from core.models import Cuenta, Parametro
from core.services import auditoria
from core.services.parametros import limpiar_cache, parametro


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def crear_cuenta(sender, instance, created, **kwargs):
    if created:
        rol = getattr(instance, "_rol_inicial", None)
        datos = {"rol": rol} if rol else {}
        Cuenta.objects.get_or_create(usuario=instance, defaults=datos)


@receiver(post_save, sender=Parametro)
def parametro_cambiado(sender, **kwargs):
    limpiar_cache()


@receiver(request_started)
def nueva_peticion(sender, **kwargs):
    # Cada petición lee los parámetros vigentes aunque haya varios procesos.
    limpiar_cache()


@receiver(user_login_failed)
def ingreso_fallido(sender, credentials, request=None, **kwargs):
    identificador = (credentials or {}).get("username", "")
    usuario = (
        get_user_model()
        .objects.filter(Q(username__iexact=identificador) | Q(email__iexact=identificador))
        .select_related("cuenta")
        .first()
    )
    if usuario is None or not hasattr(usuario, "cuenta"):
        auditoria.registrar("ingreso_fallido", request=request, detalle="Usuario inexistente.")
        return

    cuenta = usuario.cuenta
    cuenta.intentos_fallidos += 1
    detalle = f"Intento fallido {cuenta.intentos_fallidos}."
    if cuenta.intentos_fallidos >= parametro("intentos_login_max"):
        cuenta.bloqueado_hasta = timezone.now() + timedelta(minutes=parametro("bloqueo_minutos"))
        cuenta.intentos_fallidos = 0
        detalle += " Cuenta bloqueada temporalmente."
    cuenta.save(update_fields=["intentos_fallidos", "bloqueado_hasta"])
    auditoria.registrar(
        "ingreso_fallido", usuario=usuario, request=request, entidad="Cuenta",
        entidad_id=cuenta.pk, detalle=detalle,
    )


@receiver(user_logged_in)
def ingreso(sender, request, user, **kwargs):
    cuenta = getattr(user, "cuenta", None)
    if cuenta is not None and (cuenta.intentos_fallidos or cuenta.bloqueado_hasta):
        cuenta.intentos_fallidos = 0
        cuenta.bloqueado_hasta = None
        cuenta.save(update_fields=["intentos_fallidos", "bloqueado_hasta"])
    auditoria.registrar("ingreso", usuario=user, request=request, entidad="Usuario", entidad_id=user.pk)


@receiver(user_logged_out)
def salida(sender, request, user, **kwargs):
    if user is not None:
        auditoria.registrar("salida", usuario=user, request=request, entidad="Usuario", entidad_id=user.pk)
