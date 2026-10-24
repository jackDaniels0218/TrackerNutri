"""
RF20 Notificaciones y recordatorios.

Las notificaciones se guardan en la base de datos (lista dentro de la app) y,
cuando corresponde, se envían también por correo. En el prototipo el correo
usa el backend de consola de Django: el mensaje aparece en la terminal donde
corre el servidor. Las notificaciones push de una app móvil quedan fuera del
prototipo web (ver docs/desviaciones del SRS).

Los mensajes son neutros: informan, no insisten ni culpabilizan.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db.models import Sum
from django.utils import timezone

from core.models import (
    Comida,
    Cuenta,
    EstadoCuenta,
    Notificacion,
    RecordatorioUsuario,
    Rol,
)

logger = logging.getLogger(__name__)


def notificar(usuario, tipo: str, titulo: str, mensaje: str, *, url: str = "", correo: bool = False) -> Notificacion:
    notificacion = Notificacion.objects.create(
        destinatario=usuario, tipo=tipo, titulo=titulo[:120], mensaje=mensaje, url=url[:200]
    )
    if correo and usuario.email:
        try:
            send_mail(
                f"NutriRegional: {titulo}", f"{mensaje}\n\n{settings.URL_BASE}{url}",
                settings.DEFAULT_FROM_EMAIL, [usuario.email], fail_silently=False,
            )
            notificacion.enviada_por_correo = True
            notificacion.save(update_fields=["enviada_por_correo"])
        except Exception:  # el correo nunca debe tumbar la operación
            logger.exception("No se pudo enviar el correo de la notificación %s.", notificacion.pk)
    return notificacion


def notificar_rol(rol: str, tipo: str, titulo: str, mensaje: str, *, url: str = "", correo: bool = True) -> int:
    usuarios = get_user_model().objects.filter(cuenta__rol=rol, cuenta__estado=EstadoCuenta.ACTIVO, is_active=True)
    for usuario in usuarios:
        notificar(usuario, tipo, titulo, mensaje, url=url, correo=correo)
    return usuarios.count()


def no_leidas(usuario) -> int:
    return Notificacion.objects.filter(destinatario=usuario, leida=False).count()


def generar_recordatorios(momento=None, ventana_minutos: int = 30) -> int:
    """
    Crea los recordatorios de registro cuya hora cae en la ventana actual.

    Se ejecuta periódicamente (`python manage.py procesos recordatorios`). No
    recuerda nada a quien tiene el seguimiento en pausa ni repite el mismo
    recordatorio el mismo día.
    """
    momento = timezone.localtime(momento or timezone.now())
    inicio = (momento - timedelta(minutes=ventana_minutos)).time()
    fin = momento.time()
    creados = 0
    recordatorios = RecordatorioUsuario.objects.filter(activo=True).select_related("usuario__cuenta")
    for r in recordatorios:
        cuenta = getattr(r.usuario, "cuenta", None)
        if cuenta is None or cuenta.seguimiento_pausado or cuenta.estado != EstadoCuenta.ACTIVO:
            continue
        if not (inicio <= r.hora <= fin):
            continue
        titulo = f"Recordatorio de las {r.hora:%H:%M}"
        if Notificacion.objects.filter(destinatario=r.usuario, titulo=titulo, creada_en__date=momento.date()).exists():
            continue
        notificar(r.usuario, Notificacion.Tipo.RECORDATORIO, titulo,
                  "Cuando quieras, puedes registrar lo que comiste. Una frase es suficiente.", url="/comidas/nueva/")
        creados += 1
    return creados


def resumen_semanal(fecha_fin=None) -> int:
    """Resumen de la semana para cada usuario que lo tenga activado."""
    fecha_fin = fecha_fin or timezone.localdate()
    inicio = fecha_fin - timedelta(days=6)
    enviados = 0
    for cuenta in Cuenta.objects.filter(rol=Rol.USUARIO, recibir_resumen_semanal=True, seguimiento_pausado=False,
                                        estado=EstadoCuenta.ACTIVO).select_related("usuario"):
        usuario = cuenta.usuario
        comidas = Comida.objects.filter(usuario=usuario, fecha_hora__date__gte=inicio, fecha_hora__date__lte=fecha_fin).que_cuentan()
        dias = comidas.dates("fecha_hora", "day").count()
        if not dias:
            continue
        perfil = getattr(usuario, "perfil", None)
        if perfil and perfil.ocultar_cifras:
            mensaje = f"Esta semana registraste comidas en {dias} de 7 días. Puedes ver tu tendencia en los reportes."
        else:
            total = comidas.aggregate(t=Sum("kcal"))["t"] or 0
            mensaje = (
                f"Esta semana registraste comidas en {dias} de 7 días, con un promedio estimado de "
                f"{total / dias:.0f} kcal por día registrado. Los valores son estimaciones."
            )
        notificar(usuario, Notificacion.Tipo.RESUMEN, "Tu resumen semanal", mensaje, url="/reportes/", correo=True)
        enviados += 1
    return enviados
