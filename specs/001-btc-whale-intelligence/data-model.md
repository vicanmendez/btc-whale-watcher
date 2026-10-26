# Data Model: BTC Whale Intelligence

**Feature**: `001-btc-whale-intelligence`  
**Date**: 2026-10-26  
**ORM**: SQLAlchemy 2.0 (Declarative Base)  
**Storage**: SQLite (WAL Mode enabled)  
**Convención de Nombres**: Idioma español para tablas, modelos y columnas internas (Principio XVI de la Constitución), preservando identificadores técnicos estándar de protocolos y APIs externas (`txid`, `vin`, `vout`, `hash`).

---

## Diagrama Entidad-Relación (Visión General)

```text
  ┌────────────────┐       1:N       ┌───────────────────────────┐       N:1       ┌────────────────┐
  │   entidades    │ <────────────── │ atribuciones_direcciones  │ ──────────────> │  direcciones   │
  └────────────────┘                 └───────────────────────────┘                 └────────────────┘
                                                                                            ▲
                                                                                            │ 1:N
                                                                                   ┌────────────────┐
                                                                                   │saldos_historicos│
                                                                                   └────────────────┘

  ┌─────────────────────────┐       1:N       ┌────────────────────────┐
  │  transacciones_onchain  │ <────────────── │    entradas_salidas    │
  └─────────────────────────┘                 └────────────────────────┘
               │ 1:1
               ▼
  ┌─────────────────────────┐       1:1       ┌───────────────────────────────┐
  │   eventos_analizados    │ <────────────── │  caracteristicas_calculadas   │
  └─────────────────────────┘                 └───────────────────────────────┘
         │ 1:N                                                │
         │                                                    │
         ▼                                                    ▼
  ┌─────────────────────────┐                 ┌───────────────────────────────┐
  │       predicciones      │                 │         velas_mercado         │
  └─────────────────────────┘                 └───────────────────────────────┘
         │ 1:1                                (Precio y contexto temporal)
         ▼
  ┌─────────────────────────┐
  │  resultados_predicciones│
  └─────────────────────────┘
         ▲
         │ 1:N
  ┌─────────────────────────┐
  │   alertas_despachadas   │
  └─────────────────────────┘
```

---

## 1. Módulo de Entidades y Direcciones

### Tabla: `entidades`
Almacena el catálogo de actores identificados en el ecosistema.

| Columna | Tipo SQLite / SQLAlchemy | Restricciones | Descripción |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | Identificador único interno. |
| `nombre` | `VARCHAR(100)` | `NOT NULL UNIQUE` | Nombre de la entidad (ej. "Binance", "MicroStrategy"). |
| `categoria` | `VARCHAR(50)` | `NOT NULL` | `Exchange`, `Custodio`, `Empresa`, `Fondo`, `Minero`, `Gran_Tenedor`, `Desconocida`. |
| `nivel_confianza` | `FLOAT` | `NOT NULL CHECK (nivel_confianza BETWEEN 0.0 AND 1.0)` | Puntuación de certeza sobre la identificación global de la entidad. |
| `fuentes_identificacion` | `TEXT` | `NOT NULL` | Justificación documental (enlaces regulatorios, *Proof of Reserves*, informes). |
| `activo` | `BOOLEAN` | `NOT NULL DEFAULT 1` | Si la entidad se encuentra bajo monitoreo activo. |
| `creado_en` | `DATETIME` | `NOT NULL DEFAULT CURRENT_TIMESTAMP` | Marca temporal de registro. |
| `actualizado_en` | `DATETIME` | `NOT NULL DEFAULT CURRENT_TIMESTAMP` | Marca temporal de última modificación. |

### Tabla: `direcciones`
Registro único de direcciones públicas de Bitcoin observadas.

| Columna | Tipo SQLite / SQLAlchemy | Restricciones | Descripción |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | Identificador interno. |
| `direccion_btc` | `VARCHAR(100)` | `NOT NULL UNIQUE` | Dirección de Bitcoin (Base58 o Bech32/Taproot). |
| `formato` | `VARCHAR(20)` | `NOT NULL` | `P2PKH`, `P2SH`, `P2WPKH`, `P2WSH`, `P2TR`. |
| `saldo_actual_satoshis` | `BIGINT` | `NOT NULL DEFAULT 0` | Último saldo conocido en satoshis. |
| `conteo_transacciones` | `INTEGER` | `NOT NULL DEFAULT 0` | Número total de transacciones registradas. |
| `primera_vista_en` | `DATETIME` | `NOT NULL DEFAULT CURRENT_TIMESTAMP` | Fecha de detección inicial. |
| `ultima_consulta_en` | `DATETIME` | `NULL` | Fecha de la última consulta a la API on-chain. |

