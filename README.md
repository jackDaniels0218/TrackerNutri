# Tracker Nutricional Algorítmico para Dietas Regionales Colombianas

Aplicación web para registrar comidas colombianas describiéndolas con
palabras normales ("hoy almorcé una arepa frita y 150 g de carne asada") y
obtener una estimación nutricional **comprensible, editable y trazable**.

Proyecto académico de Ingeniería de Software: 2 semanas, 4 personas,
metodología incremental.

---

## Idea central

> **La inteligencia artificial interpreta. Python calcula.**

La IA solo convierte el texto en una lista de alimentos con cantidades. Los
totales los calcula el backend con los datos del catálogo, mediante fórmulas
probadas con pruebas unitarias. Por eso:

- los resultados son **reproducibles** (una fórmula, no una respuesta de un
  modelo de lenguaje);
- la aplicación **sigue funcionando sin IA**, con el registro manual.

---

## Qué hace

- Registro, inicio y cierre de sesión (sistema de Django, sin contraseñas propias).
- Perfil con meta diaria de calorías configurable.
- Registro de comidas **por texto libre** interpretado por IA.
- Pantalla de **confirmación editable**: nada se guarda sin que lo apruebes.
- **Registro manual** como alternativa equivalente y siempre disponible.
- Cálculo de calorías, proteínas, carbohidratos y grasas.
- Catálogo inicial con 22 alimentos y preparaciones colombianas.
- Panel diario, historial por fecha y gráficos con Chart.js.
- API REST para las operaciones que la necesitan.
- 119 pruebas automatizadas.

Distingue lo que otras aplicaciones confunden: **arepa frita ≠ arepa asada**,
**carne frita ≠ carne asada**, los líquidos se miden en mililitros y "una
unidad" no son gramos.

---

## Instalación

Necesitas **Python 3.11 o superior**. Probado con Python 3.13 y Django 5.1.

```bash
# 1. Clonar el repositorio
git clone https://github.com/jackDaniels0218/TrackerNutri.git
cd TrackerNutri

# 2. Crear y activar el entorno virtual
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Instalar las dependencias
pip install -r requirements.txt

# 4. Configurar las variables de entorno
cp .env.example .env               # Windows: copy .env.example .env

# 5. Crear la base de datos
python manage.py migrate

# 6. Cargar el catálogo de alimentos
python manage.py loaddata catalogo_alimentos

# 7. Arrancar
python manage.py runserver
```

Abre **http://127.0.0.1:8000/** y crea tu cuenta en «Crea una».

### Comandos útiles

```bash
# Crear un usuario administrador (para entrar en /admin/)
python manage.py createsuperuser

# Cargar un usuario de demostración con comidas de ejemplo
python manage.py cargar_datos_demo
#   → usuario: demo   contraseña: demo12345

# Ejecutar todas las pruebas
python manage.py test

# Ejecutar solo las pruebas del motor de cálculo
python manage.py test core.tests.test_nutrition
```

---

## Configurar la IA (opcional)

**La aplicación funciona sin esto.** Sin clave, el botón «Analizar»
desaparece y queda el registro manual, que calcula exactamente lo mismo.

Para activar la interpretación por IA:

1. Consigue una clave en https://platform.openai.com/api-keys
2. Ponla en tu archivo `.env`:

   ```
   OPENAI_API_KEY=sk-...
   ```

3. Reinicia el servidor.

La clave se lee de una variable de entorno, nunca se escribe en el código ni
viaja al navegador. Solo se envía la descripción de la comida: ni tu nombre,
ni tu correo, ni tu perfil salen del servidor.

---

## Cómo probar que funciona

### Escenario A — Registro con IA (requiere clave)

1. Entra en **Registrar**.
2. Escribe: *"Hoy almorcé una arepa frita mediana, 150 gramos de carne de res
   asada, una porción de arroz y una gaseosa de 400 ml"*.
3. Pulsa **Analizar**.
4. Revisa la lista: la arepa debe salir como **frita** y la gaseosa en **ml**.
   Los alimentos con cantidad dudosa aparecen marcados en amarillo.
5. Corrige lo que no cuadre y pulsa **Guardar comida**.
6. El panel muestra el total actualizado.

### Escenario B — Registro manual (siempre funciona)

