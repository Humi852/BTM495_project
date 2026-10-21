from dataclasses import dataclass
from enum import Enum


class ResponseLevel(Enum):
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    LOG = "log"


@dataclass(frozen=True)
class Response:
    msg: str
    level: ResponseLevel
    data: object | None = None

    @property
    def success(self) -> bool:
        return self.level in (ResponseLevel.SUCCESS, ResponseLevel.LOG)

    @classmethod
    def ok(cls, msg: str, data: object | None = None) -> "Response":
        return cls(msg, ResponseLevel.SUCCESS, data)

    @classmethod
    def warning(cls, msg: str, data: object | None = None) -> "Response":
        return cls(msg, ResponseLevel.WARNING, data)

    @classmethod
    def error(cls, msg: str, data: object | None = None) -> "Response":
        return cls(msg, ResponseLevel.ERROR, data)

    @classmethod
    def info(cls, msg: str, data: object | None = None) -> "Response":
        return cls(msg, ResponseLevel.LOG, data)
