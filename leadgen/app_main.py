"""Startpunt van de Mac-app (Lead Generator.app).

Er is geen terminalvenster: meldingen gaan naar een logbestand in
~/Library/Application Support/Lead Generator/leadgen.log.
"""
from __future__ import annotations

import os
import sys
import traceback

from . import config


def main() -> None:
    config.USER_DIR.mkdir(parents=True, exist_ok=True)
    log = open(config.LOG_PATH, "a", buffering=1, encoding="utf-8")
    sys.stdout = sys.stderr = log
    print(f"--- Lead Generator gestart (pid {os.getpid()}) ---")
    try:
        from .server import run

        run(open_browser=os.environ.get("LEADGEN_NO_OPEN") != "1", idle_exit_minutes=20)
    except Exception:
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
