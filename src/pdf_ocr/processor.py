"""Verarbeitung einer einzelnen PDF-Datei.

Ablauf pro Datei (entspricht der früheren ocr.bat, mit Sicherheitsnetz):

  1. Vorprüfung, ob die Datei übersprungen wird:
       - bereits PDF/A                      -> schon verarbeitet
       - Creator "ocrmypdf ..."            -> schon verarbeitet (auch ohne PDF/A)
       - verschlüsselt / digital signiert   -> würde zerstört bzw. ungültig
       - eingebettete Dateien               -> z.B. E-Rechnung (ZUGFeRD/Factur-X):
                                               das XML darf nicht verloren gehen
  2. Zeitstempel (Erstellt/Geändert) merken.
  3. Arbeitskopie im Temp-Ordner anlegen. Das Original bleibt unberührt.
  4. Metadaten in der Kopie bereinigen (wie früher exiftool):
       Info-Dictionary: /Creator, /Producer
       XMP: dc:creator, xmp:CreatorTool, pdf:Producer
  5. OCRmyPDF: Texterkennung (nur Seiten ohne Text), Optimierung, PDF/A-2b.
  6. Ergebnis prüfen, dann Original atomar ersetzen.
  7. Zeitstempel wiederherstellen.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import pikepdf

log = logging.getLogger("pdf_ocr")

TEMP_SUFFIX = ".pdf-ocr-tmp"


@dataclass
class Result:
    path: Path
    status: str            # "ocr", "skip", "error", "dry"
    message: str = ""
    size_before: int = 0
    size_after: int = 0
    pdfa: bool = False
    seconds: float = 0.0


# --------------------------------------------------------------------------
# 1. Vorprüfung
# --------------------------------------------------------------------------

def _is_signed(pdf: pikepdf.Pdf) -> bool:
    acro = pdf.Root.get("/AcroForm")
    if acro is None:
        return False
    try:
        if int(acro.get("/SigFlags", 0)) & 1:
            return True
    except (TypeError, ValueError):
        pass
    stack = list(acro.get("/Fields", []))
    seen = 0
    while stack and seen < 5000:
        f = stack.pop()
        seen += 1
        try:
            if f.get("/FT") == pikepdf.Name.Sig and f.get("/V") is not None:
                return True
            stack.extend(f.get("/Kids", []))
        except Exception:
            continue
    return False


def _has_embedded_files(pdf: pikepdf.Pdf) -> bool:
    try:
        if len(pdf.attachments) > 0:
            return True
    except Exception:
        pass
    return "/AF" in pdf.Root


def precheck(path: Path) -> str | None:
    """Liefert einen Grund zum Überspringen oder None (= verarbeiten)."""
    try:
        with pikepdf.open(path) as pdf:
            meta = pdf.open_metadata()
            if meta.pdfa_status:
                return f"bereits PDF/A-{meta.pdfa_status.lower()} (vermutlich schon verarbeitet)"
            creator = str(pdf.docinfo.get("/Creator", "")) if pdf.docinfo else ""
            if creator.lower().startswith("ocrmypdf"):
                return "wurde bereits mit OCRmyPDF verarbeitet"
            if _is_signed(pdf):
                return "digital signiert - Signatur würde ungültig, Datei bleibt unverändert"
            if _has_embedded_files(pdf):
                return ("enthält eingebettete Dateien (z.B. E-Rechnung ZUGFeRD/Factur-X) "
                        "- wird nicht verändert, damit nichts verloren geht")
    except pikepdf.PasswordError:
        return "verschlüsselt/kennwortgeschützt"
    except pikepdf.PdfError as e:
        return f"nicht lesbar als PDF ({e})"
    return None


# --------------------------------------------------------------------------
# 4. Metadaten bereinigen (Ersatz für exiftool)
# --------------------------------------------------------------------------

def strip_metadata(src: Path, dst: Path) -> list[str]:
    removed: list[str] = []
    with pikepdf.open(src) as pdf:
        for key in ("/Creator", "/Producer"):
            if pdf.docinfo is not None and key in pdf.docinfo:
                del pdf.docinfo[key]
                removed.append(f"Info{key}")
        with pdf.open_metadata(set_pikepdf_as_editor=False, update_docinfo=False) as meta:
            for key in ("dc:creator", "xmp:CreatorTool", "pdf:Producer"):
                if key in meta:
                    del meta[key]
                    removed.append(f"XMP {key}")
        pdf.save(dst)
    return removed


# --------------------------------------------------------------------------
# 5. OCR
# --------------------------------------------------------------------------

def run_ocrmypdf(src: Path, dst: Path, languages: list[str]) -> None:
    import ocrmypdf

    kwargs = dict(
        language=languages,
        skip_text=True,          # Seiten mit vorhandenem Text nicht erneut erkennen
        output_type="auto",      # PDF/A-2b, wenn möglich; sonst normales PDF
        progress_bar=True,
        use_threads=True,
    )
    # Nur für Tests/Fehlersuche: zusätzliche OCRmyPDF-Parameter als JSON
    extra = os.environ.get("PDF_OCR_EXTRA_OCRMYPDF_ARGS")
    if extra:
        kwargs.update(json.loads(extra))
    log.debug("ocrmypdf.ocr(%s, %s, %s)", src, dst, kwargs)
    ocrmypdf.ocr(src, dst, **kwargs)


def _friendly_ocr_error(e: Exception) -> str:
    from ocrmypdf import exceptions as ex

    if isinstance(e, ex.EncryptedPdfError):
        return "verschlüsselt - kann nicht verarbeitet werden"
    if isinstance(e, ex.DigitalSignatureError):
        return "digital signiert - nicht verarbeitet"
    if isinstance(e, ex.TaggedPDFError):
        return "Tagged PDF (meist aus Office erzeugt, braucht keine OCR)"
    if isinstance(e, ex.MissingDependencyError):
        return f"fehlendes Programm: {e}"
    if isinstance(e, ex.ExitCodeException):
        return f"{type(e).__name__}: {e}".strip()
    return f"{type(e).__name__}: {e}"


# --------------------------------------------------------------------------
# Gesamtablauf
# --------------------------------------------------------------------------

def process(path: Path, languages: list[str], dry_run: bool = False,
            say=print) -> Result:
    from pdf_ocr.osutil import get_times, set_times

    t0 = time.monotonic()
    path = path.resolve()
    res = Result(path=path, status="error")
    try:
        res.size_before = path.stat().st_size
    except OSError as e:
        res.message = f"Datei nicht erreichbar: {e}"
        return res

    say("  [1/5] Vorprüfung (PDF/A? signiert? verschlüsselt? eingebettete Dateien?)")
    reason = precheck(path)
    if reason:
        res.status = "error" if reason.startswith("nicht lesbar") else "skip"
        res.message = reason
        return res
    if dry_run:
        res.status, res.message = "dry", "würde verarbeitet (Probelauf, nichts geändert)"
        return res

    times = get_times(path)
    workdir = Path(tempfile.mkdtemp(prefix="pdf-ocr-"))
    tmp_target = path.with_name(f".{path.name}{TEMP_SUFFIX}")
    try:
        say(f"  [2/5] Arbeitskopie anlegen in {workdir}")
        src = workdir / "original.pdf"
        shutil.copy2(path, src)

        cleaned = workdir / "bereinigt.pdf"
        removed = strip_metadata(src, cleaned)
        say("  [3/5] Metadaten bereinigt: " + (", ".join(removed) if removed else "nichts zu entfernen"))

        say(f"  [4/5] OCRmyPDF: Texterkennung ({'+'.join(languages)}), Optimierung, PDF/A ...")
        out = workdir / "ergebnis.pdf"
        try:
            run_ocrmypdf(cleaned, out, languages)
        except Exception as e:  # noqa: BLE001 - alles melden, Original bleibt
            res.message = _friendly_ocr_error(e)
            if "Tagged PDF" in res.message or "signiert" in res.message:
                res.status = "skip"
            log.debug("OCRmyPDF-Fehler", exc_info=True)
            return res

        if not out.is_file() or out.stat().st_size == 0:
            res.message = "OCRmyPDF hat keine Ausgabedatei erzeugt"
            return res
        with pikepdf.open(out) as check:          # Ergebnis ist ein lesbares PDF?
            res.pdfa = bool(check.open_metadata().pdfa_status)
            pages_out = len(check.pages)
        with pikepdf.open(cleaned) as orig:
            pages_in = len(orig.pages)
        if pages_in != pages_out:
            res.message = f"Seitenzahl abweichend ({pages_in} -> {pages_out}), Original bleibt"
            return res

        say("  [5/5] Original ersetzen und Zeitstempel wiederherstellen")
        shutil.copyfile(out, tmp_target)
        try:
            os.replace(tmp_target, path)
        except PermissionError:
            res.message = ("Original ist gesperrt (in einem anderen Programm geöffnet?) "
                           "- nicht ersetzt")
            return res
        try:
            set_times(path, times)
        except OSError as e:
            say(f"        Hinweis: Zeitstempel konnten nicht gesetzt werden ({e})")
        res.size_after = path.stat().st_size
        res.status = "ocr"
        res.message = "PDF/A-2b" if res.pdfa else "normales PDF (PDF/A war nicht möglich)"
        return res
    finally:
        if tmp_target.exists():
            try:
                tmp_target.unlink()
            except OSError:
                pass
        shutil.rmtree(workdir, ignore_errors=True)
        res.seconds = time.monotonic() - t0
