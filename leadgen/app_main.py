"""Startpunt van de Mac-app (Lead Generator.app): het dashboard in een eigen venster.

Er is geen terminal: meldingen gaan naar een logbestand in
~/Library/Application Support/Lead Generator/leadgen.log.
"""
from __future__ import annotations

import os
import sys
import threading
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
    found = server.running_instance("127.0.0.1", server.PREFERRED_PORT)
    if found:
        url, meta = found
        if meta.get("window"):
            # Deze app is al open in een venster; macOS brengt dat venster naar voren.
            print(f"Venster draait al op {url}")
            return
        # Een oudere versie of een startbestand draait nog zonder venster (in de browser):
        # die stoppen we, zodat dit venster de leiding neemt.
        print(f"Oude instantie zonder venster gevonden op {url}: die wordt gestopt")
        if not server.stop_instance(url):
            print("Oude instantie stopt niet: ik gebruik een andere poort")

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
    from . import mac_native

    geo = mac_native.load_geometry()
    window = webview.create_window(
        "Lead Generator", url, width=geo["width"], height=geo["height"], x=geo["x"], y=geo["y"],
        min_size=mac_native.MIN_SIZE, text_select=True, js_api=mac_native.JsApi(),
    )
    mac_native.track_geometry(window, geo)
    loaded = threading.Event()

    def on_loaded():
        print("Dashboard geladen in het venster")
        loaded.set()
    window.events.loaded += on_loaded

    def after_start():
        print("Venster geopend")
        mac_native.install(window)
        if os.environ.get("LEADGEN_SELFTEST") == "1":
            loaded.wait(30)
            time.sleep(2)  # dashboard laat zijn gegevens laden
            mac_native.selftest(window)

    webview.start(after_start)
    print("Venster gesloten: Lead Generator stopt")
    os._exit(0)


if __name__ == "__main__":
    main()
