"""
Vistas del Usuario para el registro de comidas (RF7, RF10, RF13, RF14) y el
panel del día (RF17, RF18).

Cada consulta filtra por `usuario=request.user`: pedir la comida de otra
persona devuelve 404.
"""

import uuid
from datetime import datetime, timedelta

from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.forms import (
    AgregarItemForm,
    ComidaManualForm,
    ComidaTextoForm,
    CorreccionForm,
    FilasManualesFormSet,
)
from core.models import (
    Comida,
    Correccion,
    DiaRegistro,
    EstadoComida,
    ItemComida,
    MetodoCoccion,
    PorcionCasera,
    Preparacion,
)
from core.services import comidas as servicio
from core.services import curacion, reportes, salvaguardas
from core.services.calculo import CantidadInvalida
from core.services.catalogo import buscar_por_nombre, opciones_busqueda
from core.services.ia import ia_disponible
from core.services.parametros import parametro
from core.views.utilidades import fecha_de, solo_usuario


def _momento(fecha, hora):
    return timezone.make_aware(datetime.combine(fecha, hora or timezone.localtime().time()))


def _mis_comidas(request):
    return Comida.objects.filter(usuario=request.user)


# --- Panel del día -----------------------------------------------------------------


@solo_usuario
def panel(request):
    fecha = fecha_de(request)
    resumen = reportes.resumen_dia(request.user, fecha)
    alertas = salvaguardas.notificar_riesgos(request.user) if fecha == timezone.localdate() else []
    pendiente = _mis_comidas(request).filter(estado=EstadoComida.INTERPRETADA).first()
    return render(request, "usuario/panel.html", {
        "fecha": fecha, "resumen": resumen, "alertas": alertas, "pendiente": pendiente,
        "dia_anterior": fecha - timedelta(days=1), "dia_siguiente": fecha + timedelta(days=1),
        "es_hoy": fecha == timezone.localdate(), "series": reportes.series(request.user, 7, fecha),
        "contacto": parametro("contacto_apoyo"),
    })


@solo_usuario
@require_POST
def marcar_dia(request):
    """Marcar el día como completo evita falsas alertas y habilita el ajuste semanal."""
    fecha = fecha_de(request)
    dia, _ = DiaRegistro.objects.get_or_create(usuario=request.user, fecha=fecha)
    dia.completo = not dia.completo
    dia.save(update_fields=["completo"])
    messages.success(request, "Día marcado como completo." if dia.completo else "El día ya no está marcado como completo.")
    return redirect(f"/panel/?fecha={fecha:%Y-%m-%d}")


# --- Registro por texto libre (RF13) --------------------------------------------------


@solo_usuario
def comida_nueva(request):
    form = ComidaTextoForm(request.POST or None, initial={"fecha": fecha_de(request)})
    if request.method == "POST" and form.is_valid():
        datos = form.cleaned_data
        try:
            comida = servicio.crear_desde_texto(request.user, datos["texto"],
                                                fecha_hora=_momento(datos["fecha"], datos["hora"]),
                                                tipo=datos["tipo"] or None)
        except servicio.ComidaNoConfirmable as exc:
            form.add_error("texto", str(exc))
        else:
            for aviso in getattr(comida, "avisos_interpretacion", []):
                messages.info(request, aviso)
            if comida.preguntas:
                return redirect("comida_aclarar", pk=comida.pk)
            return redirect("comida_confirmar", pk=comida.pk)
    return render(request, "usuario/comida_nueva.html", {
        "form": form, "ia_disponible": ia_disponible(), "acepta_ia": request.user.cuenta.acepta_ia,
        "recientes": _mis_comidas(request).que_cuentan().exclude(texto_original="")[:5],
    })


