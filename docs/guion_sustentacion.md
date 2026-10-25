# Guion de sustentación (≈ 20 minutos)

Recorrido que muestra **explícitamente** cada actividad del SRS. Cada paso
indica la actividad (RF/RNF) que se está demostrando para decirla en voz alta.

## Preparación (antes de entrar)

```bash
python manage.py migrate
python manage.py inicializar_sistema
python manage.py cargar_demo        # rehace las cuentas demo con datos frescos
python manage.py test               # mostrar las pruebas en verde si lo piden
python manage.py runserver
```

- Contraseña de todas las cuentas demo: `NutriDemo2026`.
- Si se va a mostrar la IA externa: `.env` con `OPENAI_API_KEY` y
  `python manage.py probar_ia` cinco minutos antes. Si falla, no pasa nada: el
  paso 2.3 muestra justamente la degradación.
- Tener abiertas dos ventanas: una normal y una privada (para dos roles a la vez).

---

## 1. Presentación y mapa de requerimientos (2 min)

1. Abrir `/requerimientos/` sin iniciar sesión: «Cada una de las 36 actividades
   del SRS está aquí, con el rol que la demuestra, cómo mostrarla y su prueba
   automatizada». Señalar la tabla de no funcionales con su estado honesto.
2. Pie de página: aviso de que no es un servicio médico (**RF12**, **RF17**).

## 2. Usuario (9 min)

### 2.1 Registro (RF1, RF2, RF12, RF16)
1. *Crear cuenta*: barra de 3 pasos, autorización de datos **separada** de la de
   IA (RNF27). Intentar sin aceptar datos → no deja.
2. Paso 2, perfil: poner una fecha de nacimiento de 16 años → error (RF2, RF17).
   Corregir.
3. Paso 3: la meta inicial con la **explicación paso a paso** (Mifflin-St Jeor,
   factor de actividad, déficit, piso) (RF16, RNF25).

### 2.2 Panel del día (RF7, RF17, RF18)
Entrar como `usuaria@nutriregional.demo`: consumido, meta, restante, macros,
aceite estimado, gráfico de 7 días. Botón *Marcar día como completo*: «solo los
días completos alimentan las alertas y el ajuste semanal».

### 2.3 Registro por texto libre (RF13, RF14, RF15, RF21)
1. *Registrar* → escribir **«una arepa y una gaseosa»** → el sistema pregunta
   cómo estaba la arepa y qué presentación de gaseosa (máximo dos preguntas).
2. Pantalla de confirmación: cada componente con cantidad, método, energía,
   **rango** y **confianza**; todo editable. «Nada cuenta hasta confirmar.»
3. Otra frase: **«chicarron con aripa»** → entiende los errores de ortografía.
4. Otra: **«una bandeja paisa»** → abrir el detalle y desplegar el cálculo:
   cada ingrediente con su método, agua, grasa que gotea y aceite (RF14).
5. Frase con algo desconocido: **«un plato de chontaduro»** → queda como
   pendiente; no se inventa. (Se resolverá como Curador en 3.1.)
6. Si hay IA: una frase rara la resuelve la IA y se ve «Identificado con ayuda
   de la IA». Si no hay: aparece el aviso y todo sigue con reglas (RNF32).

### 2.4 Búsqueda manual, favoritas y baja lógica (RF7)
*Prefiero buscar en el catálogo* → agregar dos filas → guardar. En el detalle:
marcar como favorita → *Favoritas* → repetir. Eliminar una comida → deja de
contar (baja lógica).

### 2.5 Corrección (RF10)
En el detalle de una comida → *Reportar un error* → cantidad «200 g» → se
corrige **al instante** en la comida y queda pendiente para el Curador.

### 2.6 Peso, metas y ajuste semanal (RF8, RF9, RF16)
1. *Peso*: registrar un valor 4 kg distinto al anterior → advierte sin
   bloquear. Gráfico con el peso tendencial (media móvil).
2. *Meta*: el ajuste automático de la semana (1778 → 1628 kcal) con su
   explicación y el botón **Revertir** (48 h). Historial de metas con origen.
3. Proponer una meta de 1000 kcal → rechazada por los límites de seguridad.

### 2.7 Calculadora de aceite (RF15)
*Más → Calculadora de aceite*: plátano verde, 65 g, fritura profunda →
**6,5 g de aceite (3,3–9,8 g), 58,5 kcal** (el ejemplo del SRS). Cambiar a
pieza pequeña y escurrido en papel → cambia el rango.

