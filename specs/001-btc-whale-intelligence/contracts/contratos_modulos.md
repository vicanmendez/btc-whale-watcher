# Module Contracts: BTC Whale Intelligence

**Feature**: `001-btc-whale-intelligence`  
**Date**: 2026-10-26  
**Standards**: Tipado estricto con `dataclasses` y `pydantic` v2 / `typing` estándar de Python. Nombres en español según el Principio XVI de la Constitución.

---

## 1. Contrato: Ingesta On-Chain (`ProveedorOnChain`)

Interfaz abstracta para interactuar con APIs de exploradores de Bitcoin (Mempool.space y Blockstream Esplora).

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

@dataclass(frozen=True)
class EntradaDetalle:
    indice_vin: int
    txid_anterior: str
    vout_anterior: int
    direccion: Optional[str]
    monto_satoshis: int

@dataclass(frozen=True)
class SalidaDetalle:
    indice_vout: int
    direccion: Optional[str]
    monto_satoshis: int

@dataclass(frozen=True)
class TransaccionPlana:
    txid: str
    bloque_altura: Optional[int]
    bloque_hash: Optional[str]
    marca_tiempo_utc: datetime
    total_entrada_satoshis: int
    total_salida_satoshis: int
    comision_satoshis: int
    tamano_bytes: int
    peso_vbytes: int
    confirmaciones: int
    es_mempool: bool
    entradas: List[EntradaDetalle]
    salidas: List[SalidaDetalle]

class ProveedorOnChain(ABC):
    @abstractmethod
    def obtener_altura_punta(self) -> int:
        """Retorna la altura del bloque más reciente confirmado."""
        ...

    @abstractmethod
    def obtener_transacciones_bloque(self, hash_o_altura: str) -> List[TransaccionPlana]:
        """Obtiene todas las transacciones incluidas en un bloque."""
        ...

    @abstractmethod
    def obtener_transaccion(self, txid: str) -> Optional[TransaccionPlana]:
        """Obtiene una transacción puntual por su txid."""
        ...

    @abstractmethod
    def obtener_saldo_direccion(self, direccion_btc: str) -> int:
        """Retorna el saldo actual en satoshis de una dirección observada."""
        ...
```

---

## 2. Contrato: Ingesta de Mercado (`ProveedorMercado`)

Interfaz abstracta para la obtención de datos de mercado spot (Binance y CoinGecko).

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

@dataclass(frozen=True)
class VelaMercadoDTO:
    marca_tiempo_apertura: datetime
    precio_apertura: float
    precio_maximo: float
    precio_minimo: float
    precio_cierre: float
    volumen_btc: float
    volumen_usdt: float
    conteo_operaciones: int

@dataclass(frozen=True)
class InstantaneaMercado:
    marca_tiempo_utc: datetime
    precio_spot_usd: float
    volumen_24h_usd: float
    variacion_24h_pct: float
    profundidad_compra_2pct_usd: Optional[float]
    profundidad_venta_2pct_usd: Optional[float]

class ProveedorMercado(ABC):
    @abstractmethod
    def obtener_precio_instantaneo(self, par: str = "BTCUSDT") -> float:
        """Obtiene el último precio spot negociado."""
        ...

    @abstractmethod
    def obtener_velas(
        self, par: str, intervalo: str, inicio: datetime, fin: datetime
    ) -> List[VelaMercadoDTO]:
        """Obtiene velas OHLCV históricas para una ventana temporal."""
        ...

    @abstractmethod
    def obtener_instantanea_mercado(self, par: str = "BTCUSDT") -> InstantaneaMercado:
        """Obtiene resumen de liquidez y cotización para contextualizar un evento."""
        ...
```

---

## 3. Contrato: Detección y Clasificación (`ClasificadorMovimientos`)

