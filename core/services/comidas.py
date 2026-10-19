"""
Creación y actualización de comidas.

Junta las tres piezas anteriores: toma las filas que confirmó el usuario,
busca el alimento (food_parser), calcula los nutrientes (nutrition) y guarda
el RegistroComida con sus DetalleComida.

Vive aquí y no en views.py para que la página web y la API REST usen
exactamente el mismo código y no se desincronicen.
"""

from __future__ import annotations

from datetime import date, time
from typing import Iterable, Optional

from django.db import transaction

from core.models import (
    Alimento,
    DetalleComida,
    MetodoPreparacion,
    OrigenRegistro,
    RegistroComida,
)
from core.services.nutrition import (
    CantidadInvalida,
    aplicar_calculo,
    calcular,
    validar_cantidad,
)


def construir_detalle(registro: RegistroComida, fila: dict) -> DetalleComida:
    """
    Convierte una fila del formulario en un DetalleComida ya calculado.

    `fila` debe traer: alimento (instancia o None), nombre_mostrado, cantidad,
    unidad y, opcionalmente, metodo_preparacion.

    El detalle se devuelve sin guardar para que el llamador decida cuándo
    escribir en la base de datos.
    """
    alimento: Optional[Alimento] = fila.get("alimento")
    cantidad = validar_cantidad(fila.get("cantidad"))
    unidad = fila.get("unidad")
    metodo = fila.get("metodo_preparacion") or MetodoPreparacion.NO_ESPECIFICADA

    detalle = DetalleComida(
        registro=registro,
        alimento=alimento,
        nombre_mostrado=(fila.get("nombre_mostrado") or "").strip()[:120]
        or (alimento.nombre if alimento else "Alimento sin identificar"),
        cantidad=cantidad,
        unidad=unidad,
        metodo_preparacion=metodo,
    )

    resultado = calcular(
        alimento,
        cantidad,
        unidad,
        nombre_mostrado=detalle.nombre_mostrado,
        metodo_declarado=metodo,
    )
    return aplicar_calculo(detalle, resultado)


@transaction.atomic
def guardar_comida(
    usuario,
    *,
    descripcion: str,
    fecha: date,
    filas: Iterable[dict],
    hora: Optional[time] = None,
    origen: str = OrigenRegistro.MANUAL,
    confirmado: bool = True,
) -> RegistroComida:
    """
    Crea una comida completa con sus detalles.

    Es atómica: si una fila tiene una cantidad inválida, no queda una comida a
    medias en la base de datos.

    Devuelve el RegistroComida ya guardado.
    """
    filas = list(filas)
    if not filas:
        raise CantidadInvalida("La comida debe tener al menos un alimento.")

    registro = RegistroComida.objects.create(
        usuario=usuario,
        descripcion=descripcion.strip()[:300] or "Comida",
        fecha=fecha,
        hora=hora,
        origen=origen,
        confirmado=confirmado,
    )

    detalles = [construir_detalle(registro, fila) for fila in filas]
    DetalleComida.objects.bulk_create(detalles)
    return registro


@transaction.atomic
def reemplazar_detalles(registro: RegistroComida, filas: Iterable[dict]) -> RegistroComida:
    """
    Sustituye todos los detalles de una comida por los nuevos y recalcula.

    Se usa al editar una comida del historial. Se recalcula todo en lugar de
    ajustar valores a mano para que no queden totales inconsistentes.
    """
    filas = list(filas)
    if not filas:
        raise CantidadInvalida("La comida debe tener al menos un alimento.")

    nuevos = [construir_detalle(registro, fila) for fila in filas]
    registro.detalles.all().delete()
    DetalleComida.objects.bulk_create(nuevos)
    registro.save(update_fields=["actualizado_en"])
    return registro


def filas_desde_formset(formset) -> list[dict]:
    """
    Extrae las filas útiles de un DetalleComidaFormSet validado.

    Ignora las marcadas para borrar y las vacías.
    """
    filas = []
    for form in formset:
        if not form.cleaned_data or form.cleaned_data.get("DELETE"):
            continue
        filas.append(
            {
                "alimento": form.cleaned_data.get("alimento"),
                "nombre_mostrado": form.cleaned_data.get("nombre_mostrado"),
                "cantidad": form.cleaned_data.get("cantidad"),
                "unidad": form.cleaned_data.get("unidad"),
                "metodo_preparacion": form.cleaned_data.get("metodo_preparacion"),
            }
        )
    return filas