@solo_usuario
def comida_aclarar(request, pk):
    """Como máximo dos preguntas cortas con opciones tocables (RF13)."""
    comida = get_object_or_404(_mis_comidas(request), pk=pk, estado=EstadoComida.INTERPRETADA)
    if not comida.preguntas:
        return redirect("comida_confirmar", pk=comida.pk)
    if request.method == "POST":
        servicio.responder_preguntas(comida, request.POST)
        return redirect("comida_confirmar", pk=comida.pk)
    return render(request, "usuario/comida_aclarar.html", {"comida": comida})


def _contexto_edicion(request, comida, agregar=None):
    return {
        "comida": comida,
        "items": comida.items.all().select_related("alimento", "preparacion", "metodo"),
        "metodos": MetodoCoccion.objects.filter(estado="activo"),
        "agregar": agregar or AgregarItemForm(),
        "catalogo": opciones_busqueda(request.user),
        "umbral": parametro("umbral_confianza"),
    }


def _procesar_edicion(request, comida) -> bool:
    """Aplica los cambios de la lista editable. Devuelve False si hubo errores."""
    correcto = True
    for item in comida.items.all():
        prefijo = f"item-{item.pk}-"
        if f"{prefijo}cantidad" not in request.POST:
            continue
        descartar = request.POST.get(f"{prefijo}descartar") == "on"
        destino = None
        nombre = request.POST.get(f"{prefijo}destino", "").strip()
        if nombre and nombre != item.nombre_mostrado and not descartar:
            destino = buscar_por_nombre(nombre, request.user)
            if destino is None:
                messages.error(request, f"«{nombre}» no está en el catálogo. Elígelo de la lista o créalo como alimento personal.")
                correcto = False
        metodo = None
        metodo_id = request.POST.get(f"{prefijo}metodo", "")
        if metodo_id and (item.metodo is None or str(item.metodo_id) != metodo_id):
            metodo = MetodoCoccion.objects.filter(pk=metodo_id).first()
        cantidad = request.POST.get(f"{prefijo}cantidad", "").replace(",", ".").strip()
        try:
            servicio.editar_item(item, destino=destino, metodo=metodo, descartar=descartar,
                                 cantidad_g=cantidad if cantidad and not descartar else None)
        except CantidadInvalida as exc:
            messages.error(request, f"{item.nombre_mostrado}: {exc}")
            correcto = False
    return correcto


@solo_usuario
def comida_confirmar(request, pk):
    """
    Pantalla de confirmación (RF13): cada componente con cantidad, método,
    energía, rango y confianza, todo editable. Nada cuenta hasta confirmar.
    """
    comida = get_object_or_404(_mis_comidas(request).exclude(estado=EstadoComida.DESCARTADA), pk=pk)
    agregar = AgregarItemForm(request.POST if request.POST.get("accion") == "agregar" else None)
    if request.method == "POST":
        accion = request.POST.get("accion")
        if accion == "agregar":
            if agregar.is_valid():
                destino = buscar_por_nombre(agregar.cleaned_data["alimento"], request.user)
                if destino is None:
                    agregar.add_error("alimento", "No está en el catálogo.")
                else:
                    servicio.agregar_item(comida, destino, agregar.cleaned_data["cantidad_g"], agregar.cleaned_data["metodo"])
                    messages.success(request, f"Se agregó {destino.nombre}.")
                    return redirect("comida_confirmar", pk=comida.pk)
        elif accion in ("recalcular", "confirmar", "guardar"):
            correcto = _procesar_edicion(request, comida)
            comida.refresh_from_db()
            if accion == "confirmar" and correcto:
                try:
                    servicio.confirmar(comida)
                except servicio.ComidaNoConfirmable as exc:
                    messages.error(request, str(exc))
                else:
                    messages.success(request, "Comida guardada.")
                    return redirect(f"/panel/?fecha={comida.fecha:%Y-%m-%d}")
            elif accion == "guardar" and correcto:
                messages.success(request, "Cambios guardados y recalculados.")
                return redirect("comida_detalle", pk=comida.pk)
            elif correcto:
                messages.info(request, "Valores recalculados.")
                return redirect("comida_confirmar", pk=comida.pk)
        elif accion == "descartar_comida":
            servicio.descartar(comida)
            messages.info(request, "La comida se descartó.")
            return redirect("panel")
    return render(request, "usuario/comida_confirmar.html", _contexto_edicion(request, comida, agregar))


