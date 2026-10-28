"""
Carga del catálogo inicial y consultas de apoyo sobre el catálogo.

`cargar_catalogo_inicial()` es idempotente: si se ejecuta dos veces no
duplica nada (usa get_or_create por nombre).
"""

from __future__ import annotations

import re
from decimal import Decimal

from django.db import transaction
from django.db.models import Q

from core.datos import alimentos as datos_alimentos
from core.datos import lexico as datos_lexico
from core.datos import metodos as datos_metodos
from core.datos import preparaciones as datos_preparaciones
from core.models import (
    Alimento,
    Ambito,
    CoeficienteAbsorcion,
    Componente,
    EstadoRegistro,
    MetodoCoccion,
    PorcionCasera,
    Preparacion,
    TerminoLexico,
    TipoTermino,
    VersionCatalogo,
)
from core.services.texto import normalizar, singular_frase

_PARENTESIS = re.compile(r"\(.*?\)")


def variantes_de_nombre(nombre: str) -> list[str]:
    """
    Términos de léxico que se derivan de un nombre del catálogo.

    'Mojarra (tilapia)'            -> ['mojarra tilapia', 'mojarra']
    'Carne de res, punta de anca'  -> ['carne de res punta de anca', 'carne de res']
    """
    completo = normalizar(nombre.replace(",", " ").replace("(", " ").replace(")", " "))
    sin_parentesis = normalizar(_PARENTESIS.sub(" ", nombre).split(",")[0])
    resultado = []
    for t in (completo, sin_parentesis, singular_frase(completo), singular_frase(sin_parentesis)):
        if t and t not in resultado:
            resultado.append(t)
    return resultado


def _crear_termino(termino: str, **destino) -> bool:
    termino = normalizar(termino)
    if not termino or TerminoLexico.objects.filter(termino=termino).exists():
        return False
    if "alimento" in destino:
        tipo = TipoTermino.ALIMENTO
    elif "preparacion" in destino:
        tipo = TipoTermino.PREPARACION
    else:
        tipo = TipoTermino.METODO
    TerminoLexico.objects.create(termino=termino, tipo=tipo, **destino)
    return True


