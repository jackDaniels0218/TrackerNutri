# Trazabilidad SRS → prototipo

> Generado con `python manage.py generar_trazabilidad` a partir de `core/requerimientos.py`.
> No editar a mano. La prueba `core/tests/test_trazabilidad.py` verifica que todas las pantallas
> y pruebas mencionadas existen y que cada pantalla abre con el rol que la demuestra.

Cuentas de demostración (`python manage.py cargar_demo`), contraseña `NutriDemo2026`:
`usuaria@nutriregional.demo`, `gestante@nutriregional.demo`, `curador@nutriregional.demo`,
`admin@nutriregional.demo`.

## Resumen de requerimientos funcionales

| RF | Actividad | Roles | Pantallas | Pruebas |
|---|---|---|---|---|
| 1 | CRUD Usuarios | Usuario, Administrador | [Crear cuenta](/registro/), [Editar datos de contacto](/cuenta/), [Eliminar cuenta](/privacidad/), [Administrar cuentas](/administracion/cuentas/) | `test_rf01_rf12_cuentas` |
| 2 | CRUD Perfil nutricional | Usuario | [Paso 2 del registro](/registro/perfil/), [Editar perfil](/perfil/) | `test_rf02_rf08_rf16_metas` |
| 3 | CRUD Alimentos base | Curador, Usuario | [Catálogo (Curador)](/catalogo/alimentos/), [Alimentos personales (Usuario)](/mis-alimentos/) | `test_rf03_rf06_catalogo` |
| 4 | CRUD Preparaciones regionales y componentes | Curador | [Preparaciones y su deconstrucción](/catalogo/preparaciones/) | `test_rf03_rf06_catalogo`, `test_rf14_rf15_calculo` |
| 5 | CRUD Métodos de cocción y absorción de aceite | Curador | [Métodos de cocción](/catalogo/metodos/), [Coeficientes de absorción](/catalogo/coeficientes/) | `test_rf03_rf06_catalogo`, `test_rf14_rf15_calculo` |
| 6 | CRUD Léxico y porciones caseras | Curador | [Léxico regional](/catalogo/lexico/), [Porciones caseras](/catalogo/porciones/) | `test_rf03_rf06_catalogo`, `test_rf13_interpretacion` |
| 7 | CRUD Registro de comidas | Usuario | [Registrar por texto](/comidas/nueva/), [Búsqueda manual](/comidas/manual/), [Historial](/comidas/historial/), [Favoritas](/comidas/favoritas/) | `test_rf07_rf10_comidas` |
| 8 | CRUD Metas calóricas y de macronutrientes | Usuario | [Meta vigente e historial](/metas/) | `test_rf02_rf08_rf16_metas` |
| 9 | CRUD Seguimiento de peso | Usuario | [Pesajes y peso tendencial](/peso/) | `test_rf09_rf17_peso_salvaguardas` |
| 10 | CRUD Correcciones y retroalimentación | Usuario, Curador | [Mis correcciones (Usuario)](/correcciones/), [Bandeja (Curador)](/curacion/) | `test_rf07_rf10_comidas`, `test_rf19_curacion` |
| 11 | CRUD Parámetros del sistema | Administrador, Curador | [Parámetros](/administracion/parametros/) | `test_rf11_rf21_rf22_sistema` |
| 12 | Módulo Acceso y registro | Usuario | [Registro en 3 pasos](/registro/), [Ingreso](/cuentas/login/), [Recuperar contraseña](/cuentas/password_reset/), [Aviso de no ser servicio médico](/legal/aviso-medico/) | `test_rf01_rf12_cuentas` |
| 13 | Módulo Interpretación de texto libre (NLP) | Usuario | [Escribir lo que comiste](/comidas/nueva/) | `test_rf13_interpretacion` |
| 14 | Módulo Deconstrucción de recetas y cálculo nutricional | Usuario | [Detalle de cada comida con su desglose](/comidas/historial/) | `test_rf14_rf15_calculo` |
| 15 | Módulo Calculadora dinámica de absorción de aceite | Usuario | [Calculadora de aceite](/herramientas/aceite/) | `test_rf14_rf15_calculo` |
| 16 | Módulo Cálculo de metas y ajuste automático semanal | Usuario, Administrador | [Explicación de la meta inicial](/registro/meta/), [Ajuste semanal y reversión](/metas/), [Ejecutar el proceso semanal (Administrador)](/administracion/procesos/) | `test_rf02_rf08_rf16_metas` |
| 17 | Módulo Salvaguardas de salud y seguridad del usuario | Usuario | [Avisos de cuidado y día completo](/panel/), [Ocultar cifras y pausar seguimiento](/privacidad/) | `test_rf09_rf17_peso_salvaguardas` |
| 18 | Módulo Gráficos de tendencias y reportes | Usuario, Administrador, Curador | [Gráficos 7/30/90 días](/reportes/), [Exportar CSV](/reportes/exportar.csv), [Panel agregado](/curacion/indicadores/) | `test_rf18_rf20_reportes_notificaciones` |
| 19 | Módulo Curación del catálogo y mejora continua | Curador | [Bandeja de pendientes](/curacion/), [Versiones e historial](/curacion/versiones/), [Pruebas de exactitud](/curacion/exactitud/) | `test_rf19_curacion` |
| 20 | Módulo Notificaciones y recordatorios | Usuario, Curador, Administrador | [Notificaciones](/notificaciones/), [Configurar recordatorios](/recordatorios/) | `test_rf18_rf20_reportes_notificaciones` |
| 21 | Módulo Integración con el proveedor de IA | Administrador | [Uso, costo, plantillas y proveedor](/administracion/ia/) | `test_rf11_rf21_rf22_sistema` |
| 22 | Módulo Trazabilidad y auditoría | Administrador, Curador | [Bitácora, consentimientos y metas](/administracion/auditoria/), [Historial del catálogo](/curacion/versiones/) | `test_rf11_rf21_rf22_sistema` |

