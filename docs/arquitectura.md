# Arquitectura de NutriRegional

## 1. Principio rector

> **La IA interpreta, Python calcula.**

El SRS exige que los cálculos nutricionales los haga un motor determinista
sobre un catálogo curado. Por eso el sistema separa tres responsabilidades:

| Responsabilidad | Quién la tiene | Por qué |
|---|---|---|
| Entender el texto | Léxico regional → similitud → semántica → IA (opcional) | El léxico es gratis, rápido y explicable; la IA solo cubre lo que el léxico no reconoce |
| Saber qué contiene cada alimento | Catálogo curado y versionado | Fuente documentada, validación de Atwater, historial de cambios |
| Calcular | `core/services/calculo.py` y `aceite.py` | Determinista: la misma entrada da siempre el mismo resultado, con su desglose |

La respuesta de la IA se valida con un esquema JSON estricto que **no tiene
campos de energía ni nutrientes**: aunque el modelo los invente, no pasan.

## 2. Capas

```
Navegador (plantillas + Chart.js)       Cliente móvil futuro
            │                                    │
     core/views/  (por rol)              core/api/  (REST v1, OpenAPI)
            │                                    │
            └──────────────┬─────────────────────┘
                           │   sin lógica de negocio en las vistas
                    core/services/
   interpretacion · calculo · aceite · comidas · metas · salvaguardas
   ia · curacion · reportes · notificaciones · cuentas · parametros · auditoria
                           │
                     core/models/   (ORM de Django)
                           │
                        SQLite  (PostgreSQL en producción)
```

- **Vistas y API** solo validan la entrada, verifican el rol y llaman a un
  servicio. Las dos interfaces comparten los mismos servicios: no hay dos
  implementaciones del mismo cálculo.
- **Servicios** contienen todas las reglas del SRS y se prueban sin HTTP.
- **Parámetros como datos** (RF11): umbrales, factores, límites de seguridad,
  costos y modelo de IA están en la tabla `Parametro` y se leen con
  `parametro("clave")`. Cambiar un valor no exige desplegar código, y cada
  cambio queda en la bitácora.

## 3. Recorrido de una comida (RF13 → RF14 → RF15 → RF7)

1. **Segmentar** la frase por conectores («y», «con», comas), salvo que el
   conjunto sea un nombre conocido («arroz con pollo»).
2. **Extraer** cantidades («200 g», «dos», «un vaso») y método de cocción
   («frita», «asada», «al ajillo»).
3. **Resolver** cada fragmento contra el catálogo en cascada:
   léxico exacto → similitud de texto (errores como «aripa») → coincidencia
   semántica → IA (solo los fragmentos sin resolver, con autorización y dentro
   del presupuesto) → **pendiente** (va a la bandeja del Curador; nunca se
   inventa un alimento).
4. **Método**: explícito, implícito en la preparación («mojarra frita»), por
   defecto del alimento o pregunta de aclaración.
5. **Cantidad**: gramos, medida casera del catálogo o porción por defecto.
6. **Confianza** = resolución × cantidad × método. Bajo el umbral
   (`umbral_confianza`) se hacen como máximo dos preguntas con opciones
   tocables, priorizando lo que más energía aporta.
7. **Calcular**: las preparaciones se deconstruyen en sus componentes, cada uno
   con su método (factor de agua, grasa que gotea, aceite absorbido según la
   matriz). El resultado incluye rango mínimo–máximo y el desglose línea por
   línea, que se guarda congelado en `ItemComida.detalle_calculo`.
8. **Confirmar**: la comida queda *interpretada* hasta que la persona la
   confirma; solo entonces cuenta en los totales. Cada comida guarda la versión
   del motor, del catálogo y de la plantilla de IA usadas.

## 4. Metas y salvaguardas (RF8, RF16, RF17)

- **Meta inicial**: Mifflin-St Jeor × factor de actividad − déficit del ritmo
  (10 % lento, 20 % moderado), nunca por debajo del piso (1200 / 1500 kcal) ni
  por encima del déficit máximo (25 %). La explicación paso a paso se guarda
  con la meta.
- **Ajuste semanal**: con al menos 5 días marcados como completos y 2 pesajes,
  se estima el gasto real (ingesta media − cambio del peso tendencial × 7700
  kcal/kg), se suaviza con el anterior, se limita a ±150 kcal o 10 % y queda
  **revertible 48 horas**.
- **Elegibilidad**: menores de edad, gestantes o lactantes y quien declare una
  condición que requiere acompañamiento reciben metas informativas, sin
  déficit.
- **Riesgos**: días completos seguidos bajo el piso o pérdida mayor al 1 %
  semanal dos semanas seguidas generan un aviso amable con el contacto de
  apoyo y detienen las reducciones.
