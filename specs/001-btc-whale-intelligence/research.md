# Research & Architecture Decisions: BTC Whale Intelligence

**Feature**: `001-btc-whale-intelligence`  
**Date**: 2026-10-26  
**Status**: Completed  

---

## 1. Ingesta de Datos On-Chain

### Decisión
Utilizar la API REST pública de **Mempool.space** (`https://mempool.space/api/`) como fuente primaria, implementando un adaptador intercambiable compatible con **Blockstream Esplora** (`https://blockstream.info/api/`) como fuente de respaldo automática.

### Razón
- Mempool.space y Blockstream Esplora comparten esencialmente la misma especificación de API abierta (Esplora API), lo que permite usar el mismo contrato de deserialización para ambas fuentes con mínima duplicación.
- Mempool.space ofrece endpoints gratuitos sin necesidad de clave de API para:
  - Último bloque y estado de la cadena (`/api/blocks/tip/height`, `/api/blocks/tip/hash`).
  - Bloques recientes y transacciones de un bloque (`/api/block/:hash/txs`).
  - Mempool reciente y transacciones prioritarias (`/api/mempool/recent`).
  - Información de transacciones (`/api/tx/:txid`).
  - Historial y saldos de direcciones (`/api/address/:address`).
- Límites razonables: Permite hasta 10–15 solicitudes por segundo en uso no abusivo. Se implementará un regulador de tasa local (*rate limiter*) con retroceso exponencial (*exponential backoff*).

### Alternativas Evaluadas
- **Nodo completo local de Bitcoin Core (bitcoind):** Ofrece soberanía y datos 100% locales, pero requiere >600 GB de almacenamiento SSD y CPU/RAM incompatibles con un VPS Linux modesto de 2–4 GB de RAM a bajo coste. Queda como opción futura para usuarios avanzados.
- **APIs comerciales (Glassnode, CryptoQuant, Nansen):** Rechazadas categóricamente por infringir el Principio II y XVIII de la Constitución (requieren suscripciones de cientos de dólares al mes).
- **Blockchain.com API pública:** Históricamente inestable con límites estrictos de tasa y sin soporte completo para formatos de direcciones modernos de Bitcoin (Bech32/Taproot) tan actualizado como Esplora.

---

## 2. Ingesta de Datos de Mercado Spot

### Decisión
Utilizar la API REST pública de **Binance** (`https://api.binance.com/api/v3/`) como fuente principal de cotización spot de BTC/USDT, con fallback a **CoinGecko API pública** (`https://api.coingecko.com/api/v3/`).

### Razón
- Binance Public API no requiere clave de API para datos públicos de mercado y provee:
  - Velas históricas y recientes (`/api/v3/klines` con intervalos de 1m, 1h, 1d).
  - Precio instantáneo (`/api/v3/ticker/price?symbol=BTCUSDT`).
  - Resumen de 24 horas con volumen y cambio porcentual (`/api/v3/ticker/24hr?symbol=BTCUSDT`).
  - Libro de órdenes (*depth*) para evaluar liquidez superficial (`/api/v3/depth?symbol=BTCUSDT&limit=100`).
- La granularidad de 1 minuto y 1 hora permite anclar con alta precisión el precio de BTC en el instante exacto en que un bloque es minado o una transacción es detectada.

### Alternativas Evaluadas
- **CoinMarketCap:** Requiere clave de API incluso en su capa gratuita y restringe severamente el historial por minuto.
- **Kraken Public API:** Excelente alternativa pública, pero con menor volumen relativo en USDT comparado con Binance; puede incorporarse como fuente secundaria de verificación de precio ponderado.

---

## 3. Catálogo y Resolución de Entidades

### Decisión
Almacenar el catálogo de entidades y atribución de direcciones en base de datos relacional con carga inicial vía archivos semilla **CSV y JSON**. El sistema categoriza las entidades en:
1. `Exchange` (Intercambios centralizados: Binance, Coinbase, Kraken, etc.).
2. `Custodio` (Custodios institucionales: BitGo, Fidelity Digital Assets, etc.).
3. `Empresa` (Corporaciones con reservas de BTC: MicroStrategy, Tesla, etc.).
4. `Fondo` (ETFs spot y fondos de inversión: BlackRock IBIT, Fidelity FBTC, etc.).
5. `Minero` (Pools de minería: Foundry USA, AntPool, F2Pool, etc.).
6. `Gran_Tenedor` (Ballenas individuales o direcciones históricas conocidas).
7. `Desconocida` (Cualquier dirección no vinculada formalmente).

