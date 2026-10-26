# Feature Specification: BTC Whale Intelligence

**Feature Branch**: `001-btc-whale-intelligence`

**Created**: 2026-10-26

**Status**: Approved

**Input**: User description: "Desarrolla la especificación funcional de BTC Whale Intelligence, una plataforma de análisis on-chain que detecta movimientos de grandes entidades vinculadas a Bitcoin y estima su posible impacto en el precio de BTC a corto y medio plazo."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Gestión de Catálogo de Entidades y Direcciones Atribuidas (Priority: P1)

Un inversor particular o analista de mercado desea configurar y consultar un catálogo de entidades conocidas (exchanges, custodios institucionales, empresas con reservas de Bitcoin y billeteras de grandes tenedores), importando direcciones verificadas desde fuentes públicas o archivos locales (CSV/JSON), registrando la procedencia y el nivel de certeza de cada atribución sin dar por sentado que una dirección pertenece a una entidad sin pruebas documentadas.

**Why this priority**: Es la base ontológica del sistema; sin entidades ni direcciones mapeadas y respaldadas, no es posible atribuir transacciones ni realizar análisis contextuales fidedignos.

**Independent Test**: Puede probarse de forma aislada importando un conjunto de entidades y direcciones desde un archivo CSV de prueba y verificando que el catálogo mantiene las atribuciones con su procedencia, fecha y nivel de confianza, rechazando registros mal formados o no respaldados.

**Acceptance Scenarios**:

1. **Given** un catálogo vacío o existente y un archivo con direcciones y metadatos de entidades (ej. exchanges o fondos), **When** el usuario ejecuta la importación, **Then** el sistema almacena las entidades y asocia las direcciones catalogando su origen, fecha de verificación y grado de certeza, distinguiéndolas claramente de las direcciones no identificadas.
2. **Given** una dirección sin evidencia de vinculación a una entidad, **When** el sistema la procesa, **Then** se clasifica como entidad desconocida y no se le asigna ninguna pertenencia arbitraria.

---

### User Story 2 - Monitoreo On-Chain y Detección de Movimientos Relevantes (Priority: P1)

El sistema monitorea periódicamente la blockchain de Bitcoin a través de APIs públicas gratuitas para registrar transacciones, detectar transferencias que superen los umbrales configurados y agrupar los flujos netos por entidad, distinguiendo transacciones confirmadas de aquellas en mempool y evitando procesar transacciones duplicadas.

**Why this priority**: Constituye el núcleo operacional continuo de la plataforma: sin captura y procesamiento de eventos on-chain fiables, no se pueden disparar análisis ni generar alertas.

**Independent Test**: Puede probarse de manera autónoma suministrando un feed simulado o real de bloques/mempool con transacciones conocidas y comprobando que se identifican los movimientos mayores al umbral, se calculan las variaciones netas por entidad y no se duplican registros ante reintentos.

**Acceptance Scenarios**:

1. **Given** un umbral de detección configurado, **When** se observa una transacción en la que intervienen direcciones catalogadas o cuyo volumen supera el umbral, **Then** el sistema registra el evento con su identificador, entradas, salidas, montos, marcas temporales y direcciones, marcando su estado (confirmado o mempool).
2. **Given** una transacción ya procesada previamente, **When** el colector vuelve a consultar el bloque o la dirección, **Then** el sistema reconoce el identificador existente y evita duplicar registros o alertas.
3. **Given** una transferencia entre dos direcciones que no cuentan con evidencia suficiente de pertenecer a la misma entidad, **When** se realiza el cálculo de saldo, **Then** el sistema no asume transferencia interna ni concluye independencia sin soporte de datos.

---

### User Story 3 - Enriquecimiento de Contexto de Mercado y Clasificación No Sesgada (Priority: P2)

Al detectarse un movimiento relevante, el sistema recolecta automáticamente el contexto del mercado de Bitcoin (precio spot reciente, volatilidad histórica, variaciones porcentuales previas y volumen negociado en múltiples ventanas temporales) y clasifica el movimiento en categorías formales (entrada a exchange, salida de exchange, movimiento corporativo, reorganización interna o entidad desconocida), declarando las limitaciones y prohibiendo calificar el evento automáticamente como "compra" o "venta".