# --- Búsqueda manual (RF7, RF12 de respaldo) -------------------------------------------


def _filas_desde_formset(formset):
    filas = []
    for form in formset:
        if not form.cleaned_data or form.cleaned_data.get("DELETE"):
            continue
        destino = form.cleaned_data["destino"]
        cantidad = form.cleaned_data["cantidad"]
        unidad = form.cleaned_data["unidad"]
        fila = {"destino": destino, "metodo": form.cleaned_data.get("metodo"), "fuente_cantidad": "gramos"}
        # Solo los líquidos tienen densidad; para los sólidos vale 1 (g = g).
        densidad = getattr(destino, "densidad", None) or 1
        if unidad == "g":
            fila["cantidad_g"] = cantidad
        elif unidad == "ml":
            fila["cantidad_g"] = cantidad * densidad
        else:
            filtro = {"preparacion": destino} if isinstance(destino, Preparacion) else {"alimento": destino}
            porcion = PorcionCasera.objects.filter(medida=unidad, **filtro).first()
            if porcion is not None:
                base = porcion.cantidad * densidad
            else:
                genericas = parametro("medidas_genericas_ml")
                if unidad not in genericas:
                    form.add_error("unidad", f"{destino.nombre} no tiene la medida «{unidad}». Indícalo en gramos.")
                    return None
                base = genericas[unidad] * densidad
            fila["cantidad_g"] = cantidad * base
            fila["fuente_cantidad"] = "medida"
            fila["medida"] = unidad
        filas.append(fila)
    return filas


@solo_usuario
def comida_manual(request):
    """Siempre disponible, también sin IA ni conexión con el proveedor."""
    cabecera = ComidaManualForm(request.POST or None, initial={"fecha": fecha_de(request), "clave": uuid.uuid4()})
    filas = FilasManualesFormSet(request.POST or None, usuario=request.user, prefix="fila")
    if request.method == "POST" and cabecera.is_valid() and filas.is_valid():
        datos_filas = _filas_desde_formset(filas)
        if datos_filas:
            try:
                comida = servicio.crear_manual(
                    request.user, datos_filas, fecha_hora=_momento(cabecera.cleaned_data["fecha"], cabecera.cleaned_data["hora"]),
                    tipo=cabecera.cleaned_data["tipo"], clave_idempotencia=cabecera.cleaned_data["clave"],
                )
            except CantidadInvalida as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, "Comida registrada.")
                return redirect(f"/panel/?fecha={comida.fecha:%Y-%m-%d}")
    return render(request, "usuario/comida_manual.html", {
        "cabecera": cabecera, "filas": filas, "catalogo": opciones_busqueda(request.user),
    })


# --- Historial, detalle, favoritas, eliminación -------------------------------------------


@solo_usuario
def historial(request):
    hasta = fecha_de(request, "hasta")
    try:
        desde = timezone.datetime.strptime(request.GET.get("desde", ""), "%Y-%m-%d").date()
    except ValueError:
        desde = hasta - timedelta(days=13)
    comidas = (_mis_comidas(request).que_cuentan()
               .filter(fecha_hora__date__gte=desde, fecha_hora__date__lte=hasta)
               .prefetch_related("items__metodo").order_by("-fecha_hora"))
    dias = {}
    for comida in comidas:
        dias.setdefault(comida.fecha, []).append(comida)
    pagina = Paginator(list(dias.items()), 7).get_page(request.GET.get("pagina"))
    return render(request, "usuario/historial.html", {
        "pagina": pagina, "desde": desde, "hasta": hasta,
        "totales": {f: reportes.resumen_dia(request.user, f) for f, _ in pagina},
    })