- **Lenguaje**: una prueba revisa que ninguna plantilla use palabras como
  «malo», «trampa» o «pecado».

## 5. Catálogo y mejora continua (RF3–RF6, RF19)

- Todo cambio del Curador queda en una **versión en borrador** con su valor
  anterior y el nuevo (`HistorialCatalogo`) y se puede revertir.
- **Publicar** una versión ejecuta el conjunto de 200 frases de referencia; si
  la identificación o el método de cocción bajan de los umbrales, o empeoran
  frente a la versión publicada, la publicación se bloquea.
- Los términos no reconocidos llegan a la bandeja ordenados por frecuencia,
  sin datos de quién los escribió.

## 6. Seguridad y datos personales (RNF26, RNF27, RNF28)

| Medida | Dónde |
|---|---|
| Rol verificado en el servidor en cada petición | `core/views/utilidades.py` (`solo_usuario`, `solo_curador`, `solo_admin`) |
| Cada consulta del Usuario filtra por su cuenta: lo ajeno da 404 | vistas y API |
| Bloqueo tras 5 intentos fallidos durante 15 minutos | `core/forms.py` (`IngresoForm`), `core/signals.py` |
| Sesión de 60 minutos renovable; cerrar sesión en todos los dispositivos | `config/settings.py`, `services/cuentas.py` |
| Cuenta bloqueada o inactiva: su sesión se cierra en la siguiente petición | `core/middleware.py` |
| Autorizaciones de datos y de IA separadas, revocables y con historial de solo inserción | `Consentimiento` |
| Exportar todos los datos y suprimir la cuenta | `privacidad/` |
| El Administrador ve datos individuales solo con autorización temporal del titular, y queda registrado | `cuenta_soporte` |
| Bitácora de solo inserción | `Bitacora.save()` / `delete()` |
| Clave de IA solo en variables de entorno, nunca en el código ni en el cliente | `.env` |
| CSRF, ORM sin SQL manual, cookies seguras con `DEBUG=False` | Django |

## 7. Disponibilidad y costos de la IA (RNF32, RNF33)

- Si la IA no está configurada, no hay autorización, se agotó el límite diario
  o el presupuesto, o el proveedor falla, la interpretación sigue con reglas y
  la persona ve un aviso; el registro manual está siempre disponible.
- Caché de interpretaciones por fragmento normalizado, límite diario por
  usuario, presupuesto mensual con alerta al 80 % y registro de tokens, costo,
  latencia y errores (`UsoIA`).
- El proveedor es intercambiable (`ia_proveedor`): **openai**; **compatible**,
  cualquier servicio con la API de OpenAI y nivel gratuito (Groq, OpenRouter,
  Google AI Studio, Cerebras, Mistral…) con su propia clave
  `IA_COMPATIBLE_API_KEY`; **local** (Ollama, LM Studio), que no recibe
  ninguna clave; o **ninguno**. Si el modelo no admite el esquema estricto se
  pide JSON simple y la respuesta pasa por la misma validación.

## 8. API REST v1

Autenticación por sesión; solo el rol Usuario. Esquema en `/api/v1/esquema/`.

| Método y ruta | Uso |
|---|---|
| `GET /api/v1/perfil/` | Perfil y meta vigente |
| `GET /api/v1/alimentos/?buscar=`, `GET /api/v1/preparaciones/?buscar=` | Búsqueda en el catálogo |
| `POST /api/v1/interpretar/` | Interpreta texto libre y crea la comida sin confirmar |
| `GET/POST /api/v1/comidas/` | Comidas del día · registro manual idempotente |
| `GET/DELETE /api/v1/comidas/<id>/`, `POST .../confirmar/` | Detalle, baja lógica, confirmación |
| `GET /api/v1/resumen/`, `GET /api/v1/series/?dias=` | Totales del día y series para gráficos |
| `GET/POST /api/v1/pesajes/`, `GET /api/v1/metas/`, `GET /api/v1/notificaciones/` | Seguimiento |

## 9. Modelo de datos

El detalle de cada tabla está en [diccionario_datos.md](diccionario_datos.md).
Decisiones que conviene saber explicar:

1. **Valores congelados**: cada ítem guarda sus nutrientes y su desglose. Si el
   Curador corrige el catálogo, el historial del usuario no cambia en silencio.
2. **Baja lógica**: una comida eliminada pasa a *descartada*; deja de contar
   pero se conserva para auditoría.
3. **Una sola meta vigente** por usuario (restricción única condicional) y un
   historial que no se borra.
4. **Nulo no es cero**: un nutriente desconocido queda vacío; el sistema avisa
   que el total puede estar incompleto en lugar de sumar cero.
