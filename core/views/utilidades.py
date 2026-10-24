"""
Utilidades comunes de las vistas: control de acceso por rol (RNF26) y
lectura segura de parámetros de la URL.
"""

from __future__ import annotations

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from core.models import Rol


def rol_requerido(*roles):
    """
    Habilita una vista solo para ciertos roles. Se valida en el servidor en
    cada petición: ocultar un enlace en el menú no es control de acceso.
    """

    def decorador(vista):
        @login_required
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            cuenta = getattr(request.user, "cuenta", None)
            if cuenta is None or cuenta.rol not in roles:
                raise PermissionDenied("Esta sección no está disponible para tu rol.")
            return vista(request, *args, **kwargs)

        return envoltura

    return decorador


solo_usuario = rol_requerido(Rol.USUARIO)
solo_curador = rol_requerido(Rol.CURADOR)
solo_admin = rol_requerido(Rol.ADMINISTRADOR)
curador_o_admin = rol_requerido(Rol.CURADOR, Rol.ADMINISTRADOR)


def fecha_de(request, nombre: str = "fecha"):
    """Lee ?fecha=AAAA-MM-DD; si falta o no es válida, devuelve hoy."""
    texto = request.GET.get(nombre) or request.POST.get(nombre)
    if texto:
        try:
            return timezone.datetime.strptime(texto, "%Y-%m-%d").date()
        except ValueError:
            pass
    return timezone.localdate()


def entero_de(request, nombre: str, defecto: int, permitidos=None) -> int:
    try:
        valor = int(request.GET.get(nombre, defecto))
    except (TypeError, ValueError):
        return defecto
    if permitidos and valor not in permitidos:
        return defecto
    return valor
