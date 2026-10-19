"""
Vistas de la aplicación web (las páginas que ve el usuario).

Cada vista hace tres cosas y nada más: leer lo que llega, pedirle el trabajo a
un servicio de core/services/ y elegir qué plantilla mostrar. Los cálculos no
se hacen aquí.

CONTROL DE ACCESO
-----------------
Todas las vistas privadas llevan @login_required y todas las consultas filtran
por `usuario=request.user`. Pedir la comida de otro usuario devuelve 404, no
el contenido ajeno.
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.forms import (
    AnalisisComidaForm,
    ComidaManualForm,
    DetalleComidaFormSet,
    DetalleComidaFormSetManual,
    PerfilForm,
    RegistroUsuarioForm,
)
from core.models import DetalleComida, OrigenRegistro, RegistroComida
from core.services import ai_service
from core.services.comidas import (
    filas_desde_formset,
    guardar_comida,
    reemplazar_detalles,
)
from core.services.nutrition import CantidadInvalida, resumen_diario, sumar_detalles

DIAS_EN_LA_TENDENCIA = 7


def _fecha_de_la_peticion(request):
    """
    Lee ?fecha=AAAA-MM-DD de la URL; si no viene o es inválida, usa hoy.

    Se usa en el panel y en el historial para moverse entre días.
    """
    texto = request.GET.get("fecha")
    if texto:
        parsed = timezone.datetime.strptime
        try:
            return parsed(texto, "%Y-%m-%d").date()
        except ValueError:
            messages.warning(request, "La fecha indicada no es válida; se muestra hoy.")
    return timezone.localdate()


def _comidas_con_detalles(usuario, **filtros):
    """Consulta de comidas con sus detalles y alimentos en una sola pasada."""
    return (
        RegistroComida.objects.filter(usuario=usuario, **filtros)
        .prefetch_related(
            Prefetch("detalles", queryset=DetalleComida.objects.select_related("alimento"))
        )
    )


# --- Autenticación -----------------------------------------------------------


def registro_usuario(request):
    """
    Alta de una cuenta nueva.

    Al guardar, la señal de core/signals.py crea el perfil nutricional, y aquí
    se inicia sesión para que el usuario caiga directamente en su panel.
    """
    if request.user.is_authenticated:
        return redirect("panel")

    if request.method == "POST":
        form = RegistroUsuarioForm(request.POST)
        if form.is_valid():
            usuario = form.save()
            login(request, usuario)
            messages.success(
                request,
                "Cuenta creada. Configura tu meta diaria en la página de perfil.",
            )
            return redirect("panel")
    else:
        form = RegistroUsuarioForm()

    return render(request, "registration/registro.html", {"form": form})


# --- Panel principal ---------------------------------------------------------


@login_required
def panel(request):
    """
    Panel del día: meta, consumo, macronutrientes, gráficos y comidas.

    Los datos de los gráficos se calculan aquí, en el servidor, a partir de los
    registros reales. Si el usuario no tiene nada guardado se muestra un estado
    vacío, nunca datos de ejemplo.
    """
    fecha = _fecha_de_la_peticion(request)
    resumen = resumen_diario(request.user, fecha)
    comidas = _comidas_con_detalles(request.user, fecha=fecha)

    # Tendencia de los últimos días (incluido el seleccionado).
    inicio = fecha - timedelta(days=DIAS_EN_LA_TENDENCIA - 1)
    detalles_rango = DetalleComida.objects.filter(
        registro__usuario=request.user,
        registro__confirmado=True,
        registro__fecha__gte=inicio,
        registro__fecha__lte=fecha,
    ).select_related("registro")

    por_dia: dict[str, float] = {}
    for i in range(DIAS_EN_LA_TENDENCIA):
        dia = inicio + timedelta(days=i)
        por_dia[dia.isoformat()] = 0.0
    for detalle in detalles_rango:
        if detalle.calorias is None:
            continue
        clave = detalle.registro.fecha.isoformat()
        if clave in por_dia:
            por_dia[clave] += float(detalle.calorias)

    datos_grafico = {
        "tendencia": {
            "etiquetas": list(por_dia.keys()),
            "valores": [round(v, 1) for v in por_dia.values()],
            "meta": resumen["meta"],
        },
        "macros": {
            "etiquetas": ["Proteínas", "Carbohidratos", "Grasas"],
            "valores": [
                float(resumen["proteinas"] or 0),
                float(resumen["carbohidratos"] or 0),
                float(resumen["grasas"] or 0),
            ],
        },
    }

    contexto = {
        "fecha": fecha,
        "dia_anterior": fecha - timedelta(days=1),
        "dia_siguiente": fecha + timedelta(days=1),
        "resumen": resumen,
        "comidas": comidas,
        "tiene_registros": comidas.exists(),
        # Se pasa el diccionario tal cual: el filtro json_script de la
        # plantilla es el que lo convierte a JSON (y lo escapa). Serializarlo
        # aquí con json.dumps lo codificaría dos veces y el JavaScript
        # recibiría una cadena en lugar de un objeto.
        "datos_grafico": datos_grafico,
        "ia_disponible": ai_service.ia_configurada(),
    }
    return render(request, "core/panel.html", contexto)


# --- Registro de comidas -----------------------------------------------------


@login_required
def nueva_comida(request):
    """
    Paso 1: el usuario describe lo que comió y se envía a la IA.

    Si la IA no está configurada o falla, se muestra el motivo y se ofrece el
    registro manual. La aplicación nunca se queda sin salida.
    """
    fecha_inicial = _fecha_de_la_peticion(request)

    if request.method == "POST":
        form = AnalisisComidaForm(request.POST)
        if form.is_valid():
            texto = form.cleaned_data["texto"]
            fecha = form.cleaned_data["fecha"]
            try:
                items = ai_service.analizar_texto(texto)
            except ai_service.ErrorIA as exc:
                messages.error(request, exc.mensaje_usuario)
                return render(
                    request,
                    "core/nueva_comida.html",
                    {
                        "form": form,
                        "ia_disponible": ai_service.ia_configurada(),
                        "hubo_error_ia": True,
                    },
                )

            formset = DetalleComidaFormSet(
                initial=[
                    {
                        "alimento": item["alimento_id"],
                        "nombre_mostrado": item["nombre"],
                        "cantidad": item["cantidad"],
                        "unidad": item["unidad"],
                        "metodo_preparacion": item["metodo_preparacion"],
                    }
                    for item in items
                ]
            )
            return render(
                request,
                "core/confirmar_comida.html",
                {
                    "formset": formset,
                    "items": items,
                    "descripcion": texto,
                    "fecha": fecha,
                    "origen": OrigenRegistro.IA,
                },
            )
    else:
        form = AnalisisComidaForm(initial={"fecha": fecha_inicial})

    return render(
        request,
        "core/nueva_comida.html",
        {"form": form, "ia_disponible": ai_service.ia_configurada()},
    )


@login_required
@require_POST
def confirmar_comida(request):
    """
    Paso 2: guarda la comida con las correcciones que hizo el usuario.

    Lo que se guarda es SIEMPRE lo que el usuario confirmó en el formulario,
    no lo que devolvió la IA: la IA solo rellenó los valores iniciales.
    """
    formset = DetalleComidaFormSet(request.POST)
    descripcion = request.POST.get("descripcion", "Comida")
    fecha_texto = request.POST.get("fecha", "")
    origen = (
        OrigenRegistro.IA
        if request.POST.get("origen") == OrigenRegistro.IA
        else OrigenRegistro.MANUAL
    )

    try:
        fecha = timezone.datetime.strptime(fecha_texto, "%Y-%m-%d").date()
    except ValueError:
        fecha = timezone.localdate()

    if formset.is_valid():
        filas = filas_desde_formset(formset)
        try:
            registro = guardar_comida(
                request.user,
                descripcion=descripcion,
                fecha=fecha,
                filas=filas,
                origen=origen,
                confirmado=True,
            )
        except CantidadInvalida as exc:
            messages.error(request, str(exc))
        else:
            pendientes = sum(
                1 for d in registro.detalles.all() if not d.tiene_datos_nutricionales
            )
            if pendientes:
                messages.warning(
                    request,
                    f"La comida se guardó, pero {pendientes} alimento(s) quedaron "
                    "sin valores nutricionales porque no están en el catálogo.",
                )
            else:
                messages.success(request, "Comida guardada.")
            return redirect(f"{_url_panel()}?fecha={fecha.isoformat()}")

    messages.error(request, "Revisa los datos de la lista de alimentos.")
    return render(
        request,
        "core/confirmar_comida.html",
        {
            "formset": formset,
            "descripcion": descripcion,
            "fecha": fecha,
            "origen": origen,
        },
    )


def _url_panel() -> str:
    from django.urls import reverse

    return reverse("panel")


@login_required
def comida_manual(request):
    """
    Registro manual, la alternativa que funciona siempre.

    No depende de la IA ni de JavaScript: el usuario elige los alimentos del
    catálogo y escribe las cantidades.
    """
    if request.method == "POST":
        form = ComidaManualForm(request.POST)
        formset = DetalleComidaFormSetManual(request.POST)
        if form.is_valid() and formset.is_valid():
            filas = filas_desde_formset(formset)
            try:
                registro = guardar_comida(
                    request.user,
                    descripcion=form.cleaned_data["descripcion"],
                    fecha=form.cleaned_data["fecha"],
                    hora=form.cleaned_data.get("hora"),
                    filas=filas,
                    origen=OrigenRegistro.MANUAL,
                    confirmado=True,
                )
            except CantidadInvalida as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, "Comida registrada manualmente.")
                return redirect(f"{_url_panel()}?fecha={registro.fecha.isoformat()}")
    else:
        form = ComidaManualForm(initial={"fecha": _fecha_de_la_peticion(request)})
        formset = DetalleComidaFormSetManual()

    return render(
        request, "core/comida_manual.html", {"form": form, "formset": formset}
    )


# --- Historial ---------------------------------------------------------------


@login_required
def historial(request):
    """
    Comidas del usuario agrupadas por fecha, de la más reciente a la más
    antigua, con el total de cada día.
    """
    comidas = _comidas_con_detalles(request.user).order_by("-fecha", "-creado_en")

    dias: dict = {}
    for comida in comidas:
        dias.setdefault(comida.fecha, []).append(comida)

    agrupado = []
    for fecha, lista in dias.items():
        detalles = [d for comida in lista for d in comida.detalles.all() if comida.confirmado]
        agrupado.append(
            {"fecha": fecha, "comidas": lista, "totales": sumar_detalles(detalles)}
        )

    return render(
        request,
        "core/historial.html",
        {"dias": agrupado, "tiene_registros": bool(agrupado)},
    )


@login_required
def detalle_comida(request, pk: int):
    """Ficha de una comida concreta. 404 si no es del usuario autenticado."""
    comida = get_object_or_404(
        _comidas_con_detalles(request.user), pk=pk
    )
    return render(
        request,
        "core/detalle_comida.html",
        {"comida": comida, "totales": comida.totales()},
    )


@login_required
def editar_comida(request, pk: int):
    """
    Corrige una comida ya guardada.

    Al guardar se recalculan todos sus detalles con el catálogo actual.
    """
    comida = get_object_or_404(RegistroComida, pk=pk, usuario=request.user)

    if request.method == "POST":
        form = ComidaManualForm(request.POST, instance=comida)
        formset = DetalleComidaFormSetManual(request.POST)
        if form.is_valid() and formset.is_valid():
            try:
                comida = form.save()
                reemplazar_detalles(comida, filas_desde_formset(formset))
            except CantidadInvalida as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, "Comida actualizada.")
                return redirect("detalle_comida", pk=comida.pk)
    else:
        form = ComidaManualForm(instance=comida)
        formset = DetalleComidaFormSetManual(
            initial=[
                {
                    "alimento": d.alimento_id,
                    "nombre_mostrado": d.nombre_mostrado,
                    "cantidad": d.cantidad,
                    "unidad": d.unidad,
                    "metodo_preparacion": d.metodo_preparacion,
                }
                for d in comida.detalles.all()
            ]
        )

    return render(
        request,
        "core/editar_comida.html",
        {"form": form, "formset": formset, "comida": comida},
    )


@login_required
def eliminar_comida(request, pk: int):
    """
    Elimina una comida, pidiendo confirmación antes (nunca con un GET suelto).
    """
    comida = get_object_or_404(RegistroComida, pk=pk, usuario=request.user)

    if request.method == "POST":
        fecha = comida.fecha
        comida.delete()
        messages.success(request, "Comida eliminada.")
        return redirect(f"{_url_panel()}?fecha={fecha.isoformat()}")

    return render(request, "core/eliminar_comida.html", {"comida": comida})


# --- Perfil ------------------------------------------------------------------


@login_required
def perfil(request):
    """Configura la meta diaria de calorías y los datos opcionales."""
    perfil_usuario = getattr(request.user, "perfil", None)
    if perfil_usuario is None:
        raise Http404("El usuario no tiene perfil nutricional.")

    if request.method == "POST":
        form = PerfilForm(request.POST, instance=perfil_usuario)
        if form.is_valid():
            form.save()
            messages.success(request, "Perfil actualizado.")
            return redirect("perfil")
    else:
        form = PerfilForm(instance=perfil_usuario)

    return render(
        request,
        "core/perfil.html",
        {"form": form, "perfil": perfil_usuario, "ia_disponible": ai_service.ia_configurada()},
    )
