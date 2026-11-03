# PyInstaller-specificatie voor "Lead Generator.app".
# Bouwen (op een Mac):  pyinstaller packaging/leadgen.spec --noconfirm
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent  # noqa: F821 (SPECPATH wordt door PyInstaller gezet)
VERSION = "1.1.0"

a = Analysis(  # noqa: F821
    [str(ROOT / "packaging" / "app_entry.py")],
    pathex=[str(ROOT)],
    datas=[
        (str(ROOT / "leadgen" / "web" / "templates"), "leadgen/web/templates"),
        (str(ROOT / "leadgen" / "web" / "static"), "leadgen/web/static"),
    ],
    hiddenimports=["leadgen.web.app", "playwright.sync_api", "webview"],
    excludes=["tkinter", "pytest"],
)
pyz = PYZ(a.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Lead Generator",
    console=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Lead Generator")  # noqa: F821

if sys.platform == "darwin":
    icon = ROOT / "packaging" / "icon.png"  # PyInstaller zet dit (met Pillow) om naar .icns
    app = BUNDLE(  # noqa: F821
        coll,
        name="Lead Generator.app",
        icon=str(icon) if icon.exists() else None,
        bundle_identifier="be.leadgenerator.app",
        version=VERSION,
        info_plist={
            "CFBundleShortVersionString": VERSION,
            "NSHighResolutionCapable": True,
            "LSApplicationCategoryType": "public.app-category.business",
            "NSHumanReadableCopyright": "Lead Generator",
        },
    )
