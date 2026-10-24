"""
RF19 Curación del catálogo y mejora continua, y RF10 Correcciones.

* Bandeja de pendientes: términos no reconocidos, alimentos personales y
  correcciones de usuarios, ordenados por impacto.
* Cada cambio queda en el historial con valor anterior y nuevo, dentro de la
  versión en borrador, y se puede revertir.
* Antes de publicar una versión se ejecuta el conjunto de prueba de
  referencia; si la exactitud baja de los umbrales o empeora respecto a la
  versión anterior, la publicación se bloquea.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from django.db import transaction
from django.forms.models import model_to_dict
from django.utils import timezone

from core.models import (
    Alimento,
    Ambito,
    CoeficienteAbsorcion,
    Correccion,
    EjecucionExactitud,
    FraseReferencia,
    HistorialCatalogo,
    MetodoCoccion,
    Notificacion,
    PorcionCasera,
    Preparacion,
    Rol,
    TerminoLexico,
    TerminoPendiente,
    TipoTermino,
    VersionCatalogo,
)
from core.services import auditoria
from core.services.parametros import parametro
from core.services.texto import normalizar

MODELOS_CATALOGO = {
    "Alimento": Alimento,
    "Preparacion": Preparacion,
    "MetodoCoccion": MetodoCoccion,
    "CoeficienteAbsorcion": CoeficienteAbsorcion,
    "TerminoLexico": TerminoLexico,
    "PorcionCasera": PorcionCasera,
}
EXCLUIDOS = {"version", "modificado_por", "modificado_en"}


def instantanea(obj) -> dict:
    """Valores editables de un registro del catálogo, serializables a JSON."""
    datos = model_to_dict(obj)
    resultado = {}
    for campo, valor in datos.items():
        if campo in EXCLUIDOS:
            continue
        if isinstance(valor, Decimal):
            valor = str(valor)
        elif isinstance(valor, (date, datetime)):
            valor = valor.isoformat()
        elif hasattr(valor, "pk"):
            valor = valor.pk
        resultado[campo] = valor
    return resultado


@transaction.atomic
def registrar_cambio(obj, descripcion: str, antes: dict | None, usuario) -> HistorialCatalogo:
    """Guarda el cambio en la versión en borrador y marca el registro con ella."""
    version = VersionCatalogo.borrador()
    if hasattr(obj, "version_id"):
        type(obj).objects.filter(pk=obj.pk).update(version=version)
    if hasattr(obj, "modificado_por_id"):
        type(obj).objects.filter(pk=obj.pk).update(modificado_por=usuario, modificado_en=timezone.now())
    cambio = HistorialCatalogo.objects.create(
        version=version, entidad=type(obj).__name__, entidad_id=obj.pk, descripcion=descripcion[:200],
        valor_anterior=antes, valor_nuevo=instantanea(obj), usuario=usuario,
    )
    auditoria.registrar("catalogo_cambio", usuario=usuario, entidad=type(obj).__name__, entidad_id=obj.pk,
                        detalle=f"{descripcion} (v{version.numero})")
    return cambio


@transaction.atomic
def revertir_cambio(cambio: HistorialCatalogo, usuario) -> None:
    """Vuelve un registro a su valor anterior (o lo inactiva si era nuevo)."""
    if cambio.revertido:
        return
    modelo = MODELOS_CATALOGO[cambio.entidad]
    obj = modelo.objects.get(pk=cambio.entidad_id)
    antes = instantanea(obj)
    if cambio.valor_anterior is None:
        if hasattr(obj, "estado"):
            obj.estado = "inactivo"
            obj.save()
    else:
        for campo, valor in cambio.valor_anterior.items():
            field = modelo._meta.get_field(campo)
            if field.is_relation:
                setattr(obj, f"{campo}_id", valor)
            elif field.get_internal_type() == "DecimalField" and valor is not None:
                setattr(obj, campo, Decimal(valor))
            else:
                setattr(obj, campo, valor)
        obj.save()
    cambio.revertido = True
    cambio.save(update_fields=["revertido"])
    registrar_cambio(obj, f"Reversión de: {cambio.descripcion}", antes, usuario)


# --- Bandeja de pendientes -------------------------------------------------------


def bandeja() -> dict:
    return {
        "terminos": TerminoPendiente.objects.filter(estado=TerminoPendiente.Estado.PENDIENTE).order_by("-veces", "-ultima_vez"),
        "alimentos_personales": Alimento.objects.filter(ambito=Ambito.PERSONAL, verificado=False, estado="activo"),
        "correcciones": Correccion.objects.filter(estado__in=[Correccion.Estado.PENDIENTE, Correccion.Estado.EN_REVISION])
        .select_related("item__alimento", "item__preparacion"),
        "sin_verificar": Alimento.objects.filter(ambito=Ambito.GLOBAL, verificado=False).count(),
        "preparaciones_sin_verificar": Preparacion.objects.filter(verificada=False).count(),
    }


@transaction.atomic
def resolver_termino(pendiente: TerminoPendiente, destino, usuario) -> TerminoLexico:
    """Incorpora un término no reconocido al léxico apuntando a `destino`."""
    datos = {"termino": normalizar(pendiente.termino)}
    if isinstance(destino, Preparacion):
        datos.update(tipo=TipoTermino.PREPARACION, preparacion=destino)
    elif isinstance(destino, MetodoCoccion):
        datos.update(tipo=TipoTermino.METODO, metodo=destino)
    else:
        datos.update(tipo=TipoTermino.ALIMENTO, alimento=destino)
    termino = TerminoLexico(**datos)
    termino.full_clean()
    termino.save()
    pendiente.estado = TerminoPendiente.Estado.RESUELTO
    pendiente.resuelto_por = usuario
    pendiente.save(update_fields=["estado", "resuelto_por", "ultima_vez"])
    registrar_cambio(termino, f"Nuevo término «{termino.termino}» → {destino}", None, usuario)
    return termino


def descartar_termino(pendiente: TerminoPendiente, usuario) -> None:
    pendiente.estado = TerminoPendiente.Estado.DESCARTADO
    pendiente.resuelto_por = usuario
    pendiente.save(update_fields=["estado", "resuelto_por", "ultima_vez"])


@transaction.atomic
def aprobar_alimento_personal(alimento: Alimento, usuario) -> Alimento:
    """
    Copia un alimento personal al catálogo global una vez revisado. El
    original sigue siendo del usuario; el Curador no ve quién lo creó.
    """
    copia = Alimento.objects.get(pk=alimento.pk)
    copia.pk = None
    copia.ambito = Ambito.GLOBAL
    copia.propietario = None
    copia.verificado = True
    copia.fuente_detalle = f"Propuesto por un usuario y revisado por el Curador. {alimento.fuente_detalle}".strip()
    copia.full_clean()
    copia.save()
    alimento.verificado = True  # ya no está pendiente de revisión
    alimento.save(update_fields=["verificado"])
    registrar_cambio(copia, f"Alimento personal incorporado al catálogo: {copia.nombre}", None, usuario)
    return copia


def rechazar_alimento_personal(alimento: Alimento, usuario) -> None:
    alimento.verificado = True  # revisado; sigue siendo solo personal
    alimento.save(update_fields=["verificado"])
    auditoria.registrar("alimento_personal_rechazado", usuario=usuario, entidad="Alimento", entidad_id=alimento.pk)


@transaction.atomic
def validar_registro(obj, usuario) -> None:
    """El Curador marca un alimento o preparación como verificado contra su fuente."""
    antes = instantanea(obj)
    if isinstance(obj, Preparacion):
        obj.verificada = True
    else:
        obj.verificado = True
    obj.save()
    registrar_cambio(obj, f"Verificado contra la fuente: {obj}", antes, usuario)


# --- Correcciones (RF10) -----------------------------------------------------------


def crear_correccion(item, usuario, tipo: str, valor_sugerido: str, comentario: str = "") -> Correccion:
    """
    El usuario reporta un error. Si la corrección se puede aplicar a su
    propia comida (cantidad, método o componente), se aplica de inmediato;
    al catálogo global solo llega si el Curador la acepta.
    """
    from core.services.comidas import editar_item
    from core.services.interpretacion import Lexico, ItemInterpretado, resolver

    valor_original = {
        Correccion.Tipo.CANTIDAD: f"{item.cantidad_g} g",
        Correccion.Tipo.METODO: item.metodo.nombre if item.metodo else "sin método",
        Correccion.Tipo.COMPONENTE: item.nombre_mostrado,
        Correccion.Tipo.VALOR: f"{item.kcal} kcal",
    }.get(tipo, item.nombre_mostrado)
    correccion = Correccion.objects.create(
        item=item, usuario=usuario, tipo=tipo, valor_original=valor_original[:200],
        valor_sugerido=valor_sugerido[:200], comentario=comentario,
    )
    aplicada = False
    try:
        if tipo == Correccion.Tipo.CANTIDAD:
            numero = "".join(c for c in valor_sugerido.replace(",", ".") if c.isdigit() or c == ".")
            if numero:
                editar_item(item, cantidad_g=Decimal(numero))
                aplicada = True
        elif tipo == Correccion.Tipo.METODO:
            lexico = Lexico(usuario)
            metodo = lexico.metodos.get(normalizar(valor_sugerido)) or MetodoCoccion.objects.filter(
                nombre__iexact=valor_sugerido.strip()).first()
            if metodo:
                editar_item(item, metodo=metodo)
                aplicada = True
        elif tipo == Correccion.Tipo.COMPONENTE:
            lexico = Lexico(usuario)
            tentativo = ItemInterpretado(fragmento=valor_sugerido)
            resolver([normalizar(valor_sugerido)], lexico, tentativo)
            if tentativo.destino is not None:
                editar_item(item, destino=tentativo.destino)
                aplicada = True
    except ValueError:
        aplicada = False
    if aplicada:
        correccion.aplicada_a_comida = True
        correccion.save(update_fields=["aplicada_a_comida"])
    from core.services.notificaciones import notificar_rol

    if Correccion.objects.filter(estado=Correccion.Estado.PENDIENTE).count() in (1, 10, 25):
        notificar_rol(Rol.CURADOR, Notificacion.Tipo.CURACION, "Correcciones pendientes de revisión",
                      "Hay correcciones de usuarios esperando revisión en la bandeja.", url="/curacion/", correo=False)
    return correccion


@transaction.atomic
def revisar_correccion(correccion: Correccion, aceptar: bool, resolucion: str, usuario) -> Correccion:
    from core.services.notificaciones import notificar

    correccion.estado = Correccion.Estado.ACEPTADA if aceptar else Correccion.Estado.RECHAZADA
    correccion.revisor = usuario
    correccion.resolucion = resolucion
    correccion.fecha_revision = timezone.now()
    correccion.save()
    if aceptar and correccion.item and correccion.item.comida.texto_original:
        comida = correccion.item.comida
        esperados = [
            {"nombre": i.destino.nombre, "metodo": i.metodo.clave if i.metodo else ""}
            for i in comida.items.filter(descartado=False) if i.destino is not None
        ]
        FraseReferencia.objects.create(texto=comida.texto_original, componentes_esperados=esperados,
                                       origen=FraseReferencia.Origen.CORRECCION, validada=False)
    if correccion.usuario:
        estado = "aceptó" if aceptar else "revisó y no aplicó al catálogo"
        notificar(correccion.usuario, Notificacion.Tipo.CORRECCION, "Respuesta a tu corrección",
                  f"El equipo de curación {estado} tu reporte sobre «{correccion.valor_original}». {resolucion}".strip(),
                  url="/comidas/historial/")
    auditoria.registrar("correccion_revisada", usuario=usuario, entidad="Correccion", entidad_id=correccion.pk,
                        detalle=correccion.get_estado_display())
    return correccion


# --- Pruebas de exactitud y publicación -----------------------------------------------


def ejecutar_exactitud(version: VersionCatalogo | None = None, usuario=None) -> EjecucionExactitud:
    """
    Corre el conjunto de prueba con el motor de reglas (sin IA: así el
    resultado es reproducible y no cuesta dinero).
    """
    from core.services.calculo import Solicitud, calcular
    from core.services.interpretacion import interpretar

    esperados_total = identificados = metodos_total = metodos_ok = 0
    errores_energia = []
    detalle = []
    for frase in FraseReferencia.objects.filter(activa=True):
        resultado = interpretar(frase.texto, permitir_ia=False, registrar_pendientes=False)
        encontrados = {}
        for item in resultado.items:
            if item.destino is not None:
                metodo = item.metodo.clave if item.metodo else ""
                encontrados.setdefault(normalizar(item.destino.nombre), metodo)
        fallos = []
        for esperado in frase.componentes_esperados:
            nombre = normalizar(esperado["nombre"])
            esperados_total += 1
            if nombre in encontrados:
                identificados += 1
                if esperado.get("metodo"):
                    metodos_total += 1
                    if encontrados[nombre] == esperado["metodo"]:
                        metodos_ok += 1
                    else:
                        fallos.append(f"método de {esperado['nombre']}: {encontrados[nombre] or '—'} (esperado {esperado['metodo']})")
            else:
                fallos.append(f"no identificó {esperado['nombre']}")
                if esperado.get("metodo"):
                    metodos_total += 1
        if frase.kcal_referencia:
            kcal = sum(
                (calcular(Solicitud(destino=i.destino, cantidad_g=i.cantidad_g, metodo=i.metodo,
                                    fuente_cantidad=i.fuente_cantidad)).kcal
                 for i in resultado.items if i.destino is not None and i.cantidad_g),
                Decimal("0"),
            )
            errores_energia.append(abs(kcal - frase.kcal_referencia) / frase.kcal_referencia * 100)
        detalle.append({"frase": frase.texto, "ok": not fallos, "fallos": fallos})

    identificacion = Decimal(identificados * 100 / esperados_total if esperados_total else 0).quantize(Decimal("0.1"))
    coccion = Decimal(metodos_ok * 100 / metodos_total if metodos_total else 100).quantize(Decimal("0.1"))
    error = (sum(errores_energia) / len(errores_energia)).quantize(Decimal("0.1")) if errores_energia else None
    aprobada = (
        identificacion >= parametro("exactitud_identificacion_min")
        and coccion >= parametro("exactitud_coccion_min")
        and (error is None or error <= parametro("error_energia_max"))
    )
    anterior = EjecucionExactitud.objects.filter(aprobada=True, version__estado=VersionCatalogo.Estado.PUBLICADA).first()
    if anterior and (identificacion < anterior.identificacion_pct or coccion < anterior.coccion_pct):
        aprobada = False
        detalle.insert(0, {"frase": "Comparación con la versión publicada", "ok": False,
                           "fallos": [f"La exactitud empeoró frente a la v{anterior.version.numero} "
                                      f"({anterior.identificacion_pct} % / {anterior.coccion_pct} %)."]})
    return EjecucionExactitud.objects.create(
        version=version, total_frases=len(detalle), identificacion_pct=identificacion, coccion_pct=coccion,
        error_energia_pct=error, aprobada=aprobada, detalle=detalle, ejecutada_por=usuario,
    )


@transaction.atomic
def publicar_version(version: VersionCatalogo, usuario, notas: str = "") -> EjecucionExactitud:
    from core.services.notificaciones import notificar_rol

    ejecucion = ejecutar_exactitud(version, usuario)
    if ejecucion.aprobada:
        version.estado = VersionCatalogo.Estado.PUBLICADA
        version.publicada_en = timezone.now()
        version.notas = notas or version.notas
        version.save()
        titulo = f"Catálogo v{version.numero} publicado"
    else:
        titulo = f"Publicación de v{version.numero} bloqueada por exactitud"
    notificar_rol(
        Rol.CURADOR, Notificacion.Tipo.EXACTITUD, titulo,
        f"Identificación {ejecucion.identificacion_pct} %, método de cocción {ejecucion.coccion_pct} %"
        + (f", error de energía {ejecucion.error_energia_pct} %" if ejecucion.error_energia_pct is not None else "") + ".",
        url="/curacion/exactitud/", correo=False,
    )
    auditoria.registrar("catalogo_publicacion", usuario=usuario, entidad="VersionCatalogo", entidad_id=version.pk,
                        detalle=titulo)
    return ejecucion