*Índice:* `ix_direcciones_btc (direccion_btc)`

### Tabla: `atribuciones_direcciones`
Relación N:1 documentada entre direcciones y entidades. Cumple el Principio III y IV.

| Columna | Tipo SQLite / SQLAlchemy | Restricciones | Descripción |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | Identificador interno. |
| `direccion_id` | `INTEGER` | `NOT NULL REFERENCES direcciones(id) ON DELETE CASCADE` | Llave foránea hacia dirección. |
| `entidad_id` | `INTEGER` | `NOT NULL REFERENCES entidades(id) ON DELETE CASCADE` | Llave foránea hacia entidad. |
| `grado_certeza` | `FLOAT` | `NOT NULL CHECK (grado_certeza BETWEEN 0.0 AND 1.0)` | Nivel de confianza de esta atribución específica. |
| `fuente_atribucion` | `TEXT` | `NOT NULL` | Evidencia precisa de la atribución. |
| `fecha_verificacion` | `DATE` | `NOT NULL` | Fecha en que se verificó la evidencia. |
| `activo` | `BOOLEAN` | `NOT NULL DEFAULT 1` | Si la atribución se mantiene válida. |

*Restricción Única:* `UNIQUE(direccion_id, entidad_id)`

---

## 2. Módulo On-Chain

### Tabla: `transacciones_onchain`
Registro factual e inmutable de transacciones procesadas (Principio III).

| Columna | Tipo SQLite / SQLAlchemy | Restricciones | Descripción |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | Identificador interno. |
| `txid` | `VARCHAR(64)` | `NOT NULL UNIQUE` | Hash de la transacción de Bitcoin (preservado de API externa). |
| `bloque_altura` | `INTEGER` | `NULL` | Altura del bloque (`NULL` si está en mempool). |
| `bloque_hash` | `VARCHAR(64)` | `NULL` | Hash del bloque (`NULL` si está en mempool). |
| `marca_tiempo_utc` | `DATETIME` | `NOT NULL` | Fecha y hora UTC del bloque o recepción en mempool. |
| `total_entrada_satoshis` | `BIGINT` | `NOT NULL` | Suma de todas las entradas en satoshis. |
| `total_salida_satoshis` | `BIGINT` | `NOT NULL` | Suma de todas las salidas en satoshis. |
| `comision_satoshis` | `BIGINT` | `NOT NULL` | Comisión de red pagada (`entradas - salidas`). |
| `tamano_bytes` | `INTEGER` | `NOT NULL` | Tamaño en bytes de la transacción. |
| `peso_vbytes` | `INTEGER` | `NOT NULL` | Peso virtual en vBytes. |
| `confirmaciones` | `INTEGER` | `NOT NULL DEFAULT 0` | Número de confirmaciones acumuladas. |
| `es_mempool` | `BOOLEAN` | `NOT NULL DEFAULT 0` | 1 si la transacción no ha sido confirmada aún. |
| `creado_en` | `DATETIME` | `NOT NULL DEFAULT CURRENT_TIMESTAMP` | Registro en base de datos. |

*Índices:* `ix_transacciones_txid (txid)`, `ix_transacciones_bloque (bloque_altura)`

### Tabla: `entradas_salidas`
Detalle de inputs y outputs para permitir análisis de flujos y reconstrucción.

| Columna | Tipo SQLite / SQLAlchemy | Restricciones | Descripción |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | Identificador interno. |
| `transaccion_id` | `INTEGER` | `NOT NULL REFERENCES transacciones_onchain(id) ON DELETE CASCADE` | Llave foránea de transacción. |
| `tipo` | `VARCHAR(10)` | `NOT NULL CHECK (tipo IN ('ENTRADA', 'SALIDA'))` | Tipo de flujo. |
| `indice` | `INTEGER` | `NOT NULL` | Índice `vin` o `vout` en la transacción. |
| `direccion_id` | `INTEGER` | `NULL REFERENCES direcciones(id) ON DELETE SET NULL` | Dirección asociada si es decodificable. |
| `monto_satoshis` | `BIGINT` | `NOT NULL` | Importe involucrado en satoshis. |

