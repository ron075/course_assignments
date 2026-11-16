
from __future__ import annotations

import importlib.metadata
import re
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
REQUIREMENTS_FILE = PROJECT_ROOT / "requirements.txt"


def _version_tuple(version: str) -> tuple[int, ...]:
    match = re.match(r"(\d+(?:\.\d+)*)", version)
    if match is None:
        raise ValueError(f"Cannot interpret installed package version: {version}")
    return tuple(int(part) for part in match.group(1).split("."))


def _missing_requirements() -> list[str]:
    missing = []

    for raw_requirement in REQUIREMENTS_FILE.read_text(
        encoding="utf-8"
    ).splitlines():
        requirement = raw_requirement.partition("#")[0].strip()

        if not requirement:
            continue

        match = re.fullmatch(
            r"([A-Za-z0-9_.-]+)(?:\s*>=\s*([0-9.]+))?",
            requirement,
        )

        if match is None:
            raise ValueError(
                f"Unsupported requirement format: {requirement}"
            )

        package, minimum_version = match.groups()

        try:
            installed_version = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            missing.append(requirement)
            continue

        if minimum_version and _version_tuple(
            installed_version
        ) < _version_tuple(minimum_version):
            missing.append(requirement)

    return missing


def _install_requirements() -> None:
    missing = _missing_requirements()

    if not missing:
        print("Requirements are already installed.")
        return

    print(
        "Installing missing or outdated requirements: "
        + ", ".join(missing)
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-r",
            str(REQUIREMENTS_FILE),
        ],
        cwd=PROJECT_ROOT,
        check=False,
    )

    if result.returncode:
        raise RuntimeError(
            "Dependency installation failed. "
            "Check your internet connection and try again."
        )

    still_missing = _missing_requirements()

    if still_missing:
        raise RuntimeError(
            "Requirements are still unavailable after installation: "
            + ", ".join(still_missing)
        )


def main() -> int:
    if not REQUIREMENTS_FILE.is_file():
        raise FileNotFoundError(
            f"Requirements file not found: {REQUIREMENTS_FILE}"
        )

    web_app_file = PROJECT_ROOT / "web_app.py"

    if not web_app_file.is_file():
        raise FileNotFoundError(
            f"Web application file not found: {web_app_file}"
        )

    # Check and install dependencies before importing the application.
    _install_requirements()

    # Import only after dependencies are installed.
    from web_app import create_app

    host = "127.0.0.1"
    port = 5000
    url = f"http://{host}:{port}"

    print(f"Starting web application at {url}")

    threading.Timer(
        1,
        webbrowser.open,
        args=(url,),
    ).start()

    try:
        create_app().run(
            host=host,
            port=port,
            debug=False,
            use_reloader=False,
        )
    except KeyboardInterrupt:
        print("\nWeb application stopped.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
