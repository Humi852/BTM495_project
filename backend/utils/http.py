import json
from http.server import BaseHTTPRequestHandler
from typing import Any


class HTTPRequestError(ValueError):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def read_json_object(
    handler: BaseHTTPRequestHandler,
    max_bytes: int,
    request_name: str = "Request",
) -> dict[str, Any]:
    try:
        content_length = int(handler.headers.get("Content-Length", ""))
    except ValueError as error:
        raise HTTPRequestError("Invalid Content-Length header.") from error

    if content_length <= 0 or content_length > max_bytes:
        raise HTTPRequestError(
            f"Invalid {request_name.lower()} request size."
        )

    try:
        payload = json.loads(handler.rfile.read(content_length))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise HTTPRequestError("Request body must be valid JSON.") from error
    if not isinstance(payload, dict):
        raise HTTPRequestError(f"{request_name} request must be an object.")
    return payload


def send_json(
    handler: BaseHTTPRequestHandler,
    response: dict[str, object],
    status_code: int = 200,
) -> None:
    encoded_response = json.dumps(response).encode("utf-8")
    handler.send_response(status_code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(encoded_response)))
    handler.end_headers()
    handler.wfile.write(encoded_response)
