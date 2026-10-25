@echo off
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    echo Environment already exists, skipping setup.
) else (
    echo Creating environment in .venv ...
    python -m venv .venv || (
        echo Could not create the environment. Install Python 3.10 or newer first.
        exit /b 1
    )
)

echo Starting the local website. Press Ctrl+C to stop.
".venv\Scripts\python.exe" run_local_website.py %*
