# Diccionario de datos

> Generado con `python manage.py generar_trazabilidad` a partir de los modelos de `core/models/`.
> Las tablas de usuarios y sesiones son las de `django.contrib.auth` y `django.contrib.sessions`.

## VersionCatalogo (`core_versioncatalogo`)

Cada conjunto de cambios del Curador genera una versión (actividad 19).

| Campo | Tipo | Nulo | Restricciones | Descripción |
|---|---|---|---|---|
| `id` | BigAutoField | no | PK | ID |
| `numero` | PositiveIntegerField | no | único |  |
| `estado` | CharField | no | máx. 10; valores: borrador, publicada, rechazada |  |
| `notas` | TextField | no |  |  |
| `creada_por_id` | FK → User | sí |  |  |
| `creada_en` | DateTimeField | no |  |  |
| `publicada_en` | DateTimeField | sí |  |  |

## MetodoCoccion (`core_metodococcion`)

Forma de preparar un alimento y cómo cambia su peso y su grasa.

| Campo | Tipo | Nulo | Restricciones | Descripción |
|---|---|---|---|---|
| `id` | BigAutoField | no | PK | ID |
| `clave` | SlugField | no | único; máx. 30 |  |
| `nombre` | CharField | no | único; máx. 60 |  |
| `usa_grasa` | BooleanField | no |  |  |
| `es_fritura` | BooleanField | no |  | Activa la calculadora de absorción de aceite. |
| `factor_agua` | DecimalField | no | 5,1 |  |
| `perdida_grasa` | DecimalField | no | 5,1 |  |
| `palabras` | TextField | no |  | Palabras que lo identifican en el texto, separadas por comas. |
| `estado` | CharField | no | máx. 10; valores: activo, inactivo |  |
| `version_id` | FK → VersionCatalogo | sí |  |  |

## CoeficienteAbsorcion (`core_coeficienteabsorcion`)

% de aceite absorbido sobre el peso crudo: mínimo, típico y máximo.

| Campo | Tipo | Nulo | Restricciones | Descripción |
|---|---|---|---|---|
| `id` | BigAutoField | no | PK | ID |
| `metodo_id` | FK → MetodoCoccion | no |  |  |
| `matriz` | CharField | no | máx. 15; valores: masa_maiz, masa_trigo, apanado, tuberculo, carne, pescado, huevo, otro |  |
| `pct_min` | DecimalField | no | 5,1 |  |
| `pct_tipico` | DecimalField | no | 5,1 |  |
| `pct_max` | DecimalField | no | 5,1 |  |
| `fuente` | CharField | no | máx. 250 |  |
| `estado` | CharField | no | máx. 10; valores: activo, inactivo |  |
| `version_id` | FK → VersionCatalogo | sí |  |  |

*Restricción `coeficiente_unico`*

## Alimento (`core_alimento`)

Alimento base del catálogo o alimento personal de un usuario.

