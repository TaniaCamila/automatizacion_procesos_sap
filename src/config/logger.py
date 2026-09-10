from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

from .config import resolve_log_dir


LOG_FILE: str = "app.log"


class LoggerManager:
    """Gestor centralizado de logging para la aplicación.

    Proporciona loggers configurados con fichero y salida a consola.
    """

    _configured: set[str] = set()
    _default_level: int = logging.INFO

    @classmethod
    def _ensure_log_dir(cls) -> None:
        """Crear la carpeta de logs si no existe."""
        resolve_log_dir().mkdir(parents=True, exist_ok=True)

    @classmethod
    def _configure_handlers(cls, logger: logging.Logger) -> None:
        """Configurar los handlers (archivo y consola) para un logger.

        El formateo incluye fecha y hora, nivel, nombre del módulo y mensaje.
        """
        fmt = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        datefmt = "%Y-%m-%d %H:%M:%S"
        formatter = logging.Formatter(fmt, datefmt=datefmt)

        file_path: Path = resolve_log_dir() / LOG_FILE
        file_handler = logging.FileHandler(file_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(cls._default_level)

        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        stream_handler.setLevel(cls._default_level)

        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)
        logger.propagate = False

    @classmethod
    def rebind_isolated_file_handlers(cls) -> None:
        """Reasigna FileHandlers de app.log al `resolve_log_dir()` actual.

        Solo para pruebas aisladas. No toca handlers que no apunten a app.log.
        """
        cls._ensure_log_dir()
        dest = (resolve_log_dir() / LOG_FILE).resolve()
        fallback_fmt = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        for name in list(cls._configured):
            logger = logging.getLogger(name)
            for handler in list(logger.handlers):
                if not isinstance(handler, logging.FileHandler):
                    continue
                current = Path(handler.baseFilename).resolve()
                if current.name != LOG_FILE or current == dest:
                    continue
                level = handler.level
                formatter = handler.formatter or fallback_fmt
                logger.removeHandler(handler)
                handler.close()
                replacement = logging.FileHandler(dest, encoding="utf-8")
                replacement.setFormatter(formatter)
                replacement.setLevel(level)
                logger.addHandler(replacement)

    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """Obtener un logger configurado.

        Uso:
            logger = LoggerManager.get_logger(__name__)

        Args:
            name: Nombre del logger, típicamente `__name__`.

        Returns:
            logging.Logger: Logger configurado con archivo y consola.
        """
        cls._ensure_log_dir()
        logger = logging.getLogger(name)
        if name in cls._configured:
            return logger

        logger.setLevel(cls._default_level)
        cls._configure_handlers(logger)
        cls._configured.add(name)
        return logger

    @classmethod
    def set_level(cls, level: int | str) -> None:
        """Cambiar el nivel de log global y de los handlers existentes.

        Args:
            level: Nivel numérico de logging o nombre (por ejemplo, "DEBUG").
        """
        if isinstance(level, str):
            level_val = logging.getLevelName(level.upper())
        else:
            level_val = level

        if not isinstance(level_val, int):
            # Fallback si el nombre no es válido
            level_val = logging.INFO

        cls._default_level = level_val

        for name in set(cls._configured):
            logger = logging.getLogger(name)
            logger.setLevel(level_val)
            for handler in logger.handlers:
                handler.setLevel(level_val)


__all__ = ("LoggerManager",)
