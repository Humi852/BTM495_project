import argparse
import webbrowser

from backend.apis.local_test import create_server
from database.db import initialize_database

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def open_browser(url: str) -> None:
    if not webbrowser.open(url):
        print("Could not open the default browser. Open this URL manually:")
        print(url)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local web/database smoke test.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Bind address (default: loopback only)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port (default: 8765)")
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    initialize_database()
    with create_server(args.host, args.port) as server:
        host, port = server.server_address[:2]
        display_host = "localhost" if host in ("127.0.0.1", "::1") else host
        url = f"http://{display_host}:{port}/"

        print(f"Local integration test is running at {url}")
        print("Press Ctrl+C to stop.")
        if not args.no_browser:
            open_browser(url)

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nLocal integration test stopped.")


if __name__ == "__main__":
    main()
