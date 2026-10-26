"""Logging estructurado con rotación y redacción de secretos (Principios XI y XII)."""

from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Iterable

from .configuracion import Configuracion

_PATRONES_SENSIBLES = [
    # user:password@host en URLs
    re.compile(r"(?P<pre>://[^:/@\s]+:)(?P<secreto>[^@\s]+)(?P<post>@)"),
    # password=..., token=..., api_key=...
    re.compile(r"(?i)(?P<pre>(password|passwd|contrasena|token|api[_-]?key|secret)\s*[=:]\s*)(?P<secreto>[^\s,;&]+)(?P<post>)"),
]


class FiltroSecretos(logging.Filter):
    """Sustituye secretos conocidos y patrones sensibles por '***'."""

    def __init__(self, secretos: Iterable[str] = ()) -> None:
        super().__init__()
        self._secretos = [s for s in secretos if s and len(s) >= 3]

    def redactar(self, texto: str) -> str:
        for secreto in self._secretos:
            texto = texto.replace(secreto, "***")
        for patron in _PATRONES_SENSIBLES:
            texto = patron.sub(lambda m: f"{m.group('pre')}***{m.group('post')}", texto)
        return texto

    def filter(self, record: logging.LogRecord) -> bool:
        mensaje = record.getMessage()
        redactado = self.redactar(mensaje)
        if redactado != mensaje:
            record.msg = redactado
            record.args = None
        return True


def configurar_logging(config: Configuracion) -> logging.Logger:
    raiz = logging.getLogger("btc_whale_intelligence")
    raiz.setLevel(config.nivel_log.upper())
    for manejador in list(raiz.handlers):
        raiz.removeHandler(manejador)

    formato = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    filtro = FiltroSecretos(config.secretos())

    consola = logging.StreamHandler()
    consola.setFormatter(formato)
    consola.addFilter(filtro)
    raiz.addHandler(consola)

    if config.archivo_log:
        Path(config.archivo_log).parent.mkdir(parents=True, exist_ok=True)
        archivo = RotatingFileHandler(
            config.archivo_log,
            maxBytes=config.log_max_bytes,
            backupCount=config.log_respaldos,
            encoding="utf-8",
        )
        archivo.setFormatter(formato)
        archivo.addFilter(filtro)
        raiz.addHandler(archivo)

    raiz.propagate = False
    return raiz