| Campo | Tipo | Nulo | Restricciones | Descripción |
|---|---|---|---|---|
| `id` | BigAutoField | no | PK | ID |
| `nombre` | CharField | no | máx. 120 |  |
| `categoria` | CharField | no | máx. 60 |  |
| `estado_fisico` | CharField | no | máx. 10; valores: crudo, cocido |  |
| `kcal` | DecimalField | no | 6,1 | energía (kcal) |
| `proteinas` | DecimalField | no | 5,1 |  |
| `carbohidratos` | DecimalField | no | 5,1 |  |
| `azucares` | DecimalField | sí | 5,1 |  |
| `grasas` | DecimalField | no | 5,1 |  |
| `grasas_saturadas` | DecimalField | sí | 5,1 |  |
| `fibra` | DecimalField | sí | 5,1 |  |
| `sodio_mg` | DecimalField | sí | 7,1 |  |
| `agua_pct` | DecimalField | sí | 4,1 |  |
| `densidad` | DecimalField | sí | 4,2 | g/ml. Solo para líquidos: convierte mililitros a gramos. |
| `rendimiento_pct` | DecimalField | sí | 4,1 | Parte comestible, para cortes de carne con hueso. |
| `grasa_visible_pct` | DecimalField | sí | 4,1 | Grasa visible que suele retirarse, para cortes de carne. |
| `matriz` | CharField | no | máx. 15; valores: masa_maiz, masa_trigo, apanado, tuberculo, carne, pescado, huevo, otro | Tipo de alimento para la calculadora de absorción de aceite. |
| `metodo_defecto_id` | FK → MetodoCoccion | sí |  | Para alimentos crudos: cómo se suele preparar si el usuario no lo dice. |
| `ambito` | CharField | no | máx. 10; valores: global, personal |  |
| `propietario_id` | FK → User | sí |  |  |
| `fuente` | CharField | no | máx. 10; valores: tcac, usda, etiqueta, estimado |  |
| `fuente_detalle` | CharField | no | máx. 250 |  |
| `verificado` | BooleanField | no |  |  |
| `estado` | CharField | no | máx. 10; valores: activo, inactivo |  |
| `version_id` | FK → VersionCatalogo | sí |  |  |
| `modificado_por_id` | FK → User | sí |  |  |
| `modificado_en` | DateTimeField | no |  |  |

## Preparacion (`core_preparacion`)

Preparación regional que se deconstruye en ingredientes crudos.

| Campo | Tipo | Nulo | Restricciones | Descripción |
|---|---|---|---|---|
| `id` | BigAutoField | no | PK | ID |
| `nombre` | CharField | no | único; máx. 120 |  |
| `descripcion` | TextField | no |  |  |
| `region` | CharField | no | máx. 60 |  |
| `categoria` | CharField | no | máx. 15; valores: desayuno, plato_fuerte, sopa, fritura, bebida, postre, pasabocas, otra |  |
| `peso_porcion_g` | DecimalField | no | 6,1 | Peso de la porción típica ya preparada. |
| `metodo_defecto_id` | FK → MetodoCoccion | no |  |  |
| `admite_variantes` | BooleanField | no |  | Si se prepara de varias formas (arepa asada o frita), se pregunta cuando no se dice. |
| `verificada` | BooleanField | no |  |  |
| `estado` | CharField | no | máx. 10; valores: activo, inactivo |  |
| `version_id` | FK → VersionCatalogo | sí |  |  |
| `modificado_por_id` | FK → User | sí |  |  |
| `modificado_en` | DateTimeField | no |  |  |

## Componente (`core_componente`)

Una línea de la receta: cuántos gramos crudos de qué alimento.

| Campo | Tipo | Nulo | Restricciones | Descripción |
|---|---|---|---|---|
| `id` | BigAutoField | no | PK | ID |
| `preparacion_id` | FK → Preparacion | no |  |  |
| `alimento_id` | FK → Alimento | no |  |  |
| `cantidad_g` | DecimalField | no | 6,1 | Gramos en crudo por porción típica. |
| `metodo_id` | FK → MetodoCoccion | sí |  | Solo si difiere del método de la preparación. |
| `rol` | CharField | no | máx. 15; valores: base, relleno, acompanante, salsa, grasa_coccion |  |
| `opcional` | BooleanField | no |  |  |

## TerminoLexico (`core_terminolexico`)

Palabra o expresión que el sistema reconoce, y a qué apunta.

| Campo | Tipo | Nulo | Restricciones | Descripción |
|---|---|---|---|---|
| `id` | BigAutoField | no | PK | ID |
| `termino` | CharField | no | único; máx. 120 | En minúsculas y sin tildes. |
| `tipo` | CharField | no | máx. 15; valores: alimento, preparacion, metodo |  |
| `alimento_id` | FK → Alimento | sí |  |  |
| `preparacion_id` | FK → Preparacion | sí |  |  |
| `metodo_id` | FK → MetodoCoccion | sí |  |  |
| `region` | CharField | no | máx. 60 |  |
| `estado` | CharField | no | máx. 10; valores: activo, inactivo |  |

