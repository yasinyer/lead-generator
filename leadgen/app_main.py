"""Startpunt van de Mac-app (Lead Generator.app): het dashboard in een eigen venster.

Er is geen terminal: meldingen gaan naar een logbestand in
~/Library/Application Support/Lead Generator/leadgen.log.
"""
from __future__ import annotations

import os
import sys
import time
import traceback
import webbrowser

from . import config, server


def main() -> None:
    config.USER_DIR.mkdir(parents=True, exist_ok=True)
    log = open(config.LOG_PATH, "a", buffering=1, encoding="utf-8")
    sys.stdout = sys.stderr = log
    print(f"--- Lead Generator gestart {time.strftime('%Y-%m-%d %H:%M')} (pid {os.getpid()}) ---")
    try:
        run_app()
    except Exception:
        traceback.print_exc()
        raise


def run_app() -> None:
    running = server.find_running("127.0.0.1", server.PREFERRED_PORT)
    if running:
        print(f"Draait al op {running}")
        webbrowser.open(running)
        return

    url, app, thread = server.start()
    state = app.config["LEADGEN_STATE"]
    print(f"Server draait op {url}")

    try:
        import webview
    except ImportError:
        # Geen venster-bibliotheek: val terug op de browser.
        print("pywebview niet beschikbaar: dashboard opent in de browser")
        webbrowser.open(url)
        server._idle_watch(app, 20 * 60)
        return

    state["window"] = True
    window = webview.create_window(
        "Lead Generator", url, width=1320, height=860, min_size=(960, 640), text_select=True,
    )
    window.events.loaded += lambda: print("Dashboard geladen in het venster")
    webview.start(lambda: print("Venster geopend"))
    print("Venster gesloten: Lead Generator stopt")
    os._exit(0)


if __name__ == "__main__":
    main()
