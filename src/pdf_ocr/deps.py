"""Prüfung der externen Programme (Tesseract, optional Ghostscript).

Python und OCRmyPDF sind in der .exe enthalten. Tesseract ist ein
eigenständiges Programm und wird vom Installer per winget installiert.
Die Sprachdaten (deu, eng, osd) bringt PDF-OCR selbst mit.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from pdf_ocr.osutil import IS_WINDOWS, resource_dir

WINGET_TESSERACT = "winget install -e --id UB-Mannheim.TesseractOCR"


@dataclass
class DepReport:
    tesseract: Path | None = None
    tesseract_version: str = ""
    tessdata: Path | None = None          # verwendeter Sprachdaten-Ordner
    tessdata_source: str = ""             # "mitgeliefert" / "System"
    languages: list[str] = field(default_factory=list)
    ghostscript: Path | None = None
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def _no_window() -> int:
    return 0x08000000 if IS_WINDOWS else 0  # CREATE_NO_WINDOW


def _windows_tesseract_candidates() -> list[Path]:
    cands: list[Path] = []
    try:
        import winreg

        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(hive, r"SOFTWARE\Tesseract-OCR") as k:
                    val, _ = winreg.QueryValueEx(k, "InstallDir")
                    cands.append(Path(val) / "tesseract.exe")
            except OSError:
                pass
    except ImportError:
        pass
    for env in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        if os.environ.get(env):
            cands.append(Path(os.environ[env]) / "Tesseract-OCR" / "tesseract.exe")
    if os.environ.get("LOCALAPPDATA"):
        cands.append(
            Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Tesseract-OCR" / "tesseract.exe"
        )
    return cands


def find_tesseract() -> Path | None:
    found = shutil.which("tesseract")
    if found:
        return Path(found)
    if IS_WINDOWS:
        for c in _windows_tesseract_candidates():
            if c.is_file():
                return c
    return None


def find_ghostscript() -> Path | None:
    for name in ("gswin64c", "gswin32c", "gs"):
        found = shutil.which(name)
        if found:
            return Path(found)
    if IS_WINDOWS:
        for env in ("ProgramFiles", "ProgramFiles(x86)"):
            base = Path(os.environ.get(env, "")) / "gs"
            if base.is_dir():
                hits = sorted(base.glob("gs*/bin/gswin*c.exe"), reverse=True)
                if hits:
                    return hits[0]
    return None


def _list_langs(tesseract: Path, env: dict) -> list[str]:
    try:
        out = subprocess.run(
            [str(tesseract), "--list-langs"], capture_output=True, text=True,
            env=env, timeout=30, creationflags=_no_window(),
        )
    except (OSError, subprocess.SubprocessError):
        return []
    lines = (out.stdout + out.stderr).splitlines()
    return sorted({ln.strip() for ln in lines[1:] if ln.strip() and " " not in ln.strip()})


def check(languages: list[str], apply_env: bool = True) -> DepReport:
    """Sucht Tesseract + Sprachdaten. Mit apply_env=True werden PATH und
    TESSDATA_PREFIX für diesen Prozess (und damit für OCRmyPDF) gesetzt."""
    rep = DepReport()

    tess = find_tesseract()
    if tess is None:
        rep.problems.append(
            "Tesseract OCR wurde nicht gefunden.\n"
            f"    Installieren mit:  {WINGET_TESSERACT}\n"
            "    (oder PDF-OCR-Setup erneut ausführen)"
        )
        return rep
    rep.tesseract = tess
    if apply_env and str(tess.parent) not in os.environ.get("PATH", ""):
        os.environ["PATH"] = str(tess.parent) + os.pathsep + os.environ.get("PATH", "")

    try:
        out = subprocess.run(
            [str(tess), "--version"], capture_output=True, text=True, timeout=30,
            creationflags=_no_window(),
        )
        rep.tesseract_version = (out.stdout or out.stderr).splitlines()[0].strip()
    except (OSError, subprocess.SubprocessError, IndexError):
        rep.tesseract_version = "?"

    # Sprachdaten: zuerst die mitgelieferten, sonst die der Tesseract-Installation.
    env = dict(os.environ)
    bundled = resource_dir() / "tessdata"
    chosen_langs: list[str] = []
    if bundled.is_dir():
        env_b = dict(env, TESSDATA_PREFIX=str(bundled))
        langs_b = _list_langs(tess, env_b)
        if all(lang in langs_b for lang in languages):
            rep.tessdata, rep.tessdata_source = bundled, "mitgeliefert"
            chosen_langs = langs_b
            if apply_env:
                os.environ["TESSDATA_PREFIX"] = str(bundled)
    if rep.tessdata is None:
        langs_s = _list_langs(tess, env)
        chosen_langs = langs_s
        rep.tessdata_source = "Tesseract-Installation"
        rep.tessdata = Path(env["TESSDATA_PREFIX"]) if env.get("TESSDATA_PREFIX") else tess.parent / "tessdata"
        missing = [lang for lang in languages if lang not in langs_s]
        if missing:
            rep.problems.append(
                f"Tesseract-Sprachdaten fehlen: {', '.join(missing)}\n"
                f"    Vorhanden: {', '.join(langs_s) or '(keine)'}\n"
                "    Fehlende .traineddata-Dateien gibt es unter\n"
                "    https://github.com/tesseract-ocr/tessdata"
            )
    rep.languages = chosen_langs
    rep.ghostscript = find_ghostscript()
    return rep
