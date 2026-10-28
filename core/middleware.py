"""
Middleware de control de cuenta (actividades 1 y 12).

* Si un Administrador bloquea o desactiva una cuenta, la sesión abierta de
  esa persona se cierra en su siguiente petición.
* Un Usuario que no terminó el registro en tres pasos vuelve al paso que le
  falta antes de poder usar el resto de la aplicación.
"""

from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse

from core.models import Cuenta, EstadoCuenta, Rol

RUTAS_LIBRES = ("/static/", "/cuentas/", "/legal/", "/registro/", "/requerimientos/", "/admin/", "/qr")


class ControlDeCuentaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = getattr(request, "user", None)
        if usuario is not None and usuario.is_authenticated:
            cuenta = getattr(usuario, "cuenta", None)
            if cuenta is not None and (cuenta.estado != EstadoCuenta.ACTIVO or cuenta.esta_bloqueada):
                logout(request)
                messages.error(request, "Tu cuenta no está activa en este momento. Si crees que es un error, contacta al soporte.")
                return redirect("login")
            if cuenta is not None and cuenta.rol == Rol.USUARIO and not cuenta.registro_completo:
                if not request.path.startswith(RUTAS_LIBRES) and not request.path.startswith("/api/"):
                    pasos = {
                        Cuenta.PASO_PERFIL: "registro_perfil",
                        Cuenta.PASO_META: "registro_meta",
                    }
                    return redirect(reverse(pasos.get(cuenta.paso_registro, "registro_perfil")))
        return self.get_response(request)
