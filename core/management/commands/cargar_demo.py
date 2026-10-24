"""
Datos de demostración para la sustentación.

    python manage.py inicializar_sistema
    python manage.py cargar_demo

Crea una cuenta de cada rol y tres semanas de uso de la usuaria demo. Todas
las comidas pasan por el MISMO flujo que usa la aplicación (interpretación
del texto, preguntas de aclaración y motor de cálculo): ningún número está
escrito a mano.

Cuentas creadas (la contraseña se puede cambiar con --clave):
    usuaria@nutriregional.demo    Usuario con 21 días de registros
    gestante@nutriregional.demo   Usuario con salvaguarda activa (gestación)
    curador@nutriregional.demo    Curador nutricional
    admin@nutriregional.demo      Administrador
"""

from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models import (
    Alimento,
    Ambito,
    DiaRegistro,
    EstadoComida,
    FuenteDato,
    MetaCalorica,
    Pesaje,
    RecordatorioUsuario,
    Rol,
)
from core.services import comidas as servicio_comidas
from core.services import cuentas, curacion, metas
from core.services.interpretacion import interpretar

CLAVE_DEMO = "NutriDemo2026"

MENU = [
    ("desayuno", time(7, 30), [
        "desayuné una arepa asada con queso y un chocolate",
        "dos huevos pericos, una arepa y un tinto con una cucharada de azúcar",
        "un pandebono y un café con leche",
        "changua con calado",
        "calentado paisa con huevo frito",
        "una avena y un banano",
    ]),
    ("almuerzo", time(13, 0), [
        "almorcé arroz con pollo y una limonada",
        "un plato de ajiaco con aguacate",
        "frijoles con arroz, carne molida guisada y tajadas de maduro",
        "sudado de pollo con arroz y ensalada",
        "lentejas con arroz y un jugo de mora",
        "pechuga a la plancha con arroz y ensalada",
        "una bandeja paisa",
    ]),
    ("merienda", time(16, 30), [
        "una manzana",
        "un yogur",
        "una empanada de carne y una gaseosa de 400 ml",
        "bocadillo con queso",
        "un tinto",
    ]),
    ("cena", time(19, 30), [
        "sopa de verduras y una arepa",
        "carne en bistec con papa y arroz",
        "una arepa de choclo con quesito",
        "crema de ahuyama con pan",
        "huevos revueltos con pan y chocolate",
    ]),
]


