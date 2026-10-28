"""
RF1 Usuarios, RF2 Perfil, RF12 Acceso y RNF27 Protección de datos.

Operaciones sobre cuentas que tocan varias tablas o dejan rastro en la
bitácora. Las vistas no crean usuarios ni borran datos directamente: llaman
a estas funciones.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.db import transaction
from django.utils import timezone

from core.models import (
    Alimento,
    Comida,
    Consentimiento,
    Correccion,
    Cuenta,
    DiaRegistro,
    EstadoCuenta,
    MetaCalorica,
    Notificacion,
    PerfilNutricional,
    Pesaje,
    RecordatorioUsuario,
    Rol,
    TipoConsentimiento,
)
from core.services import auditoria


class OperacionNoPermitida(ValueError):
    pass


@transaction.atomic
def crear_usuario(*, correo: str, password: str, nombres: str = "", apellidos: str = "", rol: str = Rol.USUARIO,
                  acepta_datos: bool = False, acepta_ia: bool = False, request=None):
    """Crea el usuario con su cuenta y registra las autorizaciones por separado."""
    if rol == Rol.USUARIO and not acepta_datos:
        raise OperacionNoPermitida("La autorización de tratamiento de datos es obligatoria para registrarse.")
    User = get_user_model()
    usuario = User(username=correo.lower(), email=correo.lower(), first_name=nombres, last_name=apellidos)
    usuario.set_password(password)
    usuario._rol_inicial = rol
    usuario.save()
    cuenta = usuario.cuenta
    ahora = timezone.now()
    cuenta.acepta_datos = acepta_datos
    cuenta.fecha_acepta_datos = ahora if acepta_datos else None
    cuenta.acepta_ia = acepta_ia
    cuenta.fecha_acepta_ia = ahora if acepta_ia else None
    cuenta.paso_registro = Cuenta.PASO_PERFIL if rol == Rol.USUARIO else Cuenta.REGISTRO_COMPLETO
    cuenta.save()
    ip = auditoria.ip_de(request)
    Consentimiento.objects.create(usuario=usuario, tipo=TipoConsentimiento.DATOS, otorgado=acepta_datos, ip=ip)
    Consentimiento.objects.create(usuario=usuario, tipo=TipoConsentimiento.IA, otorgado=acepta_ia, ip=ip)
    auditoria.registrar("cuenta_creada", usuario=usuario, request=request, entidad="Usuario", entidad_id=usuario.pk,
                        detalle=f"Rol {cuenta.get_rol_display()}.")
    return usuario


@transaction.atomic
def guardar_perfil(usuario, datos: dict, *, request=None) -> tuple[PerfilNutricional, bool]:
    """
    Crea o actualiza el perfil. Devuelve (perfil, hubo_recalculo). Un cambio de
    peso, actividad, objetivo o ritmo dispara el recálculo de la meta.
    """
    from core.services import metas

    perfil = getattr(usuario, "perfil", None)
    nuevo = perfil is None
    campos_meta = ("peso_inicial_kg", "nivel_actividad", "objetivo", "ritmo", "fecha_nacimiento", "sexo",
                   "estatura_cm", "gestante_lactante", "requiere_acompanamiento")
    antes = {c: getattr(perfil, c) for c in campos_meta} if perfil else {}
    if nuevo:
        perfil = PerfilNutricional(usuario=usuario)
    for campo, valor in datos.items():
        setattr(perfil, campo, valor)
    perfil.full_clean()
    perfil.save()
    usuario.perfil = perfil
    recalculo = False
    if nuevo or not metas.meta_vigente(usuario):
        metas.meta_inicial(usuario)
        recalculo = True
    elif any(antes.get(c) != getattr(perfil, c) for c in campos_meta):
        metas.recalcular_por_perfil(usuario)
        recalculo = True
    auditoria.registrar("perfil_actualizado", usuario=usuario, request=request, entidad="PerfilNutricional",
                        entidad_id=perfil.pk)
    return perfil, recalculo


def avanzar_registro(usuario, paso: int) -> None:
    cuenta = usuario.cuenta
    if paso > cuenta.paso_registro:
        cuenta.paso_registro = paso
        cuenta.save(update_fields=["paso_registro"])


@transaction.atomic
def cambiar_consentimiento(usuario, tipo: str, otorgado: bool, *, request=None) -> None:
    """Otorga o retira una autorización. El registro histórico nunca se modifica."""
    cuenta = usuario.cuenta
    if tipo == TipoConsentimiento.DATOS:
        if not otorgado:
            raise OperacionNoPermitida(
                "La autorización de datos es necesaria para usar el servicio. Si quieres retirarla, elimina tu cuenta."
            )
        cuenta.acepta_datos, cuenta.fecha_acepta_datos = True, timezone.now()
    else:
        cuenta.acepta_ia, cuenta.fecha_acepta_ia = otorgado, timezone.now() if otorgado else None
    cuenta.save()
    Consentimiento.objects.create(usuario=usuario, tipo=tipo, otorgado=otorgado, ip=auditoria.ip_de(request))
    auditoria.registrar("consentimiento", usuario=usuario, request=request, entidad="Consentimiento",
                        detalle=f"{tipo}: {'otorgado' if otorgado else 'retirado'}")


def cerrar_todas_las_sesiones(usuario, *, request=None) -> int:
    """Cierra la sesión en todos los dispositivos (actividad 12)."""
    cerradas = 0
    for sesion in Session.objects.filter(expire_date__gte=timezone.now()):
        if str(sesion.get_decoded().get("_auth_user_id")) == str(usuario.pk):
            sesion.delete()
            cerradas += 1
    auditoria.registrar("sesiones_cerradas", usuario=usuario, request=request, detalle=f"{cerradas} sesiones.")
    return cerradas


@transaction.atomic
def eliminar_cuenta(usuario, *, request=None) -> None:
    """
    Supresión de datos a petición del titular (Ley 1581). Se borran sus datos
    personales y de salud; las cuentas internas solo se desactivan.

    Se conservan, sin vínculo con la persona, las correcciones (útiles para
    mejorar el catálogo) y la bitácora.
    """
    cuenta = usuario.cuenta
    if cuenta.es_interna:
        raise OperacionNoPermitida("Las cuentas de Curador y Administrador se desactivan, no se eliminan.")
    Correccion.objects.filter(usuario=usuario).update(usuario=None)
    Comida.objects.filter(usuario=usuario).delete()
    for modelo in (Pesaje, DiaRegistro, Notificacion, RecordatorioUsuario):
        modelo.objects.filter(**{("destinatario" if modelo is Notificacion else "usuario"): usuario}).delete()
    # El borrado en bloque no pasa por MetaCalorica.delete(), que protege el
    # historial frente a borrados normales: la supresión es la excepción legal.
    MetaCalorica.objects.filter(usuario=usuario).delete()
    Alimento.objects.filter(propietario=usuario).update(estado="inactivo")
    PerfilNutricional.objects.filter(usuario=usuario).delete()
    cerrar_todas_las_sesiones(usuario)
    anonimo = f"eliminado-{uuid.uuid4().hex[:12]}"
    usuario.username = anonimo
    usuario.email = ""
    usuario.first_name = usuario.last_name = ""
    usuario.is_active = False
    usuario.set_unusable_password()
    usuario.save()
    cuenta.estado = EstadoCuenta.INACTIVO
    cuenta.acepta_ia = False
    cuenta.save()
    auditoria.registrar("cuenta_eliminada", usuario=usuario, request=request, entidad="Usuario", entidad_id=usuario.pk,
                        detalle="Supresión de datos solicitada por el titular.")


@transaction.atomic
def cambiar_estado(cuenta: Cuenta, estado: str, *, administrador, request=None) -> None:
    """Activar, desactivar o bloquear una cuenta (acción del Administrador)."""
    if cuenta.usuario_id == administrador.pk:
        raise OperacionNoPermitida("No puedes cambiar el estado de tu propia cuenta.")
    cuenta.estado = estado
    if estado == EstadoCuenta.ACTIVO:
        cuenta.bloqueado_hasta = None
        cuenta.intentos_fallidos = 0
    cuenta.save()
    if estado != EstadoCuenta.ACTIVO:
        cerrar_todas_las_sesiones(cuenta.usuario)
    auditoria.registrar("cuenta_estado", usuario=administrador, request=request, entidad="Cuenta",
                        entidad_id=cuenta.pk, detalle=f"Nuevo estado: {estado}")


def autorizar_soporte(usuario, horas: int = 24, *, request=None) -> None:
    """El titular autoriza que el Administrador vea sus datos para soporte."""
    cuenta = usuario.cuenta
    cuenta.autoriza_soporte_hasta = timezone.now() + timedelta(hours=horas) if horas else None
    cuenta.save(update_fields=["autoriza_soporte_hasta"])
    auditoria.registrar("soporte_autorizado" if horas else "soporte_revocado", usuario=usuario, request=request,
                        entidad="Cuenta", entidad_id=cuenta.pk, detalle=f"{horas} horas" if horas else "")