1. Entra en **Registrar → Registrar manualmente**.
2. Nombre: "Almuerzo". Elige *Arroz blanco (cocido)*, cantidad **150**,
   unidad **gramos**.
3. Guarda. El resultado debe ser **195 kcal**
   (130 kcal/100 g × 150 g ÷ 100 = 195).

### Escenario C — Alimento fuera del catálogo

Registra manualmente un alimento dejando el catálogo en «Sin coincidencia» y
escribiendo "Sushi". Se guarda **sin valores nutricionales** y el panel avisa
de que hay alimentos sin datos. No se inventan calorías ni se cuentan como
cero.

### Escenario D — Aislamiento entre usuarios

Crea dos cuentas, registra una comida con la primera y entra con la segunda:
su panel y su historial están vacíos. Si copias la URL de la comida ajena,
obtienes un **404**.

---

## Estructura del proyecto

```
TrackerNutri/
├── manage.py                      Punto de entrada de Django
├── requirements.txt               Dependencias
├── .env.example                   Plantilla de configuración (sin secretos)
│
├── config/                        Configuración del proyecto
│   ├── settings.py                Ajustes, seguridad, variables de entorno
│   └── urls.py                    Rutas raíz
│
├── core/                          La aplicación
│   ├── models.py                  Perfil, Alimento, RegistroComida, DetalleComida
│   ├── views.py                   Páginas web
│   ├── api.py                     Endpoints REST
│   ├── forms.py                   Formularios y validación
│   ├── serializers.py             Serializadores de la API
│   ├── urls.py                    Rutas de la aplicación
│   ├── admin.py                   Panel de administración
│   ├── signals.py                 Crea el perfil al registrarse
│   │
│   ├── services/                  ← La lógica de negocio vive aquí
│   │   ├── nutrition.py           Motor de cálculo (el archivo clave)
│   │   ├── food_parser.py         Normalización y búsqueda en el catálogo
│   │   ├── ai_service.py          Integración con la API de IA
│   │   └── comidas.py             Guardado y recálculo de comidas
│   │
│   ├── fixtures/
│   │   └── catalogo_alimentos.json   22 alimentos colombianos
│   │
│   ├── management/commands/
│   │   └── cargar_datos_demo.py   Datos para la sustentación
│   │
│   └── tests/                     119 pruebas
│       ├── test_nutrition.py      Motor de cálculo
│       ├── test_parser.py         Normalización y emparejamiento
│       ├── test_ai_service.py     IA (con respuestas simuladas)
│       ├── test_vistas.py         Páginas, permisos y gráficos
│       ├── test_api.py            Endpoints REST
│       └── test_persistencia.py   Datos tras reiniciar
│
├── templates/                     Plantillas HTML
├── static/css/estilos.css         Estilos (sin framework, adaptados a móvil)
├── static/js/                     Gráficos y ayudas de formulario
│
└── docs/
    ├── plan_incremental.md        Plan de 2 semanas, 4 personas, roles
    └── arquitectura.md            Qué hace cada archivo y por qué
```

---

## Cómo se calculan los nutrientes

Los valores del catálogo están **por 100 g** (o por 100 ml en los líquidos).
Para una cantidad consumida se aplica una regla de tres:

```
nutriente = valor_por_100 × cantidad_en_gramos ÷ 100
```

Ejemplo comprobable: el arroz blanco cocido tiene 130 kcal/100 g.
Para 150 g → `130 × 150 ÷ 100 = 195 kcal`.

**Reglas que sigue el motor** (`core/services/nutrition.py`):

- Se convierten las unidades **antes** de calcular.
- No se convierten gramos a mililitros: haría falta la densidad, que el
  catálogo no guarda. Se pide la cantidad en la unidad correcta.
- "1 unidad" usa la equivalencia documentada del alimento
  (`gramos_por_unidad`). Si no existe, **se pide confirmación** en lugar de
  suponer un peso.
- Redondeo consistente: 1 decimal, ROUND_HALF_UP, aplicado al calcular cada
  alimento. Los totales suman valores ya redondeados, así que el panel
  coincide exactamente con la suma de las filas.
- Si falta un dato esencial, el resultado es **«sin datos»**, nunca cero.
- Si el catálogo ya describe el alimento frito, **no se vuelve a sumar aceite**.

---

## Limitaciones conocidas

Conviene decirlas en voz alta antes que esconderlas:

