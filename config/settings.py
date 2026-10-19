"""
Configuración del proyecto "Tracker Nutricional Algorítmico para Dietas
Regionales Colombianas".

Los valores sensibles (SECRET_KEY, DEBUG, clave de la API de IA) se leen de
variables de entorno para no quedar escritos en el repositorio. El archivo
.env.example documenta cuáles existen; .env (no versionado) guarda los reales.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Carga las variables definidas en el archivo .env, si existe.
load_dotenv(BASE_DIR / ".env")


def env_bool(nombre: str, por_defecto: bool = False) -> bool:
    """Lee una variable de entorno como booleano ("1", "true", "yes")."""
    valor = os.environ.get(nombre)
    if valor is None:
        return por_defecto
    return valor.strip().lower() in {"1", "true", "yes", "si", "sí"}


# En desarrollo se admite una clave por defecto; en producción es obligatorio
# definir DJANGO_SECRET_KEY.
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY", "clave-solo-para-desarrollo-no-usar-en-produccion"
)

DEBUG = env_bool("DJANGO_DEBUG", True)

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if h.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# SQLite es suficiente para el alcance académico del proyecto.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-co"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Rutas de autenticación: a dónde va el usuario al entrar y al salir.
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "panel"
LOGOUT_REDIRECT_URL = "login"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    # Los decimales viajan como números JSON y no como texto, para que
    # Chart.js pueda usarlos sin convertirlos y para que toda la API sea
    # coherente (los totales calculados ya salían como números).
    "COERCE_DECIMAL_TO_STRING": False,
}

# --- Integración con la API de IA -------------------------------------------
# Si OPENAI_API_KEY no está definida, el sistema sigue funcionando en modo
# manual: core/services/ai_service.py lo detecta y devuelve un error controlado.
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_TIMEOUT = float(os.environ.get("OPENAI_TIMEOUT", "20"))

# --- Seguridad para despliegue ----------------------------------------------
# Con DEBUG=False se activan las cabeceras y cookies seguras.
if not DEBUG:
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    X_FRAME_OPTIONS = "DENY"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        # Registra errores técnicos del servicio de IA sin volcar datos del
        # usuario en los logs.
        "core.services.ai_service": {"handlers": ["console"], "level": "WARNING"},
    },
}
