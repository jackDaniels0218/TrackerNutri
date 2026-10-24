"""
Páginas públicas, registro en tres pasos e ingreso (RF1, RF2, RF12).
"""

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from core.forms import IngresoForm, PerfilForm, RegistroCuentaForm
from core.models import Cuenta, Rol
from core.requerimientos import NO_FUNCIONALES, REQUERIMIENTOS
from core.services import cuentas, metas
from core.services.parametros import parametro
from core.views.utilidades import solo_usuario


def inicio(request):
    """Lleva a cada rol a su pantalla principal; a quien no ha entrado, a la portada."""
    if not request.user.is_authenticated:
        return render(request, "publico/portada.html")
    rol = getattr(getattr(request.user, "cuenta", None), "rol", None)
    if rol == Rol.CURADOR:
        return redirect("curacion")
    if rol == Rol.ADMINISTRADOR:
        return redirect("administracion")
    return redirect("panel")


def politica_datos(request):
    return render(request, "publico/politica_datos.html")


def aviso_medico(request):
    return render(request, "publico/aviso_medico.html", {"contacto": parametro("contacto_apoyo")})


def requerimientos(request):
    """Mapa de requerimientos del SRS: dónde ver cada uno en la aplicación."""
    return render(request, "publico/requerimientos.html", {"funcionales": REQUERIMIENTOS, "no_funcionales": NO_FUNCIONALES})


class IngresoView(LoginView):
    """Ingreso con correo y contraseña. El bloqueo lo aplican el formulario y signals.py."""

    form_class = IngresoForm
    template_name = "registration/login.html"
    redirect_authenticated_user = True


def registro(request):
    """Paso 1 de 3: cuenta y autorizaciones por separado."""
    if request.user.is_authenticated:
        return redirect("inicio")
    form = RegistroCuentaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        datos = form.cleaned_data
        usuario = cuentas.crear_usuario(
            correo=datos["correo"], password=datos["password1"], nombres=datos["nombres"],
            apellidos=datos["apellidos"], acepta_datos=datos["acepta_datos"], acepta_ia=datos["acepta_ia"],
            request=request,
        )
        login(request, usuario, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, "Cuenta creada. Ahora cuéntanos un poco de ti para calcular tu meta.")
        return redirect("registro_perfil")
    return render(request, "registro/paso.html", {"form": form, "paso": 1, "titulo": "Crea tu cuenta"})


@solo_usuario
def registro_perfil(request):
    """Paso 2 de 3: perfil nutricional. Se puede volver más tarde: el avance queda guardado."""
    perfil = getattr(request.user, "perfil", None)
    form = PerfilForm(request.POST or None, instance=perfil)
    if request.method == "POST" and form.is_valid():
        cuentas.guardar_perfil(request.user, form.cleaned_data, request=request)
        cuentas.avanzar_registro(request.user, Cuenta.PASO_META)
        return redirect("registro_meta")
    return render(request, "registro/paso.html", {"form": form, "paso": 2, "titulo": "Tu perfil"})


@solo_usuario
def registro_meta(request):
    """Paso 3 de 3: revisión de la meta inicial con la explicación de cómo se calculó."""
    if getattr(request.user, "perfil", None) is None:
        return redirect("registro_perfil")
    meta = metas.meta_vigente(request.user) or metas.meta_inicial(request.user)
    if request.method == "POST":
        cuentas.avanzar_registro(request.user, Cuenta.REGISTRO_COMPLETO)
        messages.success(request, "¡Listo! Ya puedes registrar tu primera comida.")
        return redirect("panel")
    return render(request, "registro/meta.html", {"meta": meta, "paso": 3, "titulo": "Tu meta inicial"})


@login_required
@require_POST
def cerrar_sesiones(request):
    """Cerrar la sesión en todos los dispositivos."""
    cerradas = cuentas.cerrar_todas_las_sesiones(request.user, request=request)
    messages.success(request, f"Se cerraron {cerradas} sesiones abiertas. Vuelve a entrar.")
    return redirect("login")
