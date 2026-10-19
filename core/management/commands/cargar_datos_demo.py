"""
Comando para preparar una demostración con datos realistas.

    python manage.py cargar_datos_demo

Crea el usuario `demo` (contraseña `demo12345`) con comidas en los últimos
días, para que el panel, los gráficos y el historial tengan algo que mostrar
al presentar el proyecto.

No inventa datos sobre un usuario real: solo crea este usuario de ejemplo. Si
ya existe, borra sus comidas y las vuelve a generar para que la demostración
siempre salga igual.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Alimento, MetodoPreparacion, OrigenRegistro, Unidad
from core.services.comidas import guardar_comida

USUARIO = "demo"
CLAVE = "demo12345"

# (nombre en el catálogo, preparación, cantidad, unidad)
DESAYUNO = [("Arepa de maíz", MetodoPreparacion.ASADO, "100", Unidad.GRAMOS),
            ("Huevo", MetodoPreparacion.FRITO, "2", Unidad.UNIDAD)]
ALMUERZO = [("Arroz blanco", MetodoPreparacion.COCIDO, "150", Unidad.GRAMOS),
            ("Carne de res", MetodoPreparacion.ASADO, "150", Unidad.GRAMOS),
            ("Fríjoles", MetodoPreparacion.COCIDO, "120", Unidad.GRAMOS),
            ("Gaseosa azucarada", MetodoPreparacion.NO_APLICA, "400", Unidad.MILILITROS)]
CENA = [("Patacón", MetodoPreparacion.FRITO, "2", Unidad.UNIDAD),
        ("Aguacate", MetodoPreparacion.CRUDO, "80", Unidad.GRAMOS)]


class Command(BaseCommand):
    help = "Crea el usuario demo con comidas de ejemplo de los últimos días."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dias",
            type=int,
            default=5,
            help="Cuántos días hacia atrás generar (por defecto, 5).",
        )

    def handle(self, *args, **opciones):
        if not Alimento.objects.exists():
            self.stderr.write(
                self.style.ERROR(
                    "El catálogo está vacío. Ejecuta primero:\n"
                    "  python manage.py loaddata catalogo_alimentos"
                )
            )
            return

        usuario, creado = User.objects.get_or_create(
            username=USUARIO, defaults={"email": "demo@ejemplo.com"}
        )
        usuario.set_password(CLAVE)
        usuario.save()
        usuario.perfil.meta_calorias_diaria = 2200
        usuario.perfil.edad = 22
        usuario.perfil.peso_kg = Decimal("68.5")
        usuario.perfil.estatura_cm = 172
        usuario.perfil.save()

        usuario.comidas.all().delete()

        hoy = timezone.localdate()
        total_comidas = 0
        for dia in range(opciones["dias"]):
            fecha = hoy - timedelta(days=dia)
            # Un día de cada tres se salta la cena, para que la tendencia no
            # salga como una línea plana artificial.
            menus = [("Desayuno", DESAYUNO, "07:30"), ("Almuerzo", ALMUERZO, "13:00")]
            if dia % 3 != 2:
                menus.append(("Cena", CENA, "19:30"))

            for nombre, items, hora in menus:
                filas = []
                for nombre_alimento, preparacion, cantidad, unidad in items:
                    alimento = Alimento.objects.filter(
                        nombre=nombre_alimento, metodo_preparacion=preparacion
                    ).first()
                    if alimento is None:
                        continue
                    filas.append(
                        {
                            "alimento": alimento,
                            "nombre_mostrado": str(alimento),
                            "cantidad": Decimal(cantidad),
                            "unidad": unidad,
                            "metodo_preparacion": preparacion,
                        }
                    )
                if not filas:
                    continue
                guardar_comida(
                    usuario,
                    descripcion=nombre,
                    fecha=fecha,
                    hora=timezone.datetime.strptime(hora, "%H:%M").time(),
                    filas=filas,
                    origen=OrigenRegistro.MANUAL,
                    confirmado=True,
                )
                total_comidas += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Usuario «{USUARIO}» {'creado' if creado else 'actualizado'} "
                f"con {total_comidas} comidas en {opciones['dias']} días.\n"
                f"Entra con: usuario «{USUARIO}», contraseña «{CLAVE}»."
            )
        )
