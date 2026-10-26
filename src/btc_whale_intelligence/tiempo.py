"""Utilidades de tiempo: todo el sistema trabaja en UTC con datetimes conscientes de zona."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

DURACION_HORIZONTE: dict[str, timedelta] = {
    "24H": timedelta(hours=24),
    "7D": timedelta(days=7),
    "30D": timedelta(days=30),
}


def ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


def a_utc(momento: datetime) -> datetime:
    """Normaliza a UTC consciente. Un datetime ingenuo se interpreta como UTC."""
    if momento.tzinfo is None:
        return momento.replace(tzinfo=timezone.utc)
    return momento.astimezone(timezone.utc)


def desde_epoch(segundos: float) -> datetime:
    return datetime.fromtimestamp(segundos, tz=timezone.utc)


def a_epoch_ms(momento: datetime) -> int:
    return int(a_utc(momento).timestamp() * 1000)
