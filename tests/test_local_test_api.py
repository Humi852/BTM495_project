import json
import sqlite3
import threading
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
from urllib.request import urlopen
from unittest.mock import patch

from backend.apis.local_test import create_server


class LocalTestApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "test.db"
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
            connection.executemany(
                "INSERT INTO sample (id) VALUES (?)",
                [(1,), (2,)],
            )
            connection.commit()

        self.database_patch = patch(
            "backend.apis.local_test.DB_PATH",
            self.database_path,
        )
        self.database_patch.start()
        self.server = create_server("127.0.0.1", 0)
        self.server_thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )
        self.server_thread.start()
        host, port = self.server.server_address[:2]
        self.api_url = f"http://{host}:{port}/api/status"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join()
        self.database_patch.stop()
        self.temp_dir.cleanup()

    def test_status_reports_readable_tables_and_row_counts(self) -> None:
        with urlopen(self.api_url) as response:
            self.assertEqual(response.status, 200)
            payload = json.load(response)

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["database"], "test.db")
        self.assertEqual(payload["tables"], [{"name": "sample", "rows": 2}])

        with closing(sqlite3.connect(self.database_path)) as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM sample").fetchone()[0],
                2,
            )

    def test_frontend_page_is_served(self) -> None:
        base_url = self.api_url.removesuffix("/api/status")
        page_url = base_url + "/"
        with urlopen(page_url) as response:
            self.assertEqual(response.status, 200)
            page = response.read().decode("utf-8")
        with urlopen(base_url + "/app.js") as response:
            script = response.read().decode("utf-8")

        self.assertIn("Integration test", page)
        self.assertIn("/api/status", script)

    def test_status_reports_missing_database_as_an_error(self) -> None:
        self.database_path.unlink()

        with self.assertRaises(HTTPError) as error:
            urlopen(self.api_url)

        self.assertEqual(error.exception.code, 500)
        payload = json.load(error.exception)
        self.assertEqual(payload["status"], "error")
        self.assertTrue(payload["message"])


if __name__ == "__main__":
    unittest.main()
