# -*- mode: python ; coding: utf-8 -*-
# PyInstaller-Spezifikation für PDF-OCR.
# Erzeugt zwei Varianten:
#   dist/pdf-ocr/pdf-ocr.exe        Ordner-Variante, wird vom Installer verteilt
#   dist/pdf-ocr-portable.exe       Einzeldatei: in einen Ordner kopieren, doppelklicken
#
# OCRmyPDF bringt seinen eigenen PyInstaller-Hook mit (Plugins, Fonts, ICC-Profile).

from PyInstaller.utils.hooks import collect_all, copy_metadata

datas = [("tessdata", "tessdata"), ("LICENSE", "."), ("THIRD_PARTY_NOTICES.md", ".")]
binaries = []
hiddenimports = ["tkinter", "tkinter.filedialog"]

for pkg in ("ocrmypdf", "pikepdf", "pypdfium2", "pypdfium2_raw", "uharfbuzz", "fpdf",
            "rich", "pydantic", "pydantic_core"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# OCRmyPDF/pluggy lesen Paket-Metadaten (Versionen, Plugins)
for pkg in ("ocrmypdf", "pikepdf", "pypdfium2", "fpdf2", "img2pdf", "pdfminer.six", "pluggy"):
    datas += copy_metadata(pkg)

a = Analysis(
    ["pdf-ocr.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["matplotlib", "numpy.tests", "PyQt5", "PySide6", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)

common = dict(
    debug=False,
    strip=False,
    upx=False,
    console=True,           # bewusst: das Tool zeigt, was es tut
    icon="assets/pdf-ocr.ico",
    version="build/version_info.txt",
)

# --- Ordner-Variante (Installer)
exe_dir = EXE(pyz, a.scripts, [], exclude_binaries=True, name="pdf-ocr", **common)
COLLECT(exe_dir, a.binaries, a.datas, strip=False, upx=False, name="pdf-ocr")

# --- Einzeldatei (portabel)
EXE(pyz, a.scripts, a.binaries, a.datas, [], name="pdf-ocr-portable",
    runtime_tmpdir=None, **common)
