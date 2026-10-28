"""
Mapa de trazabilidad SRS → aplicación.

Única fuente de verdad que conecta cada actividad del SRS con:
    · las pantallas donde se ve (nombres de URL de Django),
    · el rol con el que se demuestra,
    · los pasos para mostrarlo en la sustentación,
    · los modelos y servicios que lo implementan,
    · las pruebas automatizadas que lo verifican.

Lo usan la página /requerimientos/ y el comando `generar_trazabilidad`, que
escribe docs/trazabilidad_srs.md. Así la documentación no se desincroniza del
programa: una prueba comprueba que todas las URL de este mapa existen.
"""

U, C, A = "Usuario", "Curador", "Administrador"

REQUERIMIENTOS = [
    {
        "id": 1, "nombre": "CRUD Usuarios", "tipo": "funcional", "roles": [U, A],
        "pantallas": [("registro", "Crear cuenta"), ("cuenta", "Editar datos de contacto"),
                      ("privacidad", "Eliminar cuenta"), ("cuentas_admin", "Administrar cuentas")],
        "demo": "Crear una cuenta nueva; luego, como Administrador, bloquearla y ver que su sesión se cierra.",
        "modelos": ["User (Django)", "Cuenta", "Consentimiento"], "servicios": ["cuentas.py"],
        "pruebas": ["test_rf01_rf12_cuentas"],
    },
    {
        "id": 2, "nombre": "CRUD Perfil nutricional", "tipo": "funcional", "roles": [U],
        "pantallas": [("registro_perfil", "Paso 2 del registro"), ("perfil", "Editar perfil")],
        "demo": "Cambiar el nivel de actividad y ver que la meta se recalcula; intentar una fecha de nacimiento de menor de edad.",
        "modelos": ["PerfilNutricional"], "servicios": ["cuentas.guardar_perfil"],
        "pruebas": ["test_rf02_rf08_rf16_metas"],
    },
    {
        "id": 3, "nombre": "CRUD Alimentos base", "tipo": "funcional", "roles": [C, U],
        "pantallas": [("catalogo_alimentos", "Catálogo (Curador)"), ("mis_alimentos", "Alimentos personales (Usuario)")],
        "demo": "Como Curador, editar un alimento con energía incoherente y ver la validación de Atwater. Como Usuario, crear un alimento personal.",
        "modelos": ["Alimento"], "servicios": ["catalogo.py", "curacion.registrar_cambio"],
        "pruebas": ["test_rf03_rf06_catalogo"],
    },
    {
        "id": 4, "nombre": "CRUD Preparaciones regionales y componentes", "tipo": "funcional", "roles": [C],
        "pantallas": [("catalogo_preparaciones", "Preparaciones y su deconstrucción")],
        "demo": "Abrir la bandeja paisa y ver sus diez ingredientes con su método propio y la validación de peso de la porción.",
        "modelos": ["Preparacion", "Componente"], "servicios": ["catalogo.py"],
        "pruebas": ["test_rf03_rf06_catalogo", "test_rf14_rf15_calculo"],
    },
    {
        "id": 5, "nombre": "CRUD Métodos de cocción y absorción de aceite", "tipo": "funcional", "roles": [C],
        "pantallas": [("catalogo_metodos", "Métodos de cocción"), ("catalogo_coeficientes", "Coeficientes de absorción")],
        "demo": "Cambiar el coeficiente típico de masa de maíz y ver en el historial el valor anterior y el nuevo.",
        "modelos": ["MetodoCoccion", "CoeficienteAbsorcion"], "servicios": ["aceite.py"],
        "pruebas": ["test_rf03_rf06_catalogo", "test_rf14_rf15_calculo"],
    },
    {
        "id": 6, "nombre": "CRUD Léxico y porciones caseras", "tipo": "funcional", "roles": [C],
        "pantallas": [("catalogo_lexico", "Léxico regional"), ("catalogo_porciones", "Porciones caseras")],
        "demo": "Agregar el término «chontaduro» desde la bandeja de pendientes y ver que la próxima frase ya lo reconoce.",
        "modelos": ["TerminoLexico", "PorcionCasera", "TerminoPendiente"], "servicios": ["interpretacion.Lexico"],
        "pruebas": ["test_rf03_rf06_catalogo", "test_rf13_interpretacion"],
    },
    {
        "id": 7, "nombre": "CRUD Registro de comidas", "tipo": "funcional", "roles": [U],
        "pantallas": [("comida_nueva", "Registrar por texto"), ("comida_manual", "Búsqueda manual"),
                      ("historial", "Historial"), ("favoritas", "Favoritas")],
        "demo": "Registrar, editar un ítem (queda marcado como editado), marcar como favorita, repetirla y eliminarla (baja lógica).",
        "modelos": ["Comida", "ItemComida"], "servicios": ["comidas.py"],
        "pruebas": ["test_rf07_rf10_comidas"],
    },
    {
        "id": 8, "nombre": "CRUD Metas calóricas y de macronutrientes", "tipo": "funcional", "roles": [U],
        "pantallas": [("metas", "Meta vigente e historial")],
        "demo": "Ver el historial de metas con su origen y motivo; proponer una meta por debajo del piso y ver que se rechaza.",
        "modelos": ["MetaCalorica"], "servicios": ["metas.py"],
        "pruebas": ["test_rf02_rf08_rf16_metas"],
    },
    {
        "id": 9, "nombre": "CRUD Seguimiento de peso", "tipo": "funcional", "roles": [U],
        "pantallas": [("peso", "Pesajes y peso tendencial")],
        "demo": "Registrar un peso con 4 kg de diferencia respecto al anterior: se advierte sin bloquear. Ver la media móvil.",
        "modelos": ["Pesaje"], "servicios": ["salvaguardas.peso_tendencial"],
        "pruebas": ["test_rf09_rf17_peso_salvaguardas"],
    },
    {
        "id": 10, "nombre": "CRUD Correcciones y retroalimentación", "tipo": "funcional", "roles": [U, C],
        "pantallas": [("mis_correcciones", "Mis correcciones (Usuario)"), ("curacion", "Bandeja (Curador)")],
        "demo": "Reportar que una cantidad estaba mal: se corrige al instante en la comida; el Curador la acepta y el usuario recibe la respuesta.",
        "modelos": ["Correccion"], "servicios": ["curacion.crear_correccion", "curacion.revisar_correccion"],
        "pruebas": ["test_rf07_rf10_comidas", "test_rf19_curacion"],
    },
    {
        "id": 11, "nombre": "CRUD Parámetros del sistema", "tipo": "funcional", "roles": [A, C],
        "pantallas": [("parametros", "Parámetros")],
        "demo": "Cambiar el umbral de confianza y ver que cambian las preguntas de aclaración. El Curador solo ve los nutricionales.",
        "modelos": ["Parametro"], "servicios": ["parametros.py"],
        "pruebas": ["test_rf11_rf21_rf22_sistema"],
    },
    {
        "id": 12, "nombre": "Módulo Acceso y registro", "tipo": "funcional", "roles": [U],
        "pantallas": [("registro", "Registro en 3 pasos"), ("login", "Ingreso"), ("password_reset", "Recuperar contraseña"),
                      ("aviso_medico", "Aviso de no ser servicio médico")],
        "demo": "Registro con barra de progreso y autorizaciones separadas; 5 intentos fallidos bloquean la cuenta; recuperación por correo (aparece en la consola).",
        "modelos": ["Cuenta", "Consentimiento"], "servicios": ["cuentas.py", "signals.py", "middleware.py"],
        "pruebas": ["test_rf01_rf12_cuentas"],
    },
    {
        "id": 13, "nombre": "Módulo Interpretación de texto libre (NLP)", "tipo": "funcional", "roles": [U],
        "pantallas": [("comida_nueva", "Escribir lo que comiste")],
        "demo": "Escribir «una arepa y una gaseosa»: el sistema pregunta cómo estaba la arepa y qué presentación de gaseosa. Probar errores como «chicarron con aripa».",
        "modelos": ["TerminoLexico", "TerminoPendiente"], "servicios": ["interpretacion.py", "ia.py"],
        "pruebas": ["test_rf13_interpretacion"],
    },
    {
        "id": 14, "nombre": "Módulo Deconstrucción de recetas y cálculo nutricional", "tipo": "funcional", "roles": [U],
        "pantallas": [("historial", "Detalle de cada comida con su desglose")],
        "demo": "Abrir una bandeja paisa en el historial y desplegar el cálculo: ingredientes, método, agua, grasa que gotea, aceite y rango.",
        "modelos": ["ItemComida (detalle_calculo)"], "servicios": ["calculo.py"],
        "pruebas": ["test_rf14_rf15_calculo"],
    },
    {
        "id": 15, "nombre": "Módulo Calculadora dinámica de absorción de aceite", "tipo": "funcional", "roles": [U],
        "pantallas": [("calculadora_aceite", "Calculadora de aceite")],
        "demo": "Calcular 65 g de plátano verde en fritura profunda; cambiar a pieza pequeña y escurrido en papel y ver cómo cambia el rango.",
        "modelos": ["CoeficienteAbsorcion"], "servicios": ["aceite.py"],
        "pruebas": ["test_rf14_rf15_calculo"],
    },
    {
        "id": 16, "nombre": "Módulo Cálculo de metas y ajuste automático semanal", "tipo": "funcional", "roles": [U, A],
        "pantallas": [("registro_meta", "Explicación de la meta inicial"), ("metas", "Ajuste semanal y reversión"),
                      ("procesos", "Ejecutar el proceso semanal (Administrador)")],
        "demo": "Con la usuaria demo, ver el ajuste automático (−150 kcal), su explicación y el botón para revertirlo en 48 horas.",
        "modelos": ["MetaCalorica", "DiaRegistro"], "servicios": ["metas.py"],
        "pruebas": ["test_rf02_rf08_rf16_metas"],
    },
    {
        "id": 17, "nombre": "Módulo Salvaguardas de salud y seguridad del usuario", "tipo": "funcional", "roles": [U],
        "pantallas": [("panel", "Avisos de cuidado y día completo"), ("privacidad", "Ocultar cifras y pausar seguimiento")],
        "demo": "Entrar con la cuenta gestante: la meta es informativa y no hay déficit. Ocultar cifras y ver el panel sin números.",
        "modelos": ["PerfilNutricional", "DiaRegistro"], "servicios": ["salvaguardas.py"],
        "pruebas": ["test_rf09_rf17_peso_salvaguardas"],
    },
    {
        "id": 18, "nombre": "Módulo Gráficos de tendencias y reportes", "tipo": "funcional", "roles": [U, A, C],
        "pantallas": [("reportes", "Gráficos 7/30/90 días"), ("reporte_csv", "Exportar CSV"),
                      ("indicadores", "Panel agregado")],
        "demo": "Cambiar entre 7, 30 y 90 días; exportar CSV; abrir el informe para imprimir o guardar en PDF.",
        "modelos": ["Comida", "Pesaje", "MetaCalorica"], "servicios": ["reportes.py"],
        "pruebas": ["test_rf18_rf20_reportes_notificaciones"],
    },
    {
        "id": 19, "nombre": "Módulo Curación del catálogo y mejora continua", "tipo": "funcional", "roles": [C],
        "pantallas": [("curacion", "Bandeja de pendientes"), ("versiones", "Versiones e historial"),
                      ("exactitud", "Pruebas de exactitud")],
        "demo": "Resolver un término pendiente, publicar la versión 2 (corre el conjunto de prueba) y revertir un cambio.",
        "modelos": ["VersionCatalogo", "HistorialCatalogo", "FraseReferencia", "EjecucionExactitud"],
        "servicios": ["curacion.py"], "pruebas": ["test_rf19_curacion"],
    },
    {
        "id": 20, "nombre": "Módulo Notificaciones y recordatorios", "tipo": "funcional", "roles": [U, C, A],
        "pantallas": [("notificaciones", "Notificaciones"), ("recordatorios", "Configurar recordatorios")],
        "demo": "Configurar tres horas de recordatorio; como Administrador, ejecutar «recordatorios» en procesos y verlos llegar.",
        "modelos": ["Notificacion", "RecordatorioUsuario"], "servicios": ["notificaciones.py"],
        "pruebas": ["test_rf18_rf20_reportes_notificaciones"],
    },
    {
        "id": 21, "nombre": "Módulo Integración con el proveedor de IA", "tipo": "funcional", "roles": [A],
        "pantallas": [("ia_admin", "Uso, costo, plantillas y proveedor")],
        "demo": "Ver el consumo y el costo; cambiar el proveedor a «compatible» (Groq, OpenRouter… gratuitos) o a «ninguno» y comprobar que la interpretación sigue con reglas.",
        "modelos": ["UsoIA", "CacheInterpretacion"], "servicios": ["ia.py"],
        "pruebas": ["test_rf11_rf21_rf22_sistema", "test_rf21_proveedores"],
    },
    {
        "id": 22, "nombre": "Módulo Trazabilidad y auditoría", "tipo": "funcional", "roles": [A, C],
        "pantallas": [("auditoria", "Bitácora, consentimientos y metas"), ("versiones", "Historial del catálogo")],
        "demo": "Filtrar la bitácora por acción: ingresos, cambios de parámetros, publicaciones. Intentar borrar un registro desde el código: se impide.",
        "modelos": ["Bitacora", "Consentimiento", "HistorialCatalogo", "MetaCalorica"], "servicios": ["auditoria.py"],
        "pruebas": ["test_rf11_rf21_rf22_sistema"],
    },
]

