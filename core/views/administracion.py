"""
Vistas del Administrador: cuentas (RF1), parámetros (RF11), proveedor de IA
y costos (RF21, RNF33), auditoría (RF22) y procesos en segundo plano.

El Administrador solo ve datos agregados. Para ver los datos de una persona
necesita su autorización vigente, y el acceso queda en la bitácora.
"""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core.forms import CambiarEstadoCuentaForm, CuentaInternaForm, ParametroForm
from core.models import (
    Bitacora,
    Consentimiento,
    Cuenta,
    HistorialCatalogo,
    MetaCalorica,
    Parametro,
    Rol,
)
from core.services import auditoria, cuentas, curacion, ia, metas, notificaciones, reportes
from core.views.utilidades import curador_o_admin, solo_admin


@solo_admin
def inicio(request):
    return render(request, "administracion/inicio.html", {"panel": reportes.panel_agregado(), "ia": ia.resumen_uso(30)})


@solo_admin
def cuentas_lista(request):
    consulta = request.GET.get("q", "").strip()
    lista = Cuenta.objects.select_related("usuario").order_by("rol", "usuario__email")
    if consulta:
        lista = lista.filter(usuario__email__icontains=consulta)
    if request.GET.get("rol"):
        lista = lista.filter(rol=request.GET["rol"])
    pagina = Paginator(lista, 40).get_page(request.GET.get("pagina"))
    return render(request, "administracion/cuentas.html", {"pagina": pagina, "q": consulta, "roles": Rol.choices,
                                                           "form_estado": CambiarEstadoCuentaForm()})


@solo_admin
@require_POST
def cuenta_estado(request, pk):
    cuenta = get_object_or_404(Cuenta, pk=pk)
    form = CambiarEstadoCuentaForm(request.POST)
    if form.is_valid():
        try:
            cuentas.cambiar_estado(cuenta, form.cleaned_data["estado"], administrador=request.user, request=request)
        except cuentas.OperacionNoPermitida as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"Cuenta {cuenta.usuario.email}: {cuenta.get_estado_display().lower()}.")
    return redirect("cuentas_admin")


@solo_admin
def cuenta_interna_nueva(request):
    form = CuentaInternaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        datos = form.cleaned_data
        cuentas.crear_usuario(correo=datos["correo"], password=datos["password"], nombres=datos["nombres"],
                              apellidos=datos["apellidos"], rol=datos["rol"], acepta_datos=True, request=request)
        messages.success(request, f"Cuenta de {dict(Rol.choices)[datos['rol']]} creada.")
        return redirect("cuentas_admin")
    return render(request, "generico/formulario.html", {
        "titulo": "Nueva cuenta interna", "form": form, "boton": "Crear", "volver": reverse("cuentas_admin"),
        "intro": "Las cuentas de Curador y Administrador se crean aquí; los usuarios se registran solos. El rol no cambia después.",
    })


@solo_admin
def cuenta_soporte(request, pk):
    """Datos de un usuario para soporte: solo con su autorización vigente, y queda en la bitácora."""
    cuenta = get_object_or_404(Cuenta, pk=pk, rol=Rol.USUARIO)
    if not cuenta.soporte_autorizado:
        messages.error(request, "Este usuario no ha autorizado el acceso de soporte.")
        return redirect("cuentas_admin")
    auditoria.registrar("acceso_soporte", request=request, entidad="Usuario", entidad_id=cuenta.usuario_id,
                        detalle="Acceso a datos individuales autorizado por el titular.")
    usuario = cuenta.usuario
    return render(request, "administracion/soporte.html", {
        "cuenta": cuenta, "usuario_soporte": usuario, "meta": metas.meta_vigente(usuario),
        "comidas": usuario.comidas.que_cuentan()[:10], "pesajes": usuario.pesajes.all()[:10],
    })


@curador_o_admin
def parametros(request):
    lista = Parametro.objects.all()
    if request.user.cuenta.rol == Rol.CURADOR:
        lista = lista.filter(grupo=Parametro.Grupo.NUTRICIONAL)
    grupos = {}
    for p in lista:
        grupos.setdefault(p.get_grupo_display(), []).append(p)
    return render(request, "administracion/parametros.html", {"grupos": grupos})