**Why this priority**: Evita el error crítico de interpretar transferencias en crudo sin contexto macro ni microeconómico, asegurando que el análisis cumpla la constitución del proyecto en cuanto a imparcialidad y rigor causal.

**Independent Test**: Puede validarse de forma independiente procesando un evento on-chain histórico y verificando que el reporte generado adjunta los datos de mercado del momento exacto del evento y clasifica el movimiento sin afirmaciones de compra/venta no fundamentadas.

**Acceptance Scenarios**:

1. **Given** un movimiento relevante confirmado hacia una dirección perteneciente a un exchange, **When** se procesa el evento, **Then** el sistema lo clasifica como "Entrada a dirección de exchange", asocia los datos de precio, volumen y volatilidad de BTC en ventanas de 1h, 24h y 7d, y explicita el nivel de confianza y limitaciones de la inferencia.
2. **Given** datos de libro de órdenes o liquidez no disponibles en la fuente gratuita consultada, **When** se genera el contexto, **Then** el sistema deja explícita la ausencia de dicha métrica sin detener el flujo general ni alterar los demás cálculos.

---

### User Story 4 - Análisis Probabilístico de Impacto, Pre-registro y Evaluación con Baselines (Priority: P2)

Para cada movimiento calificado, el sistema genera estimaciones probabilísticas independientes para horizontes de 0–24 horas, 1–7 días y 8–30 días (probabilidad de retorno positivo, negativo o neutral dentro de rangos definidos), pre-registrando la predicción de forma inmutable antes de que transcurra el tiempo y contrastándola a posteriori contra referencias simples (*Buy & Hold* y persistencia de precio).

**Why this priority**: Proporciona el valor analítico diferencial para la toma de decisiones informada del inversor, garantizando la honestidad metodológica al impedir la manipulación retrospectiva.

**Independent Test**: Puede probarse ejecutando el evaluador sobre una serie de predicciones históricas simuladas o pasadas, constatando que el sistema evalúa métricas como Brier score y error absoluto frente a los baselines y emite estado "indeterminado" cuando faltan datos suficientes.

**Acceptance Scenarios**:

1. **Given** un evento clasificado y un modelo validado estadísticamente fuera de muestra, **When** se ejecuta el análisis de impacto, **Then** el sistema genera una estimación con su horizonte temporal, intervalo de incertidumbre, evidencia considerada y la almacena con marca temporal inmutable antes del resultado.
2. **Given** un escenario donde los datos de mercado u on-chain son insuficientes o el modelo carece de validación fuera de muestra, **When** se solicita la estimación, **Then** el sistema responde con estado "Indeterminado", detallando exactamente los datos o pruebas faltantes.
3. **Given** una predicción cuyo horizonte temporal ha finalizado, **When** se ejecuta la rutina de evaluación retrospectiva, **Then** el sistema compara el resultado real observado contra la predicción y contra los baselines de mantener BTC y precio sin cambios.

---

### User Story 5 - Notificaciones por Alerta y Resumen Diario Consolidado (Priority: P3)

El usuario recibe alertas en tiempo real vía correo electrónico ante eventos relevantes y predicciones completadas, junto con un resumen diario periódico que consolida las entidades más activas, los flujos netos observados, el contexto general del mercado y el desempeño de las predicciones evaluadas en el periodo.

**Why this priority**: Garantiza que el inversor particular esté informado oportunamente sin necesidad de supervisar continuamente una consola o base de datos.

**Independent Test**: Puede probarse configurando un destinatario de prueba y simulando la activación de un evento relevante y el cierre del ciclo diario, verificando la estructura, claridad y enlaces de los correos emitidos sin duplicidad.

**Acceptance Scenarios**:

1. **Given** la detección de un movimiento relevante, **When** se completa la clasificación y el análisis de impacto, **Then** el sistema despacha un correo con los datos clave (entidad, importe, direcciones, clasificación, horizonte, probabilidades, incertidumbre y enlace al explorador de bloques).
2. **Given** el horario configurado para el reporte diario, **When** se ejecuta la tarea programada, **Then** el sistema compila y envía el boletín resumen con la actividad agregada y la evaluación de precisión reciente.

---

### Edge Cases

