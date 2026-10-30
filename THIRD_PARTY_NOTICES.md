# Drittkomponenten und Lizenzen

PDF-OCR selbst steht unter der MIT-Lizenz (siehe `LICENSE`). Das Programm
verwendet die folgenden Open-Source-Komponenten. Sie werden **unverändert**
weitergegeben. Die vollständigen Lizenztexte aller mitgelieferten
Python-Pakete stehen in `THIRD_PARTY_LICENSES_PYTHON.txt` (wird beim Build
automatisch erzeugt).

## In PDF-OCR enthalten

| Komponente | Lizenz | Quellcode |
|---|---|---|
| OCRmyPDF | MPL-2.0 | https://github.com/ocrmypdf/OCRmyPDF |
| pikepdf | MPL-2.0 | https://github.com/pikepdf/pikepdf |
| qpdf (in pikepdf) | Apache-2.0 | https://github.com/qpdf/qpdf |
| pypdfium2 / PDFium | Apache-2.0 / BSD-3-Clause | https://github.com/pypdfium2-team/pypdfium2 |
| fpdf2 | LGPL-3.0 | https://github.com/py-pdf/fpdf2 |
| uharfbuzz / HarfBuzz | Apache-2.0 / MIT ("Old MIT") | https://github.com/harfbuzz/uharfbuzz |
| Pillow | MIT-CMU (HPND) | https://github.com/python-pillow/Pillow |
| pdfminer.six | MIT | https://github.com/pdfminer/pdfminer.six |
| img2pdf | LGPL-3.0 | https://gitlab.mister-muffin.de/josch/img2pdf |
| rich, pluggy, pydantic, packaging u.a. | MIT / Apache-2.0 / BSD | siehe `THIRD_PARTY_LICENSES_PYTHON.txt` |
| Python | PSF-2.0 | https://www.python.org |
| PyInstaller-Bootloader | GPL-2.0 mit Ausnahme für gebündelte Programme | https://github.com/pyinstaller/pyinstaller |
| Tesseract-Sprachdaten `deu`, `eng` (tessdata) | Apache-2.0 | https://github.com/tesseract-ocr/tessdata |

**Hinweis zu MPL-2.0 und LGPL-3.0:** Diese Pakete werden unverändert genutzt.
Ihr Quellcode ist unter den genannten Adressen verfügbar. Der vollständige
Quellcode von PDF-OCR und das Build-Skript (`build.ps1`) sind öffentlich. Damit
lässt sich das Programm mit einer geänderten Version jeder dieser Bibliotheken
neu bauen.

## Nicht enthalten, separat installiert

| Komponente | Lizenz | Hinweis |
|---|---|---|
| Tesseract OCR (Build der UB Mannheim) | Apache-2.0 | Installation per `winget install -e --id UB-Mannheim.TesseractOCR` |
| Ghostscript | AGPL-3.0 | **wird nicht benötigt und nicht mitgeliefert.** Ist es installiert, nutzt OCRmyPDF es als Rückfallebene für PDF/A |

Marken: "OCRmyPDF", "Tesseract" und "Ghostscript" sind Namen der jeweiligen
Projekte bzw. Rechteinhaber. PDF-OCR ist ein unabhängiges Projekt.
