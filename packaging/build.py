"""Build the standalone app bundle and the Windows installer.

Usage:
    python packaging/build.py

Steps:
    1. PyInstaller one-dir bundle  -> dist/Magnetventilsteuerung/
    2. Inno Setup installer        -> dist/installer/Ventilsteuerung-Setup-X.Y.Z.exe

The version is read from ``__version__`` in GUI/gui.py.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUI_SCRIPT = ROOT / "GUI" / "gui.py"
DIST = ROOT / "dist"
BUILD = ROOT / "build"


def app_version() -> str:
    match = re.search(
        r'^__version__ = "([^"]+)"', GUI_SCRIPT.read_text(encoding="utf-8"), re.M
    )
    if not match:
        sys.exit("__version__ nicht in GUI/gui.py gefunden")
    return match.group(1)


def find_iscc() -> str | None:
    found = shutil.which("iscc")
    if found:
        return found
    candidates = [
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
        Path.home() / r"AppData\Local\Programs\Inno Setup 6\ISCC.exe",
    ]
    return next((str(c) for c in candidates if c.exists()), None)


def main() -> None:
    version = app_version()
    print(f"== Baue Magnetventilsteuerung v{version} ==")

    subprocess.run(
        [
            sys.executable, "-m", "PyInstaller",
            "--noconfirm", "--clean", "--windowed",
            "--name", "Magnetventilsteuerung",
            "--distpath", str(DIST),
            "--workpath", str(BUILD),
            "--specpath", str(BUILD),
            str(GUI_SCRIPT),
        ],
        check=True,
    )
    print(f"Bundle: {DIST / 'Magnetventilsteuerung'}")

    iscc = find_iscc()
    if iscc is None:
        sys.exit("Inno Setup (ISCC.exe) nicht gefunden — Installer wurde nicht gebaut.")
    subprocess.run(
        [iscc, f"/DMyAppVersion={version}", str(ROOT / "packaging" / "installer.iss")],
        check=True,
    )
    print(f"Installer: {DIST / 'installer' / f'Ventilsteuerung-Setup-{version}.exe'}")


if __name__ == "__main__":
    main()