## Detalle por requerimiento

### RF1 · CRUD Usuarios

- **Roles:** Usuario, Administrador
- **Pantallas:** Crear cuenta (`/registro/`); Editar datos de contacto (`/cuenta/`); Eliminar cuenta (`/privacidad/`); Administrar cuentas (`/administracion/cuentas/`)
- **Modelos:** User (Django), Cuenta, Consentimiento
- **Servicios (`core/services/`):** cuentas.py
- **Pruebas (`core/tests/`):** test_rf01_rf12_cuentas
- **Cómo demostrarlo:** Crear una cuenta nueva; luego, como Administrador, bloquearla y ver que su sesión se cierra.

### RF2 · CRUD Perfil nutricional

- **Roles:** Usuario
- **Pantallas:** Paso 2 del registro (`/registro/perfil/`); Editar perfil (`/perfil/`)
- **Modelos:** PerfilNutricional
- **Servicios (`core/services/`):** cuentas.guardar_perfil
- **Pruebas (`core/tests/`):** test_rf02_rf08_rf16_metas
- **Cómo demostrarlo:** Cambiar el nivel de actividad y ver que la meta se recalcula; intentar una fecha de nacimiento de menor de edad.

### RF3 · CRUD Alimentos base

- **Roles:** Curador, Usuario
- **Pantallas:** Catálogo (Curador) (`/catalogo/alimentos/`); Alimentos personales (Usuario) (`/mis-alimentos/`)
- **Modelos:** Alimento
- **Servicios (`core/services/`):** catalogo.py, curacion.registrar_cambio
- **Pruebas (`core/tests/`):** test_rf03_rf06_catalogo
- **Cómo demostrarlo:** Como Curador, editar un alimento con energía incoherente y ver la validación de Atwater. Como Usuario, crear un alimento personal.

### RF4 · CRUD Preparaciones regionales y componentes

- **Roles:** Curador
- **Pantallas:** Preparaciones y su deconstrucción (`/catalogo/preparaciones/`)
- **Modelos:** Preparacion, Componente
- **Servicios (`core/services/`):** catalogo.py
- **Pruebas (`core/tests/`):** test_rf03_rf06_catalogo, test_rf14_rf15_calculo
- **Cómo demostrarlo:** Abrir la bandeja paisa y ver sus diez ingredientes con su método propio y la validación de peso de la porción.

### RF5 · CRUD Métodos de cocción y absorción de aceite

- **Roles:** Curador
- **Pantallas:** Métodos de cocción (`/catalogo/metodos/`); Coeficientes de absorción (`/catalogo/coeficientes/`)
- **Modelos:** MetodoCoccion, CoeficienteAbsorcion
- **Servicios (`core/services/`):** aceite.py
- **Pruebas (`core/tests/`):** test_rf03_rf06_catalogo, test_rf14_rf15_calculo
- **Cómo demostrarlo:** Cambiar el coeficiente típico de masa de maíz y ver en el historial el valor anterior y el nuevo.

### RF6 · CRUD Léxico y porciones caseras

