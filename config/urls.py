"""
Rutas del proyecto.

* /admin/   -> administración de Django (catálogo de alimentos).
* /cuentas/ -> login y logout, que aporta django.contrib.auth.
* /         -> la aplicación (core/urls.py).
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("cuentas/", include("django.contrib.auth.urls")),
    path("", include("core.urls")),
]
