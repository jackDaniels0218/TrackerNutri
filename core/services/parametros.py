"""
RF11 Parámetros del sistema.

El SRS exige que coeficientes, factores, límites de seguridad y listas sean
datos configurables y no valores fijos en el código (restricción de diseño
3.4). Este módulo es la única puerta de acceso a ellos:

    from core.services.parametros import parametro
    piso = parametro("piso_calorico_femenino")

DEFINICIONES contiene el valor inicial de cada parámetro. Se carga en la base
de datos con `python manage.py inicializar_sistema`; desde ese momento manda
la base de datos y el Administrador (o el Curador, en los nutricionales) los
cambia desde la aplicación. Si alguna clave faltara en la base de datos, se
usa el valor inicial para que el sistema no se caiga.
"""

from __future__ import annotations

import json
from decimal import Decimal

N = "nutricional"
S = "salvaguardas"
I = "ia"  # noqa: E741
X = "sistema"

# clave: (tipo, grupo, valor inicial, descripción)
DEFINICIONES: dict[str, tuple[str, str, object, str]] = {
    # --- Cálculo de la meta (actividad 16) ---
    "ecuacion_tmb": ("texto", N, "mifflin_st_jeor", "Ecuación para la tasa metabólica basal."),
    "factores_actividad": ("json", N, {"sedentario": 1.2, "ligero": 1.375, "moderado": 1.55, "alto": 1.725, "muy_alto": 1.9}, "Multiplicador de la TMB según el nivel de actividad."),
    "deficit_por_ritmo": ("json", N, {"lento": 10, "moderado": 20}, "Porcentaje de déficit según el ritmo elegido."),
    "proteina_g_por_kg": ("decimal", N, "1.6", "Gramos de proteína por kilogramo de peso."),
    "grasa_pct_energia": ("decimal", N, "30", "Porcentaje de la energía que se asigna a grasas."),
    "kcal_por_kg": ("decimal", N, "7700", "Energía equivalente a 1 kg de peso corporal."),
    "kcal_por_gramo_grasa": ("decimal", N, "9", "Energía de un gramo de grasa o aceite."),
    "ajuste_semanal_max_kcal": ("decimal", N, "150", "Cambio máximo de la meta en un ajuste semanal."),
    "ajuste_max_pct_meta": ("decimal", N, "10", "Ningún ajuste reduce la meta más de este porcentaje."),
    "suavizado_gasto": ("decimal", N, "0.5", "Peso del gasto observado frente al estimado (0 a 1)."),
    "dias_completos_minimos": ("entero", N, 5, "Días completos necesarios en la semana para ajustar la meta."),
    "pesajes_minimos": ("entero", N, 2, "Pesajes necesarios en 14 días para ajustar la meta."),
    "horas_para_revertir": ("entero", N, 48, "Horas que tiene el usuario para revertir un ajuste."),
    "imc_meta_minimo": ("decimal", N, "18.5", "IMC mínimo admitido para el peso meta."),
    "imc_meta_maximo": ("decimal", N, "24.9", "IMC máximo admitido para el peso meta."),
    # --- Salvaguardas (actividad 17) ---
    "piso_calorico_femenino": ("decimal", S, "1200", "Meta mínima para mujeres."),
    "piso_calorico_masculino": ("decimal", S, "1500", "Meta mínima para hombres."),
    "deficit_maximo_pct": ("decimal", S, "25", "Déficit máximo que puede tener una meta."),
    "perdida_max_semanal_pct": ("decimal", S, "1.0", "Pérdida de peso semanal máxima (% del peso)."),
    "dias_riesgo_bajo_piso": ("entero", S, 3, "Días completos seguidos bajo el piso que disparan la alerta."),
    "contacto_apoyo": ("texto", S, "Consulta con tu EPS o con un profesional en nutrición y dietética.", "Datos de contacto de apoyo profesional que se muestran al usuario."),
    # --- Cálculo e interpretación (actividades 13, 14 y 15) ---
    "umbral_confianza": ("decimal", N, "0.6", "Por debajo de esta confianza se hacen preguntas de aclaración."),
    "max_preguntas_aclaracion": ("entero", N, 2, "Máximo de preguntas de aclaración por comida."),
    "tolerancia_atwater_pct": ("decimal", N, "20", "Diferencia admitida entre la energía declarada y la de Atwater."),
    "tolerancia_peso_preparacion_pct": ("decimal", N, "35", "Diferencia admitida entre los componentes y la porción."),
    "medidas_genericas_ml": ("json", N, {"cucharada": 15, "cucharadita": 5, "taza": 240, "vaso": 250, "pocillo": 150, "lata": 330, "botella_personal": 400}, "Volumen de las medidas caseras cuando el alimento no tiene una propia."),
    "incertidumbre_porcion_pct": ("json", N, {"gramos": 5, "medida": 15, "unidad": 20, "defecto": 30}, "Margen del rango según de dónde salió la cantidad."),
    "factor_tamano_pieza": ("json", N, {"pequena": 1.2, "mediana": 1.0, "grande": 0.85}, "Ajuste de absorción por tamaño de la pieza (más superficie, más aceite)."),
    "factor_escurrido": ("decimal", N, "0.85", "Ajuste de absorción si el alimento se escurrió en papel."),
    "factor_tiempo_fritura": ("json", N, {"corto": 0.9, "normal": 1.0, "largo": 1.15}, "Ajuste de absorción por tiempo de fritura."),
    "proporcion_aceite_sarten": ("json", N, {"min": 0.25, "tipico": 0.4, "max": 0.6}, "Parte del aceite agregado a la sartén que queda en el alimento."),
    "exactitud_identificacion_min": ("decimal", N, "85", "Exactitud mínima de identificación para publicar el catálogo (%)."),
    "exactitud_coccion_min": ("decimal", N, "90", "Exactitud mínima del método de cocción para publicar (%)."),
    "error_energia_max": ("decimal", N, "15", "Error medio de energía máximo para publicar (%)."),
    # --- Proveedor de IA (actividades 21 y 33) ---
    "ia_proveedor": ("texto", I, "openai", "Proveedor activo: openai, compatible (servicio externo compatible con OpenAI, p. ej. Groq u OpenRouter), local o ninguno."),
    "ia_modelo": ("texto", I, "gpt-4o-mini", "Modelo del proveedor."),
    "ia_url_compatible": ("texto", I, "https://api.groq.com/openai/v1", "URL del servicio compatible. Ejemplos: https://api.groq.com/openai/v1, https://openrouter.ai/api/v1, https://generativelanguage.googleapis.com/v1beta/openai/, https://api.cerebras.ai/v1."),
    "ia_modelo_compatible": ("texto", I, "llama-3.3-70b-versatile", "Modelo del servicio compatible (con su nombre exacto en ese servicio)."),
    "ia_url_local": ("texto", I, "http://localhost:11434/v1", "URL de un modelo local compatible con la API de OpenAI (p. ej. Ollama)."),
    "ia_timeout_s": ("decimal", I, "10", "Tiempo máximo de espera del proveedor (segundos)."),
    "ia_limite_diario_usuario": ("entero", I, 30, "Interpretaciones con IA por usuario y día."),
    "ia_presupuesto_mensual_usd": ("decimal", I, "5", "Presupuesto mensual de IA en dólares."),
    "ia_alerta_presupuesto_pct": ("decimal", I, "80", "Porcentaje del presupuesto que dispara la alerta."),
    "ia_costo_entrada_millon": ("decimal", I, "0.15", "Costo por millón de tokens de entrada (USD). Verificar con el proveedor."),
    "ia_costo_salida_millon": ("decimal", I, "0.60", "Costo por millón de tokens de salida (USD). Verificar con el proveedor."),
    # --- Sistema y seguridad de acceso (actividades 12 y 26) ---
    "intentos_login_max": ("entero", X, 5, "Intentos fallidos antes de bloquear la cuenta."),
    "bloqueo_minutos": ("entero", X, 15, "Minutos de bloqueo temporal tras los intentos fallidos."),
    "max_recordatorios": ("entero", X, 3, "Recordatorios diarios máximos por usuario."),
    "categorias_alimento": ("json", X, ["Cereales y derivados", "Tubérculos y plátanos", "Leguminosas", "Carnes", "Pescados", "Huevos", "Lácteos", "Frutas", "Verduras", "Grasas y aceites", "Azúcares y dulces", "Bebidas", "Productos de panadería", "Embutidos", "Condimentos", "Otros"], "Categorías válidas de alimentos."),
}