## PorcionCasera (`core_porcioncasera`)

Medida casera ("unidad mediana", "vaso") y su equivalencia en g o ml.

| Campo | Tipo | Nulo | Restricciones | Descripción |
|---|---|---|---|---|
| `id` | BigAutoField | no | PK | ID |
| `alimento_id` | FK → Alimento | sí |  |  |
| `preparacion_id` | FK → Preparacion | sí |  |  |
| `medida` | CharField | no | máx. 20; valores: unidad_pequena, unidad_mediana, unidad_grande, porcion, plato, vaso, taza, pocillo … |  |
| `cantidad` | DecimalField | no | 6,1 | Gramos (o mililitros en bebidas). |
| `por_defecto` | BooleanField | no |  |  |

## TerminoPendiente (`core_terminopendiente`)

Término que un usuario escribió y el sistema no reconoció.

| Campo | Tipo | Nulo | Restricciones | Descripción |
|---|---|---|---|---|
| `id` | BigAutoField | no | PK | ID |
| `termino` | CharField | no | único; máx. 120 |  |
| `veces` | PositiveIntegerField | no |  |  |
| `estado` | CharField | no | máx. 12; valores: pendiente, resuelto, descartado |  |
| `primera_vez` | DateTimeField | no |  |  |
| `ultima_vez` | DateTimeField | no |  |  |
| `resuelto_por_id` | FK → User | sí |  |  |

## HistorialCatalogo (`core_historialcatalogo`)

Cada cambio al catálogo, con valor anterior y nuevo. Solo inserción.

| Campo | Tipo | Nulo | Restricciones | Descripción |
|---|---|---|---|---|
| `id` | BigAutoField | no | PK | ID |
| `version_id` | FK → VersionCatalogo | no |  |  |
| `entidad` | CharField | no | máx. 40 |  |
| `entidad_id` | PositiveIntegerField | no |  |  |
| `descripcion` | CharField | no | máx. 200 |  |
| `valor_anterior` | JSONField | sí |  |  |
| `valor_nuevo` | JSONField | sí |  |  |
| `usuario_id` | FK → User | sí |  |  |
| `fecha` | DateTimeField | no |  |  |
| `revertido` | BooleanField | no |  |  |

## Comida (`core_comida`)

| Campo | Tipo | Nulo | Restricciones | Descripción |
|---|---|---|---|---|
| `id` | BigAutoField | no | PK | ID |
| `usuario_id` | FK → User | no |  |  |
| `texto_original` | CharField | no | máx. 500 |  |
| `fecha_hora` | DateTimeField | no |  |  |
| `tipo` | CharField | no | máx. 10; valores: desayuno, almuerzo, cena, merienda, bebida, otro |  |
| `origen` | CharField | no | máx. 10; valores: texto, manual, favorita |  |
| `estado` | CharField | no | máx. 15; valores: interpretada, confirmada, editada, descartada |  |
| `kcal` | DecimalField | no | 7,1 |  |
| `proteinas` | DecimalField | no | 6,1 |  |
| `carbohidratos` | DecimalField | no | 6,1 |  |
| `azucares` | DecimalField | no | 6,1 |  |
| `grasas` | DecimalField | no | 6,1 |  |
| `aceite_g` | DecimalField | no | 6,1 |  |
| `kcal_min` | DecimalField | no | 7,1 |  |
| `kcal_max` | DecimalField | no | 7,1 |  |
| `confianza` | DecimalField | no | 3,2 |  |
| `motor` | CharField | no | máx. 15; valores: ia_externa, modelo_local, reglas, manual |  |
| `version_motor` | CharField | no | máx. 20 |  |
| `version_catalogo` | PositiveIntegerField | sí |  |  |
| `version_plantilla_ia` | CharField | no | máx. 20 |  |
| `sin_conexion` | BooleanField | no |  |  |
| `es_favorita` | BooleanField | no |  |  |
| `nombre_favorita` | CharField | no | máx. 80 |  |
| `preguntas` | JSONField | no |  | Preguntas de aclaración pendientes (máximo dos). |
| `clave_idempotencia` | UUIDField | no | máx. 32 | Evita duplicar la comida por un doble envío. |
| `creada_en` | DateTimeField | no |  |  |
| `editada_en` | DateTimeField | no |  |  |

