"""
Genera la documentación que se deriva del código, para que no se desincronice:

    python manage.py generar_trazabilidad

* docs/trazabilidad_srs.md: cada actividad del SRS con sus pantallas,
  modelos, servicios, pruebas y cómo demostrarla (de core/requerimientos.py).
* docs/diccionario_datos.md: cada tabla con sus campos, tipos y
  restricciones (de los modelos de Django).
"""

from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import reverse

from core.requerimientos import NO_FUNCIONALES, REQUERIMIENTOS


def _celda(texto) -> str:
    return str(texto).replace("|", "\\|").replace("\n", " ")


class Command(BaseCommand):
    help = "Escribe docs/trazabilidad_srs.md y docs/diccionario_datos.md."

    def handle(self, *args, **opciones):
        carpeta = Path(settings.BASE_DIR, "docs")
        carpeta.mkdir(exist_ok=True)
        (carpeta / "trazabilidad_srs.md").write_text(self.trazabilidad(), encoding="utf-8")
        (carpeta / "diccionario_datos.md").write_text(self.diccionario(), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS("Documentos generados en docs/."))

    def trazabilidad(self) -> str:
        lineas = [
            "# Trazabilidad SRS → prototipo",
            "",
            "> Generado con `python manage.py generar_trazabilidad` a partir de `core/requerimientos.py`.",
            "> No editar a mano. La prueba `core/tests/test_trazabilidad.py` verifica que todas las pantallas",
            "> y pruebas mencionadas existen y que cada pantalla abre con el rol que la demuestra.",
            "",
            "Cuentas de demostración (`python manage.py cargar_demo`), contraseña `NutriDemo2026`:",
            "`usuaria@nutriregional.demo`, `gestante@nutriregional.demo`, `curador@nutriregional.demo`,",
            "`admin@nutriregional.demo`.",
            "",
            "## Resumen de requerimientos funcionales",
            "",
            "| RF | Actividad | Roles | Pantallas | Pruebas |",
            "|---|---|---|---|---|",
        ]
        for r in REQUERIMIENTOS:
            pantallas = ", ".join(f"[{e}]({reverse(n)})" for n, e in r["pantallas"])
            pruebas = ", ".join(f"`{p}`" for p in r["pruebas"])
            lineas.append(f"| {r['id']} | {_celda(r['nombre'])} | {', '.join(r['roles'])} | {pantallas} | {pruebas} |")
        lineas += ["", "## Detalle por requerimiento", ""]
        for r in REQUERIMIENTOS:
            lineas += [
                f"### RF{r['id']} · {r['nombre']}",
                "",
                f"- **Roles:** {', '.join(r['roles'])}",
                f"- **Pantallas:** " + "; ".join(f"{e} (`{reverse(n)}`)" for n, e in r["pantallas"]),
                f"- **Modelos:** {', '.join(r['modelos'])}",
                f"- **Servicios (`core/services/`):** {', '.join(r['servicios'])}",
                f"- **Pruebas (`core/tests/`):** {', '.join(r['pruebas'])}",
                f"- **Cómo demostrarlo:** {r['demo']}",
                "",
            ]
        lineas += [
            "## Requerimientos no funcionales (actividades 23 a 36)",
            "",
            "| RNF | Nombre | Estado | Cómo se cumple | Dónde verlo |",
            "|---|---|---|---|---|",
        ]
        for r in NO_FUNCIONALES:
            lineas.append(f"| {r['id']} | {r['nombre']} | {r['estado']} | {_celda(r['como'])} | `{reverse(r['pantalla'])}` |")
        lineas += ["", "Las desviaciones frente al SRS se justifican en [desviaciones.md](desviaciones.md).", ""]
        return "\n".join(lineas)

    def diccionario(self) -> str:
        lineas = [
            "# Diccionario de datos",
            "",
            "> Generado con `python manage.py generar_trazabilidad` a partir de los modelos de `core/models/`.",
            "> Las tablas de usuarios y sesiones son las de `django.contrib.auth` y `django.contrib.sessions`.",
            "",
        ]
        for modelo in apps.get_app_config("core").get_models():
            meta = modelo._meta
            doc = (modelo.__doc__ or "").strip().split("\n\n")[0].replace("\n", " ")
            if doc.startswith(modelo.__name__ + "("):
                doc = ""
            lineas += [f"## {modelo.__name__} (`{meta.db_table}`)", ""]
            if doc:
                lineas += [doc, ""]
            lineas += ["| Campo | Tipo | Nulo | Restricciones | Descripción |", "|---|---|---|---|---|"]
            for campo in meta.concrete_fields:
                tipo = campo.get_internal_type()
                if campo.is_relation:
                    tipo = f"FK → {campo.related_model.__name__}"
                restricciones = []
                if campo.primary_key:
                    restricciones.append("PK")
                if campo.unique and not campo.primary_key:
                    restricciones.append("único")
                if getattr(campo, "max_length", None) and not campo.is_relation:
                    restricciones.append(f"máx. {campo.max_length}")
                if getattr(campo, "max_digits", None):
                    restricciones.append(f"{campo.max_digits},{campo.decimal_places}")
                if campo.choices:
                    restricciones.append("valores: " + ", ".join(str(v) for v, _ in campo.choices[:8])
                                         + (" …" if len(campo.choices) > 8 else ""))
                for v in campo.validators:
                    limite = getattr(v, "limit_value", None)
                    # Los límites enormes son el rango del tipo entero de la base, no reglas del negocio.
                if limite is not None and abs(limite) < 10**9 and type(v).__name__ in ("MinValueValidator", "MaxValueValidator"):
                        restricciones.append(("mín. " if "Min" in type(v).__name__ else "máx. ") + str(limite))
                descripcion = campo.help_text or (campo.verbose_name if campo.verbose_name != campo.name.replace("_", " ") else "")
                lineas.append(f"| `{campo.column}` | {tipo} | {'sí' if campo.null else 'no'} | "
                              f"{_celda('; '.join(restricciones))} | {_celda(descripcion)} |")
            for restriccion in meta.constraints:
                lineas.append(f"\n*Restricción `{restriccion.name}`*")
            lineas.append("")
        return "\n".join(lineas)