*Restricción Única:* `UNIQUE(transaccion_id, tipo, indice)`

### Tabla: `saldos_historicos`
Captura de saldo por dirección a lo largo del tiempo para calcular deltas.

| Columna | Tipo SQLite / SQLAlchemy | Restricciones | Descripción |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | Identificador interno. |
| `direccion_id` | `INTEGER` | `NOT NULL REFERENCES direcciones(id) ON DELETE CASCADE` | Dirección. |
| `bloque_altura` | `INTEGER` | `NOT NULL` | Altura del bloque del saldo. |
| `saldo_satoshis` | `BIGINT` | `NOT NULL` | Saldo resultante en ese bloque. |
| `marca_tiempo_utc` | `DATETIME` | `NOT NULL` | Marca temporal del bloque. |

*Restricción Única:* `UNIQUE(direccion_id, bloque_altura)`

---

## 3. Módulo de Mercado

### Tabla: `velas_mercado`
Datos históricos y recientes de cotización spot de BTC/USDT.

| Columna | Tipo SQLite / SQLAlchemy | Restricciones | Descripción |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | Identificador interno. |
| `intervalo` | `VARCHAR(10)` | `NOT NULL` | Temporalidad (`1m`, `1h`, `1d`). |
| `marca_tiempo_apertura` | `DATETIME` | `NOT NULL` | Hora de inicio de la vela UTC. |
| `precio_apertura` | `FLOAT` | `NOT NULL` | Precio de apertura en USDT. |
| `precio_maximo` | `FLOAT` | `NOT NULL` | Precio máximo en USDT. |
| `precio_minimo` | `FLOAT` | `NOT NULL` | Precio mínimo en USDT. |
| `precio_cierre` | `FLOAT` | `NOT NULL` | Precio de cierre en USDT. |
| `volumen_btc` | `FLOAT` | `NOT NULL` | Volumen transaccionado en BTC. |
| `volumen_usdt` | `FLOAT` | `NOT NULL` | Volumen transaccionado en USDT. |
| `conteo_operaciones` | `INTEGER` | `NOT NULL DEFAULT 0` | Número de intercambios (*trades*). |
| `fuente` | `VARCHAR(50)` | `NOT NULL DEFAULT 'Binance'` | Proveedor de la cotización. |

*Restricción Única:* `UNIQUE(intervalo, marca_tiempo_apertura, fuente)`  
*Índice:* `ix_velas_tiempo (intervalo, marca_tiempo_apertura)`

---

## 4. Módulo de Análisis y Predicciones

### Tabla: `eventos_analizados`
Eventos on-chain calificados que superan los umbrales de relevancia.

| Columna | Tipo SQLite / SQLAlchemy | Restricciones | Descripción |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | Identificador interno. |
| `transaccion_id` | `INTEGER` | `NOT NULL UNIQUE REFERENCES transacciones_onchain(id)` | Transacción disparadora. |
| `entidad_origen_id` | `INTEGER` | `NULL REFERENCES entidades(id)` | Entidad atribuida al origen (si existe evidencia). |
| `entidad_destino_id` | `INTEGER` | `NULL REFERENCES entidades(id)` | Entidad atribuida al destino (si existe evidencia). |
| `monto_total_btc` | `FLOAT` | `NOT NULL` | Monto total en BTC del evento. |
| `categoria_movimiento` | `VARCHAR(50)` | `NOT NULL` | `TRANSFERENCIA_INTERNA`, `ENTRADA_EXCHANGE`, `SALIDA_EXCHANGE`, `MOVIMIENTO_CORPORATIVO`, `DESCONOCIDA`, `INCIERTA`. |
| `nivel_confianza` | `FLOAT` | `NOT NULL` | Certeza de la categorización (0.0 a 1.0). |
| `evidencia` | `TEXT` | `NOT NULL` | Detalle objetivo de las direcciones identificadas. |
| `limitaciones` | `TEXT` | `NOT NULL` | Supuestos y restricciones del análisis (Principio V). |
| `precio_referencia_btc` | `FLOAT` | `NOT NULL` | Precio de BTC spot al momento del evento. |
| `marca_tiempo_evento` | `DATETIME` | `NOT NULL` | Marca temporal UTC del evento. |