*Restricción `comida_idempotente`*

## ItemComida (`core_itemcomida`)

Un componente de la comida, con su cálculo completo guardado.

| Campo | Tipo | Nulo | Restricciones | Descripción |
|---|---|---|---|---|
| `id` | BigAutoField | no | PK | ID |
| `comida_id` | FK → Comida | no |  |  |
| `alimento_id` | FK → Alimento | sí |  |  |
| `preparacion_id` | FK → Preparacion | sí |  |  |
| `nombre_mostrado` | CharField | no | máx. 120 |  |
| `fragmento_texto` | CharField | no | máx. 200 |  |
| `cantidad_original` | DecimalField | sí | 8,2 |  |
| `unidad_original` | CharField | no | máx. 30 |  |
| `cantidad_g` | DecimalField | sí | 8,1 |  |
| `medida` | CharField | no | máx. 20 | Medida casera usada, si la hubo. |
| `fuente_cantidad` | CharField | no | máx. 10 | De dónde salió la cantidad: gramos, medida, unidad o defecto (porción por defecto). |
| `metodo_id` | FK → MetodoCoccion | sí |  |  |
| `origen_metodo` | CharField | no | máx. 10 | explicito, implicito, defecto, ambiguo o no_aplica. |
| `tamano` | CharField | no | máx. 10 |  |
| `escurrido` | BooleanField | no |  |  |
| `aceite_agregado_g` | DecimalField | sí | 6,1 | Aceite que el usuario dijo agregar a la sartén. |
| `aplicar_rendimiento` | BooleanField | no |  | Descontar hueso o parte no comestible (porciones caseras). |
| `aceite_g` | DecimalField | no | 6,1 |  |
| `aceite_min_g` | DecimalField | no | 6,1 |  |
| `aceite_max_g` | DecimalField | no | 6,1 |  |
| `kcal` | DecimalField | sí | 7,1 |  |
| `proteinas` | DecimalField | sí | 6,1 |  |
| `carbohidratos` | DecimalField | sí | 6,1 |  |
| `azucares` | DecimalField | sí | 6,1 |  |
| `grasas` | DecimalField | sí | 6,1 |  |
| `kcal_min` | DecimalField | sí | 7,1 |  |
| `kcal_max` | DecimalField | sí | 7,1 |  |
| `confianza` | DecimalField | no | 3,2 |  |
| `origen_dato` | CharField | no | máx. 10; valores: catalogo, similitud, ia, usuario |  |
| `editado` | BooleanField | no |  | editado por el usuario |
| `estimado` | BooleanField | no |  |  |
| `pendiente` | BooleanField | no |  | No se reconoció: el usuario debe elegirlo o descartarlo. |
| `descartado` | BooleanField | no |  |  |
| `notas` | TextField | no |  |  |
| `detalle_calculo` | JSONField | no |  |  |

## DiaRegistro (`core_diaregistro`)

El usuario marca un día como completo cuando registró todo lo que comió.

| Campo | Tipo | Nulo | Restricciones | Descripción |
|---|---|---|---|---|
| `id` | BigAutoField | no | PK | ID |
| `usuario_id` | FK → User | no |  |  |
| `fecha` | DateField | no |  |  |
| `completo` | BooleanField | no |  |  |

*Restricción `dia_unico`*

## Correccion (`core_correccion`)

Un usuario reporta que una estimación está mal (actividad 10).