- **Roles:** Curador
- **Pantallas:** Léxico regional (`/catalogo/lexico/`); Porciones caseras (`/catalogo/porciones/`)
- **Modelos:** TerminoLexico, PorcionCasera, TerminoPendiente
- **Servicios (`core/services/`):** interpretacion.Lexico
- **Pruebas (`core/tests/`):** test_rf03_rf06_catalogo, test_rf13_interpretacion
- **Cómo demostrarlo:** Agregar el término «chontaduro» desde la bandeja de pendientes y ver que la próxima frase ya lo reconoce.

### RF7 · CRUD Registro de comidas

- **Roles:** Usuario
- **Pantallas:** Registrar por texto (`/comidas/nueva/`); Búsqueda manual (`/comidas/manual/`); Historial (`/comidas/historial/`); Favoritas (`/comidas/favoritas/`)
- **Modelos:** Comida, ItemComida
- **Servicios (`core/services/`):** comidas.py
- **Pruebas (`core/tests/`):** test_rf07_rf10_comidas
- **Cómo demostrarlo:** Registrar, editar un ítem (queda marcado como editado), marcar como favorita, repetirla y eliminarla (baja lógica).

### RF8 · CRUD Metas calóricas y de macronutrientes

- **Roles:** Usuario
- **Pantallas:** Meta vigente e historial (`/metas/`)
- **Modelos:** MetaCalorica
- **Servicios (`core/services/`):** metas.py
- **Pruebas (`core/tests/`):** test_rf02_rf08_rf16_metas
- **Cómo demostrarlo:** Ver el historial de metas con su origen y motivo; proponer una meta por debajo del piso y ver que se rechaza.

### RF9 · CRUD Seguimiento de peso

- **Roles:** Usuario
- **Pantallas:** Pesajes y peso tendencial (`/peso/`)
- **Modelos:** Pesaje
- **Servicios (`core/services/`):** salvaguardas.peso_tendencial
- **Pruebas (`core/tests/`):** test_rf09_rf17_peso_salvaguardas
- **Cómo demostrarlo:** Registrar un peso con 4 kg de diferencia respecto al anterior: se advierte sin bloquear. Ver la media móvil.

### RF10 · CRUD Correcciones y retroalimentación

- **Roles:** Usuario, Curador
- **Pantallas:** Mis correcciones (Usuario) (`/correcciones/`); Bandeja (Curador) (`/curacion/`)
- **Modelos:** Correccion
- **Servicios (`core/services/`):** curacion.crear_correccion, curacion.revisar_correccion
- **Pruebas (`core/tests/`):** test_rf07_rf10_comidas, test_rf19_curacion
- **Cómo demostrarlo:** Reportar que una cantidad estaba mal: se corrige al instante en la comida; el Curador la acepta y el usuario recibe la respuesta.

### RF11 · CRUD Parámetros del sistema

- **Roles:** Administrador, Curador
- **Pantallas:** Parámetros (`/administracion/parametros/`)
- **Modelos:** Parametro
- **Servicios (`core/services/`):** parametros.py
- **Pruebas (`core/tests/`):** test_rf11_rf21_rf22_sistema
- **Cómo demostrarlo:** Cambiar el umbral de confianza y ver que cambian las preguntas de aclaración. El Curador solo ve los nutricionales.

### RF12 · Módulo Acceso y registro

- **Roles:** Usuario
- **Pantallas:** Registro en 3 pasos (`/registro/`); Ingreso (`/cuentas/login/`); Recuperar contraseña (`/cuentas/password_reset/`); Aviso de no ser servicio médico (`/legal/aviso-medico/`)
- **Modelos:** Cuenta, Consentimiento
- **Servicios (`core/services/`):** cuentas.py, signals.py, middleware.py
- **Pruebas (`core/tests/`):** test_rf01_rf12_cuentas
- **Cómo demostrarlo:** Registro con barra de progreso y autorizaciones separadas; 5 intentos fallidos bloquean la cuenta; recuperación por correo (aparece en la consola).

### RF13 · Módulo Interpretación de texto libre (NLP)

- **Roles:** Usuario
- **Pantallas:** Escribir lo que comiste (`/comidas/nueva/`)
- **Modelos:** TerminoLexico, TerminoPendiente
- **Servicios (`core/services/`):** interpretacion.py, ia.py
- **Pruebas (`core/tests/`):** test_rf13_interpretacion
- **Cómo demostrarlo:** Escribir «una arepa y una gaseosa»: el sistema pregunta cómo estaba la arepa y qué presentación de gaseosa. Probar errores como «chicarron con aripa».