class Command(BaseCommand):
    help = "Crea cuentas de los tres roles y tres semanas de datos de demostración."

    def add_arguments(self, parser):
        parser.add_argument("--dias", type=int, default=21)
        parser.add_argument("--clave", default=CLAVE_DEMO)

    def handle(self, *args, dias, clave, **opciones):
        if not Alimento.objects.exists():
            raise CommandError("El catálogo está vacío. Ejecuta primero: python manage.py inicializar_sistema")
        User = get_user_model()
        correos = ["usuaria@nutriregional.demo", "gestante@nutriregional.demo",
                   "curador@nutriregional.demo", "admin@nutriregional.demo"]
        User.objects.filter(username__in=correos).delete()

        with transaction.atomic():
            admin = cuentas.crear_usuario(correo=correos[3], password=clave, nombres="Admin", apellidos="Demo",
                                          rol=Rol.ADMINISTRADOR, acepta_datos=True)
            curador = cuentas.crear_usuario(correo=correos[2], password=clave, nombres="Curador", apellidos="Demo",
                                            rol=Rol.CURADOR, acepta_datos=True)
            usuaria = self._usuaria(correos[0], clave, dias)
            self._gestante(correos[1], clave)
            self._pendientes_curacion(usuaria, curador)

        self.stdout.write(self.style.SUCCESS("Datos de demostración creados."))
        self.stdout.write(f"Contraseña de todas las cuentas: {clave}")
        for correo in correos:
            self.stdout.write(f"  {correo}")
        del admin

    # --- Usuaria principal -------------------------------------------------------

    def _usuaria(self, correo, clave, dias):
        usuaria = cuentas.crear_usuario(correo=correo, password=clave, nombres="Usuaria", apellidos="Demo",
                                        acepta_datos=True, acepta_ia=True)
        hoy = timezone.localdate()
        inicio = hoy - timedelta(days=dias)
        cuentas.guardar_perfil(usuaria, {
            "fecha_nacimiento": hoy.replace(year=hoy.year - 27, day=1), "sexo": "femenino", "estatura_cm": 162,
            "peso_inicial_kg": Decimal("72.0"), "fecha_peso_inicial": inicio, "nivel_actividad": "ligero",
            "objetivo": "perder", "peso_meta_kg": Decimal("62.0"), "ritmo": "lento",
        })
        MetaCalorica.objects.filter(usuario=usuaria).update(fecha_inicio=inicio)
        cuentas.avanzar_registro(usuaria, 4)
        for hora in (time(8, 0), time(13, 0), time(19, 0)):
            RecordatorioUsuario.objects.create(usuario=usuaria, hora=hora)

        total = 0
        for d in range(dias, 0, -1):
            fecha = hoy - timedelta(days=d)
            for indice, (tipo, hora, opciones) in enumerate(MENU):
                if tipo == "merienda" and d % 2:
                    continue  # no todos los días hay merienda
                texto = opciones[(d + indice) % len(opciones)]
                momento = timezone.make_aware(datetime.combine(fecha, hora))
                comida = servicio_comidas.crear_desde_texto(usuaria, texto, fecha_hora=momento, tipo=tipo)
                # Responde las preguntas de aclaración con la primera opción.
                respuestas = {f"pregunta_{p['item']}_{p['tipo']}": p["opciones"][0]["valor"] for p in comida.preguntas}
                servicio_comidas.responder_preguntas(comida, respuestas)
                for item in comida.items.filter(pendiente=True):
                    servicio_comidas.editar_item(item, descartar=True, marcar_editado=False)
                servicio_comidas.confirmar(comida)
                total += 1
            if d % 5:  # cuatro de cada cinco días quedan marcados como completos
                DiaRegistro.objects.update_or_create(usuario=usuaria, fecha=fecha, defaults={"completo": True})
            if d % 3 == 0:
                # Baja de peso más despacio de lo que predice su meta: el ajuste
                # semanal lo detecta y propone una meta algo menor.
                peso = Decimal("72.0") - Decimal(dias - d) * Decimal("0.012")
                Pesaje.objects.create(usuario=usuaria, fecha=fecha, peso_kg=peso.quantize(Decimal("0.1")))

        # Una comida favorita y una edición, para que se vean en el historial.
        favorita = usuaria.comidas.filter(estado=EstadoComida.CONFIRMADA, tipo="desayuno").first()
        if favorita:
            servicio_comidas.marcar_favorita(favorita, "Mi desayuno de siempre")
        Pesaje.objects.create(usuario=usuaria, fecha=hoy - timedelta(days=1), peso_kg=Decimal("71.8"))

        resultado = metas.evaluar_ajuste_semanal(usuaria, hasta=hoy - timedelta(days=1))
        self.stdout.write(f"Usuaria demo: {total} comidas. Ajuste semanal: {resultado.mensaje}")
        return usuaria

    def _gestante(self, correo, clave):
        """Cuenta para mostrar la salvaguarda: con gestación no se aplica déficit."""
        usuaria = cuentas.crear_usuario(correo=correo, password=clave, nombres="Usuaria", apellidos="Gestante",
                                        acepta_datos=True, acepta_ia=False)
        hoy = timezone.localdate()
        cuentas.guardar_perfil(usuaria, {
            "fecha_nacimiento": hoy.replace(year=hoy.year - 30, day=1), "sexo": "femenino", "estatura_cm": 158,
            "peso_inicial_kg": Decimal("64.0"), "nivel_actividad": "ligero", "objetivo": "perder",
            "ritmo": "moderado", "gestante_lactante": True,
        })
        cuentas.avanzar_registro(usuaria, 4)

    def _pendientes_curacion(self, usuaria, curador):
        """Deja trabajo en la bandeja del Curador para la demostración."""
        for frase in ("un chontaduro con sal", "sushi de salmón", "salsa de soya", "un chontaduro con miel"):
            interpretar(frase, usuario=usuaria, permitir_ia=False)
        personal = Alimento(
            nombre="Galleta integral de la tienda", categoria="Productos de panadería", estado_fisico="cocido",
            kcal=Decimal("450"), proteinas=Decimal("8"), carbohidratos=Decimal("65"), grasas=Decimal("17"),
            azucares=Decimal("20"), ambito=Ambito.PERSONAL, propietario=usuaria, fuente=FuenteDato.ETIQUETA,
            fuente_detalle="Etiqueta del paquete", verificado=False,
        )
        personal.full_clean()
        personal.save()
        item = (usuaria.comidas.filter(estado=EstadoComida.CONFIRMADA, origen="texto")
                .order_by("-fecha_hora").first().items.filter(descartado=False).first())
        if item:
            curacion.crear_correccion(item, usuaria, "cantidad", "120", "La porción era más pequeña.")
