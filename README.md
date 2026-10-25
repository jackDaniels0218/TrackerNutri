# NutriRegional

**Tracker nutricional algorítmico para dietas regionales colombianas.**
Prototipo académico del SRS *Requerimientos NutriRegional V1* (IEEE 830) ·
Facultad de Ingeniería, Universidad de Cundinamarca, Facatativá.

La persona escribe lo que comió con sus palabras —«almorcé una arepa frita,
carne asada y una gaseosa»— y el sistema identifica cada componente, infiere
el método de cocción, deconstruye las preparaciones regionales en sus
ingredientes, estima el aceite que absorbe lo frito y calcula la energía y los
macronutrientes **con un rango y un nivel de confianza** que la persona
confirma o corrige. Con el historial de ingesta y de peso calcula la meta
diaria, la ajusta cada semana dentro de límites seguros y muestra tendencias.

> **La IA interpreta, Python calcula.** Los valores nutricionales salen siempre
> de un motor determinista sobre un catálogo curado. La IA (opcional) solo
> ayuda a entender frases que el léxico regional no reconoce, y su respuesta
> se valida contra un esquema que no admite calorías.

NutriRegional **no es un servicio médico** y no reemplaza a un profesional de
la salud o de la nutrición.

---

## Cómo ver cada requerimiento

Con el servidor en marcha, abre **<http://127.0.0.1:8000/requerimientos/>**:
las 22 actividades funcionales y las 14 no funcionales del SRS, cada una con
el rol que la demuestra, los pasos para mostrarla y botones a sus pantallas.
La misma información está en [docs/trazabilidad_srs.md](docs/trazabilidad_srs.md),
y el guion de la presentación en [docs/guion_sustentacion.md](docs/guion_sustentacion.md).

Cuentas de demostración (contraseña `NutriDemo2026` para todas):

| Cuenta | Rol | Para mostrar |
|---|---|---|
| `usuaria@nutriregional.demo` | Usuario | 3 semanas de comidas y pesajes, ajuste semanal revertible, gráficos |
| `gestante@nutriregional.demo` | Usuario | Salvaguardas: meta informativa, sin déficit |
| `curador@nutriregional.demo` | Curador nutricional | Bandeja de pendientes, catálogo, versiones, exactitud |
| `admin@nutriregional.demo` | Administrador | Cuentas, parámetros, IA y costos, auditoría, procesos |

---

## Instalación

Requiere Python 3.11 o superior.

```bash
git clone https://github.com/jackDaniels0218/TrackerNutri.git
cd TrackerNutri

python -m venv .venv
# Windows (PowerShell):  .venv\Scripts\Activate.ps1
# Linux / macOS:         source .venv/bin/activate

python -m pip install -r requirements.txt
cp .env.example .env            # Windows: copy .env.example .env

python manage.py migrate
python manage.py inicializar_sistema   # parámetros, catálogo, 200 frases, publica la v1
python manage.py cargar_demo           # las cuatro cuentas de demostración
python manage.py runserver
```

> Si aparece `ModuleNotFoundError`, instala con `python -m pip ...` usando el
> Python del entorno virtual activado.

### IA (opcional)

Sin clave, todo funciona con el léxico regional y la búsqueda manual. Para
activarla, pon tu clave en `.env` (nunca en el código ni en el chat):

```
OPENAI_API_KEY=sk-...
```

El modelo, el tiempo de espera, el límite diario por usuario y el presupuesto
mensual son **parámetros del sistema** que el Administrador cambia en
*Parámetros*.

**Sin pagar:** cualquier servicio compatible con la API de OpenAI que tenga
nivel gratuito ([lista](https://github.com/raullenchai/free-llm-api-resources)),
por ejemplo Groq:

```
IA_COMPATIBLE_API_KEY=gsk_...
```

y en *Parámetros*: `ia_proveedor = compatible`, `ia_url_compatible =
https://api.groq.com/openai/v1`, `ia_modelo_compatible = llama-3.3-70b-versatile`.
Para OpenRouter: `https://openrouter.ai/api/v1` y un modelo terminado en
`:free`; para Google AI Studio: `https://generativelanguage.googleapis.com/v1beta/openai/`.
También sirve un modelo local (Ollama, LM Studio) con `ia_proveedor = local`.

```bash
python manage.py probar_ia      # comprueba la conexión real (gasta crédito)
```

---

## Comandos

| Comando | Para qué |
|---|---|
| `python manage.py test` | Las 178 pruebas automatizadas, organizadas por requerimiento |
| `python manage.py inicializar_sistema` | Carga inicial idempotente y publicación de la v1 del catálogo |
| `python manage.py cargar_demo` | Cuentas y datos de demostración (`--dias 30` para más historial) |
| `python manage.py procesos ajuste_semanal` | Ajuste semanal de metas (RF16) |
| `python manage.py procesos recordatorios` | Recordatorios (RF20) |
| `python manage.py procesos resumen_semanal` | Resumen semanal por correo (RF20) |
| `python manage.py procesos exactitud` | Conjunto de prueba de exactitud (RF19) |
| `python manage.py respaldar` | Respaldo de la base en `respaldos/` (RNF34) |
| `python manage.py generar_trazabilidad` | Regenera `docs/trazabilidad_srs.md` y `docs/diccionario_datos.md` |
| `python manage.py probar_ia` | Prueba real del proveedor de IA |

Los correos (recuperación de contraseña, resumen semanal) se imprimen en la
consola del servidor.

---

## Estructura

```
config/                 configuración de Django
core/
  models/               cuentas, catálogo, comidas, metas, sistema
  services/             lógica de negocio (sin HTTP): interpretación, cálculo,
                        aceite, metas, salvaguardas, IA, curación, reportes…
  views/                vistas por rol (acceso, comidas, seguimiento, cuenta,
                        curación, administración)
  api/                  API REST v1 (DRF) con esquema OpenAPI en /api/v1/esquema/
  datos/                catálogo inicial: alimentos, preparaciones, métodos,
                        léxico, porciones y frases de referencia
  management/commands/  comandos de la tabla anterior
  requerimientos.py     mapa SRS → pantallas, modelos, servicios y pruebas
  tests/                una prueba por grupo de requerimientos
templates/, static/     interfaz web adaptable a celular
docs/                   arquitectura, plan incremental, trazabilidad,
                        diccionario de datos, desviaciones y guion
```

Detalle en [docs/arquitectura.md](docs/arquitectura.md).

---

## Documentación

- [Trazabilidad SRS → prototipo](docs/trazabilidad_srs.md) (generada)
- [Diccionario de datos](docs/diccionario_datos.md) (generado)
- [Arquitectura](docs/arquitectura.md)
- [Plan incremental](docs/plan_incremental.md)
- [Desviaciones frente al SRS](docs/desviaciones.md)
- [Guion de sustentación](docs/guion_sustentacion.md)

## Tecnologías

Python 3 · Django 5.1 · Django REST Framework · SQLite · Chart.js · OpenAI API
(opcional).
