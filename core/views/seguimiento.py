"""
Seguimiento del Usuario: peso (RF9), metas y ajuste semanal (RF8, RF16),
reportes (RF18) y la calculadora de aceite (RF15).
"""

from decimal import Decimal

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.forms import AjusteManualForm, CalculadoraAceiteForm, PesajeForm
from core.models import MetaCalorica, Pesaje
from core.services import metas, reportes, salvaguardas
from core.services.aceite import calcular_aceite
from core.services.calculo import r1
from core.views.utilidades import entero_de, solo_usuario

# --- Peso (RF9) ---------------------------------------------------------------------


@solo_usuario
def peso(request):
    form = PesajeForm(request.POST or None, usuario=request.user, initial={"fecha": timezone.localdate()})
    if request.method == "POST" and form.is_valid():
        pesaje = form.save(commit=False)
        pesaje.usuario = request.user
        anterior = Pesaje.objects.filter(usuario=request.user, fecha__lt=pesaje.fecha).order_by("-fecha").first()
        pesaje.save()
        if anterior and abs(pesaje.peso_kg - anterior.peso_kg) > Decimal("3") and (pesaje.fecha - anterior.fecha).days <= 1:
            messages.warning(request, f"El peso cambió {abs(pesaje.peso_kg - anterior.peso_kg):.1f} kg en un día. "
                                      "Si fue un error de digitación, puedes editarlo.")
        else:
            messages.success(request, "Pesaje registrado.")
        return redirect("peso")
    return render(request, "usuario/peso.html", {
        "form": form,
        "pesajes": Pesaje.objects.filter(usuario=request.user)[:30],
        "tendencia": list(reversed(salvaguardas.peso_tendencial(request.user)))[:30],
        "series": reportes.series(request.user, entero_de(request, "dias", 90, reportes.PERIODOS)),
        "ritmo": salvaguardas.ritmo_semanal_pct(request.user),
    })


@solo_usuario
def peso_editar(request, pk):
    pesaje = get_object_or_404(Pesaje, pk=pk, usuario=request.user)
    form = PesajeForm(request.POST or None, instance=pesaje, usuario=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Pesaje corregido.")
        return redirect("peso")
    return render(request, "generico/formulario.html", {"titulo": "Corregir pesaje", "form": form, "volver": "/peso/"})


@solo_usuario
def peso_eliminar(request, pk):
    pesaje = get_object_or_404(Pesaje, pk=pk, usuario=request.user)
    if request.method == "POST":
        pesaje.delete()
        messages.success(request, "Pesaje eliminado.")
        return redirect("peso")
    return render(request, "generico/confirmar.html", {
        "titulo": "¿Eliminar este pesaje?", "mensaje": f"{pesaje.fecha:%d/%m/%Y}: {pesaje.peso_kg} kg.",
        "boton": "Sí, eliminar", "volver": "/peso/",
    })


# --- Metas (RF8, RF16) -----------------------------------------------------------------


@solo_usuario
def metas_vista(request):
    vigente = metas.meta_vigente(request.user)
    form = AjusteManualForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            metas.ajuste_manual(request.user, form.cleaned_data["kcal"])
        except metas.AjusteNoPermitido as exc:
            form.add_error("kcal", str(exc))
        else:
            messages.success(request, "Meta actualizada.")
            return redirect("metas")
    perfil = getattr(request.user, "perfil", None)
    return render(request, "usuario/metas.html", {
        "vigente": vigente, "form": form,
        "historial": MetaCalorica.objects.filter(usuario=request.user).order_by("-creada_en"),
        "elegibilidad": salvaguardas.elegibilidad(perfil) if perfil else None,
        "piso": salvaguardas.piso_calorico(perfil.sexo) if perfil else None,
        "alcanzo_meta": bool(perfil and perfil.peso_meta_kg and metas.peso_actual(request.user) <= perfil.peso_meta_kg
                             and perfil.objetivo == "perder"),
    })


@solo_usuario
@require_POST
def meta_evaluar(request):
    """Ejecuta ahora la evaluación semanal de este usuario (en producción la corre el proceso semanal)."""
    resultado = metas.evaluar_ajuste_semanal(request.user)
    (messages.success if resultado.aplicado else messages.info)(request, resultado.mensaje)
    return redirect("metas")


@solo_usuario
@require_POST
def meta_revertir(request, pk):
    meta = get_object_or_404(MetaCalorica, pk=pk, usuario=request.user)
    try:
        metas.revertir(meta)
    except metas.AjusteNoPermitido as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Revertiste el ajuste: vuelves a tu meta anterior.")
    return redirect("metas")


@solo_usuario
@require_POST
def meta_mantenimiento(request):
    metas.pasar_a_mantenimiento(request.user)
    messages.success(request, "Pasaste a mantenimiento: tu meta ahora es igual a tu gasto estimado.")
    return redirect("metas")


# --- Reportes (RF18) --------------------------------------------------------------------


@solo_usuario
def reportes_vista(request):
    dias = entero_de(request, "dias", 30, reportes.PERIODOS)
    return render(request, "usuario/reportes.html", {"series": reportes.series(request.user, dias), "dias": dias,
                                                      "periodos": reportes.PERIODOS})


@solo_usuario
def reporte_csv(request):
    respuesta = HttpResponse(reportes.exportar_csv(request.user), content_type="text/csv; charset=utf-8")
    respuesta["Content-Disposition"] = f'attachment; filename="nutriregional-{timezone.localdate():%Y%m%d}.csv"'
    return respuesta


@solo_usuario
def reporte_imprimir(request):
    """Informe pensado para imprimir o guardar como PDF desde el navegador."""
    dias = entero_de(request, "dias", 30, reportes.PERIODOS)
    series = reportes.series(request.user, dias)
    filas = [
        {"fecha": e, "kcal": k, "min": mn, "max": mx, "meta": m}
        for e, k, mn, mx, m in zip(series["etiquetas"], series["ingesta"]["kcal"], series["ingesta"]["min"],
                                   series["ingesta"]["max"], series["ingesta"]["meta"])
        if k is not None
    ]
    return render(request, "usuario/reporte_imprimir.html", {"series": series, "dias": dias, "filas": filas,
                                                              "vigente": metas.meta_vigente(request.user)})


# --- Calculadora de aceite (RF15) --------------------------------------------------------


@solo_usuario
def calculadora_aceite(request):
    form = CalculadoraAceiteForm(request.GET or None)
    resultado = comparacion = None
    if form.is_valid():
        datos = form.cleaned_data
        alimento = datos["alimento"]
        resultado = calcular_aceite(
            peso_crudo_g=datos["peso_crudo_g"], matriz=alimento.matriz, metodo=datos["metodo"],
            tamano=datos["tamano"], tiempo=datos["tiempo"], escurrido=datos["escurrido"],
            aceite_agregado_g=datos["aceite_agregado_g"],
        )
        # Comparación: la energía del alimento crudo frente a la que suma el aceite.
        sin_aceite = r1(alimento.kcal * datos["peso_crudo_g"] / 100)
        comparacion = {"sin_aceite": sin_aceite, "con_aceite": sin_aceite + resultado.kcal_tipico,
                       "con_aceite_min": sin_aceite + resultado.kcal_minimo,
                       "con_aceite_max": sin_aceite + resultado.kcal_maximo}
    return render(request, "usuario/calculadora_aceite.html", {"form": form, "resultado": resultado, "comparacion": comparacion})
