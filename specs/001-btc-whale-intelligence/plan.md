# Implementation Plan: BTC Whale Intelligence

**Branch**: `001-btc-whale-intelligence` | **Date**: 2026-10-26 | **Spec**: [spec.md](file:///c:/xampp/htdocs/whalewatcher/specs/001-btc-whale-intelligence/spec.md)

**Input**: Feature specification from `/specs/001-btc-whale-intelligence/spec.md`

## Summary

Construcción e implementación de la plataforma en Python para **BTC Whale Intelligence**: un sistema modular de recolección continua, enriquecimiento de contexto de mercado, detección no sesgada de movimientos on-chain de grandes entidades de Bitcoin, pre-registro inmutable de predicciones probabilísticas para horizontes de 24h, 7d y 30d, evaluación frente a baselines (*Buy & Hold* y persistencia), despacho de alertas por correo electrónico SMTP con deduplicación y reporte diario consolidado. La versión MVP prioriza coste cero mediante APIs públicas gratuitas (Mempool.space y Binance Spot), persistencia ligera en SQLite con SQLAlchemy y ejecución optimizada para servidores VPS modestos (1–2 vCPUs y 2–4 GB RAM).

## Technical Context

**Language/Version**: Python 3.10+  
**Primary Dependencies**:
- `SQLAlchemy 2.0+` (Mapeo objeto-relacional y soporte de tipado).
- `httpx` o `requests` (Clientes HTTP resilientes para APIs REST públicas con timeouts y reintentos).
- `pandas` y `numpy` (Manipulación de series temporales, cálculo de retornos, volatilidad y agregaciones).
- `scikit-learn` (Métricas de calibración estadística como Brier score y baselines; preparado para modelos futuros).
- `pydantic` v2 (Validación estricta de esquemas de datos entrantes de APIs).
- `python-dotenv` (Carga de variables de entorno para seguridad de credenciales).

**Storage**: SQLite con modo WAL (*Write-Ahead Logging*) para concurrencia limpia, cero consumo de memoria residual y portabilidad total en disco.

**Testing**: `pytest` y `pytest-mock` con cobertura exhaustiva en:
- No-inferencia automática de compra/venta.
- Cálculo de saldos y flujos netos por entidad.
- Cálculos matemáticos y métricas de volatilidad/retorno.
- Idempotencia en procesamiento de transacciones y envío de alertas.
- Evaluación retrospectiva y comparación con baselines.

**Target Platform**: Linux Server (Ubuntu 22.04 LTS / Debian 12 / VPS modesto de 1–2 vCPUs y 2–4 GB RAM). Compatible también con Windows/macOS para desarrollo local.

**Project Type**: Servicio en segundo plano / CLI modular ejecutable mediante orquestación estándar (`cron` o `systemd`).

**Performance Goals**:
- Ciclo de escaneo y detección on-chain completado en <30 segundos por bloque/mempool.
- Despacho de alerta por correo electrónico en <60 segundos tras el evento.
- Consultas de agregación de saldos y evaluación histórica en <2 segundos.

**Constraints**:
- **Coste de infraestructura:** $0 adicionales en suscripciones de software y APIs públicas.
- **Consumo de memoria:** <250 MB de RAM en estado estacionario.
- **Seguridad:** Cero secretos en código o logs; uso exclusivo de `.env`.
- **Rigor metodológico:** Principios de no-causalidad, pre-registro inmutable y baselines obligatorios.

**Scale/Scope**: Catálogo de cientos de entidades y miles de direcciones de Bitcoin con historial de decenas de miles de eventos on-chain relevantes.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio Constitucional | Estado de Conformidad | Mecanismo de Garantía en este Plan |
| :--- | :---: | :--- |
| **I. Arquitectura Modular** | **CUMPLE** | 9 módulos independientes desacoplados con contratos de interfaz abstractos (`ProveedorOnChain`, `ProveedorMercado`, `ClasificadorMovimientos`, etc.). |
| **II. Fuentes Gratuitas y Abiertas** | **CUMPLE** | Uso exclusivo de Mempool.space, Blockstream Esplora y Binance Public API sin costes de suscripción. |
| **III. Separación Epistémica** | **CUMPLE** | Tablas segregadas para `transacciones_onchain` (datos crudos), `atribuciones_direcciones` (inferencias), `predicciones` (modelos) y `resultados_predicciones` (hechos a posteriori). |
| **IV. No Compra/Venta Automática** | **CUMPLE** | Regla explícita en `ClasificadorMovimientos`: prohíbe términos de compra/venta; clasifica como flujos entre tipos de custodia. |
| **V. Rigor Predictivo** | **CUMPLE** | Tabla `predicciones` exige horizonte, probabilidades calibradas, rangos de incertidumbre, evidencia y limitaciones. |
| **VI. Distinción Causal** | **CUMPLE** | El módulo de análisis separa formalmente Impacto en Liquidez (Capa A), Asociación Histórica (Capa B) y Predicción (Capa C). |
| **VII. Backtesting sin Lookahead Bias**| **CUMPLE** | Las características se computan exclusivamente con timestamps estrictamente anteriores al evento. |
| **VIII. Baselines Obligatorios** | **CUMPLE** | Tabla `resultados_predicciones` contrasta obligatoriamente con *Buy & Hold* y persistencia de precio. |
| **IX. Pre-registro Inmutable** | **CUMPLE** | La predicción se guarda con estampa temporal inmutable antes del desenlace temporal. |
| **X. Pruebas Automatizadas** | **CUMPLE** | Suite `pytest` con tests unitarios e integrados para cada contrato y cálculo crítico. |
| **XI. Resiliencia de Red y APIs** | **CUMPLE** | Cliente HTTP con retroceso exponencial, manejo de límites 429 y registro en `estado_ingesta`. |
| **XII. Seguridad de Credenciales** | **CUMPLE** | `.env` fuera de control de versiones y exclusión de contraseñas/tokens en logs. |
| **XIII. VPS Modesto** | **CUMPLE** | SQLite en modo WAL, bajo uso de memoria (<250 MB) y sin servicios pesados en background. |
| **XIV. Prohibición de Custodia/Trading**| **CUMPLE** | El sistema no posee módulos de trading, llaves privadas ni órdenes de ejecución en exchanges. |
| **XV. Evidencia Estadística** | **CUMPLE** | En v1 el motor analítico reporta estado "Indeterminado" justificado mientras se construye el dataset fuera de muestra. |
| **XVI. Idioma Español en Código** | **CUMPLE** | Todos los nombres de módulos, clases, métodos, variables y tablas de base de datos están en español (PEP 8). |
| **XVII. Testabilidad Independiente** | **CUMPLE** | Cada componente implementa interfaces abstractas permitiendo mocks y tests unitarios aislados. |
| **XVIII. Autosuficiencia en V1** | **CUMPLE** | Importación manual y semilla por CSV/JSON de etiquetas de entidades sin requerir APIs comerciales. |

## Project Structure

### Documentation (this feature)

```text
specs/001-btc-whale-intelligence/
├── spec.md                  # Especificación funcional aprobada
├── plan.md                  # Este plan de implementación técnico
├── research.md              # Decisiones de arquitectura y fuentes gratuitas (Fase 0)
├── data-model.md            # Esquema relacional SQLite/SQLAlchemy (Fase 1)
├── quickstart.md            # Guía de validación y despliegue rápido (Fase 1)
├── checklists/
│   └── requirements.md      # Checklist de calidad de especificación validado
└── contracts/
    └── contratos_modulos.md # Contratos técnicos e interfaces entre módulos (Fase 1)
```

### Source Code (repository root)

Estructura de paquetes en Python siguiendo la convención de nomenclatura en español requerida por el Principio XVI:

```text
whalewatcher/
├── config/
│   ├── __init__.py
│   └── configuracion.py             # Carga tipada de .env y parámetros globales
├── datos/
│   ├── semillas/
│   │   └── entidades_iniciales.csv  # Catálogo semilla de exchanges y corporaciones
│   └── .gitkeep                     # Directorio para la base de datos ballenas.db
├── logs/
│   └── .gitkeep                     # Directorio para logs rotativos
├── src/
│   └── btc_whale_intelligence/
│       ├── __init__.py
│       ├── __main__.py              # Punto de entrada CLI principal
│       ├── cli.py                   # Definición de comandos de consola (argparse / click)
│       ├── base_datos/
│       │   ├── __init__.py
│       │   ├── conexion.py          # Inicialización de motor SQLite con WAL y sesión SQLAlchemy
│       │   └── modelos.py           # Modelos ORM (entidades, transacciones, predicciones, etc.)
│       ├── clientes_externos/
│       │   ├── __init__.py
│       │   ├── base.py              # Clase base HTTP con reintentos y retroceso exponencial
│       │   ├── cliente_mempool.py   # Implementación para Mempool.space y Esplora
│       │   └── cliente_binance.py   # Implementación para cotizaciones y velas de Binance Spot
│       ├── entidades/
│       │   ├── __init__.py
│       │   ├── servicio_entidades.py # Búsqueda, resolución y agregación de direcciones
│       │   └── importador_semillas.py# Ingesta desde archivos CSV y JSON
│       ├── onchain/
│       │   ├── __init__.py
│       │   ├── colector_bloques.py  # Consulta de altura, bloques y mempool
│       │   └── parser_transaccion.py# Deserialización de vin/vout y cómputo de comisiones
│       ├── mercado/
│       │   ├── __init__.py
│       │   └── sincronizador_mercado.py # Almacenamiento y cálculo de métricas de mercado
│       ├── clasificador/
│       │   ├── __init__.py
│       │   └── motor_clasificacion.py # Categorización de movimientos sin sesgo compra/venta
│       ├── analisis/
│       │   ├── __init__.py
│       │   ├── caracteristicas.py   # Extracción de variables con timestamps pasados
│       │   ├── motor_impacto.py     # Análisis de liquidez, asociación y estado indeterminado
│       │   └── evaluador_historico.py # Cómputo de Brier score y contraste con baselines
│       └── notificaciones/
│           ├── __init__.py
│           ├── plantillas_correo.py # Generación de correo en texto plano y HTML limpio
│           └── despachador_smtp.py  # Envío SMTP idempotente con control de duplicados
├── tests/
│   ├── __init__.py
│   ├── conftest.py                  # Fixtures de base de datos en memoria y mocks
│   ├── unit/
│   │   ├── test_configuracion.py
│   │   ├── test_modelos_bd.py
│   │   ├── test_clientes_externos.py
│   │   ├── test_servicio_entidades.py
│   │   ├── test_clasificador_movimientos.py
│   │   ├── test_caracteristicas.py
│   │   ├── test_analizador_impacto.py
│   │   ├── test_evaluador_baselines.py
│   │   └── test_despachador_alertas.py
│   └── integration/
│       ├── test_importacion_entidades.py
│       ├── test_colector_onchain.py
│       └── test_flujo_e2e_completo.py
├── despliegue/
│   ├── systemd/
│   │   ├── whalewatcher.service     # Unidad de servicio systemd para ejecución continua
│   │   └── whalewatcher.timer       # Temporizador systemd para ejecuciones periódicas
│   └── logrotate/
│       └── whalewatcher             # Configuración de rotación de logs de Linux
├── .env.ejemplo                     # Plantilla documentada de variables de entorno
├── .gitignore                       # Exclusión de .env, *.db, *.log, .venv/
├── requirements.txt                 # Dependencias fijadas del proyecto
└── README.md                        # Documentación general de instalación y arquitectura
```

## Complexity Tracking

No se registran violaciones constitucionales que requieran justificación. La arquitectura mantiene deliberadamente la máxima simplicidad:
- Base de datos embebida SQLite en lugar de clústeres de bases de datos externas.
- Ejecución periódica mediante `cron`/`systemd` en lugar de colas complejas de mensajería (Kafka/RabbitMQ/Celery) que sobrecargarían el VPS modesto.
- Clientes HTTP con interfaces directas en lugar de dependencias complejas de SDKs de terceros.

## Secuencia de Implementación Incremental (Roadmap)

1. **Fase 1: Infraestructura Base y Persistencia**
   - Estructuración del proyecto, configuración con `pydantic-settings`/`dotenv` y conexión a SQLite.
   - Definición de modelos ORM SQLAlchemy en español y scripts de inicialización de base de datos.
   - Pruebas unitarias de integridad de la base de datos.
2. **Fase 2: Registro de Entidades e Ingesta de Semillas**
   - Lógica de catálogo de entidades y resolución de direcciones.
   - Importador de archivos CSV/JSON con validación documental de fuentes de atribución.
   - Pruebas de agregación de saldos sin duplicación.
3. **Fase 3: Conectores Externos Resilientes**
   - Cliente de Mempool.space con respaldo en Blockstream Esplora.
   - Cliente de Binance Spot para cotizaciones y velas históricas.
   - Manejo de reintentos con retroceso exponencial y control de cuotas.
4. **Fase 4: Procesamiento On-Chain y Detección de Movimientos**
   - Parser de transacciones y cálculo de montos/comisiones.
   - Motor de clasificación por categorías objetivas (sin sesgo de compra/venta).
   - Filtrado por umbrales configurables por categoría de entidad.
5. **Fase 5: Módulo de Contexto de Mercado e Ingeniería de Características**
   - Anclaje de cotización y volumen al instante del evento.
   - Cálculo de variables pasadas (ratios de volumen, volatilidad histórica 7d).
6. **Fase 6: Motor de Análisis de Impacto y Evaluación con Baselines**
   - Capa de pre-registro inmutable para horizontes de 24h, 7d y 30d.
   - Retorno formal de estado "Indeterminado" en v1 con desglose descriptivo.
   - Evaluador retrospectivo continuo comparando contra *Buy & Hold* y persistencia.
7. **Fase 7: Sistema de Notificaciones y Reporte Diario**
   - Plantillas de correo para alertas individuales y resumen consolidado.
   - Despachador SMTP con control estricto de idempotencia contra duplicados.
8. **Fase 8: Integración de Extremo a Extremo, CLI y Despliegue**
   - Comandos CLI para orquestación (`ejecutar-ciclo-monitoreo`, `evaluar-predicciones`, etc.).
   - Pruebas integradas de pipeline completo.
   - Archivos de configuración para systemd, cron y rotación de logs en VPS Linux.