@solo_usuario
def comida_detalle(request, pk):
    comida = get_object_or_404(_mis_comidas(request).exclude(estado=EstadoComida.INTERPRETADA), pk=pk)
    return render(request, "usuario/comida_detalle.html", {
        "comida": comida, "items": comida.items.select_related("metodo", "alimento", "preparacion"),
    })


@solo_usuario
def comida_eliminar(request, pk):
    """Eliminar con confirmación previa. Es una baja lógica: estado «descartada»."""
    comida = get_object_or_404(_mis_comidas(request).que_cuentan(), pk=pk)
    if request.method == "POST":
        servicio.descartar(comida)
        messages.success(request, "Comida eliminada de tus registros.")
        return redirect("historial")
    return render(request, "generico/confirmar.html", {
        "titulo": "¿Eliminar esta comida?",
        "mensaje": f"{comida.get_tipo_display()} del {comida.fecha:%d/%m/%Y} ({comida.kcal:.0f} kcal estimadas). "
                   "Dejará de contar en tus totales.",
        "boton": "Sí, eliminar", "volver": f"/comidas/{comida.pk}/",
    })


@solo_usuario
@require_POST
def comida_favorita(request, pk):
    comida = get_object_or_404(_mis_comidas(request).que_cuentan(), pk=pk)
    servicio.marcar_favorita(comida, request.POST.get("nombre", ""), not comida.es_favorita)
    messages.success(request, "Guardada en favoritas." if comida.es_favorita else "Quitada de favoritas.")
    return redirect("comida_detalle", pk=comida.pk)


@solo_usuario
def favoritas(request):
    return render(request, "usuario/favoritas.html", {
        "favoritas": _mis_comidas(request).filter(es_favorita=True).exclude(estado=EstadoComida.DESCARTADA),
        "clave": uuid.uuid4(),
    })


@solo_usuario
@require_POST
def favorita_repetir(request, pk):
    original = get_object_or_404(_mis_comidas(request).filter(es_favorita=True), pk=pk)
    try:
        clave = uuid.UUID(request.POST.get("clave", ""))
    except ValueError:
        clave = uuid.uuid4()
    comida = servicio.repetir_favorita(original, clave_idempotencia=clave)
    messages.success(request, f"Registrada «{original.nombre_favorita}» con el catálogo actual.")
    return redirect(f"/panel/?fecha={comida.fecha:%Y-%m-%d}")


# --- Correcciones (RF10) --------------------------------------------------------------------


@solo_usuario
def item_corregir(request, pk):
    item = get_object_or_404(ItemComida.objects.filter(comida__usuario=request.user), pk=pk)
    form = CorreccionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        correccion = curacion.crear_correccion(item, request.user, form.cleaned_data["tipo"],
                                               form.cleaned_data["valor_sugerido"], form.cleaned_data["comentario"])
        if correccion.aplicada_a_comida:
            messages.success(request, "Corregimos tu comida de inmediato. El equipo de curación revisará si el catálogo también debe cambiar.")
        else:
            messages.success(request, "Gracias. El equipo de curación revisará tu reporte.")
        return redirect("comida_detalle", pk=item.comida_id)
    return render(request, "generico/formulario.html", {
        "titulo": f"Reportar un error en «{item.nombre_mostrado}»", "form": form, "boton": "Enviar",
        "intro": f"Estimación actual: {item.cantidad_g} g, {item.metodo or 'sin método'}, {item.kcal} kcal.",
        "volver": f"/comidas/{item.comida_id}/",
    })


@solo_usuario
def mis_correcciones(request):
    return render(request, "usuario/correcciones.html", {
        "correcciones": Correccion.objects.filter(usuario=request.user).select_related("item"),
    })
