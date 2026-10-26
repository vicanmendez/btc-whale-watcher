# Tasks: BTC Whale Intelligence

**Input**: Design documents from `/specs/001-btc-whale-intelligence/`  
**Prerequisites**: [plan.md](file:///c:/xampp/htdocs/whalewatcher/specs/001-btc-whale-intelligence/plan.md), [spec.md](file:///c:/xampp/htdocs/whalewatcher/specs/001-btc-whale-intelligence/spec.md), [research.md](file:///c:/xampp/htdocs/whalewatcher/specs/001-btc-whale-intelligence/research.md), [data-model.md](file:///c:/xampp/htdocs/whalewatcher/specs/001-btc-whale-intelligence/data-model.md), [contracts/contratos_modulos.md](file:///c:/xampp/htdocs/whalewatcher/specs/001-btc-whale-intelligence/contracts/contratos_modulos.md)  
**Tests**: Se incluyen pruebas automatizadas unitarias e integradas para cálculos financieros, clasificación de transacciones, alertas y modelos según lo estipulado por el Principio X de la Constitución del proyecto.  
**Organization**: Tareas agrupadas por fases y por historias de usuario (US1 a US5) para garantizar implementabilidad y verificabilidad independiente.  

---

## Format: `[TaskID] [P?] [Story?] Description with file path`

- **[P]**: Ejecutable en paralelo (archivos distintos, sin dependencias bloqueantes sin resolver).
- **[Story]**: Identificador de historia de usuario (`[US1]`, `[US2]`, `[US3]`, `[US4]`, `[US5]`).
- Todas las rutas corresponden a la estructura del proyecto en español (Principio XVI).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Inicialización del proyecto, árbol de directorios y configuración base de dependencias.

- [X] T001 Crear estructura completa de directorios del proyecto según el plan de implementación en `src/btc_whale_intelligence/`, `config/`, `datos/semillas/`, `despliegue/` y `tests/`
- [X] T002 Crear archivo de dependencias fijadas en `requirements.txt` (incluyendo SQLAlchemy, httpx, pandas, numpy, scikit-learn, pydantic, python-dotenv, pytest)
- [X] T003 [P] Crear plantilla documentada de variables de entorno en `.env.ejemplo` con parámetros de base de datos, APIs de Mempool y Binance, umbrales y SMTP
- [X] T004 [P] Configurar exclusiones de control de versiones en `.gitignore` para ignorar `.env`, `*.db`, `*.db-wal`, `logs/`, `.venv/` y cachés de Python
- [X] T005 [P] Implementar módulo de configuración tipada y validación de variables de entorno en `config/configuracion.py` usando `pydantic-settings` o `python-dotenv`
- [X] T006 [P] Escribir pruebas unitarias para la validación de configuración y variables por defecto en `tests/unit/test_configuracion.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Infraestructura de persistencia, conexión a SQLite en modo WAL, modelos de base de datos y cliente HTTP resiliente.

**⚠️ CRITICAL**: Ninguna historia de usuario puede implementarse hasta completar esta fase fundacional.

- [X] T007 Implementar módulo de conexión a base de datos SQLite con modo WAL y gestión de sesiones SQLAlchemy 2.0 en `src/btc_whale_intelligence/base_datos/conexion.py`
- [X] T008 [P] Definir modelos ORM declarativos en español para entidades y direcciones (`EntidadORM`, `DireccionORM`, `AtribucionDireccionORM`) en `src/btc_whale_intelligence/base_datos/modelos.py`
- [X] T009 [P] Definir modelos ORM para datos on-chain y mercado (`TransaccionOnChainORM`, `EntradaSalidaORM`, `SaldoHistoricoORM`, `VelaMercadoORM`) en `src/btc_whale_intelligence/base_datos/modelos.py`
- [X] T010 [P] Definir modelos ORM para eventos analizados, predicciones y alertas (`EventoAnalizadoORM`, `CaracteristicaCalculadaORM`, `PrediccionORM`, `ResultadoPrediccionORM`, `AlertaDespachadaORM`, `EstadoIngestaORM`) en `src/btc_whale_intelligence/base_datos/modelos.py`
- [X] T011 Implementar script y función utilitaria para la inicialización y migración inicial de tablas en `src/btc_whale_intelligence/base_datos/inicializador.py`
- [X] T012 Implementar clase base de cliente HTTP con timeouts, cabeceras seguras, reintentos y retroceso exponencial ante errores 429/5xx en `src/btc_whale_intelligence/clientes_externos/base.py`
- [X] T013 [P] Escribir pruebas unitarias de creación de tablas, índices y restricciones únicas de la base de datos en `tests/unit/test_modelos_bd.py`
- [X] T014 [P] Escribir pruebas unitarias para la política de reintentos y retroceso exponencial del cliente HTTP en `tests/unit/test_clientes_externos_base.py`

**Checkpoint**: Base de datos y cliente HTTP operativo. Comienza el desarrollo de historias de usuario.

---

## Phase 3: User Story 1 - Gestión de Catálogo de Entidades y Direcciones Atribuidas (Priority: P1) 🎯 MVP

**Goal**: Permitir registrar entidades conocidas, importar direcciones verificadas desde archivos locales (CSV/JSON), registrar su procedencia documental y calcular saldos agregados sin inferencias infundadas.

**Independent Test**: Importar un catálogo semilla desde CSV y verificar que las entidades y direcciones se almacenan con su fuente y nivel de certeza, y que las direcciones huérfanas se clasifican como desconocidas.

### Tests para User Story 1 ⚠️
- [X] T015 [P] [US1] Escribir pruebas unitarias para el servicio de resolución de entidades y direcciones en `tests/unit/test_servicio_entidades.py`
- [X] T016 [P] [US1] Escribir pruebas unitarias para la validación y parseo del importador de CSV/JSON en `tests/unit/test_importador_semillas.py`
- [X] T017 [P] [US1] Escribir prueba de integración para la ingesta y consulta de un catálogo completo en `tests/integration/test_importacion_entidades.py`

### Implementación de User Story 1
- [X] T018 [P] [US1] Implementar servicio de gestión y consulta de entidades y direcciones atribuidas en `src/btc_whale_intelligence/entidades/servicio_entidades.py`
- [X] T019 [US1] Implementar cargador e importador masivo de entidades y direcciones desde archivos CSV y JSON en `src/btc_whale_intelligence/entidades/importador_semillas.py`
- [X] T020 [US1] Crear archivo semilla inicial con datos de exchanges, custodios y empresas públicas conocidas con fuentes documentadas en `datos/semillas/entidades_iniciales.csv`
- [X] T021 [US1] Añadir comando CLI `importar-entidades` en `src/btc_whale_intelligence/cli.py` para permitir la carga y actualización desde terminal

**Checkpoint**: User Story 1 funcional y comprobable de forma autónoma con datos semilla reales.

---

## Phase 4: User Story 2 - Monitoreo On-Chain y Detección de Movimientos Relevantes (Priority: P1)

**Goal**: Conectar con APIs públicas de Bitcoin (Mempool.space y Blockstream Esplora), procesar bloques y transacciones, filtrar movimientos según umbrales configurables por categoría y garantizar idempotencia absoluta.

**Independent Test**: Ejecutar el colector sobre un bloque histórico con transacciones superiores a 500 BTC y comprobar que se registran todas las entradas/salidas, se ignoran duplicados y se identifican los movimientos relevantes.

### Tests para User Story 2 ⚠️
- [X] T022 [P] [US2] Escribir pruebas unitarias del cliente de Mempool.space con simulación de respuestas JSON en `tests/unit/test_cliente_mempool.py`
- [X] T023 [P] [US2] Escribir pruebas unitarias para el parser de transacciones on-chain (`vin`, `vout`, comisiones) en `tests/unit/test_parser_transacciones.py`
- [X] T024 [P] [US2] Escribir prueba de integración para el detector de movimientos relevantes y control de idempotencia en `tests/integration/test_colector_onchain.py`

### Implementación de User Story 2
- [X] T025 [P] [US2] Implementar cliente de API REST de Mempool.space con fallback a Blockstream Esplora en `src/btc_whale_intelligence/clientes_externos/cliente_mempool.py`
- [X] T026 [US2] Implementar parser y normalizador de transacciones brutas (`vin`, `vout`, `txid`, marcas temporales) en `src/btc_whale_intelligence/onchain/parser_transaccion.py`
- [X] T027 [US2] Implementar colector de bloques confirmados y mempool reciente con verificación de altura sincronizada en `src/btc_whale_intelligence/onchain/colector_bloques.py`
- [X] T028 [US2] Implementar lógica de detección de movimientos relevantes con umbrales segmentados (500 BTC exchanges, 250 BTC custodios/empresas, 1000 BTC desconocidas) en `src/btc_whale_intelligence/onchain/detector_movimientos.py`
- [X] T029 [US2] Añadir comando CLI `sincronizar-onchain` en `src/btc_whale_intelligence/cli.py` para disparar el colector on-chain

**Checkpoint**: User Stories 1 y 2 integradas; el sistema ingesta y almacena transacciones y detecta movimientos relevantes.

---

## Phase 5: User Story 3 - Enriquecimiento de Contexto de Mercado y Clasificación No Sesgada (Priority: P2)

**Goal**: Recolectar cotizaciones spot y velas OHLCV de Binance (con fallback a CoinGecko), vincular el contexto del mercado al instante exacto del evento on-chain y clasificar el movimiento en categorías formales sin asumir compras o ventas (Principios III y IV).

**Independent Test**: Procesar una transacción relevante con destino a una dirección de exchange y verificar que se clasifica como `ENTRADA_EXCHANGE`, adjunta precio, volumen y volatilidad de BTC, y explicita las limitaciones del análisis.

### Tests para User Story 3 ⚠️
- [X] T030 [P] [US3] Escribir pruebas unitarias para el cliente público de mercado de Binance y cálculo de volatilidad en `tests/unit/test_cliente_binance.py`
- [X] T031 [P] [US3] Escribir pruebas unitarias de clasificación formal y validación estricta de la regla de no-inferencia de compra/venta en `tests/unit/test_motor_clasificacion.py`
- [X] T032 [P] [US3] Escribir prueba de integración de enriquecimiento de contexto de mercado en `tests/integration/test_enriquecimiento_mercado.py`

### Implementación de User Story 3
- [X] T033 [P] [US3] Implementar cliente de API pública de Binance Spot para precios instantáneos, velas OHLCV y libro de órdenes en `src/btc_whale_intelligence/clientes_externos/cliente_binance.py`
- [X] T034 [US3] Implementar módulo de sincronización y almacenamiento de velas de mercado en `src/btc_whale_intelligence/mercado/sincronizador_mercado.py`
- [X] T035 [US3] Implementar motor de clasificación de eventos on-chain (`ENTRADA_EXCHANGE`, `SALIDA_EXCHANGE`, `TRANSFERENCIA_INTERNA`, `MOVIMIENTO_CORPORATIVO`, `DESCONOCIDA`) en `src/btc_whale_intelligence/clasificador/motor_clasificacion.py`
- [X] T036 [US3] Implementar extractor de características contextuales basadas exclusivamente en información histórica pasada (ratio sobre volumen 24h, volatilidad 7d) en `src/btc_whale_intelligence/analisis/caracteristicas.py`
- [X] T037 [US3] Añadir comando CLI `sincronizar-mercado` en `src/btc_whale_intelligence/cli.py`

**Checkpoint**: Los eventos detectados quedan enriquecidos con métricas de mercado y clasificados objetivamente.

---

## Phase 6: User Story 4 - Análisis Probabilístico de Impacto, Pre-registro y Evaluación con Baselines (Priority: P2)

**Goal**: Implementar el motor de análisis de impacto distinguiendo liquidez, asociación histórica y predicción, pre-registrando las estimaciones para horizontes de 24h, 7d y 30d (con estado "Indeterminado" en v1), y ejecutando la evaluación histórica contra *Buy & Hold* y persistencia (Principios V, VII, VIII, IX y XV).

**Independent Test**: Simular un evento con predicción pre-registrada, cerrar la ventana temporal con un precio final y verificar que el evaluador computa el retorno real y contrasta obligatoriamente frente a los dos baselines.

### Tests para User Story 4 ⚠️
- [X] T038 [P] [US4] Escribir pruebas unitarias para el motor de impacto y verificación de emisión de estado "Indeterminado" en v1 en `tests/unit/test_motor_impacto.py`
- [X] T039 [P] [US4] Escribir pruebas unitarias para el evaluador retrospectivo y cálculo de contraste contra baselines en `tests/unit/test_evaluador_historico.py`
- [X] T040 [P] [US4] Escribir prueba de integración para el ciclo completo de pre-registro inmutable y posterior evaluación en `tests/integration/test_ciclo_predictivo.py`

### Implementación de User Story 4
- [X] T041 [P] [US4] Implementar motor de análisis de impacto distinguiendo Capa A (liquidez), Capa B (asociación) y Capa C (predicción) en `src/btc_whale_intelligence/analisis/motor_impacto.py`
- [X] T042 [US4] Implementar módulo de pre-registro inmutable de predicciones con estampas temporales y fechas de vencimiento en `src/btc_whale_intelligence/analisis/prerregistro.py`
- [X] T043 [US4] Implementar evaluador histórico retrospectivo para horizontes vencidos, calculando retornos y métricas de error frente a *Buy & Hold* y persistencia en `src/btc_whale_intelligence/analisis/evaluador_historico.py`
- [X] T044 [US4] Añadir comando CLI `evaluar-predicciones` en `src/btc_whale_intelligence/cli.py` para auditoría retrospectiva automática

**Checkpoint**: El sistema garantiza rigor epistémico, pre-registro inmutable y auditoría frente a baselines.

---

## Phase 7: User Story 5 - Notificaciones por Alerta y Resumen Diario Consolidado (Priority: P3)

**Goal**: Generar y enviar alertas por correo electrónico ante movimientos relevantes con análisis disponible, deduplicando envíos mediante hash de idempotencia, y generar un informe diario consolidado de actividad y resultados evaluados.

**Independent Test**: Disparar una alerta simulada a un servidor SMTP de prueba, verificar que el correo contiene los datos del evento, el enlace al explorador y la nota de exención de responsabilidad, y comprobar que un segundo intento idéntico no despacha un duplicado.

### Tests para User Story 5 ⚠️
- [X] T045 [P] [US5] Escribir pruebas unitarias para el generador de plantillas de correo en texto plano y HTML en `tests/unit/test_plantillas_correo.py`
- [X] T046 [P] [US5] Escribir pruebas unitarias para el despachador SMTP y control de idempotencia de alertas en `tests/unit/test_despachador_smtp.py`
- [X] T047 [P] [US5] Escribir prueba de integración para la generación del reporte diario consolidado en `tests/integration/test_reporte_diario.py`

### Implementación de User Story 5
- [X] T048 [P] [US5] Diseñar e implementar plantillas de correo electrónico responsivas (HTML y texto plano) con disclaimer financiero en `src/btc_whale_intelligence/notificaciones/plantillas_correo.py`
- [X] T049 [US5] Implementar despachador de correo electrónico SMTP con TLS/SSL y registro de idempotencia en `src/btc_whale_intelligence/notificaciones/despachador_smtp.py`
- [X] T050 [US5] Implementar generador y remitente del informe diario consolidado de entidades, flujos netos y baselines en `src/btc_whale_intelligence/notificaciones/reporte_diario.py`
- [X] T051 [US5] Añadir comando CLI `enviar-reporte-diario` en `src/btc_whale_intelligence/cli.py`

**Checkpoint**: Flujo de notificaciones y reportes automáticos listo para producción.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Orquestación de extremo a extremo, verificación de salud operativa, archivos de despliegue en Linux VPS y documentación final.

- [X] T052 Implementar comando central unificado `ejecutar-ciclo-monitoreo` en `src/btc_whale_intelligence/cli.py` que encadene ingesta on-chain, mercado, detección, clasificación y alerta
- [X] T053 [P] Implementar comando CLI `verificar-salud` para diagnóstico integral de base de datos, APIs externas y SMTP en `src/btc_whale_intelligence/cli.py`
- [X] T054 [P] Configurar el punto de entrada ejecutable `__main__.py` en `src/btc_whale_intelligence/__main__.py`
- [X] T055 [P] Crear archivos de configuración para systemd en `despliegue/systemd/whalewatcher.service` y `despliegue/systemd/whalewatcher.timer`
- [X] T056 [P] Crear archivo de configuración para rotación de logs de Linux en `despliegue/logrotate/whalewatcher`
- [X] T057 Escribir prueba de integración de extremo a extremo (E2E) simulando el flujo completo del sistema en `tests/integration/test_flujo_e2e_completo.py`
- [X] T058 [P] Redactar `README.md` exhaustivo en la raíz del repositorio con instrucciones de instalación, configuración en VPS modesto, comandos CLI y exención de responsabilidad
- [X] T059 Ejecutar y validar todos los escenarios descritos en `quickstart.md` para certificar la entrega completa

---

## Dependencies & Execution Order

### Phase Dependencies

```text
[Phase 1: Setup] ──────> [Phase 2: Foundational]
                                │
                                ├───> [Phase 3: User Story 1 (Catálogo Entidades)] (P1) 🎯 MVP
                                │           │
                                └───> [Phase 4: User Story 2 (On-Chain)] (P1)
                                            │
                                            ▼
                                      [Phase 5: User Story 3 (Mercado y Clasificación)] (P2)
                                            │
                                            ▼
                                      [Phase 6: User Story 4 (Impacto y Baselines)] (P2)
                                            │
                                            ▼
                                      [Phase 7: User Story 5 (Alertas y Reporte Diario)] (P3)
                                            │
                                            ▼
                                      [Phase 8: Polish, CLI y Despliegue VPS]
```

### Reglas de Paralelismo
- Las tareas marcadas con `[P]` pueden ejecutarse simultáneamente al afectar a archivos desacoplados y no tener dependencias directas entre sí.
- Dentro de cada historia de usuario, los tests se diseñan primero (TDD) para validar los contratos de los módulos.
- La fase fundacional (Phase 2) es un prerrequisito obligatorio antes de trabajar en cualquier historia de usuario.

---

## Implementation Strategy: MVP First (Incremental Delivery)

1. **Incremento 1 (MVP Fundacional - US1):**
   - Completar Fases 1 y 2.
   - Completar Phase 3 (US1).
   - Validar importación de catálogo semilla y consultas de entidades.
2. **Incremento 2 (Monitoreo On-Chain - US2):**
   - Completar Phase 4 (US2).
   - El sistema detecta transacciones grandes y variaciones de entidades registradas.
3. **Incremento 3 (Contexto de Mercado y Clasificación - US3):**
   - Completar Phase 5 (US3).
   - Los movimientos se clasifican objetivamente con precio y volumen spot de BTC.
4. **Incremento 4 (Rigor Analítico y Baselines - US4):**
   - Completar Phase 6 (US4).
   - Pre-registro inmutable para horizontes de 24h, 7d y 30d con evaluación frente a *Buy & Hold* y persistencia.
5. **Incremento 5 (Alertas y Despliegue en VPS - US5 y Polish):**
   - Completar Fases 7 y 8.
   - Despacho SMTP de alertas deduplicadas, reporte diario y automatización en Linux VPS.
