"""macOS-specifieke afwerking van het app-venster (via pyobjc, dat met pywebview meekomt).

- Menubalk: Lead Generator → Instellingen… (⌘,) en een menu "Leads" met
  Nieuwe scan… (⌘N), Zoeken (⌘F) en Exporteer CSV (⌘E).
- Titelbalk zonder titel, in dezelfde kleur als de kop van het dashboard.
- Vensterpositie en -grootte onthouden.

Alles is defensief geschreven: lukt iets niet, dan werkt de app gewoon zonder.
"""
from __future__ import annotations

import json
import threading
import traceback

from . import config

GEOMETRY_PATH = config.USER_DIR / "venster.json"
DEFAULT_SIZE = (1320, 860)
MIN_SIZE = (960, 640)

# tag -> (titel, sneltoets, JavaScript dat het dashboard uitvoert)
MENU_ITEMS = {
    1: ("Instellingen…", ",", "leadgenApp.openSettings()"),
    2: ("Nieuwe scan…", "n", "leadgenApp.newScan()"),
    3: ("Zoeken", "f", "leadgenApp.focusSearch()"),
    4: ("Exporteer CSV", "e", "leadgenApp.exportCsv()"),
}

_window = None   # pywebview-venster
_keep = []       # referenties die Objective-C nodig heeft (anders opgeruimd)
installed: dict[int, object] = {}  # tag -> NSMenuItem (ook gebruikt door de zelftest)


# ---------- vensterpositie ----------
def load_geometry() -> dict:
    """Bewaarde grootte/positie, of standaardwaarden als die niet (meer) op een scherm past."""
    geo = {"width": DEFAULT_SIZE[0], "height": DEFAULT_SIZE[1], "x": None, "y": None}
    try:
        saved = json.loads(GEOMETRY_PATH.read_text())
        geo["width"] = max(MIN_SIZE[0], int(saved["width"]))
        geo["height"] = max(MIN_SIZE[1], int(saved["height"]))
        x, y = int(saved["x"]), int(saved["y"])
        if _on_screen(x, y, geo["width"]):
            geo["x"], geo["y"] = x, y
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return geo


def _on_screen(x: int, y: int, width: int) -> bool:
    """Ligt de titelbalk (bovenkant) van het venster op een van de schermen?"""
    try:
        from AppKit import NSScreen

        screens = NSScreen.screens()
        primary_h = screens[0].frame().size.height
        # pywebview: oorsprong linksboven; Cocoa: oorsprong linksonder
        px, py = x + min(width, 200) / 2, primary_h - y - 10
        for s in screens:
            f = s.visibleFrame()
            if f.origin.x <= px <= f.origin.x + f.size.width and f.origin.y <= py <= f.origin.y + f.size.height:
                return True
        return False
    except Exception:
        return 0 <= x <= 4000 and 0 <= y <= 2500


class _Geometry:
    def __init__(self, geo: dict):
        self.state = dict(geo)
        self.lock = threading.Lock()

    def _save(self):
        with self.lock:
            try:
                GEOMETRY_PATH.parent.mkdir(parents=True, exist_ok=True)
                GEOMETRY_PATH.write_text(json.dumps(self.state))
            except OSError:
                pass

    def resized(self, width, height, *rest):
        self.state.update(width=int(width), height=int(height))
        self._save()

    def moved(self, x, y, *rest):
        self.state.update(x=int(x), y=int(y))
        self._save()


def track_geometry(window, geo: dict) -> None:
    g = _Geometry(geo)
    _keep.append(g)
    window.events.resized += g.resized
    window.events.moved += g.moved


# ---------- brug vanuit het dashboard (JavaScript) ----------
class JsApi:
    """Wordt in het dashboard beschikbaar als window.pywebview.api."""

    def titlebar_color(self, r, g, b):
        def apply():
            try:
                from AppKit import NSColor

                w = _ns_window()
                if w is not None:
                    w.setBackgroundColor_(NSColor.colorWithSRGBRed_green_blue_alpha_(r / 255, g / 255, b / 255, 1.0))
            except Exception:
                traceback.print_exc()
        _on_main(apply)
        print(f"Titelbalkkleur ingesteld: rgb({r:.0f}, {g:.0f}, {b:.0f})")
        return True


# ---------- menubalk en titelbalk ----------
def _on_main(fn) -> None:
    from PyObjCTools import AppHelper

    AppHelper.callAfter(fn)


def _ns_window():
    from AppKit import NSApp

    for w in NSApp.windows():
        if str(w.title()) == "Lead Generator":
            return w
    return None


def _run_js(js: str) -> None:
    # evaluate_js wacht op het antwoord: nooit op de hoofdthread aanroepen.
    threading.Thread(target=lambda: _window.evaluate_js(js), daemon=True).start()


def _target_class():
    from Foundation import NSObject

    class LeadgenMenuTarget(NSObject):
        def menuAction_(self, sender):
            item = MENU_ITEMS.get(int(sender.tag()))
            if item:
                _run_js(item[2])

    return LeadgenMenuTarget


