"""Dashboard-server starten: vrije poort, browser openen, één instantie, automatisch stoppen."""
from __future__ import annotations

import json
import logging
import os
import socket
import threading
import time
import urllib.request
import webbrowser

from . import config

PREFERRED_PORT = 8765
APP_ID = "leadgen"


def free_port(host: str, preferred: int) -> int:
    """Gebruik de gewenste poort, of de eerstvolgende vrije."""
    for port in range(preferred, preferred + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
                return port
            except OSError:
                continue
    return preferred


def find_running(host: str, preferred: int) -> str | None:
    """URL van een Lead Generator die al draait, anders None."""
    for port in range(preferred, preferred + 10):
        url = f"http://{host}:{port}"
        try:
            with urllib.request.urlopen(url + "/api/meta", timeout=0.5) as r:
                if json.load(r).get("app") == APP_ID:
                    return url
        except (OSError, ValueError):
            continue
    return None


def run(host: str = "127.0.0.1", port: int = PREFERRED_PORT, *, open_browser: bool = True,
        idle_exit_minutes: int | None = None) -> None:
    running = find_running(host, port)
    if running:
        print(f"Lead Generator draait al op {running}")
        if open_browser:
            webbrowser.open(running)
        return

    from .web.app import create_app

    port = free_port(host, port)
    url = f"http://{host}:{port}"
    print(f"\n  Dashboard draait op {url}")
    print("  Sluit dit venster (of klik 'Afsluiten' in het dashboard) om te stoppen.\n")

    app = create_app()
    if open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    if idle_exit_minutes:
        threading.Thread(target=_idle_watch, args=(app, idle_exit_minutes * 60), daemon=True).start()
    if config.FROZEN:
        threading.Thread(target=_ensure_browser, args=(app,), daemon=True).start()

    import flask.cli

    # Technische meldingen verbergen: wie dubbelklikt, hoeft die niet te zien.
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    flask.cli.show_server_banner = lambda *args, **kwargs: None
    app.run(host=host, port=port, debug=False, threaded=True)


def _idle_watch(app, max_idle: float) -> None:
    """Stop als er al een tijd geen dashboard open staat en er geen scan loopt."""
    state = app.config["LEADGEN_STATE"]
    while True:
        time.sleep(30)
        idle = time.time() - state["last_seen"]
        if idle > max_idle and not state["job"]["running"]:
            print("Geen dashboard meer open: Lead Generator stopt.")
            os._exit(0)


def _ensure_browser(app) -> None:
    """In de Mac-app: Chromium downloaden als er geen bruikbare browser is."""
    from .checks.browser import browser_status, install_chromium

    state = app.config["LEADGEN_STATE"]
    status = browser_status()
    state["browser"] = status
    if status == "missing":
        state["browser"] = "installing"
        state["browser"] = "ready" if install_chromium() else "missing"
