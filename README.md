# 🐋 BTC Whale Intelligence

Plataforma modular y verificable de análisis on-chain en Python para identificar grandes entidades del ecosistema Bitcoin, detectar sus transferencias masivas en la blockchain, enriquecerlas con contexto de mercado y evaluar retrospectivamente su impacto frente a referencias cuantitativas simples (*Buy & Hold* y persistencia).

Desarrollada bajo **18 principios constitucionales irrenunciables** orientados al rigor epistémico, uso exclusivo de fuentes de datos gratuitas y ejecución eficiente en un VPS Linux modesto.

---

## 🏛️ Principios Constitucionales Clave

1. **Arquitectura modular y documentada:** Componentes desacoplados (ingesta on-chain, mercado, catálogo de entidades, análisis probabilístico, notificaciones).
2. **Fuentes 100% gratuitas:** Empleo exclusivo de APIs públicas (Mempool.space / Blockstream Esplora para datos on-chain y Binance Spot para mercado). Cero claves de pago requeridas.
3. **Separación epistémica estricta:** Distinción taxativa entre *datos observados* (txs, saldos, velas), *inferencias documentadas* (clustering con respaldo de fuentes), *predicciones pre-registradas* y *resultados evaluados*.
4. **No presunción de compra o venta (Principio IV):** Ninguna transferencia on-chain se etiqueta automáticamente como compra o venta. Una entrada a exchange puede ser colateral, custodia, préstamo o rebalanceo.
5. **Pre-registro inmutable (Principio IX):** Las predicciones se registran con sello de tiempo y hash antes de que ocurra el desenlace para evitar el sesgo retrospectivo (*hindsight bias*).
6. **Comparación obligatoria frente a Baselines (Principio VIII):** Toda predicción se contrasta empíricamente con dos modelos de referencia: *Buy & Hold* y persistencia (retorno nulo).
7. **Modo Indeterminado en v1 (Principios V y XV):** El motor predictivo opera en modo recolección y calibración ("Indeterminado") hasta alcanzar significancia estadística en backtesting temporal fuera de muestra.
8. **Nomenclatura interna en español (Principio XVI):** Código, funciones, clases y esquemas de base de datos definidos en castellano.

---

## ⚙️ Requisitos del Sistema

- **Python:** 3.10 o superior.
- **Base de datos:** SQLite 3.35+ (con soporte para modo WAL, habilitado por defecto).
- **Sistema Operativo:** Linux (Ubuntu 22.04 LTS / Debian 12 en VPS de 1-2 vCPU, 1 GB RAM) o Windows / macOS para desarrollo.
- **Conectividad:** Salida HTTP/HTTPS hacia `mempool.space` y `data-api.binance.vision`.
- **Servidor SMTP (opcional):** Para despacho de alertas de movimientos e informes diarios.

---

## 🚀 Instalación y Puesta en Marcha

### 1. Clonar y preparar entorno virtual

```bash
git clone https://github.com/usuario/whalewatcher.git
cd whalewatcher

# Crear y activar entorno virtual
python -m venv .venv

# En Linux/macOS:
source .venv/bin/activate

# En Windows PowerShell:
.\.venv\Scripts\Activate.ps1
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
pip install -e .
```

### 3. Configurar variables de entorno

Copie la plantilla de configuración `.env.ejemplo`:

```bash
cp .env.ejemplo .env
```

Parámetros principales en `.env`:

```ini
# Base de datos
DATABASE_URL=sqlite:///datos/ballenas.db

# Umbrales de detección en BTC
UMBRAL_EXCHANGE_BTC=500.0
UMBRAL_INSTITUCIONAL_BTC=250.0
UMBRAL_DESCONOCIDO_BTC=1000.0

# SMTP (para notificaciones por correo)
ALERTAS_HABILITADAS=true
SMTP_HOST=smtp.ejemplo.com
SMTP_PUERTO=587
SMTP_USUARIO=alertas@midominio.com
SMTP_CONTRASENA=clave_segura_smtp
SMTP_REMITENTE=alertas@midominio.com
DESTINATARIOS_ALERTA=analista1@ejemplo.com,inversor@ejemplo.com
SMTP_STARTTLS=true
SMTP_SSL=false
```