- **Congestión del mempool y reorganizaciones de cadena (reorgs):** Transacciones que son reemplazadas (RBF) o bloques huérfanos que invalidan transacciones previamente registradas como confirmadas. El sistema debe rastrear el número de confirmaciones y actualizar el estado si una transacción es revertida o modificada.
- **Transacciones complejas con múltiples entradas y salidas (CoinJoin / Batched Payouts):** Transacciones de exchanges con cientos de salidas o transacciones de mezcla donde vincular entradas con salidas directas no es trivial. El sistema debe registrar la transacción sin atribuir indebidamente propiedad individual de todo el importe a una sola entidad.
- **Saturación o caída temporal de APIs públicas:** Si una API de explorador público aplica límite de tasa (*HTTP 429*) o no responde (*HTTP 5xx*), el sistema debe pausar con retroceso exponencial (*exponential backoff*) y reanudar la sincronización desde el último bloque/transacción procesada sin duplicar registros.
- **Falta de liquidez o desalineación horaria en datos de mercado:** Si las cotizaciones de mercado presentan desfases temporales respecto al bloque, el sistema debe asociar el precio y volumen más cercanos disponibles dentro de una ventana máxima de tolerancia, indicando la discrepancia temporal en los metadatos.
- **Fallo en el servicio de despacho de correos:** Si el servidor SMTP no está accesible, la alerta debe encolarse para reintento posterior sin bloquear la recolección continua on-chain ni reenviar alertas ya entregadas.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE mantener un catálogo persistente de entidades identificadas (exchanges, custodios, empresas, fondos y grandes tenedores individuales), registrando obligatoriamente: nombre, categoría, fuentes documentadas de identificación, nivel de confianza y listado de direcciones atribuidas.
- **FR-002**: El sistema DEBE permitir la incorporación y actualización de direcciones mediante archivos locales (CSV/JSON) y mecanismos de consulta automatizada, registrando origen, fecha de verificación y grado de confianza, diferenciando taxativamente direcciones identificadas de no identificadas.
- **FR-003**: El sistema DEBE consultar saldos y transacciones on-chain mediante APIs públicas gratuitas, registrando `txid`, entradas (`vin`), salidas (`vout`), importes, marcas de tiempo, número de confirmaciones y direcciones involucradas.
- **FR-004**: El sistema DEBE garantizar la idempotencia en el procesamiento de transacciones, impidiendo procesar o alertar dos veces sobre una misma transacción ya registrada.
- **FR-005**: El sistema DEBE distinguir formalmente las transacciones confirmadas en bloque de aquellas en estado pendiente dentro del mempool.
- **FR-006**: El sistema DEBE agregar saldos y movimientos por entidad para calcular flujos netos únicamente cuando las direcciones asociadas cuenten con evidencia suficiente, absteniéndose de asumir transferencias internas o independencia entre direcciones sin respaldo explícito.
- **FR-007**: El sistema DEBE permitir configurar umbrales de relevancia, adoptando como valor por defecto una segmentación por categoría: transferencias >= 500 BTC para direcciones de exchanges, >= 250 BTC para corporaciones y custodios institucionales, y >= 1,000 BTC para entidades desconocidas, activándose además ante cualquier variación neta de saldo en entidades catalogadas activas.
- **FR-008**: El sistema DEBE obtener y persistir el contexto de mercado de BTC (precio, volumen, volatilidad histórica y variaciones porcentuales en múltiples ventanas temporales) asociado al momento de cada movimiento relevante.
- **FR-009**: El sistema DEBE clasificar cada evento on-chain relevante en categorías normalizadas (transferencia interna con evidencia, entrada a exchange, salida de exchange, movimiento corporativo, entidad desconocida, o clasificación incierta), adjuntando evidencia, nivel de confianza y limitaciones.
- **FR-010**: El sistema NO DEBE clasificar ni inferir automáticamente ninguna transferencia on-chain como una "compra" o "venta".
- **FR-011**: Para cada evento relevante calificado, el sistema DEBE generar un análisis de impacto independiente para horizontes iniciales de: muy corto plazo (0–24h), corto plazo (1–7d) y medio plazo (8–30d).
- **FR-012**: El análisis de impacto DEBE calcular, cuando el modelo y los datos lo justifiquen: probabilidad de rendimiento positivo, negativo y neutral, rendimiento esperado con rango de incertidumbre y métricas de riesgo adverso; y DEBE devolver estado "Indeterminado" con justificación expresa cuando falte evidencia o el modelo no esté validado fuera de muestra.
- **FR-013**: En la versión v1, el motor analítico operará en modo "Indeterminado / Recolección y Calibración": el sistema registrará los eventos on-chain, asociará el contexto de mercado y pre-registrará las observaciones para evaluación histórica, pero emitirá formalmente estado "Indeterminado" en las estimaciones probabilísticas de retorno hasta completar un periodo de recolección y backtesting fuera de muestra con significancia estadística demostrada (cumpliendo estrictamente los Principios V, VII, VIII y XV de la Constitución).
- **FR-014**: El sistema DEBE pre-registrar de forma inmutable toda estimación antes de conocer el resultado del horizonte temporal, asociando la estampa de tiempo exacta y los datos que estaban disponibles al generarla.
- **FR-015**: El sistema DEBE ejecutar evaluaciones históricas retrospectivas continuas sin contaminación futura (*lookahead bias*), computando métricas de calibración (ej. Brier score) y contrastando obligatoriamente los resultados contra las referencias (*baselines*) de mantener BTC (*Buy & Hold*) y persistencia de precio.
- **FR-016**: El sistema DEBE enviar alertas estructuradas ante eventos relevantes exclusivamente mediante correo electrónico (protocolo SMTP estándar o servidor local) en la versión v1, deduplicando los envíos, incluyendo enlaces directos al explorador de bloques y manteniendo una arquitectura desacoplada para admitir adaptadores adicionales (Telegram, webhooks) en fases futuras.
- **FR-017**: El sistema DEBE compilar y enviar un informe periódico diario con el resumen de las entidades más activas, movimientos destacados, variaciones netas de saldo, contexto de mercado y resultados de predicciones evaluadas.
- **FR-018**: El sistema DEBE mantener un registro de auditoría y observabilidad que capture fallos de conexión, límites de tasa (*rate limits*) con retroceso exponencial, datos truncados y reintentos, permitiendo reanudar la ejecución sin pérdida ni corrupción de datos.
- **FR-019**: Toda la configuración operativa (umbrales, intervalos de muestreo, horizontes temporales, claves/rutas de APIs, credenciales de notificación y parámetros de modelos) DEBE ser gestionable externamente mediante variables de entorno y archivos de configuración sin modificar el código fuente.

