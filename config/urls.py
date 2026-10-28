"""
Rutas del proyecto.

* /admin/   -> administración técnica de Django.
* /         -> la aplicación (core/urls.py), incluido /cuentas/ (ingreso,
               salida y recuperación de contraseña).
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
]
