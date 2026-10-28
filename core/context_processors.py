"""Variables disponibles en todas las plantillas."""

from core.models import Rol


def nutriregional(request):
    contexto = {"ROL_USUARIO": Rol.USUARIO, "ROL_CURADOR": Rol.CURADOR, "ROL_ADMIN": Rol.ADMINISTRADOR}
    usuario = getattr(request, "user", None)
    if usuario is None or not usuario.is_authenticated:
        return contexto
    from core.services.notificaciones import no_leidas

    cuenta = getattr(usuario, "cuenta", None)
    perfil = getattr(usuario, "perfil", None)
    contexto.update(
        {
            "rol": cuenta.rol if cuenta else None,
            "notificaciones_sin_leer": no_leidas(usuario),
            "ocultar_cifras": bool(perfil and perfil.ocultar_cifras),
            "seguimiento_pausado": bool(cuenta and cuenta.seguimiento_pausado),
        }
    )
    return contexto
