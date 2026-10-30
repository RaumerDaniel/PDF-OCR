<#
  Baut PDF-OCR unter Windows: PyInstaller-Programm + Installer.

  Voraussetzungen auf dem Build-Rechner:
    - Python 3.12 (winget install -e --id Python.Python.3.12)
    - Inno Setup 6 (winget install -e --id JRSoftware.InnoSetup)

  Aufruf:  powershell -ExecutionPolicy Bypass -File build.ps1
  Ergebnis: dist\PDF-OCR-Setup-<Version>.exe  und  dist\pdf-ocr-portable.exe
#>
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# --- Version aus src\pdf_ocr\__init__.py
$version = (Select-String -Path "src\pdf_ocr\__init__.py" -Pattern '__version__ = "(.+)"').Matches[0].Groups[1].Value
Write-Host "== PDF-OCR $version bauen" -ForegroundColor Cyan

# --- Build-Umgebung
$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    if (Test-Path ".venv") { Remove-Item -Recurse -Force ".venv" }   # kaputter Rest eines Fehlversuchs

    # Jedes installierte Python ab 3.11 ist recht (OCRmyPDF 17 braucht >= 3.11).
    # Reihenfolge: Standard-Python des Launchers, python/python3 im PATH,
    # danach gezielt jede Version 3.11 - 3.20 über den Launcher.
    $cands = @("py -3", "python", "python3") + (20..11 | ForEach-Object { "py -3.$_" })
    $base = $null; $ver = $null; $tooOld = @()
    foreach ($cand in $cands) {
        $parts = $cand -split " "; $exe = $parts[0]; $arg = @($parts | Select-Object -Skip 1)
        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
        # try/catch: Windows PowerShell 5.1 bricht sonst bei Fehlertext auf stderr ab
        try { $v = & $exe @arg -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null } catch { $v = $null }
        if ($v -notmatch '^3\.\d+$') { continue }
        if ([version]$v -ge [version]"3.11") { $base = $cand; $ver = $v; break }
        $tooOld += "$v ($cand)"
    }
    if (-not $base) {
        $hint = if ($tooOld) { " Gefunden, aber zu alt: $(($tooOld | Select-Object -Unique) -join ', ')." } else { "" }
        throw "Kein Python ab 3.11 gefunden.$hint Installieren z.B. mit: winget install -e --id Python.Python.3.12  (danach neues Terminal öffnen)"
    }
    Write-Host "== Verwende Python $ver ($base)"

    Write-Host "== Virtuelle Python-Umgebung anlegen (.venv)"
    $parts = $base -split " "; $exe = $parts[0]; $arg = @($parts | Select-Object -Skip 1)
    & $exe @arg -m venv .venv
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $py)) { throw "Anlegen der .venv fehlgeschlagen" }
}
& $py -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip-Update fehlgeschlagen" }
& $py -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw "Installation der Python-Pakete fehlgeschlagen" }

# --- Tesseract-Sprachdaten (Apache-2.0), gleiche Quelle wie bisher
New-Item -ItemType Directory -Force tessdata | Out-Null
foreach ($lang in @("deu", "eng")) {
    $f = "tessdata\$lang.traineddata"
    if (-not (Test-Path $f)) {
        Write-Host "== Lade $lang.traineddata"
        Invoke-WebRequest -UseBasicParsing "https://github.com/tesseract-ocr/tessdata/raw/main/$lang.traineddata" -OutFile $f
    }
}

# --- Windows-Versionsinfo für die .exe (Eigenschaften > Details)
$v = ($version.Split(".") + @("0", "0", "0"))[0..3] -join ", "
New-Item -ItemType Directory -Force build | Out-Null
@"
VSVersionInfo(
  ffi=FixedFileInfo(filevers=($v), prodvers=($v)),
  kids=[StringFileInfo([StringTable('040704B0', [
    StringStruct('ProductName', 'PDF-OCR'),
    StringStruct('FileDescription', 'PDF-OCR - OCR-Textebene fuer PDFs'),
    StringStruct('FileVersion', '$version'),
    StringStruct('ProductVersion', '$version'),
    StringStruct('LegalCopyright', 'MIT License'),
    StringStruct('OriginalFilename', 'pdf-ocr.exe')])]),
    VarFileInfo([VarStruct('Translation', [1031, 1200])])]
)
"@ | Set-Content -Encoding UTF8 build\version_info.txt

# --- Programm bauen
Write-Host "== PyInstaller"
& $py -m PyInstaller pdf-ocr.spec --noconfirm --clean
if ($LASTEXITCODE -ne 0) { throw "PyInstaller fehlgeschlagen" }

# --- Lizenzen aller mitgelieferten Python-Pakete beilegen
Write-Host "== Drittlizenzen sammeln"
& $py -m piplicenses --from=mixed --with-urls --with-license-file --no-license-path `
    --format=plain-vertical --ignore-packages pyinstaller pyinstaller-hooks-contrib pip-licenses altgraph pefile pywin32-ctypes setuptools pip `
    --output-file dist\pdf-ocr\THIRD_PARTY_LICENSES_PYTHON.txt

# --- Schnelltest der gebauten exe
& "dist\pdf-ocr\pdf-ocr.exe" --version
if ($LASTEXITCODE -ne 0) { throw "pdf-ocr.exe startet nicht" }

# --- Installer
# ISCC.exe suchen: PATH, dann alle "Inno Setup *"-Ordner (6, 7, ...) in den üblichen Programmordnern
$iscc = (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source
if (-not $iscc) {
    $roots = @(${env:ProgramFiles(x86)}, $env:ProgramFiles, "$env:LOCALAPPDATA\Programs") | Where-Object { $_ -and (Test-Path $_) }
    $iscc = $roots | ForEach-Object { Get-ChildItem -Path $_ -Directory -Filter "Inno Setup*" -ErrorAction SilentlyContinue } |
        Sort-Object Name -Descending | ForEach-Object { Join-Path $_.FullName "ISCC.exe" } |
        Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $iscc) {
    throw "Inno Setup nicht gefunden. Installieren mit: winget install -e --id JRSoftware.InnoSetup  - danach build.ps1 erneut starten (das Programm selbst liegt schon fertig in dist\pdf-ocr)."
}
Write-Host "== Installer bauen mit $iscc"
& $iscc "/DAppVersion=$version" installer\pdf-ocr.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup fehlgeschlagen" }

Write-Host ""
Write-Host "Fertig:" -ForegroundColor Green
Get-ChildItem dist\*.exe | ForEach-Object { Write-Host ("  {0}  ({1:N1} MB)" -f $_.FullName, ($_.Length / 1MB)) }