# Requerimientos no funcionales (actividades 23 a 36). `estado` dice con
# franqueza hasta dónde llega el prototipo; las diferencias se explican en
# docs/desviaciones.md.
CUMPLIDO, PARCIAL, DESVIACION = "Cumplido", "Parcial en el prototipo", "Desviación justificada"

NO_FUNCIONALES = [
    {"id": 23, "nombre": "Rendimiento", "estado": PARCIAL, "pantalla": "comida_nueva",
     "como": "Interpretación con reglas y caché en menos de 1,5 s (prueba automatizada); la IA externa tiene tiempo máximo configurable. No se hicieron pruebas de carga con 200 usuarios."},
    {"id": 24, "nombre": "Exactitud nutricional", "estado": CUMPLIDO, "pantalla": "exactitud",
     "como": "Conjunto de frases de referencia ejecutado antes de publicar cada versión del catálogo; bloquea la publicación si baja la exactitud."},
    {"id": 25, "nombre": "Transparencia y explicabilidad", "estado": CUMPLIDO, "pantalla": "historial",
     "como": "Desglose, fuente, rango y confianza en cada ítem; explicación paso a paso de la meta; versiones del motor y del catálogo en cada comida."},
    {"id": 26, "nombre": "Seguridad y control de acceso", "estado": CUMPLIDO, "pantalla": "login",
     "como": "Rol validado en el servidor en cada petición, contraseñas PBKDF2, bloqueo tras 5 intentos, CSRF, ORM sin SQL manual, la IA nunca aporta valores."},
    {"id": 27, "nombre": "Protección de datos (Ley 1581)", "estado": CUMPLIDO, "pantalla": "privacidad",
     "como": "Autorizaciones separadas, revocables e históricas; exportar y suprimir datos; acceso de soporte solo con autorización del titular."},
    {"id": 28, "nombre": "Integridad y trazabilidad", "estado": CUMPLIDO, "pantalla": "auditoria",
     "como": "Claves foráneas, una sola meta vigente, baja lógica, operaciones atómicas, valores congelados por comida, bitácora de solo inserción."},
    {"id": 29, "nombre": "Usabilidad y accesibilidad", "estado": PARCIAL, "pantalla": "panel",
     "como": "Registro en una frase, preguntas con opciones tocables, diseño adaptable a celular, etiquetas y textos alternativos, enlace para saltar al contenido. Sin auditoría formal WCAG."},
    {"id": 30, "nombre": "Tecnología y compatibilidad", "estado": DESVIACION, "pantalla": "requerimientos",
     "como": "Aplicación web adaptable en lugar de app nativa Android/iOS; la API REST v1 queda lista para un cliente móvil."},
    {"id": 31, "nombre": "Escalabilidad", "estado": DESVIACION, "pantalla": "requerimientos",
     "como": "SQLite en el prototipo (PostgreSQL en producción); API versionada, proveedor de IA intercambiable y procesos en lote separados de las vistas."},
    {"id": 32, "nombre": "Disponibilidad y confiabilidad", "estado": CUMPLIDO, "pantalla": "comida_manual",
     "como": "Degradación controlada de la IA a reglas y búsqueda manual; un doble envío no duplica comidas (clave de idempotencia)."},
    {"id": 33, "nombre": "Uso responsable y costos de la IA", "estado": CUMPLIDO, "pantalla": "ia_admin",
     "como": "Solo se envía lo que el léxico no resolvió, con autorización; caché, límite diario, presupuesto mensual con alerta al 80 %."},
    {"id": 34, "nombre": "Respaldo y recuperación", "estado": PARCIAL, "pantalla": "procesos",
     "como": "Comando `respaldar` que copia la base en caliente con marca de tiempo y conserva los últimos respaldos; la restauración es reemplazar el archivo."},
    {"id": 35, "nombre": "Mantenibilidad y calidad", "estado": CUMPLIDO, "pantalla": "requerimientos",
     "como": "Arquitectura en capas (modelos, servicios, vistas), parámetros como datos y pruebas automatizadas por requerimiento."},
    {"id": 36, "nombre": "Monitoreo y registro de eventos", "estado": PARCIAL, "pantalla": "auditoria",
     "como": "Bitácora de eventos, latencia y errores de cada llamada a la IA, registro técnico en archivo sin datos personales."},
]
