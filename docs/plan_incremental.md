# Plan de desarrollo — metodología incremental

**Proyecto:** NutriRegional — Tracker nutricional algorítmico para dietas regionales
**Duración:** 2 semanas académicas (10 días hábiles) · **Equipo:** 4 personas
**Base:** SRS *Requerimientos NutriRegional V1* (36 actividades: 22 funcionales y 14 no funcionales)

---

## 1. Por qué incremental

Cada incremento recorre análisis, diseño, código y pruebas, y termina en
software que se puede demostrar. Encaja con este proyecto porque:

1. **El riesgo técnico está en el motor.** Si el cálculo o la interpretación
   fallan, todo lo demás muestra números equivocados: se construyen primero.
2. **La IA es la parte incierta** (clave, saldo, red, formato). Va en su propio
   incremento y el sistema es entregable sin ella: léxico regional y registro
   manual.
3. **Dos semanas no dan para cascada**: los errores del día 2 aparecerían el
   día 10.

De Scrum se toman dos prácticas: reunión diaria de 10 minutos y revisión al
cerrar cada incremento contra la página `/requerimientos/`.

## 2. Equipo y zonas

| Rol | Responsabilidad | Zona del código | Actividades del SRS |
|---|---|---|---|
| **P1 — Arquitectura y cuentas** | Modelos, migraciones, roles, seguridad, auditoría | `core/models/`, `services/cuentas.py`, `auditoria.py`, `middleware.py` | 1, 2, 11, 12, 22 |
| **P2 — Motor nutricional** | Cálculo, aceite, metas, salvaguardas | `services/calculo.py`, `aceite.py`, `metas.py`, `salvaguardas.py` | 8, 9, 14, 15, 16, 17 |
| **P3 — Catálogo, interpretación e IA** | Catálogo inicial, léxico, NLP, IA, curación | `core/datos/`, `services/interpretacion.py`, `ia.py`, `curacion.py` | 3, 4, 5, 6, 10, 13, 19, 21 |
| **P4 — Interfaz y reportes** | Plantillas por rol, gráficos, notificaciones, API | `templates/`, `static/`, `core/views/`, `core/api/`, `reportes.py`, `notificaciones.py` | 7, 18, 20 |

Cada persona escribe las pruebas de su zona (`core/tests/test_rfXX_*.py`).
Codex se usa como revisor externo al cerrar cada incremento.

**Definición de terminado:** código + pruebas en verde + la actividad aparece
en `core/requerimientos.py` con pantalla, demostración y prueba + revisión de
otra persona.

## 3. Incrementos

### Incremento 1 — Base de datos y cuentas (días 1–2)

| Entregable | Actividades |
|---|---|
| Modelos de las cinco áreas y migración inicial | 22 (integridad) |
| Registro en 3 pasos, autorizaciones separadas, ingreso con bloqueo, recuperación de contraseña | 1, 12 |
| Perfil con rangos del SRS, edad mínima e IMC del peso meta | 2 |
| Parámetros del sistema como datos | 11 |

**Demostrable:** crear una cuenta, completar el perfil y ver la meta inicial.

### Incremento 2 — Catálogo y motor de cálculo (días 3–4)

| Entregable | Actividades |
|---|---|
| Catálogo inicial: 153 alimentos, 67 preparaciones, 11 métodos, coeficientes de absorción | 3, 4, 5 |
| Cálculo con deconstrucción, factor de agua, grasa que gotea, rango y desglose | 14 |
| Calculadora de aceite por matriz, tamaño, tiempo y escurrido | 15 |
| Metas: Mifflin-St Jeor, déficit por ritmo, pisos, elegibilidad | 8, 16, 17 |

**Demostrable:** la calculadora de aceite reproduce el ejemplo del SRS
(65 g de plátano verde → 6,5 g de aceite).

### Incremento 3 — Interpretación de texto libre e IA (días 5–6)

