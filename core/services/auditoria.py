"""
RF22 Trazabilidad y auditoría.

`registrar` escribe una fila en la bitácora. Nunca incluye el contenido de
las comidas ni datos de salud: solo qué pasó, sobre qué entidad, quién, desde
qué IP y cuándo.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def ip_de(request) -> str | None:
    if request is None:
        return None
    reenviada = request.META.get("HTTP_X_FORWARDED_FOR")
    if reenviada:
        return reenviada.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


def registrar(accion: str, *, usuario=None, request=None, entidad: str = "", entidad_id="", detalle: str = ""):
    """Añade un registro a la bitácora. Si falla, lo deja en el log técnico."""
    from core.models import Bitacora

    if usuario is None and request is not None and getattr(request, "user", None) is not None:
        if request.user.is_authenticated:
            usuario = request.user
    try:
        return Bitacora.objects.create(
            usuario=usuario if (usuario is not None and usuario.pk) else None,
            accion=accion,
            entidad=entidad,
            entidad_id=str(entidad_id or ""),
            detalle=detalle[:2000],
            ip=ip_de(request),
        )
    except Exception:  # la auditoría nunca debe tumbar la operación principal
        logger.exception("No se pudo escribir en la bitácora (acción %s).", accion)
        return None
