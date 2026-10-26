"""Modelos ORM (SQLAlchemy 2.0). Tablas y columnas en español (Principio XVI).

Separación epistémica (Principio III):
- Datos observados: transacciones_onchain, entradas_salidas, saldos_historicos, velas_mercado.
- Inferencias: atribuciones_direcciones, eventos_analizados (clasificación).
- Predicciones: predicciones (inmutables, pre-registradas).
- Resultados históricos: resultados_predicciones.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    DDL,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

from ..tiempo import a_utc, ahora_utc

CATEGORIAS_ENTIDAD = ("Exchange", "Custodio", "Empresa", "Fondo", "Minero", "Gran_Tenedor", "Desconocida")
CATEGORIAS_MOVIMIENTO = (
    "TRANSFERENCIA_INTERNA",
    "ENTRADA_EXCHANGE",
    "SALIDA_EXCHANGE",
    "MOVIMIENTO_CORPORATIVO",
    "DESCONOCIDA",
    "INCIERTA",
)
ESTADOS_EVENTO = ("DETECTADO", "ENRIQUECIDO", "ANALIZADO", "ALERTADO")
ESTADOS_ALERTA = ("PENDIENTE", "ENVIADO", "REINTENTO", "FALLIDO")


def _lista_sql(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in valores)


class FechaHoraUTC(TypeDecorator):
    """Guarda datetimes como UTC ingenuo en SQLite y los devuelve conscientes (UTC)."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, valor, dialecto):
        if valor is None:
            return None
        return a_utc(valor).replace(tzinfo=None)

    def process_result_value(self, valor, dialecto):
        if valor is None:
            return None
        return a_utc(valor)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Entidades y direcciones
# ---------------------------------------------------------------------------


