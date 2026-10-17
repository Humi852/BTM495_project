import json
import sqlite3
from contextlib import closing
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from database.db import DB_PATH

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


def get_database_status() -> dict[str, object]:
    database_uri = f"{DB_PATH.resolve().as_uri()}?mode=ro"
    with closing(sqlite3.connect(database_uri, uri=True)) as connection:
        tables = connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        ).fetchall()
        table_status = []
        for (table_name,) in tables:
            quoted_name = table_name.replace('"', '""')
            row_count = connection.execute(
                f'SELECT COUNT(*) FROM "{quoted_name}"'
            ).fetchone()[0]
            table_status.append({"name": table_name, "rows": row_count})

    return {
        "status": "ok",
        "database": DB_PATH.name,
        "tables": table_status,
    }


class LocalTestRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def do_GET(self) -> None:
        if urlsplit(self.path).path == "/api/status":
            self._send_database_status()
            return
        super().do_GET()

    def _send_database_status(self) -> None:
        try:
            response = get_database_status()
            status_code = 200
        except (OSError, sqlite3.Error) as error:
            response = {
                "status": "error",
                "message": str(error),
            }
            status_code = 500

        encoded_response = json.dumps(response).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded_response)))
        self.end_headers()
        self.wfile.write(encoded_response)


def create_server(host: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), LocalTestRequestHandler)
