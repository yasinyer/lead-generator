"""Wordt aangeroepen door de startbestanden: installeert wat nodig is en start het dashboard.

Gebruikt alleen de standaardbibliotheek, zodat het werkt vóór de installatie.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
REQUIREMENTS = BASE / "requirements.txt"
PACKAGES_MARK = Path(sys.prefix) / ".leadgen-packages"
BROWSER_MARK = Path(sys.prefix) / ".leadgen-browser"


def run(cmd: list[str]) -> bool:
    return subprocess.call(cmd, cwd=BASE) == 0


def main() -> int:
    digest = hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest()
    if not PACKAGES_MARK.exists() or PACKAGES_MARK.read_text().strip() != digest:
        print("\n  Eerste keer opstarten: benodigdheden installeren. Dit duurt een paar minuten...\n")
        ok = run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
                  "-q", "-r", str(REQUIREMENTS)])
        if not ok:
            print("\n  Installatie mislukt. Controleer je internetverbinding en probeer opnieuw.")
            return 1
        PACKAGES_MARK.write_text(digest)

    if not BROWSER_MARK.exists():
        print("\n  Browser voor de gsm-check installeren (eenmalig, ongeveer 150 MB)...\n")
        if run([sys.executable, "-m", "playwright", "install", "chromium"]):
            BROWSER_MARK.write_text("ok")
        else:
            print("\n  De browser kon niet geïnstalleerd worden. De tool werkt wel,")
            print("  maar zonder gsm-check en screenshots. Bij de volgende start probeer ik opnieuw.\n")

    return subprocess.call([sys.executable, "-m", "leadgen", "serve"], cwd=BASE)


if __name__ == "__main__":
    sys.exit(main())
