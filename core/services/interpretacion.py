"""
RF13 Interpretación de texto libre (NLP).

Convierte "Me comí una arepa frita con carne asada y una Coca-Cola" en una
lista de componentes con cantidad, unidad, método de cocción y confianza.

    1. Normalización     minúsculas, sin tildes ni signos.
    2. Segmentación      separa por "con", "y", "más", comas... sin romper
                         nombres compuestos ("arroz con pollo").
    3. Cantidades        números, fracciones, palabras ("dos", "media"),
                         gramos, mililitros y medidas caseras ("un vaso").
    4. Método            explícito ("frita"), implícito por la preparación
                         (el patacón siempre es frito) o por defecto.
    5. Resolución en cascada:
                         léxico exacto → similitud de texto → coincidencia
                         semántica (palabras compartidas) → proveedor de IA
                         → pendiente para el Curador.
    6. Aclaración        si la confianza baja del umbral, como máximo dos
                         preguntas con opciones tocables.

La IA solo entra en el paso 5 y solo para lo que el léxico no resolvió. El
texto del usuario siempre se trata como dato: nunca se ejecuta nada de él.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from decimal import Decimal

from core.models import (
    Alimento,
    EstadoFisico,
    EstadoRegistro,
    Matriz,
    MetodoCoccion,
    PorcionCasera,
    Preparacion,
    TerminoLexico,
    TerminoPendiente,
    TipoComida,
    TipoTermino,
)
from core.services.catalogo import alimentos_visibles, porcion_defecto
from core.services.parametros import parametro
from core.services.texto import normalizar, singular, singular_frase

MAX_CARACTERES = 500

NUMEROS_PALABRA = {
    "un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
    "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "media": 0.5, "medio": 0.5, "mitad": 0.5,
    "par": 2, "doble": 2,
}

UNIDADES_PESO = {
    "kg": ("g", 1000), "kilo": ("g", 1000), "kilos": ("g", 1000), "kilogramo": ("g", 1000), "kilogramos": ("g", 1000),
    "g": ("g", 1), "gr": ("g", 1), "grs": ("g", 1), "gramo": ("g", 1), "gramos": ("g", 1),
    "ml": ("ml", 1), "cc": ("ml", 1), "mililitro": ("ml", 1), "mililitros": ("ml", 1),
    "l": ("ml", 1000), "lt": ("ml", 1000), "litro": ("ml", 1000), "litros": ("ml", 1000),
    "onza": ("g", 28.35), "onzas": ("g", 28.35), "oz": ("g", 28.35),
}

MEDIDAS = {
    "plato": "plato", "platos": "plato", "platado": "plato",
    "vaso": "vaso", "vasos": "vaso", "vasito": "vaso",
    "taza": "taza", "tazas": "taza",
    "pocillo": "pocillo", "pocillos": "pocillo",
    "cucharada": "cucharada", "cucharadas": "cucharada",
    "cucharadita": "cucharadita", "cucharaditas": "cucharadita",
    "lata": "lata", "latas": "lata",
    "botella": "botella_personal", "botellas": "botella_personal", "botellita": "botella_personal",
    "porcion": "porcion", "porciones": "porcion", "pedazo": "porcion", "pedazos": "porcion",
    "trozo": "porcion", "trozos": "porcion", "presa": "porcion", "presas": "porcion",
    "tajada": "tajada", "tajadas": "tajada", "rebanada": "tajada", "rebanadas": "tajada",
}

TAMANOS = {
    "pequena": "pequena", "pequeno": "pequena", "pequenas": "pequena", "pequenos": "pequena",
    "chiquita": "pequena", "chiquito": "pequena", "chiquitas": "pequena", "chiquitos": "pequena",
    "mediana": "mediana", "mediano": "mediana", "medianas": "mediana", "medianos": "mediana",
    "grande": "grande", "grandes": "grande", "grandota": "grande", "grandote": "grande",
}

# Palabras que no aportan a la identificación del alimento.
VACIAS = {
    "hoy", "ayer", "anoche", "manana", "tarde", "noche", "desayuno", "almuerzo", "cena", "comida",
    "me", "mi", "yo", "comi", "desayune", "almorce", "cene", "tome", "bebi", "comimos", "pedi", "cenamos",
    "el", "la", "los", "las", "un", "una", "unos", "unas", "uno", "de", "del", "al", "en", "para", "por",
    "que", "como", "poco", "poquito", "bastante", "mucho", "mucha", "aproximadamente", "unos", "casi",
    "completo", "completa", "entero", "entera", "personal", "solo", "sola", "tambien", "despues",
    "luego", "antes", "porcion", "este", "esta", "eso", "algo", "mas", "otra", "otro",
    "rico", "rica", "caliente", "fria", "frio", "helado", "helada", "sin", "le", "lo",
    "salada", "salado", "saladas", "salados", "casero", "casera", "natural",
}

CONECTORES = re.compile(
    r"\s*(?:,|;|\+|\bacompanad[oa]s? de\b|\bjunto con\b|\bademas de\b|\bademas\b|\by\b|\bcon\b|\bmas\b|\be\b)\s*"
)
RE_MEDIDA_NUMERICA = re.compile(
    r"(\d+(?:[.,]\d+)?|\d+/\d+)\s*(" + "|".join(sorted(UNIDADES_PESO, key=len, reverse=True)) + r")\b"
)
RE_NUMERO = re.compile(r"\b(\d+(?:[.,]\d+)?|\d+/\d+)\b")

TIPOS_COMIDA = [
    (re.compile(r"\bdesayun|\bdesayuno\b"), TipoComida.DESAYUNO),
    (re.compile(r"\balmorz|\balmuerzo\b|\balmorce\b"), TipoComida.ALMUERZO),
    (re.compile(r"\bcene\b|\bcena\b|\bcenamos\b|\bcomida de la noche\b"), TipoComida.CENA),
    (re.compile(r"\bonces\b|\bmerienda\b|\bmedia manana\b|\bmedias nueves\b|\bal algo\b"), TipoComida.MERIENDA),
]

# Métodos que se ofrecen como opción, según el tipo de alimento.
OPCIONES_METODO = {
    Matriz.CARNE: ["asado", "plancha", "fritura_profunda", "guisado", "hervido"],
    Matriz.PESCADO: ["fritura_profunda", "plancha", "guisado", "horno"],
    Matriz.HUEVO: ["hervido", "fritura_sarten", "fritura_profunda"],
    Matriz.TUBERCULO: ["hervido", "fritura_profunda", "horno"],
    Matriz.MASA_MAIZ: ["asado", "fritura_profunda", "plancha"],
    Matriz.MASA_TRIGO: ["horno", "fritura_profunda"],
    Matriz.APANADO: ["fritura_profunda", "horno"],
    Matriz.OTRO: ["hervido", "horno", "fritura_profunda", "crudo"],
}


def calcular_confianza(resolucion, fuente_cantidad: str, con_tamano: bool, es_liquido: bool, origen_metodo: str) -> Decimal:
    """
    Confianza de 0 a 1 de un componente = resolución × cantidad × método.

    * resolución: 0,95 léxico exacto; similitud según el parecido; 0,55
      coincidencia por palabras; hasta 0,75 si lo identificó la IA; 1 si lo
      eligió el usuario.
    * cantidad: 1 en gramos o ml; 0,9 medida casera o tamaño; 0,85 solo la
      cuenta ("dos"); 0,7 porción por defecto; 0,6 bebida sin presentación.
    * método: 1 explícito o implícito; 0,7 por defecto; 0,6 ambiguo.
    """
    f_cantidad = {"gramos": Decimal("1"), "medida": Decimal("0.9"), "unidad": Decimal("0.85"),
                  "defecto": Decimal("0.7")}.get(fuente_cantidad, Decimal("0.7"))
    if fuente_cantidad == "unidad" and con_tamano:
        f_cantidad = Decimal("0.9")
    if es_liquido and fuente_cantidad in ("unidad", "defecto"):
        f_cantidad = Decimal("0.6")  # una "gaseosa" puede ser lata, vaso o botella
    f_metodo = {"defecto": Decimal("0.7"), "ambiguo": Decimal("0.6")}.get(origen_metodo, Decimal("1"))
    return (Decimal(str(resolucion)) * f_cantidad * f_metodo).quantize(Decimal("0.01"))


@dataclass
class ItemInterpretado:
    fragmento: str
    texto_alimento: str = ""
    destino: Alimento | Preparacion | None = None
    candidatos: list = field(default_factory=list)
    cuenta: Decimal | None = None
    medida_numerica: tuple | None = None  # (cantidad, "g" | "ml")
    medida: str = ""
    tamano: str = ""
    cantidad_g: Decimal | None = None
    cantidad_original: Decimal | None = None
    unidad_original: str = ""
    fuente_cantidad: str = "defecto"
    metodo: MetodoCoccion | None = None
    origen_metodo: str = "no_aplica"
    origen_resolucion: str = "ninguno"
    puntaje_resolucion: Decimal = Decimal("0")
    escurrido: bool = False
    aceite_agregado_g: Decimal | None = None
    aplicar_rendimiento: bool = False
    notas: list[str] = field(default_factory=list)

    @property
    def es_liquido(self) -> bool:
        if isinstance(self.destino, Alimento):
            return self.destino.es_liquido
        if isinstance(self.destino, Preparacion):
            return self.destino.es_bebida
        return False

    @property
    def confianza(self) -> Decimal:
        if self.destino is None:
            return Decimal("0")
        return calcular_confianza(
            self.puntaje_resolucion, self.fuente_cantidad, bool(self.tamano), self.es_liquido, self.origen_metodo
        )


@dataclass
class Interpretacion:
    texto: str
    items: list[ItemInterpretado]
    tipo_comida: str
    motor: str = "reglas"
    version_plantilla_ia: str = ""
    avisos: list[str] = field(default_factory=list)


# --- Léxico en memoria ----------------------------------------------------------


class Lexico:
    """
    Vista en memoria del léxico para una interpretación.

    El catálogo tiene cientos de términos: cargarlos una vez por frase es más
    rápido que consultar la base de datos por cada palabra.
    """

    def __init__(self, usuario=None):
        terminos = TerminoLexico.objects.filter(estado=EstadoRegistro.ACTIVO).select_related(
            "alimento", "preparacion", "metodo"
        )
        self.destinos: dict[str, Alimento | Preparacion] = {}
        self.metodos: dict[str, MetodoCoccion] = {}
        for t in terminos:
            if t.tipo == TipoTermino.METODO and t.metodo and t.metodo.estado == EstadoRegistro.ACTIVO:
                self.metodos[t.termino] = t.metodo
            elif t.tipo == TipoTermino.PREPARACION and t.preparacion and t.preparacion.estado == EstadoRegistro.ACTIVO:
                self.destinos[t.termino] = t.preparacion
            elif t.tipo == TipoTermino.ALIMENTO and t.alimento and t.alimento.estado == EstadoRegistro.ACTIVO:
                self.destinos[t.termino] = t.alimento
        # Alimentos personales del usuario: solo él los ve.
        if usuario is not None and getattr(usuario, "is_authenticated", False):
            for alimento in alimentos_visibles(usuario).filter(propietario=usuario):
                self.destinos.setdefault(normalizar(alimento.nombre), alimento)
        self.terminos_destino = list(self.destinos)
        self.metodos_ordenados = sorted(self.metodos, key=len, reverse=True)
        self.compuestos = sorted(
            (t for t in self.destinos if re.search(r"\b(con|y|mas|e)\b", t)), key=len, reverse=True
        )

    def metodo_por_clave(self, clave: str) -> MetodoCoccion | None:
        return next((m for m in self.metodos.values() if m.clave == clave), None) or \
            MetodoCoccion.objects.filter(clave=clave).first()


# --- Pasos del proceso ----------------------------------------------------------------


def detectar_tipo_comida(texto: str) -> str:
    for patron, tipo in TIPOS_COMIDA:
        if patron.search(texto):
            return tipo
    return TipoComida.OTRO


def segmentar(texto: str, lexico: Lexico) -> list[str]:
    """Separa por conectores sin romper nombres que los contienen."""
    protegido = f" {texto} "
    for termino in lexico.compuestos:
        protegido = re.sub(rf"\b{re.escape(termino)}\b", termino.replace(" ", "_"), protegido)
    partes = [p.replace("_", " ").strip() for p in CONECTORES.split(protegido)]
    return [p for p in partes if p and re.search(r"[a-z]", p)]


def _a_decimal(texto: str) -> Decimal:
    if "/" in texto:
        a, b = texto.split("/", 1)
        return Decimal(a) / Decimal(b)
    return Decimal(texto.replace(",", "."))


def extraer_cantidades(segmento: str, item: ItemInterpretado) -> str:
    """Saca del segmento la cuenta, el peso o volumen, la medida y el tamaño."""
    resto = f" {segmento} "

    m = RE_MEDIDA_NUMERICA.search(resto)
    if m:
        unidad, factor = UNIDADES_PESO[m.group(2)]
        valor = _a_decimal(m.group(1))
        item.medida_numerica = (valor * Decimal(str(factor)), unidad)
        item.cantidad_original, item.unidad_original = valor, m.group(2)
        resto = resto[: m.start()] + " " + resto[m.end():]

    palabras = resto.split()
    restantes = []
    for i, palabra in enumerate(palabras):
        siguiente = palabras[i + 1] if i + 1 < len(palabras) else ""
        es_cuenta = palabra in NUMEROS_PALABRA and not (
            # "a media mañana" o "media hora" hablan del momento, no de la cantidad.
            palabra in ("media", "medio") and siguiente in ("manana", "hora", "tarde", "noche")
        )
        if item.cuenta is None and es_cuenta:
            item.cuenta = Decimal(str(NUMEROS_PALABRA[palabra]))
            continue
        if item.cuenta is None and RE_NUMERO.fullmatch(palabra):
            item.cuenta = _a_decimal(palabra)
            continue
        if not item.medida and palabra in MEDIDAS:
            item.medida = MEDIDAS[palabra]
            continue
        if not item.tamano and palabra in TAMANOS:
            item.tamano = TAMANOS[palabra]
            continue
        restantes.append(palabra)
    return " ".join(restantes)


def extraer_metodo(texto: str, item: ItemInterpretado, lexico: Lexico) -> str:
    """Busca palabras de método de cocción y las quita del texto."""
    resto = f" {texto} "
    if re.search(r"\bescurrid[oa]s?\b|\ben papel\b", resto):
        item.escurrido = True
        resto = re.sub(r"\bescurrid[oa]s?\b|\ben papel( absorbente)?\b", " ", resto)
    for palabra in lexico.metodos_ordenados:
        patron = rf"\b{re.escape(palabra)}\b"
        if re.search(patron, resto):
            if item.metodo is None:
                item.metodo = lexico.metodos[palabra]
                item.origen_metodo = "explicito"
            resto = re.sub(patron, " ", resto)
    return " ".join(resto.split())


def limpiar(texto: str, final: bool = True) -> str:
    """
    Quita palabras vacías y números de los EXTREMOS de la frase.

    Solo los extremos: "carne de res" debe conservar su "de", mientras que
    "hoy almorcé una arepa" pierde "hoy almorcé una". Con `final=False` se
    conserva el final, para reconocer términos como "yogur natural".
    """
    palabras = [p for p in texto.split() if not RE_NUMERO.fullmatch(p)]
    while palabras and palabras[0] in VACIAS:
        palabras.pop(0)
    while final and palabras and palabras[-1] in VACIAS:
        palabras.pop()
    return " ".join(palabras)


def _semantica(frase: str, lexico: Lexico) -> list[tuple[float, str]]:
    """Coincidencia por palabras compartidas (Jaccard sobre palabras significativas)."""
    palabras = {singular(p) for p in frase.split() if len(p) > 2}
    if not palabras:
        return []
    puntajes = []
    for termino in lexico.terminos_destino:
        del_termino = {singular(p) for p in termino.split() if len(p) > 2}
        if not del_termino:
            continue
        comunes = palabras & del_termino
        if not comunes:
            continue
        puntaje = len(comunes) / len(palabras | del_termino)
        if palabras <= del_termino:
            puntaje += 0.15  # todo lo que dijo el usuario está en el término
        puntajes.append((puntaje, termino))
    return sorted(puntajes, reverse=True)


def resolver(frases: list[str], lexico: Lexico, item: ItemInterpretado) -> str | None:
    """
    Cascada: léxico exacto → similitud → semántica. Rellena item.destino y
    devuelve la frase que coincidió en el léxico exacto (o None).
    """
    frases = [f for f in dict.fromkeys(frases) if f]
    # 1. Léxico exacto (también en singular).
    for frase in frases:
        for variante in (frase, singular_frase(frase)):
            if variante in lexico.destinos:
                item.destino = lexico.destinos[variante]
                item.origen_resolucion = "lexico"
                item.puntaje_resolucion = Decimal("0.95")
                return frase
    principal = frases[-1] if frases else ""
    if not principal:
        return None
    # 2. Similitud de texto (errores de ortografía: "aripa", "chicarron").
    # Una palabra admite más diferencia ("aripa" → "arepa") que una frase,
    # donde un cambio de palabra cambia el alimento ("salsa de soya" no es
    # "salsa de tomate").
    corte = 0.78 if " " not in principal else 0.88
    parecidos = difflib.get_close_matches(principal, lexico.terminos_destino, n=3, cutoff=corte)
    if parecidos:
        ratio = difflib.SequenceMatcher(None, principal, parecidos[0]).ratio()
        item.destino = lexico.destinos[parecidos[0]]
        item.origen_resolucion = "similitud"
        item.puntaje_resolucion = Decimal(str(round(ratio * 0.9, 2)))
        item.notas.append(f"Se interpretó «{principal}» como «{parecidos[0]}».")
        return None
    # 3. Coincidencia semántica por palabras compartidas.
    puntajes = _semantica(principal, lexico)
    if puntajes and puntajes[0][0] >= 0.55:
        mejor = puntajes[0][0]
        empatados = []
        for p, t in puntajes:
            destino = lexico.destinos[t]
            if p >= mejor - 0.05 and destino not in empatados:
                empatados.append(destino)
        item.destino = lexico.destinos[puntajes[0][1]]
        item.origen_resolucion = "semantica"
        item.puntaje_resolucion = Decimal("0.55")
        if len(empatados) > 1:
            item.candidatos = empatados[:4]
        item.notas.append(f"Coincidencia aproximada para «{principal}».")
    return None


def resolver_metodo(item: ItemInterpretado) -> None:
    """Método explícito, implícito por la preparación o por defecto."""
    destino = item.destino
    if (
        isinstance(destino, Alimento) and destino.matriz == Matriz.HUEVO and item.metodo is not None
        and item.metodo.clave == "fritura_profunda"
    ):
        # Un "huevo frito" se hace en sartén con poco aceite.
        sarten = MetodoCoccion.objects.filter(clave="fritura_sarten").first()
        if sarten:
            item.metodo = sarten
    if destino is None or item.origen_metodo == "explicito":
        return
    if isinstance(destino, Preparacion):
        item.metodo = destino.metodo_defecto
        item.origen_metodo = "defecto" if destino.admite_variantes else "implicito"
        return
    if destino.estado_fisico == EstadoFisico.COCIDO:
        item.origen_metodo = "no_aplica"
        return
    if destino.metodo_defecto and destino.metodo_defecto.clave == "crudo":
        item.metodo = destino.metodo_defecto
        item.origen_metodo = "no_aplica"
        return
    item.metodo = destino.metodo_defecto
    item.origen_metodo = "defecto" if destino.metodo_defecto else "ambiguo"


def _porcion(destino, medida: str) -> PorcionCasera | None:
    filtro = {"preparacion": destino} if isinstance(destino, Preparacion) else {"alimento": destino}
    return PorcionCasera.objects.filter(medida=medida, **filtro).first()


def _densidad(destino) -> Decimal:
    if isinstance(destino, Alimento) and destino.densidad:
        return destino.densidad
    return Decimal("1")


def resolver_cantidad(item: ItemInterpretado) -> None:
    """Convierte cuenta, medida y tamaño en gramos."""
    destino = item.destino
    if destino is None:
        return
    cuenta = item.cuenta or Decimal("1")

    if item.medida_numerica:
        valor, unidad = item.medida_numerica
        gramos = valor * _densidad(destino) if unidad == "ml" else valor
        if item.cuenta and item.cuenta > 1:
            gramos *= item.cuenta
        item.cantidad_g = gramos
        item.fuente_cantidad = "gramos"
        if unidad == "ml" and isinstance(destino, Alimento) and destino.densidad and destino.densidad != 1:
            item.notas.append(f"{valor:.0f} ml × densidad {destino.densidad} g/ml = {gramos:.0f} g.")
        return

    if item.medida:
        porcion = _porcion(destino, item.medida)
        if porcion:
            gramos = porcion.cantidad * (_densidad(destino) if item.es_liquido else 1)
            item.cantidad_g = gramos * cuenta
            item.fuente_cantidad = "medida"
            item.cantidad_original, item.unidad_original = cuenta, porcion.get_medida_display().lower()
            item.aplicar_rendimiento = True
            return
        genericas = parametro("medidas_genericas_ml")
        if item.medida in genericas:
            item.cantidad_g = Decimal(str(genericas[item.medida])) * _densidad(destino) * cuenta
            item.fuente_cantidad = "medida"
            item.cantidad_original, item.unidad_original = cuenta, item.medida
            item.notas.append(f"Se usó la medida general de {item.medida} ({genericas[item.medida]} ml).")
            return

    if item.tamano:
        porcion = _porcion(destino, f"unidad_{item.tamano}")
        if porcion:
            item.cantidad_g = porcion.cantidad * cuenta
            item.fuente_cantidad = "unidad"
            item.cantidad_original, item.unidad_original = cuenta, porcion.get_medida_display().lower()
            item.aplicar_rendimiento = True
            return

    porcion = None
    if item.cuenta and not item.es_liquido:
        porcion = _porcion(destino, "unidad_mediana")
    porcion = porcion or porcion_defecto(destino)
    if porcion is None:
        base = destino.peso_porcion_g if isinstance(destino, Preparacion) else Decimal("100")
        item.cantidad_g = base * cuenta
        item.notas.append(f"No hay porción casera registrada: se usaron {base:.0f} g.")
    else:
        gramos = porcion.cantidad * (_densidad(destino) if item.es_liquido else 1)
        item.cantidad_g = gramos * cuenta
        item.cantidad_original, item.unidad_original = cuenta, porcion.get_medida_display().lower()
        item.notas.append(
            f"Cantidad no indicada con precisión: se usó {porcion.get_medida_display().lower()} "
            f"({porcion.cantidad:.0f} {'ml' if item.es_liquido else 'g'})."
        )
    item.fuente_cantidad = "unidad" if item.cuenta else "defecto"
    item.aplicar_rendimiento = True


def _unir_aceite_agregado(items: list[ItemInterpretado], lexico: Lexico) -> list[ItemInterpretado]:
    """
    "huevo frito con una cucharada de aceite": el aceite no es otro alimento,
    es el que se agregó a la sartén. Se pasa al ítem frito para que la
    calculadora use solo la parte que el alimento retiene.
    """
    resultado: list[ItemInterpretado] = []
    sarten = lexico.metodo_por_clave("fritura_sarten")
    for item in items:
        es_grasa = isinstance(item.destino, Alimento) and item.destino.categoria == "Grasas y aceites"
        anterior = resultado[-1] if resultado else None
        if (
            es_grasa and anterior is not None and anterior.metodo is not None
            and anterior.metodo.es_fritura and item.cantidad_g
        ):
            anterior.aceite_agregado_g = item.cantidad_g
            if sarten:
                anterior.metodo = sarten
            anterior.notas.append(
                f"Se indicó {item.cantidad_g:.0f} g de aceite en la sartén; se cuenta solo la parte que retiene el alimento."
            )
            continue
        resultado.append(item)
    return resultado


def registrar_pendiente(termino: str) -> None:
    """El término no reconocido llega a la bandeja del Curador (sin datos del usuario)."""
    termino = normalizar(termino)[:120]
    if not termino:
        return
    pendiente, creado = TerminoPendiente.objects.get_or_create(termino=termino)
    if not creado:
        pendiente.veces += 1
        pendiente.save(update_fields=["veces", "ultima_vez"])


# --- Punto de entrada ---------------------------------------------------------------


def interpretar(texto: str, *, usuario=None, permitir_ia: bool = True, registrar_pendientes: bool = True) -> Interpretacion:
    texto = (texto or "").strip()[:MAX_CARACTERES]
    normal = normalizar(texto)
    lexico = Lexico(usuario)
    interpretacion = Interpretacion(texto=texto, items=[], tipo_comida=detectar_tipo_comida(normal))

    for segmento in segmentar(normal, lexico):
        item = ItemInterpretado(fragmento=segmento)
        sin_cantidades = extraer_cantidades(segmento, item)
        sin_metodo = extraer_metodo(sin_cantidades, item, lexico)
        item.texto_alimento = limpiar(sin_metodo)
        # Primero con las palabras de método ("mojarra frita" es una
        # preparación), luego sin ellas ("arepa" + método frito).
        con_metodo = limpiar(sin_cantidades)
        # El segmento completo va primero: en "tajadas de maduro" la palabra
        # "tajadas" es parte del nombre, no una medida.
        completos = (limpiar(segmento, final=False), limpiar(segmento))
        coincidio = resolver([*completos, con_metodo, item.texto_alimento], lexico, item)
        if coincidio in completos and coincidio != con_metodo:
            # Se reconoció el nombre completo: la medida no aplica.
            item.medida = ""
            item.tamano = ""
        if item.destino is None and not item.texto_alimento:
            continue  # segmento sin contenido ("hoy almorcé")
        if item.destino is not None:
            if coincidio == con_metodo and con_metodo != item.texto_alimento and isinstance(item.destino, Preparacion):
                # El método forma parte del nombre ("yuca frita"): es el de la preparación.
                item.metodo = None
                item.origen_metodo = "no_aplica"
            resolver_metodo(item)
            resolver_cantidad(item)
        interpretacion.items.append(item)

    sin_resolver = [i for i in interpretacion.items if i.destino is None]
    if sin_resolver and permitir_ia:
        from core.services import ia

        resultado_ia = ia.interpretar_fragmentos(usuario, [i.fragmento for i in sin_resolver])
        if resultado_ia.usado:
            interpretacion.motor = resultado_ia.motor
            interpretacion.version_plantilla_ia = resultado_ia.version_plantilla
            for item, propuesta in zip(sin_resolver, resultado_ia.items):
                if propuesta:
                    aplicar_propuesta_ia(item, propuesta, lexico)
        elif resultado_ia.motivo:
            interpretacion.avisos.append(resultado_ia.motivo)

    for item in interpretacion.items:
        if item.destino is None:
            item.notas.append("No se reconoció este alimento. Búscalo en el catálogo, créalo como alimento personal o descártalo.")
            if registrar_pendientes:
                registrar_pendiente(item.texto_alimento or item.fragmento)

    interpretacion.items = _unir_aceite_agregado(interpretacion.items, lexico)
    return interpretacion


def aplicar_propuesta_ia(item: ItemInterpretado, propuesta: dict, lexico: Lexico) -> None:
    """
    Usa la estructura propuesta por la IA, pero la resuelve contra el
    catálogo propio: la IA nunca aporta valores nutricionales.
    """
    nombre = normalizar(propuesta.get("name", ""))
    preparacion = normalizar(propuesta.get("preparation", ""))
    if preparacion in lexico.metodos and item.metodo is None:
        item.metodo = lexico.metodos[preparacion]
        item.origen_metodo = "explicito"
    if propuesta.get("quantity") and item.cuenta is None and item.medida_numerica is None:
        unidad = normalizar(propuesta.get("unit", ""))
        cantidad = Decimal(str(propuesta["quantity"]))
        if unidad in UNIDADES_PESO:
            base, factor = UNIDADES_PESO[unidad]
            item.medida_numerica = (cantidad * Decimal(str(factor)), base)
        else:
            item.cuenta = cantidad
            if unidad in MEDIDAS:
                item.medida = MEDIDAS[unidad]
    resolver([nombre], lexico, item)
    if item.destino is not None:
        item.origen_resolucion = "ia"
        item.puntaje_resolucion = min(item.puntaje_resolucion, Decimal("0.75"))
        item.notas.append(f"Identificado con ayuda de la IA como «{nombre}».")
        resolver_metodo(item)
        resolver_cantidad(item)


# --- Preguntas de aclaración -----------------------------------------------------------


def preguntas_para(items_y_kcal: list[tuple[int, ItemInterpretado | object, Decimal]]) -> list[dict]:
    """
    Como máximo `max_preguntas_aclaracion` preguntas, para los ítems de menor
    confianza que más energía aportan.

    `items_y_kcal`: lista de (id del ItemComida, objeto con los datos, kcal).
    El objeto puede ser un ItemInterpretado o un ItemComida.
    """
    umbral = parametro("umbral_confianza")
    maximo = parametro("max_preguntas_aclaracion")
    candidatas = []
    for item_id, item, kcal in items_y_kcal:
        confianza = Decimal(str(item.confianza))
        if confianza >= umbral or getattr(item, "pendiente", False):
            continue
        pregunta = _pregunta_para(item_id, item)
        if pregunta:
            candidatas.append((kcal or Decimal("0"), pregunta))
    candidatas.sort(key=lambda par: par[0], reverse=True)
    return [p for _, p in candidatas[:maximo]]


def _pregunta_para(item_id: int, item) -> dict | None:
    destino = getattr(item, "destino", None)
    nombre = getattr(item, "nombre_mostrado", None) or (destino.nombre if destino else "")
    candidatos = getattr(item, "candidatos", None) or []
    if candidatos:
        return {
            "item": item_id, "tipo": "candidato",
            "texto": f"¿A cuál de estos te refieres con «{getattr(item, 'texto_alimento', nombre)}»?",
            "opciones": [{"valor": f"{'p' if isinstance(c, Preparacion) else 'a'}{c.pk}", "etiqueta": c.nombre} for c in candidatos[:4]],
        }

    es_liquido = (isinstance(destino, Alimento) and destino.es_liquido) or (isinstance(destino, Preparacion) and destino.es_bebida)
    if es_liquido and getattr(item, "fuente_cantidad", "") in ("unidad", "defecto"):
        filtro = {"preparacion": destino} if isinstance(destino, Preparacion) else {"alimento": destino}
        porciones = list(PorcionCasera.objects.filter(**filtro).exclude(medida__in=["cucharada", "cucharadita"]))
        if len(porciones) >= 2:
            return {
                "item": item_id, "tipo": "presentacion",
                "texto": f"¿Qué presentación de {nombre.lower()} fue?",
                "opciones": [{"valor": p.medida, "etiqueta": f"{p.get_medida_display()} ({p.cantidad:.0f} ml)"} for p in porciones[:4]],
            }

    if getattr(item, "origen_metodo", "") in ("defecto", "ambiguo") and destino is not None:
        if isinstance(destino, Preparacion):
            claves = [destino.metodo_defecto.clave, "fritura_profunda"]
        else:
            claves = OPCIONES_METODO.get(destino.matriz, OPCIONES_METODO[Matriz.OTRO])
        metodos = [m for m in (MetodoCoccion.objects.filter(clave=c, estado=EstadoRegistro.ACTIVO).first() for c in dict.fromkeys(claves)) if m]
        if len(metodos) >= 2:
            return {
                "item": item_id, "tipo": "metodo",
                "texto": f"¿Cómo estaba preparado: {nombre.lower()}?",
                "opciones": [{"valor": m.clave, "etiqueta": m.nombre} for m in metodos[:4]],
            }

    if getattr(item, "fuente_cantidad", "") == "defecto" and destino is not None:
        filtro = {"preparacion": destino} if isinstance(destino, Preparacion) else {"alimento": destino}
        tamanos = list(PorcionCasera.objects.filter(medida__startswith="unidad_", **filtro))
        if len(tamanos) >= 2:
            return {
                "item": item_id, "tipo": "tamano",
                "texto": f"¿De qué tamaño era: {nombre.lower()}?",
                "opciones": [{"valor": p.medida, "etiqueta": f"{p.get_medida_display()} ({p.cantidad:.0f} g)"} for p in tamanos],
            }
    return None
