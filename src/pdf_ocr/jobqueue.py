"""Warteschlange für Kontextmenü-Aufrufe.

Problem: Markiert man im Explorer 20 PDFs und wählt "OCR hinzufügen", startet
Windows das Programm 20-mal gleichzeitig. Das wären 20 Konsolenfenster und
20 parallele OCR-Läufe.

Lösung: Jeder Aufruf mit --queue legt seinen Auftrag als kleine JSON-Datei in
%LOCALAPPDATA%\\PDF-OCR\\queue ab und versucht dann, die Sperrdatei zu
bekommen. Wer sie bekommt, ist das Arbeitsfenster und arbeitet die
Warteschlange ab. Alle anderen Fenster schließen sich sofort wieder.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

from pdf_ocr.osutil import FileLock, data_dir

COLLECT_SECONDS = 1.5   # so lange auf weitere Aufrufe einer Mehrfachauswahl warten


def queue_dir() -> Path:
    d = data_dir() / "queue"
    d.mkdir(parents=True, exist_ok=True)
    return d


def lock() -> FileLock:
    return FileLock(data_dir() / "worker.lock")


def submit(paths: list[str], recursive: bool) -> Path:
    job = {"paths": paths, "recursive": recursive, "time": time.time()}
    name = f"{time.time_ns()}_{os.getpid()}_{uuid.uuid4().hex[:6]}"
    tmp = queue_dir() / f"{name}.tmp"
    tmp.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
    final = tmp.with_suffix(".job")
    os.replace(tmp, final)
    return final


def take_all() -> list[dict]:
    """Alle wartenden Aufträge holen (und aus der Warteschlange entfernen)."""
    jobs = []
    for f in sorted(queue_dir().glob("*.job")):
        try:
            jobs.append(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
        try:
            f.unlink()
        except OSError:
            pass
    return jobs


def pending() -> bool:
    return any(queue_dir().glob("*.job"))
