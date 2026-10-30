# Einstiegspunkt für PyInstaller (und zum direkten Starten aus dem Quellcode).
import multiprocessing
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()
    if not getattr(sys, "frozen", False):
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
    from pdf_ocr.cli import main

    sys.exit(main())