| Campo | Tipo | Nulo | Restricciones | Descripción |
|---|---|---|---|---|
| `id` | BigAutoField | no | PK | ID |
| `item_id` | FK → ItemComida | sí |  |  |
| `usuario_id` | FK → User | sí |  |  |
| `tipo` | CharField | no | máx. 20; valores: componente, cantidad, metodo, valor_nutricional, otro |  |
| `valor_original` | CharField | no | máx. 200 |  |
| `valor_sugerido` | CharField | no | máx. 200 |  |
| `comentario` | TextField | no |  |  |
| `aplicada_a_comida` | BooleanField | no |  |  |
| `estado` | CharField | no | máx. 12; valores: pendiente, en_revision, aceptada, rechazada |  |
| `revisor_id` | FK → User | sí |  |  |
| `resolucion` | TextField | no |  |  |
| `fecha_reporte` | DateTimeField | no |  |  |
| `fecha_revision` | DateTimeField | sí |  |  |

## Cuenta (`core_cuenta`)

Datos de la cuenta que complementan al User de Django (usu_*).

| Campo | Tipo | Nulo | Restricciones | Descripción |
|---|---|---|---|---|
| `id` | BigAutoField | no | PK | ID |
| `usuario_id` | FK → User | no | único |  |
| `rol` | CharField | no | máx. 15; valores: usuario, curador, administrador |  |
| `estado` | CharField | no | máx. 10; valores: activo, inactivo, bloqueado |  |
| `acepta_datos` | BooleanField | no |  | autoriza el tratamiento de datos personales |
| `fecha_acepta_datos` | DateTimeField | sí |  |  |
| `acepta_ia` | BooleanField | no |  | autoriza enviar el texto de sus comidas a una IA externa |
| `fecha_acepta_ia` | DateTimeField | sí |  |  |
| `intentos_fallidos` | PositiveSmallIntegerField | no |  |  |
| `bloqueado_hasta` | DateTimeField | sí |  |  |
| `paso_registro` | PositiveSmallIntegerField | no |  |  |
| `seguimiento_pausado` | BooleanField | no |  | seguimiento en pausa |
| `recibir_resumen_semanal` | BooleanField | no |  |  |
| `autoriza_soporte_hasta` | DateTimeField | sí |  | Mientras esté vigente, el Administrador puede ver sus datos para soporte. |

## Consentimiento (`core_consentimiento`)

Registro inmutable de autorizaciones otorgadas o retiradas (actividad 22).

| Campo | Tipo | Nulo | Restricciones | Descripción |
|---|---|---|---|---|
| `id` | BigAutoField | no | PK | ID |
| `usuario_id` | FK → User | no |  |  |
| `tipo` | CharField | no | máx. 10; valores: datos, ia |  |
| `otorgado` | BooleanField | no |  |  |
| `version_texto` | CharField | no | máx. 10 |  |
| `ip` | GenericIPAddressField | sí | máx. 39 |  |
| `fecha` | DateTimeField | no |  |  |

## PerfilNutricional (`core_perfilnutricional`)

Datos con los que se calcula la meta (per_*). Solo los ve su dueño.

| Campo | Tipo | Nulo | Restricciones | Descripción |
|---|---|---|---|---|
| `id` | BigAutoField | no | PK | ID |
| `usuario_id` | FK → User | no | único |  |
| `fecha_nacimiento` | DateField | no |  |  |
| `sexo` | CharField | no | máx. 10; valores: femenino, masculino |  |
| `estatura_cm` | PositiveSmallIntegerField | no | máx. 230 |  |
| `peso_inicial_kg` | DecimalField | no | 5,1 |  |
| `fecha_peso_inicial` | DateField | no |  |  |
| `nivel_actividad` | CharField | no | máx. 12; valores: sedentario, ligero, moderado, alto, muy_alto |  |
| `objetivo` | CharField | no | máx. 10; valores: perder, mantener |  |
| `peso_meta_kg` | DecimalField | sí | 5,1 |  |
| `ritmo` | CharField | no | máx. 10; valores: lento, moderado |  |
| `gestante_lactante` | BooleanField | no |  | en gestación o lactancia |
| `requiere_acompanamiento` | BooleanField | no |  | tiene una condición de salud o alimentación que requiere acompañamiento profesional |
| `ocultar_cifras` | BooleanField | no |  | ocultar el peso y las cifras de calorías |
| `creado_en` | DateTimeField | no |  |  |
| `actualizado_en` | DateTimeField | no |  |  |

