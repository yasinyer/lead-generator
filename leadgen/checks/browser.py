"""Echte gsm-check met Playwright: horizontaal scrollen, piepkleine tekst, screenshot."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

MOBILE_JS = """
() => {
  const vw = window.innerWidth;
  const sw = Math.max(document.documentElement.scrollWidth, document.body ? document.body.scrollWidth : 0);
  let total = 0, small = 0;
  const walker = document.createTreeWalker(document.body || document.documentElement, NodeFilter.SHOW_TEXT);
  const seen = new Set();
  while (walker.nextNode() && total < 600) {
    const t = walker.currentNode;
    if (!t.textContent.trim() || t.textContent.trim().length < 3) continue;
    const el = t.parentElement;
    if (!el || seen.has(el)) continue;
    seen.add(el);
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    total++;
    if (parseFloat(getComputedStyle(el).fontSize) < 12) small++;
  }
  return {viewportWidth: vw, scrollWidth: sw, textElements: total, smallText: small};
}
"""


class MobileChecker:
    """Hergebruikt één browser voor alle leads. Gebruik als context manager."""

    def __init__(self, screenshot_dir: Path, log=print):
        self.screenshot_dir = Path(screenshot_dir)
        self.log = log
        self._pw = self._browser = None
        self.available = False

    def __enter__(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.log("  ! Playwright niet geïnstalleerd: gsm-check en screenshots overgeslagen")
            return self
        try:
            self._pw = sync_playwright().start()
        except Exception as e:
            self.log(f"  ! Playwright kon niet starten ({e.__class__.__name__}): gsm-check overgeslagen")
            return self
        for label, kwargs in launch_options():
            try:
                self._browser = self._pw.chromium.launch(**kwargs)
                self.available = True
                self.log(f"  gsm-check met {label}")
                break
            except Exception:
                continue
        if not self.available:
            self.log("  ! Geen browser gevonden voor de gsm-check. Installeer Google Chrome, "
                     "of wacht tot de app Chromium gedownload heeft.")
            self._pw.stop()
            self._pw = None
        return self

    def __exit__(self, *exc):
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()

    def check(self, url: str, name: str) -> dict:
        out = {"issues": [], "screenshot": None, "ok": False}
        if not self.available:
            return out
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        ctx = self._browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
            locale="nl-BE",
            user_agent=("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
                        "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"),
        )
        page = ctx.new_page()
        try:
            resp = page.goto(url, wait_until="load", timeout=25000)
            page.wait_for_timeout(1500)
            out["status"] = resp.status if resp else None
            out["final_url"] = page.url
            m = page.evaluate(MOBILE_JS)
            if m["scrollWidth"] > m["viewportWidth"] + 20:
                out["issues"].append({
                    "code": "overflow",
                    "text": f"Pagina is {m['scrollWidth']}px breed op een gsm van "
                            f"{m['viewportWidth']}px: je moet zijwaarts scrollen",
                })
            if m["textElements"] >= 10 and m["smallText"] / m["textElements"] > 0.3:
                pct = round(100 * m["smallText"] / m["textElements"])
                out["issues"].append({"code": "small_text",
                                      "text": f"{pct}% van de tekst is te klein om op gsm te lezen"})
            fname = f"{_slug(name)}-{hashlib.md5(url.encode()).hexdigest()[:8]}.png"
            page.screenshot(path=str(self.screenshot_dir / fname))
            out["screenshot"] = fname
            out["ok"] = True
        except Exception as e:
            self.log(f"    browsercheck mislukt voor {url}: {e.__class__.__name__}")
        finally:
            ctx.close()
        return out


def _slug(s: str) -> str:
    import re
    import unicodedata

    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:40] or "site"


CHROME_APP = Path("/Applications/Google Chrome.app")


def launch_options() -> list[tuple[str, dict]]:
    """Browsers om te proberen, in volgorde van voorkeur."""
    opts: list[tuple[str, dict]] = []
    if os.environ.get("CHROMIUM_PATH"):
        opts.append(("eigen browser (CHROMIUM_PATH)", {"executable_path": os.environ["CHROMIUM_PATH"]}))
    opts.append(("Chromium", {}))
    opts.append(("Google Chrome", {"channel": "chrome"}))
    return opts


def browser_status() -> str:
    """'ready' | 'chrome' | 'missing' | 'no-playwright' (zonder een browser te starten)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "no-playwright"
    if os.environ.get("CHROMIUM_PATH") and Path(os.environ["CHROMIUM_PATH"]).exists():
        return "ready"
    try:
        with sync_playwright() as p:
            if Path(p.chromium.executable_path).exists():
                return "ready"
    except Exception:
        pass
    return "chrome" if CHROME_APP.exists() else "missing"


def install_chromium(log=print) -> bool:
    """Download Playwright's Chromium. Werkt ook vanuit de verpakte Mac-app."""
    import subprocess

    try:
        from playwright._impl._driver import compute_driver_executable, get_driver_env
    except ImportError:
        return False
    driver = compute_driver_executable()
    cmd = list(driver) if isinstance(driver, (tuple, list)) else [str(driver)]
    log("Chromium downloaden voor de gsm-check (eenmalig, ongeveer 150 MB)...")
    try:
        ok = subprocess.run([*cmd, "install", "chromium"], env=get_driver_env(),
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE).returncode == 0
    except OSError as e:
        log(f"Chromium-download mislukt: {e}")
        return False
    log("Chromium geïnstalleerd." if ok else "Chromium-download mislukt.")
    return ok
