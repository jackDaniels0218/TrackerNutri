# Plan de desarrollo — metodología incremental

**Proyecto:** Tracker Nutricional Algorítmico para Dietas Regionales Colombianas
**Duración:** 2 semanas académicas (10 días hábiles)
**Equipo:** 4 personas

---

## 1. Por qué incremental

El modelo incremental construye el producto en entregas sucesivas. Cada
incremento atraviesa todas las fases (análisis, diseño, codificación y
pruebas) y termina en **software que funciona**, no en un documento.

Encaja con este proyecto por tres razones concretas:

1. **El riesgo está al principio.** Si el motor de cálculo está mal, todo lo
   demás da números incorrectos. Conviene construirlo y probarlo primero,
   antes de invertir tiempo en pantallas.
2. **La IA es la parte incierta.** Puede fallar la clave, la red o el formato
   de respuesta. Al aislarla en un incremento propio, el proyecto ya es
   entregable aunque la IA no funcione: queda el registro manual.
3. **Dos semanas no dan para un cascada.** Con un enfoque en cascada, los
   errores de los primeros días aparecerían al final, sin margen para
   corregirlos.

No se eligió Scrum completo porque dos semanas no justifican el ritual de
ceremonias; sí se toman de él dos prácticas útiles: reunión diaria corta y
revisión al cerrar cada incremento.

---

## 2. Equipo y roles

Cada persona tiene un rol principal, pero todas programan. El rol define
**quién decide** cuando hay dudas y **quién revisa** el código de esa zona.

| Rol | Responsabilidad principal | Zona del código |
|---|---|---|
| **P1 — Arquitecto / Backend** | Estructura del proyecto, modelos, migraciones, decisiones transversales | `config/`, `core/models.py`, `core/admin.py` |
| **P2 — Motor nutricional** | Fórmulas, conversión de unidades, redondeo, resumen diario | `core/services/nutrition.py`, `core/services/comidas.py` |
| **P3 — Integración de IA** | Servicio de IA, validación del JSON, emparejamiento con el catálogo | `core/services/ai_service.py`, `core/services/food_parser.py` |
| **P4 — Interfaz y frontend** | Plantillas, CSS, Chart.js, usabilidad en móvil | `templates/`, `static/` |

**Pruebas:** no hay un rol exclusivo de QA. Cada quien escribe las pruebas de
su zona (es lo que permite detectar los errores el mismo día), y se usa
**Codex** como revisor externo al cerrar cada incremento, para que una mirada
distinta busque lo que el autor no ve.

### Reglas de trabajo

- Una rama por incremento; se integra a `main` solo con las pruebas en verde.
- Nadie modifica la zona de otro sin avisar: se abre un *issue* o se pide el
  cambio.
- Reunión diaria de 10 minutos: qué hice, qué haré, qué me bloquea.
- Definición de terminado (DoD): código + pruebas que pasan + documentación
  mínima del módulo + revisión de otra persona.

---

## 3. Los cinco incrementos

Cada incremento deja el sistema en un estado ejecutable y demostrable.

### Incremento 1 — Estructura y base de datos (días 1–2)

**Objetivo:** que el proyecto arranque y los datos se puedan guardar.

| Tarea | Responsable |
|---|---|
| Crear el proyecto Django, `config/` y la app `core` | P1 |
| Definir los 4 modelos y sus relaciones | P1 con P2 |
| Migraciones iniciales y panel de administración | P1 |
| Catálogo inicial de alimentos colombianos (fixture) | P3 |
| Maqueta base de plantillas y CSS | P4 |

**Entregable:** `runserver` levanta, el admin muestra el catálogo con 22
alimentos.
**Riesgo cubierto:** un modelo de datos equivocado detectado el día 2 cuesta
horas; detectado el día 9, cuesta el proyecto.

---

### Incremento 2 — Motor nutricional (días 3–4)

**Objetivo:** calcular bien. Sin interfaz todavía.

| Tarea | Responsable |
|---|---|
| Fórmula por 100 g / 100 ml y política de redondeo | P2 |
| Conversión de unidades y equivalencias documentadas | P2 |
| Suma por comida y resumen diario | P2 |
| Pruebas unitarias del motor | P2 con P1 |
| Servicio de guardado de comidas (`comidas.py`) | P1 |

**Entregable:** pruebas del motor en verde, comprobadas contra cálculos hechos
a mano.
**Decisión tomada aquí:** lo que no se puede calcular vale `None`, nunca cero.

---

### Incremento 3 — Integración de IA (días 5–6)

**Objetivo:** interpretar texto libre, con salida digna cuando falle.

| Tarea | Responsable |
|---|---|
| Servicio de IA con esquema JSON estricto | P3 |
| Validación de la respuesta en el backend | P3 |
| Normalización y emparejamiento con el catálogo | P3 |
| Errores controlados: sin clave, sin red, respuesta inválida | P3 con P1 |
| Pruebas con respuestas simuladas (sin gastar créditos) | P3 |