### Razón
- Cumple el Principio IV y el requisito RF-01/RF-02: cada dirección catalogada almacena `fuente_atribucion` (ej. reporte de *Proof of Reserves*, divulgación regulatoria ante la SEC, o etiquetado público documentado) y `grado_certeza` (0.0 a 1.0).
- Si no existe evidencia suficiente, el sistema nunca agrupa ni infiere propiedad cruzada (Principio III y IV).

---

## 4. Persistencia y Almacenamiento

### Decisión
Utilizar **SQLite** con modo WAL (*Write-Ahead Logging*) como motor de persistencia del MVP, interactuando a través de **SQLAlchemy 2.0** con tipado estricto y modelos declarativos.

### Razón
- **Cero costes y cero sobrecarga:** No requiere servicios adicionales en el VPS (a diferencia de PostgreSQL o MySQL que consumen cientos de megabytes de RAM en segundo plano).
- El modo WAL permite lectores concurrentes sin bloquear escrituras, soportando miles de transacciones por segundo, muy por encima de la tasa de bloques de Bitcoin (1 bloque cada ~10 minutos).
- SQLAlchemy 2.0 desacopla completamente el esquema de la base de datos subyacente, lo que permite migrar a PostgreSQL en el futuro sin modificar la lógica de negocio ni las consultas del repositorio.

---

## 5. Arquitectura del Motor de Análisis de Impacto (Rigor Metodológico)

### Decisión
Diseñar el motor con una separación modular estricta en tres capas funcionales independientes:

```text
[Evento On-Chain Detectado]
          │
          ├──> 1. Capa A: Impacto en Liquidez (Microestructura)
          │       - Mide tamaño del movimiento relativo a volumen spot 24h.
          │       - Mide profundidad disponible en el libro de órdenes (si disponible).
          │
          ├──> 2. Capa B: Asociación Histórica (Estadística Descriptiva)
          │       - Distribución empírica de retornos pasados tras eventos similares.
          │       - Correlaciones observadas (sin atribuir causalidad).
          │
          └──> 3. Capa C: Predicción Estadística Fuera de Muestra (Modelos)
                  - En V1: Estado "Indeterminado" justificado hasta superar periodo de backtesting.
                  - Evaluación obligatoria contra Baselines:
                    * Baseline 1: Buy & Hold (mantener BTC)
                    * Baseline 2: Persistencia / Random Walk (precio futuro = precio actual)
                  - Métricas: Brier Score, calibración probabilística y error absoluto.
```

### Razón
- Cumple taxativamente los Principios V, VI, VII, VIII, IX y XV de la Constitución: no confunde liquidez con predicción, prohíbe inventar probabilidades, garantiza pre-registro inmutable y exige baselines.

---

## 6. Notificaciones y Resiliencia Operativa

### Decisión
- **Canal de Alertas:** Módulo `despachador_alertas` basado en `smtplib` estándar de Python con soporte para TLS/SSL (puerto 587 o 465) y plantillas en texto plano y HTML limpio.
- **Idempotencia:** Cada alerta almacena un hash único `hash(txid + identificador_movimiento + tipo_alerta)` en la tabla `alertas_despachadas`. Antes de enviar un correo, se verifica que no exista un registro previo exitoso.
- **Resiliencia de Red:** Decorador de reintentos con retroceso exponencial (`tenacity` o implementación nativa con jitter) ante caídas de conexión o errores 429/5xx.

---

## 7. Ejecución Continua y Despliegue en VPS Linux

### Decisión
- Despliegue mediante servicio **systemd** para el colector continuo (o temporizadores `systemd timers` / `cron` para el ciclo de muestreo periódico y el reporte diario).
- Manejo de entorno mediante archivo `.env` cargado con `python-dotenv`.
- Rotación de logs mediante `RotatingFileHandler` de la biblioteca estándar de Python (límite de 10 MB por archivo, 5 respaldos).
