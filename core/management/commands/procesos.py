"""
Procesos en segundo plano del SRS, para programarlos con cron o el
programador de tareas de Windows (en producción irían en Celery):

    python manage.py procesos ajuste_semanal     # RF16, cada semana
    python manage.py procesos recordatorios      # RF20, cada 30 minutos
    python manage.py procesos resumen_semanal    # RF20, cada semana
    python manage.py procesos exactitud          # RF19, ejecutar el conjunto de prueba
"""

from django.core.management.base import BaseCommand

from core.services import auditoria, curacion, metas, notificaciones


class Command(BaseCommand):
    help = "Ejecuta un proceso periódico del sistema."

    def add_arguments(self, parser):
        parser.add_argument("proceso", choices=["ajuste_semanal", "recordatorios", "resumen_semanal", "exactitud"])

    def handle(self, *args, proceso, **opciones):
        if proceso == "ajuste_semanal":
            resultado = metas.ajuste_semanal_todos()
            mensaje = f"Ajuste semanal: {resultado['evaluados']} usuarios evaluados, {resultado['ajustados']} ajustados."
        elif proceso == "recordatorios":
            mensaje = f"Recordatorios creados: {notificaciones.generar_recordatorios()}."
        elif proceso == "resumen_semanal":
            mensaje = f"Resúmenes semanales enviados: {notificaciones.resumen_semanal()}."
        else:
            ejecucion = curacion.ejecutar_exactitud()
            mensaje = (f"Exactitud: identificación {ejecucion.identificacion_pct} %, método {ejecucion.coccion_pct} % "
                       f"({'aprobada' if ejecucion.aprobada else 'no aprobada'}).")
        auditoria.registrar(f"proceso_{proceso}", detalle=mensaje)
        self.stdout.write(self.style.SUCCESS(mensaje))
