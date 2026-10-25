#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if [ -x ".venv/bin/python" ]; then
    echo "Environment already exists, skipping setup."
else
    echo "Creating environment in .venv ..."
    python3 -m venv .venv || { echo "Could not create the environment. Install Python 3.10 or newer first."; exit 1; }
fi

echo "Starting the local website. Press Ctrl+C to stop."
exec .venv/bin/python run_local_website.py "$@"