### Tabla: `caracteristicas_calculadas`
Variables cuantitativas calculadas en el instante del evento usando **exclusivamente datos pasados** (Principio VII).

| Columna | Tipo SQLite / SQLAlchemy | Restricciones | Descripción |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | Identificador interno. |
| `evento_id` | `INTEGER` | `NOT NULL UNIQUE REFERENCES eventos_analizados(id) ON DELETE CASCADE` | Evento asociado. |
| `ratio_monto_volumen_24h` | `FLOAT` | `NOT NULL` | Monto del evento / Volumen 24h de BTC. |
| `variacion_precio_1h_pct` | `FLOAT` | `NOT NULL` | Retorno porcentual de BTC en la hora previa. |
| `variacion_precio_24h_pct` | `FLOAT` | `NOT NULL` | Retorno porcentual de BTC en las 24 horas previas. |
| `volatilidad_historica_7d` | `FLOAT` | `NOT NULL` | Desviación estándar anualizada de retornos horarios en 7d previos. |
| `flujo_neto_entidad_24h_btc`| `FLOAT` | `NULL` | Acumulado neto de entradas - salidas de la entidad en 24h. |
| `profundidad_compra_2pct_usd`| `FLOAT` | `NULL` | Liquidez disponible en bids a 2% del precio (si disponible). |
| `profundidad_venta_2pct_usd` | `FLOAT` | `NULL` | Liquidez disponible en asks a 2% del precio (si disponible). |

### Tabla: `predicciones`
Pre-registro inmutable de pronósticos antes de conocer el resultado (Principio IX).

| Columna | Tipo SQLite / SQLAlchemy | Restricciones | Descripción |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | Identificador interno. |
| `evento_id` | `INTEGER` | `NOT NULL REFERENCES eventos_analizados(id) ON DELETE CASCADE` | Evento evaluado. |
| `horizonte` | `VARCHAR(10)` | `NOT NULL CHECK (horizonte IN ('24H', '7D', '30D'))` | Ventana temporal de evaluación. |
| `marca_tiempo_registro` | `DATETIME` | `NOT NULL DEFAULT CURRENT_TIMESTAMP` | Marca temporal inmutable del registro previo. |
| `fecha_vencimiento_utc` | `DATETIME` | `NOT NULL` | Momento exacto en que termina el horizonte temporal. |
| `precio_inicial_usd` | `FLOAT` | `NOT NULL` | Precio de referencia de inicio del cálculo. |
| `estado` | `VARCHAR(20)` | `NOT NULL DEFAULT 'INDETERMINADO'` | `ACTIVA`, `INDETERMINADA`, `EVALUADA`. |
| `probabilidad_alcista` | `FLOAT` | `NULL CHECK (probabilidad_alcista BETWEEN 0.0 AND 1.0)` | P(R > +umbral). `NULL` si es Indeterminado. |
| `probabilidad_bajista` | `FLOAT` | `NULL CHECK (probabilidad_bajista BETWEEN 0.0 AND 1.0)` | P(R < -umbral). `NULL` si es Indeterminado. |
| `probabilidad_neutral` | `FLOAT` | `NULL CHECK (probabilidad_neutral BETWEEN 0.0 AND 1.0)` | P(|R| <= umbral). `NULL` si es Indeterminado. |
| `retorno_esperado_pct` | `FLOAT` | `NULL` | Estimación puntual del retorno medio. |
| `rango_incertidumbre_inferior`| `FLOAT` | `NULL` | Límite inferior intervalo de confianza 95%. |
| `rango_incertidumbre_superior`| `FLOAT` | `NULL` | Límite superior intervalo de confianza 95%. |
| `razon_indeterminacion` | `TEXT` | `NULL` | Explicación obligatoria si estado = INDETERMINADO. |
| `modelo_version` | `VARCHAR(50)` | `NOT NULL` | Identificador del algoritmo o "v1.0-observacional". |