def _install_on_main() -> None:
    try:
        from AppKit import NSApp, NSMenu, NSMenuItem

        target = _target_class().alloc().init()
        _keep.append(target)
        cmd = 1 << 20  # NSEventModifierFlagCommand

        def item(tag):
            title, key, _ = MENU_ITEMS[tag]
            it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, "menuAction:", key)
            it.setTarget_(target)
            it.setTag_(tag)
            it.setKeyEquivalentModifierMask_(cmd)
            installed[tag] = it
            return it

        main = NSApp.mainMenu()
        if main is None:
            main = NSMenu.alloc().initWithTitle_("Hoofdmenu")
            NSApp.setMainMenu_(main)
        if main.numberOfItems() == 0:
            app_top = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Lead Generator", None, "")
            app_top.setSubmenu_(NSMenu.alloc().initWithTitle_("Lead Generator"))
            main.addItem_(app_top)

        app_menu = main.itemAtIndex_(0).submenu()
        pos = 1 if app_menu.numberOfItems() >= 1 else 0  # na "Over Lead Generator"
        app_menu.insertItem_atIndex_(NSMenuItem.separatorItem(), pos)
        app_menu.insertItem_atIndex_(item(1), pos + 1)

        leads = NSMenu.alloc().initWithTitle_("Leads")
        leads.addItem_(item(2))
        leads.addItem_(item(3))
        leads.addItem_(NSMenuItem.separatorItem())
        leads.addItem_(item(4))
        top = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Leads", None, "")
        top.setSubmenu_(leads)
        main.insertItem_atIndex_(top, min(1, main.numberOfItems()))

        w = _ns_window()
        if w is not None:
            w.setTitlebarAppearsTransparent_(True)
            w.setTitleVisibility_(1)  # NSWindowTitleHidden
        print("Menu's toegevoegd: " + ", ".join(f"{MENU_ITEMS[t][0]} ⌘{MENU_ITEMS[t][1].upper()}" for t in sorted(installed)))
    except Exception:
        print("Menu's/titelbalk konden niet ingesteld worden:")
        traceback.print_exc()


def install(window) -> None:
    """Na het openen van het venster: menu's en titelbalk instellen (op de hoofdthread)."""
    global _window
    _window = window
    try:
        _on_main(_install_on_main)
    except Exception:
        traceback.print_exc()


# ---------- zelftest (alleen in CI, LEADGEN_SELFTEST=1) ----------
def selftest(window) -> None:
    import time
    from pathlib import Path

    problems = []
    time.sleep(2)
    for tag in (1, 2, 3, 4):
        if tag not in installed:
            problems.append(f"menu-item {tag} ontbreekt")
    if problems:
        print("SELFTEST FOUT: " + "; ".join(problems))
        return

    def click(tag):
        _on_main(lambda: installed[tag].target().menuAction_(installed[tag]))
        time.sleep(1.0)

    checks = [
        (2, "document.getElementById('scanDialog').open", "Nieuwe scan opent het scanvenster"),
        (1, "document.getElementById('settingsDialog').open", "Instellingen opent de instellingen"),
    ]
    for tag, js, label in checks:
        click(tag)
        ok = window.evaluate_js(js) is True
        print(f"SELFTEST {'ok ' if ok else 'FOUT'} {label}")
        if not ok:
            problems.append(label)
    window.evaluate_js("document.querySelectorAll('dialog[open]').forEach(d => d.close())")

    click(3)
    ok = window.evaluate_js("document.activeElement && document.activeElement.id") == "f-q"
    print(f"SELFTEST {'ok ' if ok else 'FOUT'} Zoeken zet de cursor in het zoekveld")
    if not ok:
        problems.append("zoeken")

    downloads = Path.home() / "Downloads"
    before = set(downloads.glob("leads-*.csv")) if downloads.exists() else set()
    click(4)
    time.sleep(1.5)
    after = set(downloads.glob("leads-*.csv")) if downloads.exists() else set()
    ok = len(after - before) == 1
    print(f"SELFTEST {'ok ' if ok else 'FOUT'} Exporteer CSV zet een bestand in Downloads")
    if not ok:
        problems.append("export")

    def check_titlebar():
        w = _ns_window()
        good = bool(w and w.titlebarAppearsTransparent() and int(w.titleVisibility()) == 1)
        print(f"SELFTEST {'ok ' if good else 'FOUT'} Titelbalk transparant en zonder titel")
        if not good:
            problems.append("titelbalk")
    _on_main(check_titlebar)
    time.sleep(0.5)

    window.resize(1111, 777)
    time.sleep(1.5)
    try:
        saved = json.loads(GEOMETRY_PATH.read_text())
        ok = saved.get("width") == 1111 and saved.get("height") == 777
    except (OSError, ValueError):
        ok = False
    print(f"SELFTEST {'ok ' if ok else 'FOUT'} Venstergrootte wordt onthouden")
    if not ok:
        problems.append("vensterpositie")

    print("SELFTEST OK" if not problems else "SELFTEST FOUT: " + "; ".join(problems))