1. **Los valores nutricionales son estimaciones de referencia**, reunidas para
   uso académico con el orden de magnitud de tablas como la TCAC del ICBF y
   USDA FoodData Central. **No son cifras oficiales** y deben contrastarse
   antes de cualquier uso real. Cada alimento guarda su campo `fuente` y la
   marca `valores_aproximados`.
2. **Las preparaciones caseras varían muchísimo.** La bandeja paisa es el caso
   extremo: cambia por completo según el restaurante. Para un cálculo serio
   conviene registrar cada componente por separado.
3. **La absorción de aceite no se mide**, se estima. El parámetro existe
   (`GRAMOS_ACEITE_POR_100G_FRITO`) pero está **desactivado por defecto**,
   porque las fichas de alimentos fritos del catálogo ya incluyen el aceite.
4. **La IA puede equivocarse** identificando alimentos o cantidades. Por eso
   existe la pantalla de confirmación: nada se guarda sin que el usuario lo
   apruebe.
5. **El catálogo tiene 22 alimentos.** Es suficiente para demostrar el sistema,
   no para cubrir la cocina colombiana. Se amplía desde `/admin/` o añadiendo
   entradas al fixture.
6. **No hay ajuste automático de metas** ni recomendaciones médicas. La meta la
   define el usuario; esto no es una herramienta clínica.
7. **SQLite y `DEBUG=True`** sirven para desarrollo. Para un despliegue real
   habría que poner `DJANGO_DEBUG=false`, una `DJANGO_SECRET_KEY` propia y un
   servidor como Gunicorn detrás de Nginx.

---

## Pruebas

```bash
python manage.py test
```

**119 pruebas**, organizadas en seis archivos. Cubren los 17 escenarios
exigidos en el enunciado:

| # | Escenario | Dónde |
|---|---|---|
| 1 | Registro e inicio de sesión | `test_vistas.RegistroEInicioDeSesionTests` |
| 2 | Acceso a páginas privadas | `test_vistas.AccesoAPaginasPrivadasTests` |
| 3 | Separación de datos entre usuarios | `test_vistas.SeparacionEntreUsuariosTests`, `test_api` |
| 4 | Creación de alimentos | `test_nutrition.CreacionDeAlimentosTests` |
| 5 | Cálculo de nutrientes por cantidad | `test_nutrition.CalculoPorCantidadTests` |
| 6 | Conversión de unidades | `test_nutrition.ConversionDeUnidadesTests` |
| 7 | Suma de varios alimentos | `test_nutrition.SumaDeAlimentosTests` |
| 8 | Resumen diario | `test_nutrition.ResumenDiarioTests` |
| 9 | Crear, modificar y eliminar comidas | `test_vistas.CicloDeVidaDeComidasTests` |
| 10 | Cantidades negativas o inválidas | `test_nutrition.CantidadesInvalidasTests` |
| 11 | Alimentos no identificados | `test_nutrition.AlimentoNoIdentificadoTests` |
| 12 | Respuesta inválida de la IA | `test_ai_service.ValidacionDeRespuestaTests` |
| 13 | API de IA no disponible | `test_ai_service.LlamadaSimuladaTests` |
| 14 | Registro manual | `test_vistas.RegistroManualTests` |
| 15 | Historial sin datos | `test_vistas.EstadosVaciosTests` |
| 16 | Calorías restantes | `test_nutrition.ResumenDiarioTests` |
| 17 | Persistencia tras reiniciar | `test_persistencia` |

Las pruebas de IA **simulan** la respuesta con `unittest.mock`: no llaman a la
API real, así que son rápidas, deterministas y no gastan créditos.

---

## Documentación adicional

- **[docs/plan_incremental.md](docs/plan_incremental.md)** — plan de 2 semanas,
  reparto entre 4 personas, los 5 incrementos, riesgos y trazabilidad.
- **[docs/arquitectura.md](docs/arquitectura.md)** — qué hace cada archivo, qué
  recibe, qué devuelve, qué se puede modificar sin romper el resto.

---

## Tecnologías

Python · Django 5.1 · Django REST Framework · SQLite · HTML, CSS y JavaScript
sin framework · Chart.js 4.4 (incluido en el repositorio, sin CDN) · API de
OpenAI (opcional) · framework de pruebas de Django.
