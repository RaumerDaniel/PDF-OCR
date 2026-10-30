# PDF-OCR

Macht PDFs ohne Textebene durchsuchbar: Scans, Posteingang, Mail-Anhänge.
Ein Rechtsklick im Explorer genügt. Alles läuft **lokal**, ohne Cloud, ohne
Abo, ohne Upload.

Unter der Haube arbeiten [OCRmyPDF](https://github.com/ocrmypdf/OCRmyPDF) und
[Tesseract OCR](https://github.com/tesseract-ocr/tesseract). PDF-OCR ist der
Windows-Rahmen darum: Installer, Kontextmenü, Sicherheitsnetz und eine
nachvollziehbare Konsolenausgabe.

## Was mit jeder PDF passiert

1. **Vorprüfung.** Folgende PDFs werden übersprungen:
   - PDF/A-Dateien und schon verarbeitete PDFs
   - digital signierte PDFs (die Signatur würde sonst ungültig)
   - verschlüsselte PDFs
   - PDFs mit eingebetteten Dateien, z.B. E-Rechnungen (ZUGFeRD/Factur-X).
     Das eingebettete XML darf nicht verloren gehen.
2. **Arbeitskopie** im Temp-Ordner. Das Original bleibt bis zum Schluss unberührt.
3. **Metadaten bereinigen:** Creator/Producer und XMP-Creator/CreatorTool
   werden entfernt (früher per exiftool).
4. **OCRmyPDF:** Texterkennung (Deutsch + Englisch) nur für Seiten ohne Text,
   Optimierung, Ausgabe als **PDF/A-2b**. Gelingt PDF/A ausnahmsweise nicht,
   entsteht ein normales PDF mit Textebene, und die Ausgabe weist darauf hin.
5. **Ersetzen:** Das Original wird erst nach geprüftem Erfolg ersetzt.
   Erstell- und Änderungsdatum bleiben erhalten.

Alles wird in der Konsole angezeigt und zusätzlich protokolliert:
`%LOCALAPPDATA%\PDF-OCR\pdf-ocr.log`.

## Installation

`PDF-OCR-Setup-x.y.z.exe` aus den [Releases](../../releases) ausführen.

- Installiert nur für den aktuellen Benutzer, **ohne Administratorrechte**.
- Fehlt **Tesseract OCR**, bietet das Setup an, es per
  `winget install -e --id UB-Mannheim.TesseractOCR` zu installieren. Nur dafür
  fragt Windows nach Administratorrechten, weil Tesseract systemweit
  installiert wird.
- Python, OCRmyPDF und die Sprachdaten für Deutsch und Englisch sind enthalten.
- **Ghostscript wird nicht benötigt.** OCRmyPDF 17 erzeugt PDF/A selbst.

Windows zeigt beim ersten Start eventuell eine SmartScreen-Warnung
("Unbekannter Herausgeber"), weil das Setup nicht signiert ist. Dann
"Weitere Informationen → Trotzdem ausführen" wählen. Wer dem Setup nicht
vertraut, kann es aus diesem Quellcode selbst bauen (siehe unten).

## Benutzung

**Explorer-Kontextmenü.** Unter Windows 11 stehen die Einträge unter
"Weitere Optionen anzeigen" (Umschalt+F10).
- Rechtsklick auf eine oder mehrere PDFs → *OCR hinzufügen (PDF-OCR)*
- Rechtsklick auf einen Ordner → *OCR für PDFs in diesem Ordner* bzw.
  *… inkl. Unterordner*
- Rechtsklick in einen leeren Bereich eines Ordners → *OCR für PDFs in diesem Ordner*

Bei Mehrfachauswahl öffnet sich **ein** Fenster und arbeitet alle Dateien
nacheinander ab.

**Kommandozeile**

```
pdf-ocr "C:\Ablage"              alle PDFs im Ordner
pdf-ocr -r "C:\Ablage"           inkl. Unterordner
pdf-ocr a.pdf b.pdf              einzelne Dateien
pdf-ocr --pick                   Ordner per Dialog wählen
pdf-ocr                          (installiert) Ordner-Dialog
pdf-ocr --dry-run "C:\Ablage"    nur anzeigen, was passieren würde
pdf-ocr --check                  Voraussetzungen prüfen
pdf-ocr -l deu+eng+fra ...       andere Sprachen (Sprachdaten nötig)
pdf-ocr --help
```

**Portable Variante.** `pdf-ocr-portable.exe` in einen Ordner kopieren und
doppelklicken. Dann verarbeitet sie die PDFs in genau diesem Ordner, wie die
frühere `ocr.bat`. Tesseract muss dafür installiert sein.

Ist die exe aus einer bestehenden Konsole gestartet, endet sie ohne
Tastendruck. Per Doppelklick oder Kontextmenü gestartet, bleibt das Fenster
offen, bis man eine Taste drückt (`--pause` / `--no-pause` erzwingen das eine
oder andere).

Exit-Codes: `0` ok, `1` mindestens eine Datei mit Fehler, `2` Voraussetzung fehlt.

## Selbst bauen

Auf einem Windows-Rechner mit Python 3.12 und Inno Setup 6:

```
powershell -ExecutionPolicy Bypass -File build.ps1
```

Ergebnis: `dist\PDF-OCR-Setup-<Version>.exe` und `dist\pdf-ocr-portable.exe`.
Auf GitHub erledigt das `.github/workflows/build.yml` automatisch. Ein Tag
`v1.0.0` erzeugt ein Release.

Aus dem Quellcode starten, ohne zu bauen: `pip install ocrmypdf`, dann
`python pdf-ocr.py --help` im Projektordner.

## Lizenz

MIT, siehe `LICENSE`. Die verwendeten Komponenten und ihre Lizenzen stehen in
`THIRD_PARTY_NOTICES.md`.