class EntidadORM(Base):
    __tablename__ = "entidades"
    __table_args__ = (
        CheckConstraint(f"categoria IN ({_lista_sql(CATEGORIAS_ENTIDAD)})", name="ck_entidad_categoria"),
        CheckConstraint("nivel_confianza BETWEEN 0.0 AND 1.0", name="ck_entidad_confianza"),
        CheckConstraint("umbral_personalizado_btc IS NULL OR umbral_personalizado_btc >= 0", name="ck_entidad_umbral"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    categoria: Mapped[str] = mapped_column(String(50), nullable=False)
    nivel_confianza: Mapped[float] = mapped_column(Float, nullable=False)
    fuentes_identificacion: Mapped[str] = mapped_column(Text, nullable=False)
    # Umbral específico de la entidad (RF-05). 0 = cualquier movimiento es relevante.
    umbral_personalizado_btc: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    creado_en: Mapped[datetime] = mapped_column(FechaHoraUTC, nullable=False, default=ahora_utc)
    actualizado_en: Mapped[datetime] = mapped_column(
        FechaHoraUTC, nullable=False, default=ahora_utc, onupdate=ahora_utc
    )

    atribuciones: Mapped[list["AtribucionDireccionORM"]] = relationship(back_populates="entidad")


class DireccionORM(Base):
    __tablename__ = "direcciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    direccion_btc: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    formato: Mapped[str] = mapped_column(String(20), nullable=False)
    # NULL = saldo aún no consultado (distinto de saldo cero).
    saldo_actual_satoshis: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    conteo_transacciones: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    primera_vista_en: Mapped[datetime] = mapped_column(FechaHoraUTC, nullable=False, default=ahora_utc)
    ultima_consulta_en: Mapped[Optional[datetime]] = mapped_column(FechaHoraUTC, nullable=True)

    atribuciones: Mapped[list["AtribucionDireccionORM"]] = relationship(back_populates="direccion")


class AtribucionDireccionORM(Base):
    """Inferencia documentada: 'la dirección X pertenece a la entidad Y' (Principios III y IV)."""

    __tablename__ = "atribuciones_direcciones"
    __table_args__ = (
        UniqueConstraint("direccion_id", "entidad_id", name="uq_atribucion_direccion_entidad"),
        CheckConstraint("grado_certeza BETWEEN 0.0 AND 1.0", name="ck_atribucion_certeza"),
        CheckConstraint("length(trim(fuente_atribucion)) > 0", name="ck_atribucion_fuente"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    direccion_id: Mapped[int] = mapped_column(ForeignKey("direcciones.id", ondelete="CASCADE"), nullable=False, index=True)
    entidad_id: Mapped[int] = mapped_column(ForeignKey("entidades.id", ondelete="CASCADE"), nullable=False, index=True)
    grado_certeza: Mapped[float] = mapped_column(Float, nullable=False)
    fuente_atribucion: Mapped[str] = mapped_column(Text, nullable=False)
    fecha_verificacion: Mapped[date] = mapped_column(Date, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    creado_en: Mapped[datetime] = mapped_column(FechaHoraUTC, nullable=False, default=ahora_utc)

    direccion: Mapped[DireccionORM] = relationship(back_populates="atribuciones")
    entidad: Mapped[EntidadORM] = relationship(back_populates="atribuciones")


# ---------------------------------------------------------------------------
# Datos on-chain observados
# ---------------------------------------------------------------------------


class TransaccionOnChainORM(Base):
    __tablename__ = "transacciones_onchain"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    txid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    bloque_altura: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    bloque_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # Hora del bloque si está confirmada; si no, hora de primera observación en mempool.
    marca_tiempo_utc: Mapped[datetime] = mapped_column(FechaHoraUTC, nullable=False)
    total_entrada_satoshis: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_salida_satoshis: Mapped[int] = mapped_column(BigInteger, nullable=False)
    comision_satoshis: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tamano_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    peso_vbytes: Mapped[int] = mapped_column(Integer, nullable=False)
    confirmaciones: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    es_mempool: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    primera_deteccion_en: Mapped[datetime] = mapped_column(FechaHoraUTC, nullable=False, default=ahora_utc)
    actualizado_en: Mapped[datetime] = mapped_column(FechaHoraUTC, nullable=False, default=ahora_utc, onupdate=ahora_utc)

    flujos: Mapped[list["EntradaSalidaORM"]] = relationship(
        back_populates="transaccion", cascade="all, delete-orphan", order_by="EntradaSalidaORM.id"
    )


class EntradaSalidaORM(Base):
    __tablename__ = "entradas_salidas"
    __table_args__ = (
        UniqueConstraint("transaccion_id", "tipo", "indice", name="uq_flujo_tx_tipo_indice"),
        CheckConstraint("tipo IN ('ENTRADA', 'SALIDA')", name="ck_flujo_tipo"),
        CheckConstraint("monto_satoshis >= 0", name="ck_flujo_monto"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaccion_id: Mapped[int] = mapped_column(
        ForeignKey("transacciones_onchain.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tipo: Mapped[str] = mapped_column(String(10), nullable=False)
    indice: Mapped[int] = mapped_column(Integer, nullable=False)
    direccion_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("direcciones.id", ondelete="SET NULL"), nullable=True, index=True
    )
    monto_satoshis: Mapped[int] = mapped_column(BigInteger, nullable=False)

    transaccion: Mapped[TransaccionOnChainORM] = relationship(back_populates="flujos")
    direccion: Mapped[Optional[DireccionORM]] = relationship()


class SaldoHistoricoORM(Base):
    __tablename__ = "saldos_historicos"
    __table_args__ = (UniqueConstraint("direccion_id", "bloque_altura", name="uq_saldo_direccion_bloque"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    direccion_id: Mapped[int] = mapped_column(ForeignKey("direcciones.id", ondelete="CASCADE"), nullable=False)
    bloque_altura: Mapped[int] = mapped_column(Integer, nullable=False)
    saldo_satoshis: Mapped[int] = mapped_column(BigInteger, nullable=False)
    marca_tiempo_utc: Mapped[datetime] = mapped_column(FechaHoraUTC, nullable=False)


# ---------------------------------------------------------------------------
# Datos de mercado observados
# ---------------------------------------------------------------------------


class VelaMercadoORM(Base):
    __tablename__ = "velas_mercado"
    __table_args__ = (
        UniqueConstraint("fuente", "par", "intervalo", "marca_tiempo_apertura", name="uq_vela"),
        Index("ix_velas_tiempo", "par", "intervalo", "marca_tiempo_apertura"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fuente: Mapped[str] = mapped_column(String(50), nullable=False, default="Binance")
    par: Mapped[str] = mapped_column(String(20), nullable=False, default="BTCUSDT")
    intervalo: Mapped[str] = mapped_column(String(10), nullable=False)
    marca_tiempo_apertura: Mapped[datetime] = mapped_column(FechaHoraUTC, nullable=False)
    marca_tiempo_cierre: Mapped[datetime] = mapped_column(FechaHoraUTC, nullable=False)
    precio_apertura: Mapped[float] = mapped_column(Float, nullable=False)
    precio_maximo: Mapped[float] = mapped_column(Float, nullable=False)
    precio_minimo: Mapped[float] = mapped_column(Float, nullable=False)
    precio_cierre: Mapped[float] = mapped_column(Float, nullable=False)
    volumen_btc: Mapped[float] = mapped_column(Float, nullable=False)
    volumen_usdt: Mapped[float] = mapped_column(Float, nullable=False)
    conteo_operaciones: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


# ---------------------------------------------------------------------------
# Inferencias, análisis y predicciones
# ---------------------------------------------------------------------------


class EventoAnalizadoORM(Base):
    __tablename__ = "eventos_analizados"
    __table_args__ = (
        CheckConstraint(f"categoria_movimiento IN ({_lista_sql(CATEGORIAS_MOVIMIENTO)})", name="ck_evento_categoria"),
        CheckConstraint(f"estado_procesamiento IN ({_lista_sql(ESTADOS_EVENTO)})", name="ck_evento_estado"),
        CheckConstraint("nivel_confianza BETWEEN 0.0 AND 1.0", name="ck_evento_confianza"),
        Index("ix_evento_estado", "estado_procesamiento"),
        Index("ix_evento_referencia", "marca_tiempo_referencia"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaccion_id: Mapped[int] = mapped_column(ForeignKey("transacciones_onchain.id"), unique=True, nullable=False)
    entidad_origen_id: Mapped[Optional[int]] = mapped_column(ForeignKey("entidades.id"), nullable=True)
    entidad_destino_id: Mapped[Optional[int]] = mapped_column(ForeignKey("entidades.id"), nullable=True)
    monto_relevante_btc: Mapped[float] = mapped_column(Float, nullable=False)
    monto_total_salidas_btc: Mapped[float] = mapped_column(Float, nullable=False)
    umbral_aplicado_btc: Mapped[float] = mapped_column(Float, nullable=False)
    categoria_movimiento: Mapped[str] = mapped_column(String(50), nullable=False)
    nivel_confianza: Mapped[float] = mapped_column(Float, nullable=False)
    evidencia: Mapped[str] = mapped_column(Text, nullable=False)
    limitaciones: Mapped[str] = mapped_column(Text, nullable=False)
    # Hora de referencia = primera detección por el sistema (información disponible).
    marca_tiempo_referencia: Mapped[datetime] = mapped_column(FechaHoraUTC, nullable=False)
    precio_referencia_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    analisis_descriptivo_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    estado_procesamiento: Mapped[str] = mapped_column(String(20), nullable=False, default="DETECTADO")
    creado_en: Mapped[datetime] = mapped_column(FechaHoraUTC, nullable=False, default=ahora_utc)
    actualizado_en: Mapped[datetime] = mapped_column(FechaHoraUTC, nullable=False, default=ahora_utc, onupdate=ahora_utc)

    transaccion: Mapped[TransaccionOnChainORM] = relationship()
    entidad_origen: Mapped[Optional[EntidadORM]] = relationship(foreign_keys=[entidad_origen_id])
    entidad_destino: Mapped[Optional[EntidadORM]] = relationship(foreign_keys=[entidad_destino_id])
    caracteristicas: Mapped[Optional["CaracteristicaCalculadaORM"]] = relationship(
        back_populates="evento", uselist=False
    )
    predicciones: Mapped[list["PrediccionORM"]] = relationship(back_populates="evento", order_by="PrediccionORM.id")


class CaracteristicaCalculadaORM(Base):
    """Variables calculadas solo con información anterior a la hora de referencia (Principio VII)."""

    __tablename__ = "caracteristicas_calculadas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evento_id: Mapped[int] = mapped_column(
        ForeignKey("eventos_analizados.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    precio_referencia_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    marca_tiempo_precio: Mapped[Optional[datetime]] = mapped_column(FechaHoraUTC, nullable=True)
    volumen_24h_btc: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ratio_monto_volumen_24h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    variacion_precio_1h_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    variacion_precio_24h_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volatilidad_historica_7d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    flujo_neto_entidad_24h_btc: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    conteo_eventos_previos_24h: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    profundidad_compra_2pct_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    profundidad_venta_2pct_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    datos_faltantes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    calculado_en: Mapped[datetime] = mapped_column(FechaHoraUTC, nullable=False, default=ahora_utc)

    evento: Mapped[EventoAnalizadoORM] = relationship(back_populates="caracteristicas")


class PrediccionORM(Base):
    """Pre-registro inmutable (Principio IX). Ninguna fila puede modificarse ni borrarse."""

    __tablename__ = "predicciones"
    __table_args__ = (
        UniqueConstraint("evento_id", "horizonte", name="uq_prediccion_evento_horizonte"),
        CheckConstraint("horizonte IN ('24H', '7D', '30D')", name="ck_prediccion_horizonte"),
        CheckConstraint("tipo_estimacion IN ('PROBABILISTICA', 'INDETERMINADA')", name="ck_prediccion_tipo"),
        CheckConstraint(
            "(tipo_estimacion = 'INDETERMINADA' AND probabilidad_alcista IS NULL AND probabilidad_bajista IS NULL "
            "AND probabilidad_neutral IS NULL AND razon_indeterminacion IS NOT NULL) OR "
            "(tipo_estimacion = 'PROBABILISTICA' AND probabilidad_alcista IS NOT NULL AND "
            "probabilidad_bajista IS NOT NULL AND probabilidad_neutral IS NOT NULL AND "
            "abs(probabilidad_alcista + probabilidad_bajista + probabilidad_neutral - 1.0) < 0.0001)",
            name="ck_prediccion_coherencia",
        ),
        Index("ix_prediccion_vencimiento", "fecha_vencimiento_utc"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evento_id: Mapped[int] = mapped_column(ForeignKey("eventos_analizados.id"), nullable=False)
    horizonte: Mapped[str] = mapped_column(String(10), nullable=False)
    tipo_estimacion: Mapped[str] = mapped_column(String(20), nullable=False)
    marca_tiempo_referencia: Mapped[datetime] = mapped_column(FechaHoraUTC, nullable=False)
    marca_tiempo_registro: Mapped[datetime] = mapped_column(FechaHoraUTC, nullable=False)
    fecha_vencimiento_utc: Mapped[datetime] = mapped_column(FechaHoraUTC, nullable=False)
    precio_inicial_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    umbral_neutral_pct: Mapped[float] = mapped_column(Float, nullable=False)
    probabilidad_alcista: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    probabilidad_bajista: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    probabilidad_neutral: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    retorno_esperado_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rango_incertidumbre_inferior: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rango_incertidumbre_superior: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    razon_indeterminacion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidencia: Mapped[str] = mapped_column(Text, nullable=False)
    limitaciones: Mapped[str] = mapped_column(Text, nullable=False)
    modelo_version: Mapped[str] = mapped_column(String(50), nullable=False)
    # Instantánea de los datos disponibles al generar la predicción (trazabilidad, RF-12).
    datos_entrada_json: Mapped[str] = mapped_column(Text, nullable=False)
    hash_contenido: Mapped[str] = mapped_column(String(64), nullable=False)

    evento: Mapped[EventoAnalizadoORM] = relationship(back_populates="predicciones")
    resultado: Mapped[Optional["ResultadoPrediccionORM"]] = relationship(back_populates="prediccion", uselist=False)


class ResultadoPrediccionORM(Base):
    __tablename__ = "resultados_predicciones"
    __table_args__ = (
        CheckConstraint("estado_resultado IN ('EVALUADO', 'SIN_DATOS')", name="ck_resultado_estado"),
        CheckConstraint(
            "resultado_categoria IS NULL OR resultado_categoria IN ('ALCISTA', 'BAJISTA', 'NEUTRAL')",
            name="ck_resultado_categoria",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prediccion_id: Mapped[int] = mapped_column(ForeignKey("predicciones.id"), unique=True, nullable=False)
    estado_resultado: Mapped[str] = mapped_column(String(20), nullable=False)
    precio_final_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    marca_tiempo_precio_final: Mapped[Optional[datetime]] = mapped_column(FechaHoraUTC, nullable=True)
    retorno_real_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    resultado_categoria: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    acierto_clasificacion: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    brier_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    error_absoluto_modelo_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Referencias obligatorias (Principio VIII)
    retorno_baseline_buy_hold_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    retorno_baseline_persistencia_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    brier_baseline_persistencia: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    error_absoluto_persistencia_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evaluado_en: Mapped[datetime] = mapped_column(FechaHoraUTC, nullable=False, default=ahora_utc)

    prediccion: Mapped[PrediccionORM] = relationship(back_populates="resultado")


class ValidacionModeloORM(Base):
    """Resultado de un backtesting fuera de muestra. Requisito para activar un modelo (Principio XV)."""

    __tablename__ = "validaciones_modelos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    modelo_version: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    horizonte: Mapped[str] = mapped_column(String(10), nullable=False)
    ejecutado_en: Mapped[datetime] = mapped_column(FechaHoraUTC, nullable=False, default=ahora_utc)
    n_desarrollo: Mapped[int] = mapped_column(Integer, nullable=False)
    n_reserva: Mapped[int] = mapped_column(Integer, nullable=False)
    brier_modelo: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    brier_referencia: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    brier_persistencia: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ic_inferior_mejora: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ic_superior_mejora: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    aprobado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    informe_json: Mapped[str] = mapped_column(Text, nullable=False)


# ---------------------------------------------------------------------------
# Alertas y operación
# ---------------------------------------------------------------------------


class AlertaDespachadaORM(Base):
    __tablename__ = "alertas_despachadas"
    __table_args__ = (
        CheckConstraint(f"estado IN ({_lista_sql(ESTADOS_ALERTA)})", name="ck_alerta_estado"),
        Index("ix_alerta_estado", "estado"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evento_id: Mapped[Optional[int]] = mapped_column(ForeignKey("eventos_analizados.id"), nullable=True)
    tipo_alerta: Mapped[str] = mapped_column(String(40), nullable=False)
    clave_idempotencia: Mapped[str] = mapped_column(String(200), nullable=False)
    hash_idempotencia: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    canal: Mapped[str] = mapped_column(String(20), nullable=False, default="EMAIL_SMTP")
    destinatario: Mapped[str] = mapped_column(String(200), nullable=False)
    asunto: Mapped[str] = mapped_column(String(300), nullable=False)
    cuerpo_texto: Mapped[str] = mapped_column(Text, nullable=False)
    cuerpo_html: Mapped[str] = mapped_column(Text, nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDIENTE")
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ultimo_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(FechaHoraUTC, nullable=False, default=ahora_utc)
    despachado_en: Mapped[Optional[datetime]] = mapped_column(FechaHoraUTC, nullable=True)


class EstadoIngestaORM(Base):
    __tablename__ = "estado_ingesta"

    fuente: Mapped[str] = mapped_column(String(50), primary_key=True)
    ultimo_bloque_procesado: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ultimo_hash_procesado: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    ultima_sincronizacion_utc: Mapped[Optional[datetime]] = mapped_column(FechaHoraUTC, nullable=True)
    conteo_errores_consecutivos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ultimo_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class ErrorOperativoORM(Base):
    """Registro de errores de APIs, datos faltantes, fallos de correo y ejecuciones incompletas (RF-13)."""

    __tablename__ = "errores_operativos"
    __table_args__ = (Index("ix_error_ocurrido", "ocurrido_en"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    componente: Mapped[str] = mapped_column(String(60), nullable=False)
    tipo_error: Mapped[str] = mapped_column(String(60), nullable=False)
    mensaje: Mapped[str] = mapped_column(Text, nullable=False)
    contexto: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ocurrido_en: Mapped[datetime] = mapped_column(FechaHoraUTC, nullable=False, default=ahora_utc)


# ---------------------------------------------------------------------------
# Inmutabilidad de predicciones (ORM + triggers SQLite)
# ---------------------------------------------------------------------------


class ErrorPrediccionInmutable(RuntimeError):
    """Se intentó modificar o borrar una predicción pre-registrada."""


@event.listens_for(Session, "before_flush")
def _proteger_predicciones(sesion: Session, _contexto, _instancias) -> None:
    for objeto in sesion.dirty:
        if isinstance(objeto, PrediccionORM) and sesion.is_modified(objeto, include_collections=False):
            raise ErrorPrediccionInmutable(f"La predicción {objeto.id} es inmutable")
    for objeto in sesion.deleted:
        if isinstance(objeto, PrediccionORM):
            raise ErrorPrediccionInmutable(f"La predicción {objeto.id} no puede borrarse")


event.listen(
    PrediccionORM.__table__,
    "after_create",
    DDL(
        "CREATE TRIGGER IF NOT EXISTS tr_predicciones_sin_update BEFORE UPDATE ON predicciones "
        "BEGIN SELECT RAISE(ABORT, 'predicciones inmutables'); END;"
    ).execute_if(dialect="sqlite"),
)
event.listen(
    PrediccionORM.__table__,
    "after_create",
    DDL(
        "CREATE TRIGGER IF NOT EXISTS tr_predicciones_sin_delete BEFORE DELETE ON predicciones "
        "BEGIN SELECT RAISE(ABORT, 'predicciones inmutables'); END;"
    ).execute_if(dialect="sqlite"),
)
