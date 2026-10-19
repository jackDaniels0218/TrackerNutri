"""
Configuración del panel de administración de Django.

Sirve para cargar y corregir el catálogo de alimentos sin escribir SQL y para
revisar los registros durante la demostración del proyecto.
"""

from django.contrib import admin

from core.models import Alimento, DetalleComida, PerfilNutricional, RegistroComida


@admin.register(Alimento)
class AlimentoAdmin(admin.ModelAdmin):
    list_display = (
        "nombre",
        "metodo_preparacion",
        "categoria",
        "unidad_referencia",
        "calorias",
        "valores_aproximados",
        "activo",
    )
    list_filter = ("categoria", "metodo_preparacion", "activo", "valores_aproximados")
    search_fields = ("nombre", "categoria")
    ordering = ("nombre", "metodo_preparacion")


@admin.register(PerfilNutricional)
class PerfilNutricionalAdmin(admin.ModelAdmin):
    list_display = ("usuario", "meta_calorias_diaria", "actualizado_en")
    search_fields = ("usuario__username",)


class DetalleComidaInline(admin.TabularInline):
    model = DetalleComida
    extra = 0
    # La instantánea nutricional no se edita a mano: la calcula el servicio.
    readonly_fields = ("calorias", "proteinas", "carbohidratos", "grasas")


@admin.register(RegistroComida)
class RegistroComidaAdmin(admin.ModelAdmin):
    list_display = ("descripcion", "usuario", "fecha", "origen", "confirmado")
    list_filter = ("origen", "confirmado", "fecha")
    search_fields = ("descripcion", "usuario__username")
    date_hierarchy = "fecha"
    inlines = [DetalleComidaInline]
