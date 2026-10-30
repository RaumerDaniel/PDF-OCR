"""Kommandozeile von PDF-OCR.

Aufrufvarianten
---------------
  pdf-ocr.exe "C:\\Ablage"              alle PDFs im Ordner
  pdf-ocr.exe -r "C:\\Ablage"           ... inkl. Unterordner
  pdf-ocr.exe a.pdf b.pdf              einzelne Dateien
  pdf-ocr.exe --pick                   Ordner per Dialog auswählen
  pdf-ocr.exe                          installiert: Ordner-Dialog
                                       portable .exe: Ordner, in dem die .exe liegt
  pdf-ocr.exe --check                  nur Voraussetzungen prüfen
  pdf-ocr.exe --dry-run <Ordner>       zeigen, was passieren würde
"""

from __future__ import annotations

import argparse
import logging
import logging.handlers
import sys
import time
from pathlib import Path

from pdf_ocr import APP_NAME, __version__, deps, jobqueue
from pdf_ocr.osutil import (
    app_dir, data_dir, is_portable_build, owns_console, set_console_title, wait_for_key,
)
from pdf_ocr.processor import TEMP_SUFFIX, Result, process

log = logging.getLogger("pdf_ocr")


# --------------------------------------------------------------------------
# Ausgabe
# --------------------------------------------------------------------------

def _console():
    try:
        from rich.console import Console

        return Console(highlight=False, soft_wrap=True)
    except Exception:  # pragma: no cover
        return None


CON = _console()


def say(msg: str = "", style: str | None = None) -> None:
    log.info(msg.strip()) if msg.strip() else None
    if CON is not None:
        CON.print(msg, style=style, markup=False)
    else:
        print(msg, flush=True)


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return str(n)


# --------------------------------------------------------------------------
# Argumente
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pdf-ocr",
        description=(
            "Ergänzt PDFs ohne Textebene um eine OCR-Textebene (Tesseract/OCRmyPDF), "
            "optimiert sie und speichert sie als PDF/A. Das Original wird nur bei "
            "Erfolg ersetzt, Zeitstempel bleiben erhalten. Alles läuft lokal."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=("Aufrufvarianten" + __doc__.split("---------------", 1)[1]) if __doc__ else None,
    )
    p.add_argument("paths", nargs="*", help="PDF-Dateien und/oder Ordner")
    p.add_argument("-r", "--recursive", action="store_true",
                   help="Unterordner einbeziehen")
    p.add_argument("--pick", action="store_true", help="Ordner per Dialog auswählen")
    p.add_argument("-l", "--lang", default="deu+eng",
                   help="Tesseract-Sprachen, z.B. deu+eng (Standard)")
    p.add_argument("--dry-run", action="store_true",
                   help="nur prüfen und anzeigen, nichts verändern")
    p.add_argument("--check", action="store_true",
                   help="Voraussetzungen prüfen und beenden")
    p.add_argument("--queue", action="store_true",
                   help="(für das Kontextmenü) Aufträge sammeln, ein Fenster arbeitet ab")
    pause = p.add_mutually_exclusive_group()
    pause.add_argument("--pause", dest="pause", action="store_true", default=None,
                       help="am Ende auf Tastendruck warten")
    pause.add_argument("--no-pause", dest="pause", action="store_false",
                       help="am Ende nicht warten")
    p.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    return p


# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------

