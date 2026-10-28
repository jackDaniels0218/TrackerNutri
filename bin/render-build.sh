#!/usr/bin/env bash
# Construcción en Render: dependencias y archivos estáticos.
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --noinput
