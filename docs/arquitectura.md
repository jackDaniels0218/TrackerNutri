# Arquitectura del sistema

Documento de apoyo para explicar el proyecto: qué hace cada archivo, qué
recibe, qué devuelve y qué se puede modificar sin romper lo demás.

---

## 1. Idea central

> **La IA interpreta. Python calcula.**

El texto del usuario pasa por la IA solo para convertirse en una lista de
alimentos con cantidades. A partir de ahí, todo son cálculos propios con
datos del catálogo. Esto tiene dos consecuencias prácticas:

- Los totales son **reproducibles**: el mismo registro da siempre el mismo
  número, porque lo calcula una fórmula, no un modelo de lenguaje.
- La aplicación **funciona sin IA**: el registro manual entra por el mismo
  camino de cálculo.

---

## 2. Recorrido de una comida

```
Usuario escribe:
"una arepa frita mediana y una gaseosa de 400 ml"
        │
        ▼
┌───────────────────────┐
│ views.nueva_comida    │  valida el texto (AnalisisComidaForm)
└───────────┬───────────┘
            ▼
┌───────────────────────┐
│ ai_service            │  llama a la API con un esquema JSON estricto
│ .interpretar_comida   │  y VALIDA la respuesta en el backend
└───────────┬───────────┘
            │  [{"name":"arepa","quantity":1,"unit":"unidad",
            │    "preparation":"frita","needs_confirmation":true}, ...]
            ▼
┌───────────────────────┐
│ food_parser           │  "frita" -> frito ; "unidad" -> unidad
│ .normalizar_item      │  busca la ficha del catálogo (arepa FRITA)
└───────────┬───────────┘
            ▼
┌───────────────────────┐
│ confirmar_comida.html │  el usuario REVISA y CORRIGE  ← nada guardado aún
└───────────┬───────────┘
            ▼
┌───────────────────────┐
│ comidas.guardar_comida│  por cada fila llama a...
└───────────┬───────────┘
            ▼
┌───────────────────────┐
│ nutrition.calcular    │  convierte unidades y aplica
│                       │  valor_100 * cantidad / 100
└───────────┬───────────┘
            ▼
     RegistroComida + DetalleComida (con instantánea de los valores usados)
            ▼
     panel / historial / gráficos
```

Si la IA falla en el segundo paso, el usuario entra por
`views.comida_manual` y el recorrido continúa idéntico desde
`comidas.guardar_comida`.

---

## 3. Archivos principales

### `core/models.py`
Las cuatro entidades del dominio.

- **Recibe:** nada; define la estructura.
- **Relaciona:** `User 1—1 PerfilNutricional`, `User 1—N RegistroComida`,
  `RegistroComida 1—N DetalleComida`, `Alimento 1—N DetalleComida`.
- **Detalle importante:** `DetalleComida` guarda los campos `*_ref`, una
  instantánea de los valores por 100 que se aplicaron. Por eso corregir una
  ficha del catálogo **no altera el historial**.
- **Qué puedes cambiar:** añadir campos opcionales a `Alimento` o
  `PerfilNutricional`. Hazlo con `makemigrations`.
- **Qué NO cambies sin pensarlo:** el `on_delete=SET_NULL` de
  `DetalleComida.alimento`; borrar un alimento no debe borrar el historial.

### `core/services/nutrition.py`
El motor de cálculo. **El archivo más importante del proyecto.**

- **Recibe:** un `Alimento`, una cantidad y una unidad.
- **Procesa:** valida la cantidad, convierte a la base del alimento (g o ml),
  aplica la regla de tres y redondea a 1 decimal.
- **Devuelve:** un `ResultadoCalculo` con los cuatro nutrientes, o con
  `None` y un motivo si no se pudo calcular.
- **Cómo probarlo:** `python manage.py test core.tests.test_nutrition`
- **Qué puedes cambiar:** la política de redondeo (`DECIMALES`) o la
  estimación de aceite (`GRAMOS_ACEITE_POR_100G_FRITO`). Si cambias el
  redondeo, varias pruebas fallarán: es lo correcto, actualízalas a mano.

### `core/services/food_parser.py`
Traductor entre cómo habla la gente y cómo nombra las cosas el catálogo.

- **Recibe:** nombres y unidades en texto libre ("Coca-Cola", "gr", "fritas").
- **Devuelve:** el `Alimento` que corresponde, o `None`.
- **Qué puedes cambiar:** los diccionarios `SINONIMOS_*` del principio. Es el
  sitio natural para mejorar la cobertura regional (añadir "mute", "sancocho",
  "changua"…) sin tocar lógica.