### Key Entities *(include if feature involves data)*

- **Entidad**: Representa un participante o actor reconocido del ecosistema Bitcoin. Atributos: `identificador_entidad`, `nombre`, `categoria` (Exchange, Custodio, Empresa, Fondo, Minero, Gran Tenedor, Desconocida), `nivel_confianza`, `fuentes_verificacion`, `fecha_registro`, `notas`.
- **DireccionAtribuida**: Dirección de Bitcoin asociada a una entidad. Atributos: `direccion_btc`, `identificador_entidad`, `fecha_vinculacion`, `grado_certeza`, `fuente_atribucion`, `saldo_actual_satoshis`, `ultima_actualizacion`.
- **TransaccionOnChain**: Evento factual observado en la blockchain. Atributos: `txid`, `bloque_altura`, `bloque_hash`, `marca_tiempo_utc`, `entradas_total_satoshis`, `salidas_total_satoshis`, `comision_satoshis`, `confirmaciones`, `es_mempool`, `entradas_detalle`, `salidas_detalle`.
- **MovimientoRelevante**: Instancia de transacción o conjunto de transacciones que superan los filtros de interés. Atributos: `identificador_movimiento`, `txid`, `entidad_origen_id`, `entidad_destino_id`, `monto_total_btc`, `tipo_clasificacion`, `nivel_confianza`, `evidencia_clasificacion`, `limitaciones_declaradas`, `marca_tiempo_deteccion`.
- **ContextoMercado**: Instantánea de las condiciones del mercado al momento de un evento. Atributos: `identificador_contexto`, `marca_tiempo_utc`, `precio_btc_usd`, `volumen_24h_usd`, `volatilidad_24h`, `volatilidad_7d`, `variacion_precio_1h_pct`, `variacion_precio_24h_pct`, `profundidad_mercado_disponible`.
- **EstimacionImpacto**: Predicción probabilística registrada previamente al desenlace. Atributos: `identificador_estimacion`, `identificador_movimiento`, `horizonte_temporal` (24h, 7d, 30d), `marca_tiempo_registro`, `probabilidad_alcista`, `probabilidad_bajista`, `probabilidad_neutral`, `retorno_esperado_pct`, `rango_incertidumbre`, `estado_validez` (Activa, Indeterminada, Evaluada), `razon_indeterminacion`, `version_modelo`.
- **EvaluacionHistorica**: Resultado a posteriori contrastado con la realidad. Atributos: `identificador_evaluacion`, `identificador_estimacion`, `precio_inicial_usd`, `precio_final_usd`, `retorno_real_pct`, `acierto_clasificacion`, `brier_score`, `retorno_baseline_buy_hold`, `retorno_baseline_persistencia`, `fecha_cierre_horizonte`.
- **AlertaDespachada**: Registro de auditoría de notificaciones enviadas. Atributos: `identificador_alerta`, `identificador_movimiento`, `identificador_estimacion`, `canal_envio`, `destinatario`, `marca_tiempo_despacho`, `estado_envio`, `contenido_resumen`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El sistema debe detectar, almacenar y contextualizar cualquier movimiento on-chain relevante dentro de los 5 minutos siguientes a su inclusión en bloque o aparición en mempool.
- **SC-002**: El sistema debe garantizar una tasa del 0% de transacciones y alertas duplicadas ante interrupciones de red o reinicios de servicio.
- **SC-003**: El 100% de los movimientos clasificados y alertas generadas deben incluir de forma explícita su categoría analítica, nivel de confianza, evidencia empírica y limitaciones metodológicas, sin términos especulativos de compra/venta automática.
- **SC-004**: El 100% de las estimaciones analíticas evaluadas deben haber sido registradas con sello temporal antes de la ventana evaluada, sin permitir adiciones retroactivas.
- **SC-005**: Todo reporte de rendimiento de modelos debe exhibir su comparación contra los dos baselines obligatorios (*Buy & Hold* y persistencia de precio).
- **SC-006**: La plataforma debe poder operar de forma ininterrumpida durante 30 días en un entorno Linux con 1–2 vCPUs y máximo 4 GB de RAM consumiendo exclusivamente APIs gratuitas dentro de sus cuotas sin incurrir en suspensiones por límite de tasa (*rate limit*).
- **SC-007**: El 100% de las transacciones con saldos o datos incompletos en fuentes externas deben resultar en un estado "Indeterminado" documentado, sin generar probabilidades artificiales ni interrumpir la recolección.
- **SC-008**: Los despachos de alertas por correo electrónico deben ejecutarse en menos de 60 segundos tras completarse el análisis de contexto del movimiento.