_cache: dict[str, object] = {}


def _convertir(tipo: str, valor):
    if tipo == "entero":
        return int(valor)
    if tipo == "decimal":
        return Decimal(str(valor))
    if tipo == "booleano":
        return str(valor).strip().lower() in {"1", "true", "si", "sí", "yes"}
    if tipo == "json":
        return json.loads(valor) if isinstance(valor, str) else valor
    return str(valor)


def a_texto(tipo: str, valor) -> str:
    """Serializa un valor para guardarlo en Parametro.valor."""
    if tipo == "json":
        return json.dumps(valor, ensure_ascii=False)
    return str(valor)


def parametro(clave: str):
    """Valor tipado de un parámetro. Lanza KeyError si la clave no existe."""
    if clave in _cache:
        return _cache[clave]
    if clave not in DEFINICIONES:
        raise KeyError(f"Parámetro desconocido: {clave}")

    from core.models import Parametro

    tipo = DEFINICIONES[clave][0]
    try:
        fila = Parametro.objects.filter(clave=clave).only("valor", "tipo").first()
    except Exception:  # tabla aún no creada (primeras migraciones)
        fila = None
    valor = _convertir(fila.tipo, fila.valor) if fila else _convertir(tipo, DEFINICIONES[clave][2])
    _cache[clave] = valor
    return valor


def limpiar_cache() -> None:
    _cache.clear()


def validar_valor(tipo: str, texto: str):
    """Comprueba que `texto` sea convertible al tipo. Devuelve el valor."""
    try:
        return _convertir(tipo, texto)
    except (ValueError, ArithmeticError, json.JSONDecodeError) as exc:
        raise ValueError(f"El valor no es un {tipo} válido.") from exc


def sembrar_parametros() -> int:
    """Crea en la base de datos los parámetros que falten. Devuelve cuántos."""
    from core.models import Parametro

    creados = 0
    for clave, (tipo, grupo, valor, descripcion) in DEFINICIONES.items():
        _, nuevo = Parametro.objects.get_or_create(
            clave=clave,
            defaults={
                "valor": a_texto(tipo, valor),
                "tipo": tipo,
                "grupo": grupo,
                "descripcion": descripcion,
            },
        )
        creados += int(nuevo)
    limpiar_cache()
    return creados
