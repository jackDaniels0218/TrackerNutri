"""
RF17 Salvaguardas de salud y seguridad del usuario.

* Elegibilidad: el déficit solo se activa para adultos que no estén en
  gestación o lactancia y no hayan declarado una condición que requiera
  acompañamiento profesional. En otro caso, seguimiento informativo.
* Límites duros: piso calórico por sexo, déficit máximo y velocidad máxima de
  pérdida de peso. Ni el ajuste automático ni el manual pueden superarlos.
* Detección de patrones de riesgo en días marcados como completos.
* Lenguaje no culpabilizante (comprobado por una prueba automática que
  revisa las plantillas).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from core.models import DiaRegistro, Notificacion, PerfilNutricional, Pesaje, Sexo
from core.services.parametros import parametro

# Palabras que el SRS prohíbe en la interfaz (actividad 17).
PALABRAS_PROHIBIDAS = ("bueno", "buena", "malo", "mala", "trampa", "pecado", "culpa", "prohibido")


@dataclass
class Elegibilidad:
    elegible: bool
    motivos: list[str] = field(default_factory=list)


def elegibilidad(perfil: PerfilNutricional) -> Elegibilidad:
    motivos = []
    if perfil.edad < 18:
        motivos.append("eres menor de edad")
    if perfil.gestante_lactante:
        motivos.append("estás en gestación o lactancia")
    if perfil.requiere_acompanamiento:
        motivos.append("declaraste una condición que requiere acompañamiento profesional")
    return Elegibilidad(elegible=not motivos, motivos=motivos)


def piso_calorico(sexo: str) -> Decimal:
    clave = "piso_calorico_femenino" if sexo == Sexo.FEMENINO else "piso_calorico_masculino"
    return parametro(clave)


def aplicar_limites(kcal: Decimal, gasto_total: Decimal, sexo: str) -> tuple[Decimal, list[str]]:
    """
    Ajusta una meta propuesta a los límites duros y explica qué se cambió.
    Nunca baja del piso ni supera el déficit máximo.
    """
    avisos = []
    deficit_max = parametro("deficit_maximo_pct")
    minimo_por_deficit = gasto_total * (1 - deficit_max / 100)
    if kcal < minimo_por_deficit:
        avisos.append(f"Se limitó al déficit máximo permitido ({deficit_max} %).")
        kcal = minimo_por_deficit
    piso = piso_calorico(sexo)
    if kcal < piso:
        avisos.append(f"Se ajustó al mínimo de seguridad ({piso:.0f} kcal).")
        kcal = piso
    return kcal, avisos


def peso_tendencial(usuario, hasta=None, dias: int = 7) -> list[tuple]:
    """
    Media móvil del peso para no reaccionar a variaciones diarias (RF9).
    Devuelve [(fecha, peso, media_movil)].
    """
    hasta = hasta or timezone.localdate()
    pesajes = list(Pesaje.objects.filter(usuario=usuario, fecha__lte=hasta).order_by("fecha"))
    serie = []
    for i, p in enumerate(pesajes):
        ventana = [x.peso_kg for x in pesajes[: i + 1] if (p.fecha - x.fecha).days < dias]
        serie.append((p.fecha, p.peso_kg, (sum(ventana) / len(ventana)).quantize(Decimal("0.1"))))
    return serie


def ritmo_semanal_pct(usuario, semanas: int = 1, hasta=None) -> Decimal | None:
    """% de cambio del peso tendencial por semana en las últimas `semanas`."""
    hasta = hasta or timezone.localdate()
    serie = [s for s in peso_tendencial(usuario, hasta) if (hasta - s[0]).days <= 7 * semanas + 3]
    if len(serie) < 2 or (serie[-1][0] - serie[0][0]).days < 5:
        return None
    dias = Decimal((serie[-1][0] - serie[0][0]).days)
    cambio = (serie[-1][2] - serie[0][2]) / serie[0][2] * 100
    return (cambio / dias * 7).quantize(Decimal("0.01"))


def perdida_demasiado_rapida(usuario, hasta=None) -> bool:
    """Pérdida por encima del límite semanal durante dos semanas seguidas."""
    hasta = hasta or timezone.localdate()
    limite = parametro("perdida_max_semanal_pct")
    semana_actual = ritmo_semanal_pct(usuario, 1, hasta)
    semana_anterior = ritmo_semanal_pct(usuario, 1, hasta - timedelta(days=7))
    return all(r is not None and -r > limite for r in (semana_actual, semana_anterior))


def dias_bajo_piso(usuario, hasta=None) -> int:
    """Días completos consecutivos (hasta hoy) con ingesta por debajo del piso."""
    from core.services.reportes import kcal_del_dia

    hasta = hasta or timezone.localdate()
    perfil = getattr(usuario, "perfil", None)
    if perfil is None:
        return 0
    piso = piso_calorico(perfil.sexo)
    completos = set(DiaRegistro.objects.filter(usuario=usuario, completo=True, fecha__lte=hasta).values_list("fecha", flat=True))
    seguidos = 0
    dia = hasta
    while dia in completos:
        if kcal_del_dia(usuario, dia) >= piso:
            break
        seguidos += 1
        dia -= timedelta(days=1)
    return seguidos


@dataclass
class Alerta:
    clave: str
    titulo: str
    mensaje: str


def detectar_riesgos(usuario, hasta=None) -> list[Alerta]:
    """
    Patrones de riesgo. Los mensajes son amables y no proponen más reducciones.
    """
    alertas = []
    contacto = parametro("contacto_apoyo")
    if dias_bajo_piso(usuario, hasta) >= parametro("dias_riesgo_bajo_piso"):
        alertas.append(Alerta(
            "bajo_piso", "Queremos acompañarte",
            "En tus últimos días completos registraste menos energía de la recomendada como mínimo. "
            f"Comer muy poco por varios días puede afectar tu salud. {contacto} "
            "Mientras tanto, no te propondremos reducir más tu meta.",
        ))
    if perdida_demasiado_rapida(usuario, hasta):
        alertas.append(Alerta(
            "perdida_rapida", "Tu peso está bajando más rápido de lo previsto",
            "Durante dos semanas tu peso bajó más rápido del ritmo seguro. Hemos dejado de reducir tu meta. "
            f"{contacto}",
        ))
    return alertas


def notificar_riesgos(usuario, hasta=None) -> list[Alerta]:
    """Detecta riesgos y crea, como máximo una vez al día, la notificación."""
    from core.services.notificaciones import notificar

    alertas = detectar_riesgos(usuario, hasta)
    hoy = timezone.localdate()
    for alerta in alertas:
        if not Notificacion.objects.filter(destinatario=usuario, titulo=alerta.titulo, creada_en__date=hoy).exists():
            notificar(usuario, Notificacion.Tipo.CUIDADO, alerta.titulo, alerta.mensaje, url="/metas/")
    return alertas


def contiene_lenguaje_prohibido(texto: str) -> list[str]:
    import re

    from core.services.texto import normalizar

    normal = f" {normalizar(texto)} "
    return [p for p in PALABRAS_PROHIBIDAS if re.search(rf"\b{p}\b", normal)]