### RF14 · Módulo Deconstrucción de recetas y cálculo nutricional

- **Roles:** Usuario
- **Pantallas:** Detalle de cada comida con su desglose (`/comidas/historial/`)
- **Modelos:** ItemComida (detalle_calculo)
- **Servicios (`core/services/`):** calculo.py
- **Pruebas (`core/tests/`):** test_rf14_rf15_calculo
- **Cómo demostrarlo:** Abrir una bandeja paisa en el historial y desplegar el cálculo: ingredientes, método, agua, grasa que gotea, aceite y rango.

### RF15 · Módulo Calculadora dinámica de absorción de aceite

- **Roles:** Usuario
- **Pantallas:** Calculadora de aceite (`/herramientas/aceite/`)
- **Modelos:** CoeficienteAbsorcion
- **Servicios (`core/services/`):** aceite.py
- **Pruebas (`core/tests/`):** test_rf14_rf15_calculo
- **Cómo demostrarlo:** Calcular 65 g de plátano verde en fritura profunda; cambiar a pieza pequeña y escurrido en papel y ver cómo cambia el rango.

### RF16 · Módulo Cálculo de metas y ajuste automático semanal

- **Roles:** Usuario, Administrador
- **Pantallas:** Explicación de la meta inicial (`/registro/meta/`); Ajuste semanal y reversión (`/metas/`); Ejecutar el proceso semanal (Administrador) (`/administracion/procesos/`)
- **Modelos:** MetaCalorica, DiaRegistro
- **Servicios (`core/services/`):** metas.py
- **Pruebas (`core/tests/`):** test_rf02_rf08_rf16_metas
- **Cómo demostrarlo:** Con la usuaria demo, ver el ajuste automático (−150 kcal), su explicación y el botón para revertirlo en 48 horas.

### RF17 · Módulo Salvaguardas de salud y seguridad del usuario

- **Roles:** Usuario
- **Pantallas:** Avisos de cuidado y día completo (`/panel/`); Ocultar cifras y pausar seguimiento (`/privacidad/`)
- **Modelos:** PerfilNutricional, DiaRegistro
- **Servicios (`core/services/`):** salvaguardas.py
- **Pruebas (`core/tests/`):** test_rf09_rf17_peso_salvaguardas
- **Cómo demostrarlo:** Entrar con la cuenta gestante: la meta es informativa y no hay déficit. Ocultar cifras y ver el panel sin números.

### RF18 · Módulo Gráficos de tendencias y reportes

- **Roles:** Usuario, Administrador, Curador
- **Pantallas:** Gráficos 7/30/90 días (`/reportes/`); Exportar CSV (`/reportes/exportar.csv`); Panel agregado (`/curacion/indicadores/`)
- **Modelos:** Comida, Pesaje, MetaCalorica
- **Servicios (`core/services/`):** reportes.py
- **Pruebas (`core/tests/`):** test_rf18_rf20_reportes_notificaciones
- **Cómo demostrarlo:** Cambiar entre 7, 30 y 90 días; exportar CSV; abrir el informe para imprimir o guardar en PDF.

### RF19 · Módulo Curación del catálogo y mejora continua

- **Roles:** Curador
- **Pantallas:** Bandeja de pendientes (`/curacion/`); Versiones e historial (`/curacion/versiones/`); Pruebas de exactitud (`/curacion/exactitud/`)
- **Modelos:** VersionCatalogo, HistorialCatalogo, FraseReferencia, EjecucionExactitud
- **Servicios (`core/services/`):** curacion.py
- **Pruebas (`core/tests/`):** test_rf19_curacion
- **Cómo demostrarlo:** Resolver un término pendiente, publicar la versión 2 (corre el conjunto de prueba) y revertir un cambio.

### RF20 · Módulo Notificaciones y recordatorios

- **Roles:** Usuario, Curador, Administrador
- **Pantallas:** Notificaciones (`/notificaciones/`); Configurar recordatorios (`/recordatorios/`)
- **Modelos:** Notificacion, RecordatorioUsuario
- **Servicios (`core/services/`):** notificaciones.py
- **Pruebas (`core/tests/`):** test_rf18_rf20_reportes_notificaciones
- **Cómo demostrarlo:** Configurar tres horas de recordatorio; como Administrador, ejecutar «recordatorios» en procesos y verlos llegar.

### RF21 · Módulo Integración con el proveedor de IA

