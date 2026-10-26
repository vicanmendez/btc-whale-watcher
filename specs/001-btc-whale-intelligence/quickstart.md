# Quickstart & Validation Guide: BTC Whale Intelligence

**Feature**: `001-btc-whale-intelligence`  
**Date**: 2026-10-26  
**Target Environment**: Linux VPS (Ubuntu 22.04 LTS / Debian 12 / desarrollo local con Python 3.10+)

---

## 1. Requisitos Previos

- Python 3.10 o superior (`python3 --version`).
- `pip` y `venv` instalados.
- Acceso a internet para consultar APIs públicas (`mempool.space`, `api.binance.com`).
- Credenciales SMTP para envío de correos (cuenta estándar de Gmail, Brevo, Mailgun o servidor postfix local).

---

## 2. Instalación y Configuración

```bash
# 1. Clonar el repositorio y acceder a la carpeta
cd /ruta/hacia/whalewatcher

# 2. Crear y activar entorno virtual
python3 -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\Activate.ps1

# 3. Instalar dependencias del proyecto
pip install --upgrade pip
pip install -r requirements.txt

# 4. Crear archivo de variables de entorno desde la plantilla
cp .env.ejemplo .env
```

### Configuración de `.env`
Editar el archivo `.env` con los valores requeridos:

```ini
# Base de datos
DATABASE_URL=sqlite:///datos/ballenas.db

# Configuración de Ingesta On-Chain (Mempool.space / Esplora)
ONCHAIN_PROVIDER=mempool_space
MEMPOOL_API_URL=https://mempool.space/api
ESPLORA_FALLBACK_URL=https://blockstream.info/api

# Configuración de Mercado (Binance Public)
BINANCE_API_URL=https://api.binance.com/api/v3
COINGECKO_FALLBACK_URL=https://api.coingecko.com/api/v3

# Umbrales por defecto en BTC
UMBRAL_EXCHANGE_BTC=500.0
UMBRAL_INSTITUCIONAL_BTC=250.0
UMBRAL_DESCONOCIDO_BTC=1000.0

# Configuración de Alertas por Correo (SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu_correo@gmail.com
SMTP_PASSWORD=tu_app_password_segura
SMTP_FROM=tu_correo@gmail.com
ALERT_EMAIL_TO=inversor_analista@gmail.com

# Modo de Operación
ENVIRONMENT=production
LOG_LEVEL=INFO
LOG_FILE=logs/whalewatcher.log
```

---

## 3. Inicialización y Carga de Semillas

```bash
# 1. Crear directorios para base de datos y logs
mkdir -p datos logs datos/semillas

# 2. Inicializar el esquema de base de datos relacional
python -m btc_whale_intelligence inicializar-bd

# 3. Importar catálogo de entidades semilla (exchanges, custodios y empresas conocidas)
python -m btc_whale_intelligence importar-entidades datos/semillas/entidades_ejemplo.csv
```

---

## 4. Validación del Flujo de Extremo a Extremo (E2E)

### Escenario A: Consulta de Salud y Conectividad
Comprueba que los proveedores gratuitos responden correctamente y no hay bloqueos de red:

```bash
python -m btc_whale_intelligence verificar-salud
```
*Salida esperada:*
```text
[OK] Conexión a Base de Datos SQLite (datos/ballenas.db): EXITOSA
[OK] Proveedor On-Chain (mempool.space): EXITOSA (Último bloque: 890123)
[OK] Proveedor Mercado (Binance Spot): EXITOSA (BTC/USDT: $67,420.50)
[OK] Servicio SMTP: Conexión establecida con éxito
```

### Escenario B: Ciclo de Ingesta y Detección
Ejecuta una pasada completa de recolección de bloques, captura de transacciones, enriquecimiento de mercado y detección de movimientos:

```bash
python -m btc_whale_intelligence ejecutar-ciclo-monitoreo
```
*Salida esperada:*
```text
[INFO] Procesando bloque 890123 con 2,845 transacciones...
[INFO] Transacción relevante detectada: txid 9a8b7c... (850.0 BTC)
[INFO] Clasificación: SALIDA_EXCHANGE desde Binance Cold Storage (Confianza: 0.95)
[INFO] Contexto de Mercado: Precio $67,420.50 | Vol 24h: $18.4B | Volatilidad 7d: 2.8%
[INFO] Análisis de Impacto: Estado INDETERMINADO (Modelo v1.0 en recolección fuera de muestra)
[INFO] Pre-registro completado para horizontes 24H, 7D y 30D.
[INFO] Alerta despachada por correo electrónico a inversor_analista@gmail.com (Idempotencia OK)
```

### Escenario C: Evaluación Retrospectiva con Baselines
Ejecuta la revisión periódica para evaluar predicciones que han cumplido su horizonte temporal:

```bash
python -m btc_whale_intelligence evaluar-predicciones
```
*Salida esperada:*
```text
[INFO] Evaluando predicciones vencidas al 2026-10-26...
[INFO] Predicción #101 (Horizonte 24H): Precio Inicial: $65,000 -> Final: $66,300 (+2.00%)
[INFO] Comparación Baselines:
       - Retorno Real: +2.00%
       - Baseline 1 (Buy & Hold): +2.00%
       - Baseline 2 (Persistencia): 0.00% (Error: 2.00%)
```

---

## 5. Ejecución de la Suite de Pruebas Automatizadas

Validar que todos los cálculos matemáticos, esquemas de bases de datos, no-inferencia de compra/venta y baselines se cumplan:

```bash
pytest -v --disable-warnings
```
*Salida esperada:*
```text
tests/unit/test_clasificador.py::test_no_inferencia_compra_venta PASSED
tests/unit/test_clasificador.py::test_agrupacion_sin_evidencia PASSED
tests/unit/test_mercado.py::test_calculo_volatilidad PASSED
tests/unit/test_evaluador.py::test_comparacion_obligatoria_baselines PASSED
tests/unit/test_evaluador.py::test_pre_registro_inmutable PASSED
tests/unit/test_alertas.py::test_idempotencia_envio_duplicado PASSED
tests/integration/test_pipeline_e2e.py::test_flujo_completo_sin_costo PASSED
========================== 100% passed in 4.12s ==========================
```

---

## 6. Automatización en Linux VPS (Producción)

### Opción A: Cron (Recomendada para MVP simple)
Configurar mediante `crontab -e`:

```cron
# Monitoreo on-chain cada 5 minutos
*/5 * * * * cd /ruta/whalewatcher && .venv/bin/python -m btc_whale_intelligence ejecutar-ciclo-monitoreo >> logs/cron_monitoreo.log 2>&1

# Evaluación de predicciones y baselines cada hora
0 * * * * cd /ruta/whalewatcher && .venv/bin/python -m btc_whale_intelligence evaluar-predicciones >> logs/cron_evaluacion.log 2>&1

# Envío del informe diario consolidado a las 08:00 UTC
0 8 * * * cd /ruta/whalewatcher && .venv/bin/python -m btc_whale_intelligence enviar-reporte-diario >> logs/cron_diario.log 2>&1
```

### Opción B: Systemd Daemon
Se proveen plantillas de servicio `whalewatcher.service` y `whalewatcher.timer` en `despliegue/systemd/` para ejecución continua administrada con reinicio automático.