---

## 💻 Interfaz de Línea de Comandos (CLI)

El punto de entrada unificado es `python -m btc_whale_intelligence`:

### Diagnóstico de salud operativa
Comprueba la conexión con SQLite (WAL e integridad), Mempool.space, Binance Spot y estado de SMTP:
```bash
python -m btc_whale_intelligence verificar-salud
```

### Inicializar base de datos
Crea las 15 tablas relacionales con sus índices y disparadores de inmutabilidad:
```bash
python -m btc_whale_intelligence inicializar-bd
```

### Importar catálogo de entidades
Carga el catálogo semilla inicial de exchanges, custodios y fondos:
```bash
python -m btc_whale_intelligence importar-entidades datos/semillas/entidades_iniciales.csv
```

### Ciclo integral de monitoreo
Ejecuta la sincronización de velas de mercado, ingesta de bloques y mempool on-chain, detección de movimientos, clasificación objetiva, extracción de características, pre-registro inmutable y despacho de alertas SMTP deduplicadas:
```bash
python -m btc_whale_intelligence ejecutar-ciclo-monitoreo
```

### Servidor y Panel de Control Web
Inicia el panel de control interactivo local con métricas en tiempo real, feed de ballenas, catálogo de entidades, gráficos dinámicos y auditoría de predicciones:
```bash
python -m btc_whale_intelligence servidor-web --puerto 8000
```
Luego abra `http://localhost:8000` en su navegador web.

### Evaluación retrospectiva de predicciones
Cierra horizontes vencidos (24H, 7D, 30D), obtiene el precio real de mercado y calcula errores y contraste frente a *Buy & Hold* y persistencia:
```bash
python -m btc_whale_intelligence evaluar-predicciones
```

### Envío del informe diario consolidado
Genera un correo con la actividad de las últimas 24h, flujos netos por entidad y balance de evaluaciones:
```bash
python -m btc_whale_intelligence enviar-reporte-diario
# Opcional: para una fecha específica en formato UTC:
python -m btc_whale_intelligence enviar-reporte-diario --fecha 2026-10-25
```

---

## 🐧 Despliegue en VPS Linux (systemd & logrotate)

Para mantener la plataforma funcionando 24/7 de forma autónoma y ligera:

1. **Copiar unidad de servicio y temporizador:**
   ```bash
   sudo cp despliegue/systemd/whalewatcher.service /etc/systemd/system/
   sudo cp despliegue/systemd/whalewatcher.timer /etc/systemd/system/
   ```

2. **Habilitar el temporizador (cada 5 minutos):**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now whalewatcher.timer
   sudo systemctl status whalewatcher.timer
   ```

3. **Configurar rotación de logs:**
   ```bash
   sudo cp despliegue/logrotate/whalewatcher /etc/logrotate.d/whalewatcher
   ```

---

## 🧪 Pruebas Automatizadas

La suite incluye pruebas unitarias y de integración que cubren el 100% de los flujos y validan el cumplimiento de las restricciones constitucionales:

```bash
# Ejecutar todas las pruebas con pytest
pytest -v
```

---

## ⚖️ Aviso Legal y Metodológico (Disclaimer)

> **AVISO IMPORTANTE:** Esta plataforma tiene fines estrictamente informativos, analíticos y experimentales. Ninguna transferencia on-chain detectada debe interpretarse de forma directa o inequívoca como una compra o una venta de Bitcoin. El sistema no proporciona asesoramiento financiero ni recomendaciones de inversión. Todas las predicciones son hipótesis estadísticas sujetas a incertidumbre y riesgo sustancial de mercado.
