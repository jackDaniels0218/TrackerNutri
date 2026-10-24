"""
Vistas del Curador nutricional: catálogo (RF3–RF6), bandeja de pendientes y
correcciones (RF10, RF19), versiones y pruebas de exactitud (RF19).

El Curador no ve datos personales: en la bandeja aparecen los alimentos
personales y las correcciones sin el nombre ni el correo de quien los creó.
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core.forms import (
    AlimentoCatalogoForm,
    CoeficienteForm,
    ComponentesFormSet,
    FraseReferenciaForm,
    MetodoForm,
    PorcionForm,
    PreparacionForm,
    ResolverTerminoForm,
    RevisarCorreccionForm,
    TerminoForm,
)
from core.models import (
    Alimento,
    Ambito,
    CoeficienteAbsorcion,
    Correccion,
    EjecucionExactitud,
    FraseReferencia,
    HistorialCatalogo,
    MetodoCoccion,
    PorcionCasera,
    Preparacion,
    TerminoLexico,
    TerminoPendiente,
    VersionCatalogo,
)
from core.services import curacion, reportes
from core.services.catalogo import opciones_busqueda
from core.services.texto import normalizar
from core.views.utilidades import curador_o_admin, solo_curador


def _destinos():
    return opciones_busqueda() + list(MetodoCoccion.objects.values_list("nombre", flat=True))


@solo_curador
def bandeja(request):
    datos = curacion.bandeja()
    return render(request, "curacion/bandeja.html", {
        **datos, "resolver": ResolverTerminoForm(), "destinos": _destinos(),
        "version": VersionCatalogo.borrador(), "publicada": VersionCatalogo.publicada_vigente(),
    })


@solo_curador
@require_POST
def termino_resolver(request, pk):
    pendiente = get_object_or_404(TerminoPendiente, pk=pk, estado=TerminoPendiente.Estado.PENDIENTE)
    form = ResolverTerminoForm(request.POST)
    if form.is_valid():
        try:
            curacion.resolver_termino(pendiente, form.cleaned_data["destino"], request.user)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            messages.success(request, f"«{pendiente.termino}» ahora se reconoce como {form.cleaned_data['destino']}.")
    else:
        messages.error(request, " ".join(e for errores in form.errors.values() for e in errores))
    return redirect("curacion")


@solo_curador
@require_POST
def termino_descartar(request, pk):
    pendiente = get_object_or_404(TerminoPendiente, pk=pk)
    curacion.descartar_termino(pendiente, request.user)
    messages.info(request, f"«{pendiente.termino}» se descartó.")
    return redirect("curacion")


@solo_curador
@require_POST
def personal_revisar(request, pk):
    alimento = get_object_or_404(Alimento, pk=pk, ambito=Ambito.PERSONAL)
    if request.POST.get("decision") == "aprobar":
        try:
            curacion.aprobar_alimento_personal(alimento, request.user)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
            return redirect("curacion")
        messages.success(request, f"«{alimento.nombre}» se incorporó al catálogo global (versión en borrador).")
    else:
        curacion.rechazar_alimento_personal(alimento, request.user)
        messages.info(request, f"«{alimento.nombre}» seguirá siendo solo personal.")
    return redirect("curacion")


@solo_curador
def correccion_revisar(request, pk):
    correccion = get_object_or_404(Correccion.objects.select_related("item"), pk=pk)
    form = RevisarCorreccionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        curacion.revisar_correccion(correccion, form.cleaned_data["decision"] == "aceptar",
                                    form.cleaned_data["resolucion"], request.user)
        messages.success(request, "Corrección revisada. El usuario recibió la respuesta.")
        return redirect("curacion")
    return render(request, "curacion/correccion.html", {"correccion": correccion, "form": form})


# --- Catálogo: alimentos -------------------------------------------------------------


@curador_o_admin
def alimentos(request):
    consulta = request.GET.get("q", "").strip()
    lista = Alimento.objects.filter(ambito=Ambito.GLOBAL)
    if consulta:
        lista = lista.filter(Q(nombre__icontains=consulta) | Q(categoria__icontains=consulta))
    if request.GET.get("verificado") in ("si", "no"):
        lista = lista.filter(verificado=request.GET["verificado"] == "si")
    pagina = Paginator(lista.order_by("nombre"), 40).get_page(request.GET.get("pagina"))
    return render(request, "curacion/alimentos.html", {"pagina": pagina, "q": consulta, "total": lista.count()})


def _guardar_con_historial(request, form, descripcion_nuevo, descripcion_edicion):
    antes = curacion.instantanea(form.instance) if form.instance.pk else None
    with transaction.atomic():
        obj = form.save()
        curacion.registrar_cambio(obj, (descripcion_edicion if antes else descripcion_nuevo).format(obj=obj),
                                  antes, request.user)
    return obj


@solo_curador
def alimento_editar(request, pk=None):
    alimento = get_object_or_404(Alimento, pk=pk, ambito=Ambito.GLOBAL) if pk else None
    form = AlimentoCatalogoForm(request.POST or None, instance=alimento)
    if request.method == "POST" and form.is_valid():
        obj = _guardar_con_historial(request, form, "Nuevo alimento: {obj}", "Edición de alimento: {obj}")
        messages.success(request, f"«{obj}» guardado en la versión en borrador del catálogo.")
        return redirect("catalogo_alimentos")
    return render(request, "generico/formulario.html", {
        "titulo": f"Editar «{alimento}»" if alimento else "Nuevo alimento", "form": form, "boton": "Guardar",
        "intro": "Valores por 100 g. La energía debe coincidir con proteínas×4 + carbohidratos×4 + grasas×9 "
                 "dentro de la tolerancia configurada. Los datos desconocidos se dejan vacíos, nunca en cero.",
        "volver": reverse("catalogo_alimentos"),
    })


@solo_curador
@require_POST
def verificar(request, tipo, pk):
    modelo = Alimento if tipo == "alimento" else Preparacion
    obj = get_object_or_404(modelo, pk=pk)
    curacion.validar_registro(obj, request.user)
    messages.success(request, f"«{obj}» marcado como verificado contra su fuente.")
    return redirect(request.POST.get("volver") or "catalogo_alimentos")


# --- Catálogo: preparaciones ---------------------------------------------------------


@curador_o_admin
def preparaciones(request):
    consulta = request.GET.get("q", "").strip()
    lista = Preparacion.objects.all().prefetch_related("componentes__alimento").select_related("metodo_defecto")
    if consulta:
        lista = lista.filter(Q(nombre__icontains=consulta) | Q(region__icontains=consulta))
    return render(request, "curacion/preparaciones.html", {"preparaciones": lista, "q": consulta})


@solo_curador
def preparacion_editar(request, pk=None):
    preparacion = get_object_or_404(Preparacion, pk=pk) if pk else Preparacion()
    form = PreparacionForm(request.POST or None, instance=preparacion if pk else None)
    componentes = ComponentesFormSet(request.POST or None, instance=preparacion if pk else Preparacion(), prefix="cmp")
    if request.method == "POST" and form.is_valid() and componentes.is_valid():
        antes = curacion.instantanea(preparacion) if pk else None
        with transaction.atomic():
            obj = form.save()
            componentes.instance = obj
            componentes.save()
            curacion.registrar_cambio(obj, f"{'Edición' if pk else 'Nueva'} preparación: {obj}", antes, request.user)
        aviso = obj.validar_peso()
        if aviso:
            messages.warning(request, f"Guardada, pero revisa la receta: {aviso}")
        else:
            messages.success(request, f"«{obj}» guardada.")
        return redirect("catalogo_preparaciones")
    return render(request, "curacion/preparacion_form.html", {
        "form": form, "componentes": componentes, "preparacion": preparacion if pk else None,
        "aviso_peso": preparacion.validar_peso() if pk else "",
    })


# --- Catálogo: métodos, coeficientes, léxico, porciones ----------------------------------


@curador_o_admin
def metodos(request):
    return render(request, "curacion/metodos.html", {
        "metodos": MetodoCoccion.objects.all(),
        "coeficientes": CoeficienteAbsorcion.objects.select_related("metodo"),
    })


@solo_curador
def metodo_editar(request, pk):
    metodo = get_object_or_404(MetodoCoccion, pk=pk)
    form = MetodoForm(request.POST or None, instance=metodo)
    if request.method == "POST" and form.is_valid():
        _guardar_con_historial(request, form, "Nuevo método: {obj}", "Edición de método: {obj}")
        messages.success(request, "Método actualizado.")
        return redirect("catalogo_metodos")
    return render(request, "generico/formulario.html", {
        "titulo": f"Método: {metodo}", "form": form, "boton": "Guardar", "volver": reverse("catalogo_metodos"),
        "intro": "Los métodos no se eliminan: se inactivan. Cada cambio queda en el historial con su versión.",
    })


@solo_curador
def coeficiente_editar(request, pk=None):
    coeficiente = get_object_or_404(CoeficienteAbsorcion, pk=pk) if pk else None
    form = CoeficienteForm(request.POST or None, instance=coeficiente)
    if request.method == "POST" and form.is_valid():
        _guardar_con_historial(request, form, "Nuevo coeficiente: {obj}", "Edición de coeficiente: {obj}")
        messages.success(request, "Coeficiente guardado.")
        return redirect("catalogo_coeficientes")
    return render(request, "generico/formulario.html", {
        "titulo": "Coeficiente de absorción", "form": form, "boton": "Guardar", "volver": reverse("catalogo_coeficientes"),
        "intro": "Porcentaje de aceite absorbido sobre el peso crudo. Deben estar respaldados por referencias "
                 "y validados por el nutricionista antes de usarse.",
    })


@curador_o_admin
def lexico(request):
    consulta = normalizar(request.GET.get("q", ""))
    lista = TerminoLexico.objects.select_related("alimento", "preparacion", "metodo")
    if consulta:
        lista = lista.filter(termino__icontains=consulta)
    pagina = Paginator(lista, 60).get_page(request.GET.get("pagina"))
    return render(request, "curacion/lexico.html", {"pagina": pagina, "q": request.GET.get("q", ""), "total": lista.count()})


@solo_curador
def termino_editar(request, pk=None):
    termino = get_object_or_404(TerminoLexico, pk=pk) if pk else None
    form = TerminoForm(request.POST or None, instance=termino)
    if request.method == "POST" and form.is_valid():
        _guardar_con_historial(request, form, "Nuevo término: {obj}", "Edición de término: {obj}")
        messages.success(request, "Término guardado.")
        return redirect("catalogo_lexico")
    return render(request, "generico/formulario.html", {
        "titulo": "Término del léxico", "form": form, "boton": "Guardar", "volver": reverse("catalogo_lexico"),
        "datalist": _destinos(), "datalist_id": "destinos",
        "intro": "El término se guarda en minúsculas y sin tildes. No puede haber dos términos iguales con destinos distintos.",
    })


@curador_o_admin
def porciones(request):
    consulta = request.GET.get("q", "").strip()
    lista = PorcionCasera.objects.select_related("alimento", "preparacion")
    if consulta:
        lista = lista.filter(Q(alimento__nombre__icontains=consulta) | Q(preparacion__nombre__icontains=consulta))
    pagina = Paginator(lista.order_by("alimento__nombre", "preparacion__nombre", "medida"), 60).get_page(request.GET.get("pagina"))
    return render(request, "curacion/porciones.html", {"pagina": pagina, "q": consulta})


@solo_curador
def porcion_editar(request, pk=None):
    porcion = get_object_or_404(PorcionCasera, pk=pk) if pk else None
    inicial = {"destino_texto": (porcion.alimento or porcion.preparacion).nombre} if porcion else {}
    form = PorcionForm(request.POST or None, instance=porcion, initial=inicial)
    if request.method == "POST" and form.is_valid():
        _guardar_con_historial(request, form, "Nueva porción: {obj}", "Edición de porción: {obj}")
        messages.success(request, "Porción guardada.")
        return redirect("catalogo_porciones")
    return render(request, "generico/formulario.html", {
        "titulo": "Porción casera", "form": form, "boton": "Guardar", "volver": reverse("catalogo_porciones"),
        "datalist": opciones_busqueda(), "datalist_id": "destinos",
        "intro": "Gramos para alimentos sólidos; mililitros para bebidas.",
    })


# --- Versiones, historial y exactitud ----------------------------------------------------


@curador_o_admin
def versiones(request):
    borrador = VersionCatalogo.objects.filter(estado=VersionCatalogo.Estado.BORRADOR).first()
    return render(request, "curacion/versiones.html", {
        "versiones": VersionCatalogo.objects.all(),
        "borrador": borrador,
        "cambios": HistorialCatalogo.objects.select_related("version", "usuario")[:80],
    })


@solo_curador
@require_POST
def version_publicar(request):
    version = get_object_or_404(VersionCatalogo, estado=VersionCatalogo.Estado.BORRADOR)
    ejecucion = curacion.publicar_version(version, request.user, request.POST.get("notas", ""))
    if ejecucion.aprobada:
        messages.success(request, f"Versión {version.numero} publicada. Identificación {ejecucion.identificacion_pct} %, "
                                  f"método {ejecucion.coccion_pct} %.")
    else:
        messages.error(request, f"La publicación se bloqueó: la exactitud no alcanzó los umbrales "
                                f"(identificación {ejecucion.identificacion_pct} %, método {ejecucion.coccion_pct} %). "
                                "Revisa los fallos en las pruebas de exactitud.")
    return redirect("exactitud" if not ejecucion.aprobada else "versiones")


@solo_curador
@require_POST
def cambio_revertir(request, pk):
    cambio = get_object_or_404(HistorialCatalogo, pk=pk)
    curacion.revertir_cambio(cambio, request.user)
    messages.success(request, f"Se revirtió: {cambio.descripcion}")
    return redirect("versiones")


@curador_o_admin
def exactitud(request):
    return render(request, "curacion/exactitud.html", {
        "ultima": EjecucionExactitud.objects.first(),
        "ejecuciones": EjecucionExactitud.objects.select_related("version")[:10],
        "frases": FraseReferencia.objects.all(),
    })


@solo_curador
@require_POST
def exactitud_ejecutar(request):
    ejecucion = curacion.ejecutar_exactitud(VersionCatalogo.objects.filter(estado="borrador").first(), request.user)
    messages.info(request, f"Identificación {ejecucion.identificacion_pct} %, método de cocción {ejecucion.coccion_pct} % "
                           f"en {ejecucion.total_frases} frases.")
    return redirect("exactitud")


@solo_curador
def frase_editar(request, pk=None):
    frase = get_object_or_404(FraseReferencia, pk=pk) if pk else None
    form = FraseReferenciaForm(request.POST or None, instance=frase)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Frase de referencia guardada.")
        return redirect("exactitud")
    return render(request, "generico/formulario.html", {
        "titulo": "Frase de referencia", "form": form, "boton": "Guardar", "volver": reverse("exactitud"),
        "intro": "Marca «validada» solo cuando un nutricionista haya revisado el resultado esperado.",
    })


@curador_o_admin
def indicadores(request):
    """Panel agregado y anonimizado: nunca muestra datos individuales."""
    return render(request, "curacion/indicadores.html", {"panel": reportes.panel_agregado()})
