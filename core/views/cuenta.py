"""
Cuenta del Usuario: perfil (RF2), datos de contacto (RF1), privacidad y
protección de datos (RF17, RNF27), recordatorios y notificaciones (RF20) y
alimentos personales (RF3).
"""

import json

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.forms import AlimentoPersonalForm, CuentaDatosForm, PerfilForm, RecordatoriosForm
from core.models import Alimento, Ambito, FuenteDato, Notificacion, RecordatorioUsuario, TipoConsentimiento
from core.services import auditoria, cuentas, reportes
from core.services.parametros import parametro
from core.views.utilidades import solo_usuario


@solo_usuario
def perfil(request):
    form = PerfilForm(request.POST or None, instance=request.user.perfil)
    if request.method == "POST" and form.is_valid():
        _, recalculo = cuentas.guardar_perfil(request.user, form.cleaned_data, request=request)
        messages.success(request, "Perfil actualizado." + (" Tu meta se recalculó con los nuevos datos." if recalculo else ""))
        return redirect("perfil")
    return render(request, "generico/formulario.html", {
        "titulo": "Tu perfil nutricional", "form": form, "boton": "Guardar",
        "intro": "Solo tú ves estos datos. Un cambio de peso, actividad u objetivo recalcula tu meta.",
    })


@login_required
def cuenta(request):
    form = CuentaDatosForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        auditoria.registrar("cuenta_editada", request=request, entidad="Usuario", entidad_id=request.user.pk)
        messages.success(request, "Datos actualizados.")
        return redirect("cuenta")
    return render(request, "usuario/cuenta.html", {"form": form, "cuenta_usuario": request.user.cuenta})


@solo_usuario
def privacidad(request):
    """Autorizaciones, preferencias de cuidado, exportación y supresión de datos."""
    cuenta_usuario = request.user.cuenta
    perfil_usuario = request.user.perfil
    if request.method == "POST":
        accion = request.POST.get("accion")
        if accion == "ia":
            cuentas.cambiar_consentimiento(request.user, TipoConsentimiento.IA, not cuenta_usuario.acepta_ia, request=request)
            messages.success(request, "Autorización de IA actualizada.")
        elif accion == "ocultar":
            perfil_usuario.ocultar_cifras = not perfil_usuario.ocultar_cifras
            perfil_usuario.save(update_fields=["ocultar_cifras", "actualizado_en"])
            messages.success(request, "Preferencia guardada.")
        elif accion == "pausa":
            cuenta_usuario.seguimiento_pausado = not cuenta_usuario.seguimiento_pausado
            cuenta_usuario.save(update_fields=["seguimiento_pausado"])
            messages.success(request, "Seguimiento en pausa: no habrá ajustes ni recordatorios."
                             if cuenta_usuario.seguimiento_pausado else "Seguimiento reanudado.")
        elif accion == "soporte":
            horas = 0 if cuenta_usuario.soporte_autorizado else 24
            cuentas.autorizar_soporte(request.user, horas, request=request)
            messages.success(request, "Autorizaste al equipo de soporte por 24 horas." if horas else "Retiraste la autorización de soporte.")
        return redirect("privacidad")
    return render(request, "usuario/privacidad.html", {
        "cuenta_usuario": cuenta_usuario, "perfil_usuario": perfil_usuario,
        "consentimientos": request.user.consentimientos.all()[:10], "contacto": parametro("contacto_apoyo"),
    })


@solo_usuario
def exportar_datos(request):
    """Portabilidad: todos los datos del titular en un archivo JSON."""
    datos = reportes.exportar_todo(request.user)
    auditoria.registrar("datos_exportados", request=request, entidad="Usuario", entidad_id=request.user.pk)
    respuesta = HttpResponse(json.dumps(datos, ensure_ascii=False, indent=2), content_type="application/json; charset=utf-8")
    respuesta["Content-Disposition"] = f'attachment; filename="mis-datos-nutriregional-{timezone.localdate():%Y%m%d}.json"'
    return respuesta