Clasifica movimientos según evidencia objetiva sin inferir automáticamente compras o ventas (Principios III y IV).

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class CategoriaMovimiento(str, Enum):
    TRANSFERENCIA_INTERNA = "TRANSFERENCIA_INTERNA"
    ENTRADA_EXCHANGE = "ENTRADA_EXCHANGE"
    SALIDA_EXCHANGE = "SALIDA_EXCHANGE"
    MOVIMIENTO_CORPORATIVO = "MOVIMIENTO_CORPORATIVO"
    DESCONOCIDA = "DESCONOCIDA"
    INCIERTA = "INCIERTA"

@dataclass(frozen=True)
class ClasificacionResultado:
    categoria: CategoriaMovimiento
    entidad_origen_id: Optional[int]
    entidad_destino_id: Optional[int]
    nivel_confianza: float  # Entre 0.0 y 1.0
    evidencia: str
    limitaciones: str
    es_relevante: bool

class ClasificadorMovimientos(ABC):
    @abstractmethod
    def clasificar(self, transaccion: TransaccionPlana) -> ClasificacionResultado:
        """Analiza entradas y salidas y aplica heurísticas para clasificar el movimiento."""
        ...
```

---

## 4. Contrato: Análisis de Impacto y Predicciones (`AnalizadorImpacto`)

Calcula métricas de impacto y pre-registra predicciones respetando los principios V, VI, VII, VIII, IX y XV.

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class EstadoEstimacion(str, Enum):
    ACTIVA = "ACTIVA"
    INDETERMINADA = "INDETERMINADA"
    EVALUADA = "EVALUADA"

@dataclass(frozen=True)
class EstimacionHorizonte:
    horizonte: str  # "24H", "7D", "30D"
    estado: EstadoEstimacion
    probabilidad_alcista: Optional[float]
    probabilidad_bajista: Optional[float]
    probabilidad_neutral: Optional[float]
    retorno_esperado_pct: Optional[float]
    rango_incertidumbre_inferior: Optional[float]
    rango_incertidumbre_superior: Optional[float]
    razon_indeterminacion: Optional[str]
    version_modelo: str

class AnalizadorImpacto(ABC):
    @abstractmethod
    def evaluar_evento(
        self, evento_id: int, caracteristicas_id: int
    ) -> List[EstimacionHorizonte]:
        """Genera estimaciones para los 3 horizontes o devuelve INDETERMINADO con justificación."""
        ...
```

---

## 5. Contrato: Despacho de Alertas (`DespachadorAlertas`)

Entrega de alertas mediante SMTP con garantía de idempotencia (Principio X y XI).

```python
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class AlertaMensaje:
    evento_id: int
    asunto: str
    cuerpo_texto: str
    cuerpo_html: str
    destinatario: str
    tipo_alerta: str  # "MOVIMIENTO_RELEVANTE", "INFORME_DIARIO", "ERROR_CRITICO"

@dataclass(frozen=True)
class ResultadoEnvio:
    exito: bool
    identificador_envio: Optional[str]
    error_detalle: Optional[str]

class DespachadorAlertas(ABC):
    @abstractmethod
    def enviar_alerta(self, mensaje: AlertaMensaje) -> ResultadoEnvio:
        """Valida idempotencia y despacha el correo electrónico por SMTP."""
        ...
```

---

## 6. Contrato: CLI y Ejecución

Interfaz de línea de comandos para automatización en VPS Linux mediante tareas cron o systemd.

```text
Uso del CLI: python -m btc_whale_intelligence [COMANDO] [OPCIONES]

Comandos principales:
  sincronizar-onchain    Consulta nuevos bloques y transacciones en mempool.
  sincronizar-mercado    Actualiza cotizaciones y velas de BTC/USDT.
  evaluar-predicciones   Cierra horizontes vencidos y calcula Brier Score vs Baselines.
  enviar-reporte-diario  Genera y despacha el informe diario consolidado por correo.
  importar-entidades     Carga catálogo de entidades y direcciones desde archivo CSV/JSON.
  verificar-salud        Comprueba conectividad con APIs públicas y base de datos.
```
