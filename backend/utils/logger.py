import logging


def get_logger(name: str) -> logging.Logger:
    if not name.startswith("backend"):
        name = f"backend.{name}"
    return logging.getLogger(name)


def configure_backend_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
