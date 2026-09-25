"""Small project-owned logging facade backed by Loguru.

Configuration is explicit. Callers must pass safe messages and context only;
never include credentials, authorization headers, or raw provider requests.
"""

import sys
from threading import Lock

from loguru import logger

_config_lock = Lock()
_configured = False
_sink_id: int | None = None
_configured_level: str | None = None


def configure_logging(level: str = "INFO") -> None:
    """Configure one stderr sink; repeated calls replace the project's sink."""
    global _configured, _configured_level, _sink_id

    with _config_lock:
        logger.level(level)  # Validate before changing any installed sink.
        if _configured and level == _configured_level:
            return
        if not _configured:
            # Loguru installs a default stderr sink on import. Replace it only
            # when the application explicitly opts into logging configuration.
            logger.remove()
        elif _sink_id is not None:
            logger.remove(_sink_id)
        _sink_id = logger.add(sys.stderr, level=level)
        _configured_level = level
        _configured = True


def debug(message: str, **context: object) -> None:
    """Log a debug message with structured, request-local context."""
    logger.bind(**context).debug(message)


def info(message: str, **context: object) -> None:
    """Log an informational message with structured context."""
    logger.bind(**context).info(message)


def warning(message: str, **context: object) -> None:
    """Log a warning with structured context."""
    logger.bind(**context).warning(message)


def error(message: str, **context: object) -> None:
    """Log an error with structured context."""
    logger.bind(**context).error(message)


def exception(message: str, **context: object) -> None:
    """Log an error and the active exception traceback."""
    logger.bind(**context).exception(message)
