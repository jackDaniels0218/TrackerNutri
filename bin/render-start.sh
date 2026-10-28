#!/usr/bin/env bash
# Arranque en Render. En el plan gratuito el disco no es persistente: la base
# SQLite se recrea en cada arranque con el catálogo y los datos de demostración
# (con fechas relativas a hoy), así la demo siempre empieza en el mismo estado.
set -o errexit

python manage.py migrate --noinput

PARAMETROS=()
if [ -n "${IA_COMPATIBLE_API_KEY:-}" ]; then
  PARAMETROS+=(--parametro "ia_proveedor=compatible"
               --parametro "ia_url_compatible=${IA_URL_COMPATIBLE:-https://api.groq.com/openai/v1}"
               --parametro "ia_modelo_compatible=${IA_MODELO_COMPATIBLE:-openai/gpt-oss-20b}")
elif [ -z "${OPENAI_API_KEY:-}" ]; then
  PARAMETROS+=(--parametro "ia_proveedor=ninguno")
fi
python manage.py inicializar_sistema "${PARAMETROS[@]}"
python manage.py cargar_demo --clave "${DEMO_CLAVE:-NutriDemo2026}"

exec gunicorn config.wsgi --bind "0.0.0.0:${PORT:-8000}" --workers 2 --timeout 60