## RecordatorioUsuario (`core_recordatoriousuario`)

Horas a las que el usuario quiere que le recuerden registrar (máx. 3).

| Campo | Tipo | Nulo | Restricciones | Descripción |
|---|---|---|---|---|
| `id` | BigAutoField | no | PK | ID |
| `usuario_id` | FK → User | no |  |  |
| `hora` | TimeField | no |  |  |
| `activo` | BooleanField | no |  |  |

*Restricción `recordatorio_hora_unica`*

## MetaCalorica (`core_metacalorica`)

| Campo | Tipo | Nulo | Restricciones | Descripción |
|---|---|---|---|---|
| `id` | BigAutoField | no | PK | ID |
| `usuario_id` | FK → User | no |  |  |
| `fecha_inicio` | DateField | no |  |  |
| `fecha_fin` | DateField | sí |  |  |
| `vigente` | BooleanField | no |  |  |
| `tmb` | DecimalField | no | 6,1 | TMB (kcal) |
| `gasto_total` | DecimalField | no | 6,1 | gasto energético total, GET (kcal) |
| `kcal_dia` | DecimalField | no | 6,1 | meta diaria (kcal) |
| `deficit_pct` | DecimalField | no | 4,1 |  |
| `proteinas_g` | DecimalField | no | 5,1 |  |
| `carbohidratos_g` | DecimalField | no | 5,1 |  |
| `grasas_g` | DecimalField | no | 5,1 |  |
| `origen` | CharField | no | máx. 20; valores: inicial, ajuste_automatico, ajuste_manual, mantenimiento, recalculo, reversion |  |
| `motivo` | TextField | no |  |  |
| `explicacion` | JSONField | no |  | Pasos del cálculo, para mostrarlos al usuario. |
| `solo_informativa` | BooleanField | no |  | Salvaguarda activa: no se aplica déficit. |
| `revertida` | BooleanField | no |  |  |
| `revertible_hasta` | DateTimeField | sí |  |  |
| `meta_anterior_id` | FK → MetaCalorica | sí |  |  |
| `creada_en` | DateTimeField | no |  |  |

*Restricción `una_meta_vigente_por_usuario`*

## Pesaje (`core_pesaje`)

| Campo | Tipo | Nulo | Restricciones | Descripción |
|---|---|---|---|---|
| `id` | BigAutoField | no | PK | ID |
| `usuario_id` | FK → User | no |  |  |
| `fecha` | DateField | no |  |  |
| `peso_kg` | DecimalField | no | 5,1 |  |
| `observacion` | CharField | no | máx. 200 |  |
| `registrado_en` | DateTimeField | no |  |  |

*Restricción `un_pesaje_por_dia`*

## Parametro (`core_parametro`)

| Campo | Tipo | Nulo | Restricciones | Descripción |
|---|---|---|---|---|
| `id` | BigAutoField | no | PK | ID |
| `clave` | SlugField | no | único; máx. 60 |  |
| `valor` | TextField | no |  |  |
| `tipo` | CharField | no | máx. 10; valores: entero, decimal, texto, booleano, json |  |
| `grupo` | CharField | no | máx. 15; valores: nutricional, salvaguardas, ia, sistema |  |
| `descripcion` | CharField | no | máx. 250 |  |
| `modificado_por_id` | FK → User | sí |  |  |
| `modificado_en` | DateTimeField | no |  |  |

## Notificacion (`core_notificacion`)

| Campo | Tipo | Nulo | Restricciones | Descripción |
|---|---|---|---|---|
| `id` | BigAutoField | no | PK | ID |
| `destinatario_id` | FK → User | no |  |  |
| `tipo` | CharField | no | máx. 15; valores: recordatorio, resumen, meta, cuidado, correccion, curacion, exactitud, sistema |  |
| `titulo` | CharField | no | máx. 120 |  |
| `mensaje` | TextField | no |  |  |
| `url` | CharField | no | máx. 200 | Registro relacionado (opcional). |
| `leida` | BooleanField | no |  |  |
| `enviada_por_correo` | BooleanField | no |  |  |
| `creada_en` | DateTimeField | no |  |  |

