from http import HTTPStatus
import logging
import sys
from typing import TextIO


_ESCAPE = "\033["  # ANSI escape sequence introducer (ESC + "[")


def _rgb(red: int, green: int, blue: int) -> str:
    return f"{_ESCAPE}38;2;{red};{green};{blue}m"


class Color:
    """Terminal text colors as exact RGB values, independent of the theme."""

    GRAY = _rgb(128, 128, 128)
    DARK_BLUE = _rgb(0, 40, 140)
    YELLOW = _rgb(200, 150, 0)
    RED = _rgb(210, 40, 40)
    BOLD_RED = f"{_ESCAPE}1m" + _rgb(230, 0, 0)
    RESET = f"{_ESCAPE}0m"


_LEVEL_COLORS = {
    logging.DEBUG: Color.GRAY,
    logging.INFO: Color.DARK_BLUE,
    logging.WARNING: Color.YELLOW,
    logging.ERROR: Color.RED,
    logging.CRITICAL: Color.BOLD_RED,
}
_DISPLAY_NAMES = {"backend.utils.sqlite": "SQL"}


class BackendFormatter(logging.Formatter):
    def __init__(self, stream: TextIO) -> None:
        super().__init__(
            fmt="%(asctime)s %(levelname)s %(display_name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self._use_colors = stream.isatty()

    def format(self, record: logging.LogRecord) -> str:
        record.display_name = _DISPLAY_NAMES.get(record.name, record.name)
        formatted = super().format(record)
        color = _LEVEL_COLORS.get(record.levelno)
        if not self._use_colors or color is None:
            return formatted
        return f"{color}{formatted}{Color.RESET}"


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


def configure_backend_logging(level: int = logging.DEBUG) -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(BackendFormatter(handler.stream))
        root_logger.addHandler(handler)