*Restricción Única:* `UNIQUE(evento_id, horizonte)`

### Tabla: `resultados_predicciones`
Evaluación retrospectiva contra la realidad y contra los dos baselines obligatorios (Principio VIII).

| Columna | Tipo SQLite / SQLAlchemy | Restricciones | Descripción |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | Identificador interno. |
| `prediccion_id` | `INTEGER` | `NOT NULL UNIQUE REFERENCES predicciones(id) ON DELETE CASCADE` | Predicción evaluada. |
| `precio_final_usd` | `FLOAT` | `NOT NULL` | Precio spot observado al cierre del horizonte. |
| `retorno_real_pct` | `FLOAT` | `NOT NULL` | `((precio_final - precio_inicial) / precio_inicial) * 100`. |
| `resultado_categoria` | `VARCHAR(10)` | `NOT NULL` | `ALCISTA`, `BAJISTA`, `NEUTRAL`. |
| `acierto_clasificacion` | `BOOLEAN` | `NULL` | 1 si la clase mayoritaria predicha coincidió con la realidad. |
| `brier_score` | `FLOAT` | `NULL` | Métrica de calibración probabilística cuadrática. |
| `retorno_baseline_buy_hold` | `FLOAT` | `NOT NULL` | Retorno de mantener BTC pasivamente en el mismo periodo. |
| `retorno_baseline_persistencia` | `FLOAT` | `NOT NULL` | Error del supuesto de que el precio no cambiaría (cero retorno). |
| `evaluado_en` | `DATETIME` | `NOT NULL DEFAULT CURRENT_TIMESTAMP` | Marca temporal del cálculo retrospectivo. |

---

## 5. Módulo de Alertas y Operación

### Tabla: `alertas_despachadas`
Garantiza el control de duplicados y la trazabilidad de notificaciones enviadas (Principio X y XI).

| Columna | Tipo SQLite / SQLAlchemy | Restricciones | Descripción |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | Identificador interno. |
| `evento_id` | `INTEGER` | `NOT NULL REFERENCES eventos_analizados(id)` | Evento que detonó la alerta. |
| `hash_idempotencia` | `VARCHAR(64)` | `NOT NULL UNIQUE` | `SHA256(evento_id + canal + tipo_alerta)` para evitar envíos repetidos. |
| `canal` | `VARCHAR(20)` | `NOT NULL DEFAULT 'EMAIL_SMTP'` | Canal de comunicación. |
| `destinatario` | `VARCHAR(100)` | `NOT NULL` | Dirección de correo del receptor. |
| `asunto` | `VARCHAR(200)` | `NOT NULL` | Asunto del mensaje. |
| `cuerpo_resumen` | `TEXT` | `NOT NULL` | Contenido resumido enviado. |
| `estado` | `VARCHAR(20)` | `NOT NULL` | `ENVIADO`, `REINTENTO`, `FALLIDO`. |
| `intentos` | `INTEGER` | `NOT NULL DEFAULT 1` | Número de reintentos realizados. |
| `despachado_en` | `DATETIME` | `NOT NULL DEFAULT CURRENT_TIMESTAMP` | Fecha y hora UTC del envío. |

### Tabla: `estado_ingesta`
Rastrea el último bloque/transacción procesada para recuperación ante fallos y control de salud.

| Columna | Tipo SQLite / SQLAlchemy | Restricciones | Descripción |
| :--- | :--- | :--- | :--- |
| `fuente` | `VARCHAR(50)` | `PRIMARY KEY` | Identificador de la fuente (ej. `mempool_space`, `binance_market`). |
| `ultimo_bloque_procesado` | `INTEGER` | `NOT NULL DEFAULT 0` | Altura de bloque sincronizada. |
| `ultimo_hash_procesado` | `VARCHAR(64)` | `NULL` | Hash del último bloque confirmado. |
| `ultima_sincronizacion_utc` | `DATETIME` | `NOT NULL DEFAULT CURRENT_TIMESTAMP` | Momento de última ejecución exitosa. |
| `conteo_errores_consecutivos`| `INTEGER` | `NOT NULL DEFAULT 0` | Contador para alertas operativas. |
| `ultimo_error` | `TEXT` | `NULL` | Detalle del último mensaje de excepción. |
