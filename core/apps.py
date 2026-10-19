from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Tracker nutricional"

    def ready(self):
        # Importar las señales aquí es lo que hace que se conecten al arrancar.
        from core import signals  # noqa: F401