@transaction.atomic
def cargar_catalogo_inicial(version: VersionCatalogo | None = None) -> dict:
    """Carga métodos, coeficientes, alimentos, preparaciones, léxico y porciones."""
    version = version or VersionCatalogo.objects.filter(numero=1).first() or VersionCatalogo.objects.create(numero=1)
    conteo = {"metodos": 0, "coeficientes": 0, "alimentos": 0, "preparaciones": 0, "componentes": 0, "terminos": 0, "porciones": 0}

    # 1. Métodos de cocción y coeficientes.
    metodos = {}
    for clave, nombre, usa_grasa, es_fritura, factor_agua, perdida_grasa, palabras in datos_metodos.METODOS:
        metodo, nuevo = MetodoCoccion.objects.get_or_create(
            clave=clave,
            defaults={
                "nombre": nombre, "usa_grasa": usa_grasa, "es_fritura": es_fritura,
                "factor_agua": Decimal(str(factor_agua)), "perdida_grasa": Decimal(str(perdida_grasa)),
                "palabras": palabras, "version": version,
            },
        )
        metodos[clave] = metodo
        conteo["metodos"] += int(nuevo)
    for (clave, matriz), (minimo, tipico, maximo) in datos_metodos.COEFICIENTES.items():
        _, nuevo = CoeficienteAbsorcion.objects.get_or_create(
            metodo=metodos[clave], matriz=matriz,
            defaults={
                "pct_min": Decimal(str(minimo)), "pct_tipico": Decimal(str(tipico)), "pct_max": Decimal(str(maximo)),
                "fuente": datos_metodos.FUENTE_COEFICIENTES, "version": version,
            },
        )
        conteo["coeficientes"] += int(nuevo)

    # 2. Alimentos base.
    alimentos = {}
    for fila in datos_alimentos.ALIMENTOS:
        fila = dict(fila)
        metodo_clave = fila.pop("metodo", None)
        fuente = fila.pop("fuente", "estimado")
        renombres = {"rendimiento": "rendimiento_pct", "grasa_visible": "grasa_visible_pct"}
        for viejo, nuevo_nombre in renombres.items():
            if viejo in fila:
                fila[nuevo_nombre] = fila.pop(viejo)
        for campo, valor in list(fila.items()):
            if isinstance(valor, (int, float)) and not isinstance(valor, bool):
                fila[campo] = Decimal(str(valor))
        # Los azúcares son parte de los carbohidratos: sin carbohidratos no
        # hay azúcares. Es una deducción, no un dato inventado.
        if fila.get("azucares") is None and fila["carbohidratos"] == 0:
            fila["azucares"] = Decimal("0")
        alimento, nuevo = Alimento.objects.get_or_create(
            nombre=fila["nombre"], ambito=Ambito.GLOBAL,
            defaults={
                **fila,
                "metodo_defecto": metodos.get(metodo_clave),
                "fuente": fuente,
                "fuente_detalle": "Estimación de referencia para el prototipo; pendiente de validación por el nutricionista.",
                "verificado": False,
                "version": version,
            },
        )
        alimentos[alimento.nombre] = alimento
        conteo["alimentos"] += int(nuevo)

    # 3. Preparaciones y su deconstrucción.
    preparaciones = {}
    for datos in datos_preparaciones.PREPARACIONES:
        preparacion, nuevo = Preparacion.objects.get_or_create(
            nombre=datos["nombre"],
            defaults={
                "descripcion": datos["descripcion"], "region": datos["region"], "categoria": datos["categoria"],
                "peso_porcion_g": Decimal(str(datos["peso_porcion_g"])), "metodo_defecto": metodos[datos["metodo"]],
                "admite_variantes": datos["admite_variantes"], "version": version,
            },
        )
        preparaciones[preparacion.nombre] = (preparacion, datos)
        conteo["preparaciones"] += int(nuevo)
        if nuevo:
            for c in datos["componentes"]:
                Componente.objects.create(
                    preparacion=preparacion, alimento=alimentos[c["alimento"]],
                    cantidad_g=Decimal(str(c["cantidad_g"])), rol=c["rol"],
                    metodo=metodos.get(c["metodo"]) if c["metodo"] else None, opcional=c["opcional"],
                )
                conteo["componentes"] += 1

    # 4. Léxico: primero lo explícito (manda), luego lo derivado de los nombres.
    for termino, nombre in datos_lexico.SINONIMOS_ALIMENTOS.items():
        conteo["terminos"] += int(_crear_termino(termino, alimento=alimentos[nombre]))
    for preparacion, datos in preparaciones.values():
        for termino in datos["terminos"]:
            conteo["terminos"] += int(_crear_termino(termino, preparacion=preparacion))
        for termino in variantes_de_nombre(preparacion.nombre):
            conteo["terminos"] += int(_crear_termino(termino, preparacion=preparacion))
    for alimento in alimentos.values():
        for termino in variantes_de_nombre(alimento.nombre):
            conteo["terminos"] += int(_crear_termino(termino, alimento=alimento))
    for metodo in metodos.values():
        for palabra in metodo.lista_palabras():
            conteo["terminos"] += int(_crear_termino(palabra, metodo=metodo))

    # 5. Porciones caseras.
    def crear_porciones(destino: dict, porciones: dict, preferida: str | None = None):
        if PorcionCasera.objects.filter(**destino).exists():
            return 0
        preferida = preferida or next(
            (m for m in datos_lexico.PORCION_DEFECTO_PREFERIDA if m in porciones), next(iter(porciones))
        )
        for medida, cantidad in porciones.items():
            PorcionCasera.objects.create(
                medida=medida, cantidad=Decimal(str(cantidad)), por_defecto=(medida == preferida), **destino
            )
        return len(porciones)

    for nombre, porciones in datos_lexico.PORCIONES_ALIMENTOS.items():
        conteo["porciones"] += crear_porciones({"alimento": alimentos[nombre]}, porciones)
    for preparacion, datos in preparaciones.values():
        conteo["porciones"] += crear_porciones({"preparacion": preparacion}, datos["porciones"], datos.get("porcion_defecto"))

    return conteo


# --- Consultas ----------------------------------------------------------------


def alimentos_visibles(usuario=None):
    """Catálogo global activo más los alimentos personales del usuario."""
    filtro = Q(ambito=Ambito.GLOBAL)
    if usuario is not None and getattr(usuario, "is_authenticated", False):
        filtro |= Q(ambito=Ambito.PERSONAL, propietario=usuario)
    return Alimento.objects.filter(filtro, estado=EstadoRegistro.ACTIVO)


def preparaciones_activas():
    return Preparacion.objects.filter(estado=EstadoRegistro.ACTIVO)


def opciones_busqueda(usuario=None) -> list[str]:
    """Nombres para el buscador manual (datalist): alimentos y preparaciones."""
    nombres = list(preparaciones_activas().values_list("nombre", flat=True))
    nombres += list(alimentos_visibles(usuario).values_list("nombre", flat=True))
    return sorted(set(nombres), key=normalizar)


def buscar_por_nombre(nombre: str, usuario=None):
    """Alimento o preparación con ese nombre exacto (sin distinguir tildes)."""
    clave = normalizar(nombre)
    if not clave:
        return None
    for preparacion in preparaciones_activas():
        if normalizar(preparacion.nombre) == clave:
            return preparacion
    for alimento in alimentos_visibles(usuario):
        if normalizar(alimento.nombre) == clave:
            return alimento
    return None


def porcion_defecto(destino) -> PorcionCasera | None:
    filtro = {"preparacion": destino} if isinstance(destino, Preparacion) else {"alimento": destino}
    porciones = PorcionCasera.objects.filter(**filtro)
    return porciones.filter(por_defecto=True).first() or porciones.first()
