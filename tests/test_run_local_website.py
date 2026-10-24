import sys
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run_local_website


class RunLocalWebsiteTests(unittest.TestCase):
    def test_main_logs_initialization_server_ready_and_shutdown(self) -> None:
        server = MagicMock()
        server.__enter__.return_value = server
        server.server_address = ("127.0.0.1", 8765)
        server.serve_forever.side_effect = KeyboardInterrupt

        with (
            patch(
                "run_local_website.parse_args",
                return_value=Namespace(
                    host="127.0.0.1",
                    port=8765,
                    no_browser=True,
                ),
            ),
            patch("run_local_website.initialize_database") as initialize_database,
            patch("run_local_website.ensure_local_demo_login") as ensure_demo_login,
            patch("run_local_website.create_server", return_value=server),
            self.assertLogs("backend.run_local_website", level="INFO") as logs,
        ):
            run_local_website.main()

        initialize_database.assert_called_once_with()
        ensure_demo_login.assert_called_once_with()
        output = "\n".join(logs.output)
        self.assertIn("Starting local integration server.", output)
        self.assertIn("Initializing SQLite database schema.", output)
        self.assertIn("Database initialization complete.", output)
        self.assertIn("Local demo login is ready (login@example.com).", output)
        self.assertIn("Starting HTTP server on 127.0.0.1:8765.", output)
        self.assertIn("Server ready at http://localhost:8765/.", output)
        self.assertIn("Server stopped by user.", output)


if __name__ == "__main__":
    unittest.main()