@curador_o_admin
def parametro_editar(request, pk):
    parametro = get_object_or_404(Parametro, pk=pk)
    if request.user.cuenta.rol == Rol.CURADOR and parametro.grupo != Parametro.Grupo.NUTRICIONAL:
        messages.error(request, "Solo el Administrador puede cambiar este parámetro.")
        return redirect("parametros")
    anterior = parametro.valor
    form = ParametroForm(request.POST or None, instance=parametro)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.modificado_por = request.user
        obj.save()
        auditoria.registrar("parametro_cambiado", request=request, entidad="Parametro", entidad_id=obj.clave,
                            detalle=f"{anterior} → {obj.valor}")
        messages.success(request, f"Parámetro «{obj.clave}» actualizado.")
        return redirect("parametros")
    return render(request, "generico/formulario.html", {
        "titulo": f"Parámetro {parametro.clave}", "form": form, "boton": "Guardar", "volver": reverse("parametros"),
        "intro": f"{parametro.descripcion} Tipo: {parametro.get_tipo_display()}. Todo cambio queda en la bitácora.",
    })


@solo_admin
def ia_admin(request):
    return render(request, "administracion/ia.html", {"ia": ia.resumen_uso(30)})


@curador_o_admin
def auditoria_vista(request):
    """Bitácora, consentimientos, historial de metas y del catálogo. Solo consulta."""
    pestana = request.GET.get("ver", "bitacora")
    consulta = request.GET.get("q", "").strip()
    desde, hasta = request.GET.get("desde"), request.GET.get("hasta")
    if pestana == "consentimientos":
        lista = Consentimiento.objects.select_related("usuario")
    elif pestana == "metas":
        lista = MetaCalorica.objects.select_related("usuario").order_by("-creada_en")
    elif pestana == "catalogo":
        lista = HistorialCatalogo.objects.select_related("usuario", "version")
    else:
        pestana = "bitacora"
        lista = Bitacora.objects.select_related("usuario")
        if consulta:
            lista = lista.filter(accion__icontains=consulta) | lista.filter(entidad__icontains=consulta)
    campo_fecha = {"metas": "creada_en", "bitacora": "fecha", "consentimientos": "fecha", "catalogo": "fecha"}[pestana]
    if desde:
        lista = lista.filter(**{f"{campo_fecha}__date__gte": desde})
    if hasta:
        lista = lista.filter(**{f"{campo_fecha}__date__lte": hasta})
    if request.GET.get("usuario"):
        lista = lista.filter(usuario__email__icontains=request.GET["usuario"])
    pagina = Paginator(lista, 50).get_page(request.GET.get("pagina"))
    return render(request, "administracion/auditoria.html", {"pagina": pagina, "ver": pestana, "q": consulta,
                                                             "desde": desde or "", "hasta": hasta or "",
                                                             "filtro_usuario": request.GET.get("usuario", "")})


@solo_admin
def procesos(request):
    """Ejecuta a mano los procesos en segundo plano (en producción irían programados)."""
    resultado = None
    if request.method == "POST":
        proceso = request.POST.get("proceso")
        if proceso == "ajuste_semanal":
            r = metas.ajuste_semanal_todos()
            resultado = f"Ajuste semanal: {r['evaluados']} usuarios evaluados, {r['ajustados']} ajustados."
        elif proceso == "recordatorios":
            resultado = f"Recordatorios generados: {notificaciones.generar_recordatorios(ventana_minutos=24 * 60)}."
        elif proceso == "resumen_semanal":
            resultado = f"Resúmenes semanales enviados: {notificaciones.resumen_semanal()}."
        elif proceso == "exactitud":
            e = curacion.ejecutar_exactitud(usuario=request.user)
            resultado = f"Exactitud: identificación {e.identificacion_pct} %, método {e.coccion_pct} %."
        if resultado:
            auditoria.registrar(f"proceso_{proceso}", request=request, detalle=resultado)
            messages.success(request, resultado)
            return redirect("procesos")
    return render(request, "administracion/procesos.html", {"usuarios": get_user_model().objects.count()})