| Entregable | Actividades |
|---|---|
| Léxico regional y porciones caseras (564 términos, 293 porciones) | 6 |
| Cascada léxico → similitud → semántica → IA → pendiente; confianza y preguntas | 13 |
| Proveedor de IA con esquema estricto, caché, límites, presupuesto y degradación | 21 |
| 200 frases de referencia y pruebas de exactitud | 24 |

**Demostrable:** «chicarron con aripa» se entiende; sin clave de IA todo sigue
funcionando.

### Incremento 4 — Registro, seguimiento y curación (días 7–8)

| Entregable | Actividades |
|---|---|
| Registrar, confirmar, editar, favoritas, eliminar (baja lógica), búsqueda manual | 7 |
| Pesajes con peso tendencial; ajuste semanal revertible; alertas de riesgo | 9, 16, 17 |
| Correcciones aplicadas al instante y revisadas por el Curador | 10 |
| Bandeja, versiones, historial, reversión y publicación con exactitud | 19 |

**Demostrable:** la usuaria demo ve su ajuste semanal (−150 kcal) y lo revierte.

### Incremento 5 — Reportes, notificaciones, administración y entrega (días 9–10)

| Entregable | Actividades |
|---|---|
| Gráficos 7/30/90 días, CSV, informe imprimible, panel agregado | 18 |
| Recordatorios, resumen semanal, avisos de curación y de presupuesto | 20 |
| Administración de cuentas, soporte autorizado, auditoría, procesos, respaldo | 1, 22, 34, 36 |
| API REST v1 con OpenAPI; pruebas por requerimiento; trazabilidad y documentación | 30, 35 |

**Demostrable:** recorrido completo con los tres roles siguiendo el
[guion](guion_sustentacion.md).

## 4. Calendario

| Día | P1 | P2 | P3 | P4 |
|---|---|---|---|---|
| 1 | Modelos y migración | Fórmulas de cálculo | Alimentos base | Plantilla base y estilos |
| 2 | Registro, ingreso, perfil | Pruebas del cálculo | Preparaciones y métodos | Pantallas de registro |
| 3 | Parámetros y bitácora | Absorción de aceite | Coeficientes y porciones | Calculadora de aceite |
| 4 | Roles y middleware | Metas y salvaguardas | Léxico | Pantalla de metas |
| 5 | Consentimientos y privacidad | Rangos y confianza | Interpretación por reglas | Registro por texto |
| 6 | Control de costo de IA | Pruebas de metas | Integración con IA, frases | Confirmación y aclaración |
| 7 | Exportar y suprimir datos | Ajuste semanal | Correcciones | Historial y favoritas |
| 8 | Cuentas internas y soporte | Alertas de riesgo | Curación y versiones | Peso y gráficos |
| 9 | Auditoría y respaldo | Pruebas integradas | Exactitud y bandeja | Reportes y notificaciones |
| 10 | Revisión de seguridad | Datos de demostración | Ajuste del léxico | Trazabilidad y guion |

## 5. Riesgos

| Riesgo | Qué se hizo |
|---|---|
| La IA falla, no hay saldo o no hay red el día de la sustentación | Reglas y registro manual siempre disponibles; avisos claros; `probar_ia` para verificar antes |
| Cálculos incorrectos | Motor determinista con pruebas contra cálculos a mano y el ejemplo del SRS |
| Catálogo sin validar | Fuente declarada por registro, verificación del Curador y desviación documentada |
| Metas inseguras | Pisos, déficit máximo, elegibilidad y límites del ajuste semanal como parámetros probados |
| Documentación desincronizada | `core/requerimientos.py` como única fuente; `generar_trazabilidad` y una prueba que verifica el mapa |

## 6. Trazabilidad

El detalle actividad → pantalla → modelo → servicio → prueba está en
[trazabilidad_srs.md](trazabilidad_srs.md) (generado desde el código) y en la
página `/requerimientos/` de la aplicación.