- **Roles:** Administrador
- **Pantallas:** Uso, costo, plantillas y proveedor (`/administracion/ia/`)
- **Modelos:** UsoIA, CacheInterpretacion
- **Servicios (`core/services/`):** ia.py
- **Pruebas (`core/tests/`):** test_rf11_rf21_rf22_sistema
- **Cómo demostrarlo:** Ver el consumo y el costo; cambiar el proveedor a «ninguno» y comprobar que la interpretación sigue con reglas.

### RF22 · Módulo Trazabilidad y auditoría

- **Roles:** Administrador, Curador
- **Pantallas:** Bitácora, consentimientos y metas (`/administracion/auditoria/`); Historial del catálogo (`/curacion/versiones/`)
- **Modelos:** Bitacora, Consentimiento, HistorialCatalogo, MetaCalorica
- **Servicios (`core/services/`):** auditoria.py
- **Pruebas (`core/tests/`):** test_rf11_rf21_rf22_sistema
- **Cómo demostrarlo:** Filtrar la bitácora por acción: ingresos, cambios de parámetros, publicaciones. Intentar borrar un registro desde el código: se impide.

## Requerimientos no funcionales (actividades 23 a 36)

| RNF | Nombre | Estado | Cómo se cumple | Dónde verlo |
|---|---|---|---|---|
| 23 | Rendimiento | Parcial en el prototipo | Interpretación con reglas y caché en menos de 1,5 s (prueba automatizada); la IA externa tiene tiempo máximo configurable. No se hicieron pruebas de carga con 200 usuarios. | `/comidas/nueva/` |
| 24 | Exactitud nutricional | Cumplido | Conjunto de frases de referencia ejecutado antes de publicar cada versión del catálogo; bloquea la publicación si baja la exactitud. | `/curacion/exactitud/` |
| 25 | Transparencia y explicabilidad | Cumplido | Desglose, fuente, rango y confianza en cada ítem; explicación paso a paso de la meta; versiones del motor y del catálogo en cada comida. | `/comidas/historial/` |
| 26 | Seguridad y control de acceso | Cumplido | Rol validado en el servidor en cada petición, contraseñas PBKDF2, bloqueo tras 5 intentos, CSRF, ORM sin SQL manual, la IA nunca aporta valores. | `/cuentas/login/` |
| 27 | Protección de datos (Ley 1581) | Cumplido | Autorizaciones separadas, revocables e históricas; exportar y suprimir datos; acceso de soporte solo con autorización del titular. | `/privacidad/` |
| 28 | Integridad y trazabilidad | Cumplido | Claves foráneas, una sola meta vigente, baja lógica, operaciones atómicas, valores congelados por comida, bitácora de solo inserción. | `/administracion/auditoria/` |
| 29 | Usabilidad y accesibilidad | Parcial en el prototipo | Registro en una frase, preguntas con opciones tocables, diseño adaptable a celular, etiquetas y textos alternativos, enlace para saltar al contenido. Sin auditoría formal WCAG. | `/panel/` |
| 30 | Tecnología y compatibilidad | Desviación justificada | Aplicación web adaptable en lugar de app nativa Android/iOS; la API REST v1 queda lista para un cliente móvil. | `/requerimientos/` |
| 31 | Escalabilidad | Desviación justificada | SQLite en el prototipo (PostgreSQL en producción); API versionada, proveedor de IA intercambiable y procesos en lote separados de las vistas. | `/requerimientos/` |
| 32 | Disponibilidad y confiabilidad | Cumplido | Degradación controlada de la IA a reglas y búsqueda manual; un doble envío no duplica comidas (clave de idempotencia). | `/comidas/manual/` |
| 33 | Uso responsable y costos de la IA | Cumplido | Solo se envía lo que el léxico no resolvió, con autorización; caché, límite diario, presupuesto mensual con alerta al 80 %. | `/administracion/ia/` |
| 34 | Respaldo y recuperación | Parcial en el prototipo | Comando `respaldar` que copia la base en caliente con marca de tiempo y conserva los últimos respaldos; la restauración es reemplazar el archivo. | `/administracion/procesos/` |
| 35 | Mantenibilidad y calidad | Cumplido | Arquitectura en capas (modelos, servicios, vistas), parámetros como datos y pruebas automatizadas por requerimiento. | `/requerimientos/` |
| 36 | Monitoreo y registro de eventos | Parcial en el prototipo | Bitácora de eventos, latencia y errores de cada llamada a la IA, registro técnico en archivo sin datos personales. | `/administracion/auditoria/` |

Las desviaciones frente al SRS se justifican en [desviaciones.md](desviaciones.md).