## UsoIA (`core_usoia`)

Una llamada (o un intento) al proveedor de IA.

| Campo | Tipo | Nulo | Restricciones | Descripción |
|---|---|---|---|---|
| `id` | BigAutoField | no | PK | ID |
| `usuario_id` | FK → User | sí |  |  |
| `fecha` | DateTimeField | no |  |  |
| `proveedor` | CharField | no | máx. 20 |  |
| `modelo` | CharField | no | máx. 60 |  |
| `version_plantilla` | CharField | no | máx. 20 |  |
| `resultado` | CharField | no | máx. 20; valores: exito, cache, fallo, invalida, limite_diario, presupuesto, sin_consentimiento |  |
| `tipo_error` | CharField | no | máx. 60 |  |
| `latencia_ms` | PositiveIntegerField | no |  |  |
| `tokens_entrada` | PositiveIntegerField | no |  |  |
| `tokens_salida` | PositiveIntegerField | no |  |  |
| `costo_usd` | DecimalField | no | 10,6 |  |

## CacheInterpretacion (`core_cacheinterpretacion`)

Interpretaciones de frases ya vistas, para no pagar dos veces.

| Campo | Tipo | Nulo | Restricciones | Descripción |
|---|---|---|---|---|
| `id` | BigAutoField | no | PK | ID |
| `clave` | CharField | no | único; máx. 64 | SHA-256 del texto normalizado. |
| `version_plantilla` | CharField | no | máx. 20 |  |
| `resultado` | JSONField | no |  |  |
| `usos` | PositiveIntegerField | no |  |  |
| `creada_en` | DateTimeField | no |  |  |

## Bitacora (`core_bitacora`)

Auditoría funcional. Solo inserción: no se edita ni se borra.

| Campo | Tipo | Nulo | Restricciones | Descripción |
|---|---|---|---|---|
| `id` | BigAutoField | no | PK | ID |
| `usuario_id` | FK → User | sí |  |  |
| `accion` | CharField | no | máx. 60 |  |
| `entidad` | CharField | no | máx. 60 |  |
| `entidad_id` | CharField | no | máx. 40 |  |
| `detalle` | TextField | no |  |  |
| `ip` | GenericIPAddressField | sí | máx. 39 |  |
| `fecha` | DateTimeField | no |  |  |

## FraseReferencia (`core_frasereferencia`)

Frase regional con su resultado esperado, validado por un nutricionista.

| Campo | Tipo | Nulo | Restricciones | Descripción |
|---|---|---|---|---|
| `id` | BigAutoField | no | PK | ID |
| `texto` | CharField | no | máx. 500 |  |
| `componentes_esperados` | JSONField | no |  |  |
| `kcal_referencia` | DecimalField | sí | 7,1 |  |
| `validada` | BooleanField | no |  | Validada por un nutricionista. |
| `origen` | CharField | no | máx. 12; valores: inicial, correccion |  |
| `activa` | BooleanField | no |  |  |
| `creada_en` | DateTimeField | no |  |  |

## EjecucionExactitud (`core_ejecucionexactitud`)

| Campo | Tipo | Nulo | Restricciones | Descripción |
|---|---|---|---|---|
| `id` | BigAutoField | no | PK | ID |
| `version_id` | FK → VersionCatalogo | sí |  |  |
| `fecha` | DateTimeField | no |  |  |
| `total_frases` | PositiveIntegerField | no |  |  |
| `identificacion_pct` | DecimalField | no | 5,1 |  |
| `coccion_pct` | DecimalField | no | 5,1 |  |
| `error_energia_pct` | DecimalField | sí | 5,1 |  |
| `aprobada` | BooleanField | no |  |  |
| `detalle` | JSONField | no |  |  |
| `ejecutada_por_id` | FK → User | sí |  |  |