**Entregable:** `analizar_texto()` devuelve items emparejados; si la IA falla,
lanza un error con mensaje para el usuario.
**Riesgo cubierto:** el proyecto deja de depender de que la IA funcione el día
de la sustentación.

---

### Incremento 4 — Interfaz e historial (días 7–8)

**Objetivo:** que todo lo anterior se pueda usar desde el navegador.

| Tarea | Responsable |
|---|---|
| Autenticación: registro, login, logout | P1 |
| Panel principal con indicadores y estado vacío | P4 |
| Flujo: texto → confirmación editable → guardado | P4 con P3 |
| Registro manual (alternativa sin IA) | P4 |
| Historial, detalle, edición y borrado | P1 con P4 |
| Gráficos con Chart.js | P4 |
| Endpoints REST | P1 |

**Entregable:** la aplicación completa, usable en móvil y escritorio.

---

### Incremento 5 — Pruebas, seguridad y entrega (días 9–10)

**Objetivo:** cerrar, no añadir.

| Tarea | Responsable |
|---|---|
| Completar la batería de pruebas (los 17 escenarios) | Todos |
| Verificar aislamiento entre usuarios | P1 |
| Revisión externa con Codex y corrección de hallazgos | Todos |
| README, documentación de arquitectura, `.env.example` | P1 y P3 |
| Datos de demostración y guion de la sustentación | P4 |

**Entregable:** suite de pruebas en verde, README que permite a otra persona
instalar el proyecto, demo preparada.

---

## 4. Calendario

| Día | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| **Inc. 1** Estructura | ██ | ██ | | | | | | | | |
| **Inc. 2** Motor | | | ██ | ██ | | | | | | |
| **Inc. 3** IA | | | | | ██ | ██ | | | | |
| **Inc. 4** Interfaz | | | | | | | ██ | ██ | | |
| **Inc. 5** Pruebas y entrega | | | | | | | | | ██ | ██ |

Las pruebas no son una fase final: cada incremento incluye las suyas. El
incremento 5 es para cerrar huecos y revisar, no para empezar a probar.

---

## 5. Riesgos y qué se hizo con ellos

| Riesgo | Probabilidad | Impacto | Mitigación aplicada |
|---|---|---|---|
| La API de IA falla o no hay clave | Alta | Alto | Registro manual equivalente; errores controlados; pruebas simuladas |
| Valores nutricionales imprecisos | Alta | Medio | Campos `fuente` y `valores_aproximados`; avisos en la interfaz; se declara la limitación |
| El modelo devuelve JSON inválido | Media | Alto | Esquema estricto + validación propia en el backend |
| Cantidades ambiguas ("una porción") | Alta | Medio | `gramos_por_unidad` documentado; si falta, se pide confirmación |
| Un usuario ve datos de otro | Baja | Muy alto | Filtro por usuario en todas las consultas + pruebas específicas |
| Dos personas tocan el mismo archivo | Media | Bajo | Reparto por zonas y ramas por incremento |

---

## 6. Trazabilidad: requisito → incremento → prueba

| # | Funcionalidad obligatoria | Incremento | Prueba |
|---|---|---|---|
| 1 | Registro, inicio y cierre de sesión | 4 | `RegistroEInicioDeSesionTests` |
| 2 | Perfil nutricional | 1, 4 | `PerfilTests` |
| 3 | Meta diaria de calorías | 2, 4 | `PerfilTests`, `ResumenDiarioTests` |
| 4 | Registro por texto libre | 3, 4 | `LlamadaSimuladaTests` |
| 5 | Identificación por IA | 3 | `test_flujo_completo_con_respuesta_valida` |
| 6 | Confirmación y edición | 4 | `CicloDeVidaDeComidasTests` |
| 7 | Cálculo de nutrientes | 2 | `CalculoPorCantidadTests` |
| 8 | Catálogo de alimentos | 1 | `BusquedaEnCatalogoTests` |
| 9 | Historial por fecha | 4 | `EstadosVaciosTests`, vista `historial` |
| 10 | Resumen diario | 2 | `ResumenDiarioTests` |
| 11 | Gráficos | 4 | `DatosDeLosGraficosTests` |
| 12 | Registro manual alternativo | 4 | `RegistroManualTests` |
| 13 | Pruebas y documentación | 5 | Toda la suite + este documento |

---

## 7. Qué se dejó fuera, a propósito

App móvil nativa, reconocimiento por fotografía, modelo de IA propio,
integración con relojes, pagos, recomendaciones médicas, planes clínicos,
predicción de peso, algoritmos de absorción de aceite y sincronización con
plataformas de salud.

No es falta de tiempo: son funcionalidades que no aportan al objetivo de
demostrar un MVP correcto y defendible. Añadirlas a medias habría restado
calidad a lo que sí se entrega.