### `core/services/ai_service.py`
Único punto del sistema que habla con una API externa.

- **Recibe:** el texto del usuario (máx. 500 caracteres).
- **Devuelve:** una lista de items validados.
- **Lanza:** `IANoConfigurada`, `IANoDisponible`, `RespuestaIAInvalida` o
  `TextoNoInterpretable`; todas traen `mensaje_usuario`.
- **Garantía:** `validar_respuesta()` descarta cualquier campo que no esté en
  el esquema. Aunque el modelo devuelva "calorías: 9999", se ignora.
- **Qué puedes cambiar:** `INSTRUCCIONES` (el prompt) y `OPENAI_MODEL`.

### `core/services/comidas.py`
Pegamento entre las tres piezas anteriores y la base de datos.

- **Por qué existe:** para que la web y la API REST guarden exactamente igual.
  Si estuviera en `views.py`, la API tendría su propia copia y acabarían
  desincronizadas.

### `core/views.py` y `core/api.py`
Las páginas y los endpoints. No calculan: delegan.

- **Control de acceso:** `@login_required` + filtro `usuario=request.user` en
  cada consulta. Pedir la comida de otro devuelve 404.

---

## 4. Modelo de datos

```
        User (Django)
          │ 1
          ├──────────── 1  PerfilNutricional
          │                  meta_calorias_diaria
          │ 1
          │
          │ N
     RegistroComida
       fecha, descripcion, origen (ia|manual), confirmado
          │ 1
          │
          │ N
     DetalleComida ──── N ──── 1 ──── Alimento
       cantidad, unidad                nombre, categoria
       metodo_preparacion              calorias/proteinas/... por 100
       cantidad_base                   unidad_referencia (g|ml)
       calorias_ref, proteinas_ref…    metodo_preparacion
         (instantánea)                 gramos_por_unidad
       calorias, proteinas…            fuente, valores_aproximados
         (ya calculado)
```

### Tres decisiones de diseño que conviene saber explicar

**1. ¿Por qué los valores se guardan por 100 g y no por porción?**
Porque así vienen publicados en las tablas de composición de alimentos, y
porque una sola fórmula sirve para cualquier cantidad. La porción habitual se
guarda aparte, en `gramos_por_unidad`.

**2. ¿Por qué la instantánea en `DetalleComida`?**
Sin ella, corregir las calorías de la arepa cambiaría el historial de todos
los usuarios hacia atrás. Con ella, cada registro conserva lo que se aplicó
ese día.

**3. ¿Por qué `alimento` puede ser nulo?**
Porque "no sé cuántas calorías tiene esto" es una respuesta honesta y
"0 calorías" no lo es. El resumen diario informa de cuántos alimentos
quedaron sin datos en lugar de esconderlos.

---

## 5. Endpoints de la API

| Método | Ruta | Para qué |
|---|---|---|
| GET | `/api/alimentos/?buscar=` | Buscador del catálogo |
| GET, PATCH | `/api/perfil/` | Leer y cambiar la meta |
| POST | `/api/analizar/` | Texto → alimentos detectados (no guarda) |
| GET, POST | `/api/comidas/?fecha=` | Listar el día / crear comida |
| GET, PUT, DELETE | `/api/comidas/<id>/` | Ver, editar, borrar |
| GET | `/api/resumen/?fecha=` | Totales del día |
| GET | `/api/tendencia/?dias=7` | Serie para el gráfico |

Todos exigen sesión iniciada y filtran por el usuario autenticado.

---

## 6. Seguridad

| Medida | Dónde |
|---|---|
| Contraseñas con hash y validadores | `django.contrib.auth` (no hay sistema propio) |
| Protección CSRF | `{% csrf_token %}` en todos los formularios |
| Inyección SQL | Solo se usa el ORM; no hay SQL escrito a mano |
| Datos aislados por usuario | Filtro `usuario=request.user` en cada consulta |
| Rutas privadas | `@login_required` + permisos de DRF |
| Secretos | Variables de entorno; `.env` fuera del repositorio |
| Errores sin trazas internas | Mensajes legibles; el detalle va al log |
| Cabeceras seguras en producción | Bloque `if not DEBUG` de `settings.py` |

La prueba `SeparacionEntreUsuariosTests` comprueba expresamente que un usuario
no puede ver, editar ni borrar las comidas de otro.
