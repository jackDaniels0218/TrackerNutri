"""Rutas de la API REST v1 y su documentación OpenAPI en /api/v1/esquema/."""

from django.urls import path
from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONOpenAPIRenderer
from rest_framework.schemas import get_schema_view

from core.api import views

urlpatterns = [
    path("esquema/", get_schema_view(
        title="NutriRegional API", version="1.0.0",
        description="API REST del prototipo NutriRegional. Requiere sesión iniciada.",
        renderer_classes=[JSONOpenAPIRenderer], permission_classes=[AllowAny], public=True,
    ), name="api_esquema"),
    path("perfil/", views.PerfilView.as_view(), name="api_perfil"),
    path("alimentos/", views.AlimentosView.as_view(), name="api_alimentos"),
    path("preparaciones/", views.PreparacionesView.as_view(), name="api_preparaciones"),
    path("interpretar/", views.InterpretarView.as_view(), name="api_interpretar"),
    path("comidas/", views.ComidasView.as_view(), name="api_comidas"),
    path("comidas/<int:pk>/", views.ComidaView.as_view(), name="api_comida"),
    path("comidas/<int:pk>/confirmar/", views.ConfirmarComidaView.as_view(), name="api_comida_confirmar"),
    path("resumen/", views.ResumenView.as_view(), name="api_resumen"),
    path("series/", views.SeriesView.as_view(), name="api_series"),
    path("pesajes/", views.PesajesView.as_view(), name="api_pesajes"),
    path("metas/", views.MetasView.as_view(), name="api_metas"),
    path("notificaciones/", views.NotificacionesView.as_view(), name="api_notificaciones"),
]
