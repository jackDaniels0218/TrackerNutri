"""
Señales de la aplicación.

Única señal del proyecto: crear el perfil nutricional en cuanto se crea un
usuario, para que el panel nunca tenga que trabajar con un perfil inexistente.
"""

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import PerfilNutricional


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def crear_perfil_al_registrar(sender, instance, created, **kwargs):
    """Crea el PerfilNutricional con la meta por defecto al nacer el usuario."""
    if created:
        PerfilNutricional.objects.get_or_create(usuario=instance)