### 2.8 Reportes, privacidad y notificaciones (RF18, RF20, RNF27)
1. *Reportes*: cambiar 7 / 30 / 90 días; exportar CSV; informe para imprimir.
2. *Privacidad*: ocultar cifras → el panel muestra solo la forma de la
   tendencia; pausar seguimiento; retirar la autorización de IA; exportar mis
   datos (JSON); eliminar cuenta (no ejecutar).
3. *Recordatorios*: configurar tres horas.

### 2.9 Salvaguardas (RF17)
Entrar como `gestante@nutriregional.demo`: «Tu seguimiento es informativo: no
se aplica déficit». En *Meta*, intentar bajar la meta → no se permite.

## 3. Curador (4 min)

Entrar como `curador@nutriregional.demo`.

1. **Bandeja** (RF19, RF6, RF10): términos no reconocidos por frecuencia
   (aparece «chontaduro» del paso 2.3) → *Agregar* apuntando a un alimento.
   Volver como usuaria y escribir «chontaduro»: ahora se reconoce.
   Revisar la corrección del paso 2.5 → aceptar → la usuaria recibe la
   respuesta en sus notificaciones.
2. **Alimentos** (RF3): editar uno con energía incoherente → la validación de
   Atwater lo impide.
3. **Preparaciones** (RF4): la bandeja paisa y sus componentes, con aviso si el
   peso de la porción no cuadra.
4. **Cocción** (RF5): cambiar el coeficiente típico de masa de maíz.
5. **Versiones** (RF19, RF22): el cambio con valor anterior y nuevo →
   *Revertir*. *Revisar y publicar* → corre las 200 frases; si la exactitud
   baja, la publicación se bloquea.
6. **Exactitud** (RNF24): 98,9 % de identificación y de método, con los fallos
   a la vista.
7. **Parámetros** (RF11): el Curador solo ve los nutricionales.

## 4. Administrador (3 min)

Entrar como `admin@nutriregional.demo`.

1. **Cuentas** (RF1): crear una cuenta de Curador; **bloquear** a la usuaria
   demo y, en la otra ventana, ver que su sesión se cierra. Reactivarla.
   *Soporte*: sin autorización del titular no se ven sus datos (RNF27).
2. **Parámetros** (RF11): cambiar `umbral_confianza` de 0.6 a 0.3 → la frase
   «una arepa y una gaseosa» ya no pregunta. Volver a 0.6. Todo queda en la
   bitácora.
3. **IA y costos** (RF21, RNF33): consumo, tokens, costo, caché, errores,
   presupuesto, plantillas. Cambiar `ia_proveedor` a `ninguno` → la
   interpretación sigue con reglas.
4. **Auditoría** (RF22): filtrar por acción (ingresos, cambios de parámetros,
   publicaciones, cuentas).
5. **Procesos** (RF16, RF20, RNF34): ejecutar recordatorios, ajuste semanal,
   exactitud y respaldo.
6. **Indicadores** (RF18): panel agregado sin datos personales.

## 5. Cierre (2 min)

- `python manage.py test`: 177 pruebas en verde, una por grupo de
  requerimientos, más la prueba que verifica que cada pantalla del mapa existe
  y abre con su rol.
- API REST v1 con esquema OpenAPI en `/api/v1/esquema/`, lista para la app
  móvil.
- [desviaciones.md](desviaciones.md): web en lugar de app nativa, SQLite en
  lugar de PostgreSQL, catálogo y frases pendientes de validación por un
  nutricionista — cada una con su camino a producción.

## Preguntas probables

| Pregunta | Respuesta corta |
|---|---|
| ¿Y si la IA se equivoca de calorías? | La IA no da calorías: el esquema no tiene esos campos y el cálculo lo hace el motor con el catálogo |
| ¿De dónde salen los valores? | De la TCAC del ICBF, USDA o etiquetas, con la fuente en cada registro; pendientes de validación profesional |
| ¿Cómo evitan metas peligrosas? | Pisos de 1200/1500 kcal, déficit máximo del 25 %, ajuste máximo de 150 kcal/semana, elegibilidad y alertas de riesgo, todos parametrizables |
| ¿Qué pasa si cambia el catálogo? | Las comidas guardan sus valores y su desglose congelados y la versión del catálogo que usaron |
| ¿Cómo saben que la interpretación funciona? | 200 frases de referencia que se ejecutan antes de cada publicación y bloquean si la exactitud baja |
| ¿Por qué web y no app? | Ver desviación 1: misma lógica y API listas para el cliente móvil |
