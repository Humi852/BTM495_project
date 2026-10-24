from http import HTTPStatus
import logging
import sys
from typing import TextIO


_LEVEL_COLORS = {
    logging.WARNING: "\033[33m",
    logging.ERROR: "\033[31m",
    logging.CRITICAL: "\033[1;31m",
}
_RESET_COLOR = "\033[0m"


class BackendFormatter(logging.Formatter):
    def __init__(self, stream: TextIO) -> None:
        super().__init__(
            fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self._use_colors = stream.isatty()

    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        color = _LEVEL_COLORS.get(record.levelno)
        if not self._use_colors or color is None:
            return formatted
        return f"{color}{formatted}{_RESET_COLOR}"


def http_status_label(status_code: int) -> str:
    try:
        phrase = HTTPStatus(status_code).phrase
    except ValueError:
        phrase = "Unknown status"
    if status_code == HTTPStatus.NOT_MODIFIED:
        return f"{phrase} (browser cache)"
    return phrase


def get_logger(name: str) -> logging.Logger:
    if not name.startswith("backend"):
        name = f"backend.{name}"
    return logging.getLogger(name)


def configure_backend_logging(level: int = logging.INFO) -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(BackendFormatter(handler.stream))
        root_logger.addHandler(handler)
