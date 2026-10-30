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


# Minimal-Konfigurationen, die OCRmyPDF bei Tesseract anfordert (Inhalt wie im
# Tesseract-Repository tessdata/configs, Apache-2.0). Nur Fallback, falls die
# Tesseract-Installation keine eigenen configs mitbringt.
_FALLBACK_CONFIGS = {
    "hocr": "tessedit_create_hocr 1\nhocr_font_info 0\n",
    "txt": "tessedit_create_txt 1\n",
    "pdf": "tessedit_create_pdf 1\n",
}


def _system_tessdata(tess: Path, env: dict) -> Path | None:
    """tessdata-Ordner der Tesseract-Installation (für configs/, pdf.ttf)."""
    try:
        out = subprocess.run(
            [str(tess), "--list-langs"], capture_output=True, text=True, env=env,
            timeout=30, creationflags=_no_window(),
        )
        first = (out.stdout + out.stderr).splitlines()[0]
        if '"' in first:
            p = Path(first.split('"')[1])
            if p.is_dir():
                return p
    except (OSError, subprocess.SubprocessError, IndexError):
        pass
    for cand in (env.get("TESSDATA_PREFIX"), tess.parent / "tessdata"):
        if cand and Path(cand).is_dir():
            return Path(cand)
    return None


def _prepare_tessdata(bundled: Path, system: Path | None) -> Path:
    """Arbeits-tessdata unter %LOCALAPPDATA%\\PDF-OCR\\tessdata zusammenstellen.

    Tesseract sucht Sprachdaten UND Konfigurationsdateien (configs/hocr usw.)
    im selben Ordner (TESSDATA_PREFIX). Mitgeliefert sind nur die Sprachdaten,
    die configs kommen aus der Tesseract-Installation.
    """
    from pdf_ocr.osutil import data_dir

    target = data_dir() / "tessdata"
    (target / "configs").mkdir(parents=True, exist_ok=True)
    for src in bundled.glob("*.traineddata"):
        dst = target / src.name
        if not dst.exists() or dst.stat().st_size != src.stat().st_size:
            shutil.copyfile(src, dst)
    if system is not None and system.resolve() != target.resolve():
        for sub in ("configs", "tessconfigs"):
            if (system / sub).is_dir():
                shutil.copytree(system / sub, target / sub, dirs_exist_ok=True)
        if (system / "pdf.ttf").is_file() and not (target / "pdf.ttf").exists():
            shutil.copyfile(system / "pdf.ttf", target / "pdf.ttf")
    for name, content in _FALLBACK_CONFIGS.items():
        f = target / "configs" / name
        if not f.exists():
            f.write_text(content, encoding="ascii")
    return target


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
    if bundled.is_dir() and any(bundled.glob("*.traineddata")):
        try:
            merged = _prepare_tessdata(bundled, _system_tessdata(tess, env))
        except OSError as e:
            merged = None
            rep.problems.append(f"Sprachdaten-Ordner konnte nicht angelegt werden: {e}")
        if merged is not None:
            env_b = dict(env, TESSDATA_PREFIX=str(merged))
            langs_b = _list_langs(tess, env_b)
            if all(lang in langs_b for lang in languages):
                rep.tessdata, rep.tessdata_source = merged, "mitgeliefert"
                chosen_langs = langs_b
                if apply_env:
                    os.environ["TESSDATA_PREFIX"] = str(merged)
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
