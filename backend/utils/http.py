import logging
import json
from http.server import BaseHTTPRequestHandler
from typing import Any

from backend.utils.logger import get_logger, http_status_label

logger = get_logger(__name__)


class HTTPRequestError(ValueError):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _summarize_input(request_name: str, payload: dict[str, Any]) -> str:
    request_type = request_name.lower()
    if request_type == "login":
        fields = []
        if isinstance(payload.get("email"), str) and payload["email"]:
            fields.append("email supplied")
        if isinstance(payload.get("password"), str) and payload["password"]:
            fields.append("password supplied")
        return f"Login input received ({', '.join(fields) or 'no credentials supplied'})."
    if request_type == "payment":
        order_id = payload.get("order_id")
        order_label = f" for order #{order_id}" if type(order_id) is int else ""
        return f"Payment input received{order_label}; card details not logged."
    return f"{request_name} input received ({len(payload)} field(s))."


def _summarize_output(
    response: dict[str, object],
    status_code: int,
) -> str:
    status_label = http_status_label(status_code)
    if status_code >= 400:
        message = response.get("message")
        if isinstance(message, str):
            return f"{status_label}: {message}"
        return status_label

    user = response.get("user")
    if isinstance(user, dict):
        role = "admin" if user.get("is_admin") is True else "customer"
        return f"Login successful ({role})."

    payment = response.get("payment")
    if isinstance(payment, dict):
        outcome = "approved" if payment.get("paid_status") is True else "declined"
        order_id = payment.get("order_id")
        amount = payment.get("amount")
        if type(amount) in (int, float):
            return f"Payment {outcome} for order #{order_id}: ${amount:.2f}."
        return f"Payment {outcome} for order #{order_id}."

    order = response.get("order")
    if isinstance(order, dict):
        order_id = order.get("order_id")
        amount = order.get("total_amount")
        if type(amount) in (int, float):
            return f"Sample order #{order_id} ready for ${amount:.2f}."
        return f"Sample order #{order_id} ready."

    orders = response.get("orders")
    payments = response.get("payments")
    if isinstance(orders, list) and isinstance(payments, list):
        order_count = len(orders)
        amount_total = sum(
            order["total_amount"]
            for order in orders
            if isinstance(order, dict)
            and type(order.get("total_amount")) in (int, float)
        )
        order_label = "order" if order_count == 1 else "orders"
        summary = (
            f"Dashboard loaded: {order_count} {order_label}, "
            f"${amount_total:.2f} total, {len(payments)} payment record(s)."
        )
        order_details = []
        for item in orders[:3]:
            if not isinstance(item, dict):
                continue
            order_id = item.get("order_id", "unknown")
            amount = item.get("total_amount")
            amount_text = f"${amount:.2f}" if type(amount) in (int, float) else "amount unknown"
            order_date = item.get("order_date") or "date unknown"
            paid_label = "paid" if item.get("paid") is True else "unpaid"
            order_details.append(
                f"#{order_id} {amount_text}, {order_date}, {paid_label}"
            )
        if order_details:
            summary += " Orders: " + "; ".join(order_details) + "."
        if order_count > len(order_details):
            summary += f" Plus {order_count - len(order_details)} more."
        return summary

    tables = response.get("tables")
    if isinstance(tables, list):
        database = response.get("database")
        database_label = f" for {database}" if isinstance(database, str) else ""
        return f"Database ready{database_label}: {len(tables)} table(s) available."

    if response.get("status") == "ok":
        return f"Request completed: {status_label}."
    return f"Request completed: {status_label}."


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
    logger.info(_summarize_input(request_name, payload))
    return payload


def send_json(
    handler: BaseHTTPRequestHandler,
    response: dict[str, object],
    status_code: int = 200,
) -> None:
    encoded_response = json.dumps(response).encode("utf-8")
    if status_code >= 500:
        log_level = logging.ERROR
    elif status_code >= 400:
        log_level = logging.WARNING
    else:
        log_level = logging.INFO
    logger.log(log_level, "Backend output: %s", _summarize_output(response, status_code))
    handler.send_response(status_code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(encoded_response)))
    handler.end_headers()
    handler.wfile.write(encoded_response)
