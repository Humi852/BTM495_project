import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from backend.apis.local_test import create_server

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def find_chrome() -> Path | None:
    executable = shutil.which("chrome")
    if executable:
        return Path(executable)

    if os.name == "nt":
        candidates = [
            Path(os.environ.get("PROGRAMFILES", "C:/Program Files"))
            / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)"))
            / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("LOCALAPPDATA", ""))
            / "Google/Chrome/Application/chrome.exe",
        ]
        return next((candidate for candidate in candidates if candidate.is_file()), None)

    return None


def open_chrome(url: str) -> None:
    chrome = find_chrome()
    if chrome is None:
        print("Chrome was not found automatically. Open this URL in Chrome:")
        print(url)
        return

    try:
        subprocess.Popen([str(chrome), url])
    except OSError as error:
        print(f"Could not launch Chrome: {error}", file=sys.stderr)
        print(f"Open this URL in Chrome: {url}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local web/database smoke test.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Bind address (default: loopback only)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port (default: 8765)")
    parser.add_argument("--no-browser", action="store_true", help="Do not open Chrome")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with create_server(args.host, args.port) as server:
        host, port = server.server_address[:2]
        display_host = "localhost" if host in ("127.0.0.1", "::1") else host
        url = f"http://{display_host}:{port}/"

        print(f"Local integration test is running at {url}")
        print("Press Ctrl+C to stop.")
        if not args.no_browser:
            open_chrome(url)

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nLocal integration test stopped.")


if __name__ == "__main__":
    main()