## Assumptions

- **Disponibilidad de fuentes gratuitas:** Se asume que las APIs públicas de exploradores de Bitcoin (como mempool.space o Blockstream.info) y de mercado spot (como CoinGecko o Binance pública) mantienen cuotas gratuitas suficientes para un monitoreo periódico cada pocos minutos sin costo de suscripción.
- **Atribución incremental de billeteras:** Se asume que en la versión inicial las agrupaciones de direcciones de entidades requerirán una base de datos semilla proporcionada por archivos CSV/JSON construidos a partir de divulgaciones públicas, repositorios abiertos y reportes de prueba de reservas (*Proof of Reserves*).
- **Desarrollo iterativo de modelos:** Se asume que la capacidad predictiva no está garantizada inicialmente y que el sistema priorizará la observación honesta, el registro inmutable y la calibración empírica antes de validar formalmente cualquier modelo para consumo final.
- **Entorno de ejecución:** Se asume un servidor Linux (ej. Ubuntu Server 22.04 LTS / Debian 12) con Python 3.10+ y acceso saliente a internet por puertos estándar HTTP/HTTPS (80/443) y SMTP (587/465).
- **Ausencia de operaciones comerciales:** Se asume expresamente que el sistema no gestionará carteras privadas, no custodiará claves de criptomonedas ni ejecutará transacciones financieras de ningún tipo.