@solo_usuario
def eliminar_cuenta(request):
    if request.method == "POST":
        if request.POST.get("confirmacion", "").strip().upper() != "ELIMINAR":
            messages.error(request, "Escribe ELIMINAR para confirmar.")
            return redirect("eliminar_cuenta")
        usuario = request.user
        logout(request)
        cuentas.eliminar_cuenta(usuario, request=request)
        messages.success(request, "Tu cuenta y tus datos se eliminaron. Gracias por usar NutriRegional.")
        return redirect("inicio")
    return render(request, "usuario/eliminar_cuenta.html")


@solo_usuario
def recordatorios(request):
    actuales = list(RecordatorioUsuario.objects.filter(usuario=request.user, activo=True))
    inicial = {f"hora_{i + 1}": r.hora for i, r in enumerate(actuales[:3])}
    inicial["resumen_semanal"] = request.user.cuenta.recibir_resumen_semanal
    form = RecordatoriosForm(request.POST or None, initial=inicial)
    if request.method == "POST" and form.is_valid():
        RecordatorioUsuario.objects.filter(usuario=request.user).delete()
        for hora in form.horas()[: parametro("max_recordatorios")]:
            RecordatorioUsuario.objects.create(usuario=request.user, hora=hora)
        cuenta_usuario = request.user.cuenta
        cuenta_usuario.recibir_resumen_semanal = form.cleaned_data["resumen_semanal"]
        cuenta_usuario.save(update_fields=["recibir_resumen_semanal"])
        messages.success(request, "Recordatorios guardados. Puedes desactivarlos cuando quieras dejando las horas vacías.")
        return redirect("recordatorios")
    return render(request, "generico/formulario.html", {
        "titulo": "Recordatorios", "form": form, "boton": "Guardar",
        "intro": "Hasta tres recordatorios al día para registrar tus comidas. Los mensajes son neutros: "
                 "solo te recuerdan que puedes registrar.",
    })


@login_required
def notificaciones(request):
    lista = Notificacion.objects.filter(destinatario=request.user)
    if request.method == "POST":
        lista.filter(leida=False).update(leida=True)
        messages.success(request, "Todas marcadas como leídas.")
        return redirect("notificaciones")
    return render(request, "usuario/notificaciones.html", {"notificaciones": lista[:100]})


@login_required
@require_POST
def notificacion_leer(request, pk):
    notificacion = get_object_or_404(Notificacion, pk=pk, destinatario=request.user)
    notificacion.leida = True
    notificacion.save(update_fields=["leida"])
    return redirect(notificacion.url or "notificaciones")


# --- Alimentos personales (RF3) -----------------------------------------------------------


@solo_usuario
def mis_alimentos(request):
    return render(request, "usuario/mis_alimentos.html", {
        "alimentos": Alimento.objects.filter(ambito=Ambito.PERSONAL, propietario=request.user, estado="activo"),
    })


@solo_usuario
def mi_alimento(request, pk=None):
    alimento = get_object_or_404(Alimento, pk=pk, propietario=request.user, ambito=Ambito.PERSONAL) if pk else None
    form = AlimentoPersonalForm(request.POST or None, instance=alimento)
    if request.method == "POST" and form.is_valid():
        nuevo = form.save(commit=False)
        nuevo.ambito = Ambito.PERSONAL
        nuevo.propietario = request.user
        nuevo.fuente = FuenteDato.ETIQUETA
        nuevo.verificado = False
        try:
            nuevo.full_clean()
        except Exception as exc:  # noqa: BLE001
            for campo, errores in getattr(exc, "message_dict", {"__all__": [str(exc)]}).items():
                form.add_error(campo if campo in form.fields else None, errores)
        else:
            nuevo.save()
            messages.success(request, "Alimento guardado. Solo tú lo ves; el equipo de curación podrá revisarlo para el catálogo.")
            return redirect("mis_alimentos")
    return render(request, "generico/formulario.html", {
        "titulo": "Editar alimento personal" if alimento else "Nuevo alimento personal", "form": form, "boton": "Guardar",
        "intro": "Valores por 100 g, tal como aparecen en la tabla nutricional del empaque.", "volver": "/mis-alimentos/",
    })
