import multiprocessing
import sys

if __name__ == "__main__":
    # Pflicht für eingefrorene (PyInstaller-)Programme unter Windows.
    multiprocessing.freeze_support()
    from pdf_ocr.cli import main

    sys.exit(main())
