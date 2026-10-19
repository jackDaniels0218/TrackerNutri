"""
Rutas de la aplicación core.

Arriba las páginas web (devuelven HTML); abajo, bajo /api/, los endpoints
REST que consume JavaScript.
"""

from django.urls import path

from core import api, views

urlpatterns = [
    # --- Páginas web ---------------------------------------------------------
    path("", views.panel, name="panel"),
    path("registro/", views.registro_usuario, name="registro"),
    path("perfil/", views.perfil, name="perfil"),
    path("comidas/nueva/", views.nueva_comida, name="nueva_comida"),
    path("comidas/confirmar/", views.confirmar_comida, name="confirmar_comida"),
    path("comidas/manual/", views.comida_manual, name="comida_manual"),
    path("comidas/<int:pk>/", views.detalle_comida, name="detalle_comida"),
    path("comidas/<int:pk>/editar/", views.editar_comida, name="editar_comida"),
    path("comidas/<int:pk>/eliminar/", views.eliminar_comida, name="eliminar_comida"),
    path("historial/", views.historial, name="historial"),
    # --- API REST ------------------------------------------------------------
    path("api/alimentos/", api.AlimentoListView.as_view(), name="api_alimentos"),
    path("api/perfil/", api.PerfilView.as_view(), name="api_perfil"),
    path("api/analizar/", api.AnalizarComidaView.as_view(), name="api_analizar"),
    path("api/comidas/", api.ComidaListCreateView.as_view(), name="api_comidas"),
    path("api/comidas/<int:pk>/", api.ComidaDetailView.as_view(), name="api_comida"),
    path("api/resumen/", api.resumen_dia, name="api_resumen"),
    path("api/tendencia/", api.tendencia, name="api_tendencia"),
]