def setup_logging() -> Path:
    logfile = data_dir() / "pdf-ocr.log"
    fh = logging.handlers.RotatingFileHandler(
        logfile, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    fh.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
    fh.setLevel(logging.INFO)
    for name in ("pdf_ocr", "ocrmypdf"):
        lg = logging.getLogger(name)
        lg.addHandler(fh)
        lg.setLevel(logging.INFO)
    try:
        import ocrmypdf

        ocrmypdf.configure_logging(ocrmypdf.Verbosity.default, progress_bar_friendly=True)
        logging.getLogger("ocrmypdf").addHandler(fh)
    except Exception:
        pass
    return logfile


# --------------------------------------------------------------------------
# Ziele bestimmen
# --------------------------------------------------------------------------

def pick_folder() -> Path | None:
    say("Ordnerauswahl-Dialog geöffnet ...")
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        chosen = filedialog.askdirectory(title=f"{APP_NAME}: Ordner mit PDFs wählen")
        root.destroy()
    except Exception as e:  # noqa: BLE001
        say(f"Ordner-Dialog nicht verfügbar ({e}). Bitte Ordner als Parameter angeben.",
            "red")
        return None
    return Path(chosen) if chosen else None


def collect_pdfs(paths: list[Path], recursive: bool) -> tuple[list[Path], list[str]]:
    files: list[Path] = []
    notes: list[str] = []
    seen: set[str] = set()

    def add(f: Path):
        key = str(f.resolve()).casefold()
        if key not in seen and not f.name.endswith(TEMP_SUFFIX):
            seen.add(key)
            files.append(f)

    for p in paths:
        if p.is_dir():
            pattern = "**/*" if recursive else "*"
            found = sorted(
                (f for f in p.glob(pattern) if f.is_file() and f.suffix.lower() == ".pdf"),
                key=lambda f: str(f).casefold(),
            )
            notes.append(f"Ordner {p}{' (inkl. Unterordner)' if recursive else ''}: "
                         f"{len(found)} PDF(s)")
            for f in found:
                add(f)
        elif p.is_file():
            if p.suffix.lower() == ".pdf":
                add(p)
            else:
                notes.append(f"keine PDF, ignoriert: {p}")
        else:
            notes.append(f"nicht gefunden: {p}")
    return files, notes


# --------------------------------------------------------------------------
# Hauptablauf
# --------------------------------------------------------------------------

def print_banner(logfile: Path, languages: list[str], dry_run: bool) -> None:
    say(f"{APP_NAME} {__version__}  -  OCR für PDFs, lokal auf diesem Rechner", "bold")
    say("Was passiert mit jeder PDF:")
    say("  - Übersprungen werden: PDF/A, schon verarbeitete, signierte, verschlüsselte")
    say("    PDFs und PDFs mit eingebetteten Dateien (z.B. E-Rechnungen).")
    say("  - Sonst: Arbeitskopie -> Metadaten (Creator/Producer) entfernen ->")
    say(f"    Texterkennung ({'+'.join(languages)}) für Seiten ohne Text -> optimieren -> PDF/A-2b")
    say("  - Das Original wird erst ersetzt, wenn alles geklappt hat;")
    say("    Erstell- und Änderungsdatum bleiben erhalten.")
    if dry_run:
        say("  PROBELAUF: es wird nichts verändert.", "yellow")
    say(f"Protokoll: {logfile}")
    say()


def print_deps(rep: deps.DepReport) -> None:
    say("Voraussetzungen:")
    say(f"  Tesseract:   {rep.tesseract or 'NICHT GEFUNDEN'}  {rep.tesseract_version}")
    if rep.tessdata:
        say(f"  Sprachdaten: {rep.tessdata} ({rep.tessdata_source})")
        say(f"  Sprachen:    {', '.join(rep.languages) or '-'}")
    say(f"  Ghostscript: {rep.ghostscript or 'nicht installiert (nicht nötig)'}")
    for prob in rep.problems:
        say(f"  FEHLER: {prob}", "red")
    say()


def run_files(files: list[Path], languages: list[str], dry_run: bool) -> list[Result]:
    results: list[Result] = []
    for i, f in enumerate(files, 1):
        say(f"({i}/{len(files)}) {f}", "bold cyan")
        try:
            r = process(f, languages, dry_run=dry_run, say=say)
        except KeyboardInterrupt:
            raise
        except Exception as e:  # noqa: BLE001
            log.exception("Unerwarteter Fehler bei %s", f)
            r = Result(path=f, status="error", message=f"unerwarteter Fehler: {e}")
        results.append(r)
        if r.status == "ocr":
            delta = r.size_after - r.size_before
            say(f"  -> FERTIG: {r.message}, {human(r.size_before)} -> {human(r.size_after)} "
                f"({'+' if delta >= 0 else ''}{human(delta)}), {r.seconds:.0f} s", "green")
        elif r.status == "skip":
            say(f"  -> übersprungen: {r.message}", "yellow")
        elif r.status == "dry":
            say(f"  -> {r.message}", "cyan")
        else:
            say(f"  -> FEHLER: {r.message} (Original unverändert)", "red")
        say()
    return results


def print_summary(results: list[Result]) -> None:
    by = {s: [r for r in results if r.status == s] for s in ("ocr", "skip", "error", "dry")}
    say("Zusammenfassung", "bold")
    say(f"  verarbeitet:   {len(by['ocr'])}")
    if by["dry"]:
        say(f"  würden verarbeitet: {len(by['dry'])}")
    say(f"  übersprungen:  {len(by['skip'])}")
    say(f"  Fehler:        {len(by['error'])}", "red" if by["error"] else None)
    nonpdfa = [r for r in by["ocr"] if not r.pdfa]
    if nonpdfa:
        say(f"  davon ohne PDF/A (OCR ist drin, PDF/A war nicht möglich): {len(nonpdfa)}",
            "yellow")
    if by["ocr"]:
        before = sum(r.size_before for r in by["ocr"])
        after = sum(r.size_after for r in by["ocr"])
        say(f"  Größe gesamt:  {human(before)} -> {human(after)}")
    for r in by["error"]:
        say(f"  FEHLER {r.path.name}: {r.message}", "red")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    languages = [x for x in args.lang.replace(",", "+").split("+") if x]
    pause = args.pause if args.pause is not None else owns_console()
    set_console_title(APP_NAME)

    try:
        return _main(args, languages)
    except KeyboardInterrupt:
        say("\nAbgebrochen (Strg+C). Bereits verarbeitete Dateien sind fertig, "
            "die aktuelle Datei ist unverändert.", "yellow")
        return 130
    finally:
        if pause and not getattr(args, "_handed_off", False):
            wait_for_key("\nTaste drücken zum Schließen ...")


def _main(args, languages: list[str]) -> int:
    # --- Kontextmenü: Auftrag in Warteschlange, ggf. an laufendes Fenster übergeben
    worker_lock = None
    if args.queue:
        jobqueue.submit([str(Path(p).resolve()) for p in args.paths], args.recursive)
        worker_lock = jobqueue.lock()
        if not worker_lock.acquire():
            print(f"{APP_NAME}: Auftrag an das bereits laufende Fenster übergeben.")
            args._handed_off = True
            time.sleep(0.8)
            return 0

    logfile = setup_logging()
    log.info("==== Start %s %s, argv=%s", APP_NAME, __version__, sys.argv)
    print_banner(logfile, languages, args.dry_run)

    rep = deps.check(languages)
    print_deps(rep)
    if args.check:
        say(f"Programmordner: {app_dir()}")
        say(f"Datenordner:    {data_dir()}")
        return 0 if rep.ok else 2
    if not rep.ok:
        if worker_lock:
            jobqueue.take_all()  # Aufträge verwerfen, sonst bleiben sie liegen
            worker_lock.release()
        return 2

    # --- Ziele bestimmen
    all_results: list[Result] = []
    if args.queue:
        say("Sammle Aufträge aus dem Kontextmenü ...")
        time.sleep(jobqueue.COLLECT_SECONDS)
        while True:
            jobs = jobqueue.take_all()
            if not jobs:
                time.sleep(jobqueue.COLLECT_SECONDS)
                jobs = jobqueue.take_all()
            if not jobs:
                # Sperre freigeben; kam genau jetzt noch ein Auftrag, übernehmen.
                worker_lock.release()
                if jobqueue.pending() and worker_lock.acquire():
                    continue
                break
            paths: list[Path] = []
            notes: list[str] = []
            for rec in (False, True):
                ps = [Path(p) for j in jobs if bool(j.get("recursive")) == rec
                      for p in j["paths"]]
                if ps:
                    f, n = collect_pdfs(ps, rec)
                    paths += f
                    notes += n
            for n in notes:
                say(n)
            done = {str(r.path).casefold() for r in all_results}
            paths = [p for p in paths if str(p.resolve()).casefold() not in done]
            say(f"{len(paths)} PDF(s) in der Warteschlange.\n")
            all_results += run_files(paths, languages, args.dry_run)
    else:
        targets = [Path(p) for p in args.paths]
        if args.pick or not targets:
            if not args.pick and is_portable_build():
                targets = [app_dir()]
                say(f"Kein Parameter: verarbeite den Ordner der .exe: {app_dir()}")
            else:
                folder = pick_folder()
                if folder is None:
                    say("Kein Ordner gewählt - nichts zu tun.")
                    return 0
                targets = [folder]
        files, notes = collect_pdfs(targets, args.recursive)
        for n in notes:
            say(n)
        say()
        all_results = run_files(files, languages, args.dry_run)

    print_summary(all_results)
    log.info("==== Ende")
    return 1 if any(r.status == "error" for r in all_results) else 0
