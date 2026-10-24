# Desviaciones del prototipo frente al SRS

El SRS describe el sistema completo en producción. Este repositorio es un
**prototipo académico** construido en dos semanas por cuatro personas con
Django y SQLite. Cumple las 22 actividades funcionales; las diferencias que
siguen son de **plataforma e infraestructura**, no de funcionalidad, y cada
una tiene un camino claro hacia lo que pide el SRS.

| # | El SRS pide | El prototipo hace | Por qué | Cómo se llega a lo pedido |
|---|---|---|---|---|
| 1 | App móvil nativa Android e iOS (RNF30, interfaz de usuario) | Aplicación web adaptable a celular (sin desbordes a 390 px de ancho) | Una sola base de código demostrable en el plazo; la consigna fija Django | La API REST v1 ya expone perfil, interpretación, comidas, resumen, series, pesajes, metas y notificaciones para un cliente Flutter o React Native |
| 2 | PostgreSQL 15 (interfaz de software, RNF31) | SQLite | Sin servidor que instalar para evaluar el proyecto | El ORM de Django no usa SQL propio de SQLite: basta cambiar `DATABASES`. La restricción de una meta vigente es un índice único condicional, soportado por ambos |
| 3 | Autenticación por tokens para la app | Sesión de Django (cookie segura, CSRF) en web y API | Es la autenticación natural de una app web | Agregar JWT o `TokenAuthentication` de DRF en `REST_FRAMEWORK` sin tocar los servicios |
| 4 | Notificaciones *push* | Notificaciones dentro de la aplicación y correo (en la consola del servidor) | Push requiere la app nativa y Firebase/APNs | `services/notificaciones.notificar()` es el único punto de envío: se agrega el canal push allí |
| 5 | Cola de tareas en segundo plano (ajuste semanal, recordatorios) | Comando `procesos` para cron / Programador de tareas, y botones en *Procesos* para la demostración | Evita instalar Redis y Celery | Las funciones del proceso son independientes de la vista: se envuelven en tareas de Celery |
| 6 | Trabajo sin conexión con sincronización | No aplica en web; el registro manual funciona sin IA y la clave de idempotencia evita duplicados al reenviar | Depende de la app nativa | El campo `Comida.sin_conexion` y la idempotencia ya están en el modelo y la API |
| 7 | Reportes en PDF | CSV y un informe pensado para «Imprimir → Guardar como PDF» desde el navegador | Sin dependencias de generación de PDF | Renderizar la misma plantilla con WeasyPrint |
| 8 | Catálogo validado por un nutricionista | 153 alimentos y 67 preparaciones con fuente declarada (TCAC, USDA, etiqueta o estimado), validación de Atwater y peso de receta; **pendientes de validación profesional** (`verificado = False`) | El equipo no incluye un nutricionista | Pantalla de verificación del Curador y versiones con historial: la validación queda registrada registro por registro |
| 9 | 200 frases de referencia validadas por un nutricionista | 200 frases escritas por el equipo, cargadas con `validada = False`; 98,9 % de identificación y 98,9 % de método de cocción, con 4 fallos visibles | Igual que el punto 8 | El Curador puede validar, editar o agregar frases desde *Exactitud*; las correcciones aceptadas generan frases nuevas |
| 10 | Error medio de energía ≤ 15 % frente a referencias de un nutricionista | El cálculo está implementado (`error_energia_pct`), pero las frases no tienen aún energía de referencia | Requiere las referencias validadas | Al llenar `kcal_referencia` en las frases, la ejecución de exactitud calcula y exige el umbral automáticamente |
| 11 | Cifrado de datos sensibles en reposo | HTTPS y cookies seguras con `DEBUG=False`; contraseñas con PBKDF2; la base local no se cifra | Cifrar SQLite exige extensiones externas | Cifrado de disco o de columnas en PostgreSQL (pgcrypto) en el despliegue |
| 12 | Tiempos de respuesta con 200 usuarios concurrentes (RNF23) | Prueba automatizada: interpretación con reglas en menos de 1,5 s. Sin pruebas de carga | Sin infraestructura de despliegue | Prueba de carga con Locust sobre la API una vez desplegada |
| 13 | Respaldo con RPO y RTO definidos (RNF34) | Comando `respaldar` con copia en caliente y rotación; restauración manual | Alcance del prototipo | Programar el comando (o `pg_dump`) y documentar la restauración en el despliegue |
| 14 | Monitoreo centralizado (RNF36) | Bitácora en base de datos, registro técnico en archivo rotativo y panel de uso de IA | Sin servicio externo de monitoreo | Enviar el registro a un servicio como Sentry o un ELK |

## Lo que no es desviación

- Las 22 actividades funcionales tienen pantalla, servicio y pruebas: ver
  [trazabilidad_srs.md](trazabilidad_srs.md) y la página `/requerimientos/`.
- Los roles, los límites de seguridad nutricional, las autorizaciones de la
  Ley 1581, la degradación de la IA y la auditoría funcionan como describe el
  SRS, no simulados.
- La IA es real: con una clave en `.env`, `python manage.py probar_ia` hace la
  llamada al proveedor y muestra la respuesta validada.
