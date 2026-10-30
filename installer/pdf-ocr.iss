; Inno Setup Skript für PDF-OCR
; Bauen:  iscc installer\pdf-ocr.iss   (erwartet den PyInstaller-Ordner dist\pdf-ocr)
;
; Grundsätze:
;  - Installation nur für den aktuellen Benutzer -> KEINE Administratorrechte nötig.
;  - Kontextmenü unter HKEY_CURRENT_USER, nur für PDFs und Ordner (nicht für alle Dateien).
;  - Tesseract OCR ist ein eigenständiges Programm. Fehlt es, bietet das Setup an,
;    es offiziell per winget zu installieren. Nur dafür fragt Windows nach Adminrechten,
;    und das Setup sagt vorher, warum.

#define AppName "PDF-OCR"
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#define AppExe "pdf-ocr.exe"
#define AppUrl "https://github.com/RaumerDaniel/PDF-OCR"

[Setup]
AppId={{6EC01411-0051-4BFD-96A4-98662AEFE89D}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}/issues
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ChangesEnvironment=yes
ChangesAssociations=yes
OutputDir=..\dist
OutputBaseFilename=PDF-OCR-Setup-{#AppVersion}
SetupIconFile=..\assets\pdf-ocr.ico
UninstallDisplayIcon={app}\{#AppExe}
LicenseFile=..\LICENSE
InfoBeforeFile=info-vorher.txt
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "de"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "contextmenu"; Description: "Kontextmenü-Einträge für PDFs und Ordner anlegen"; GroupDescription: "Integration:"
Name: "addtopath"; Description: "pdf-ocr zum PATH hinzufügen (Aufruf aus cmd/PowerShell)"; GroupDescription: "Integration:"; Flags: unchecked
Name: "tesseract"; Description: "Tesseract OCR installieren (per winget; Windows fragt nach Administratorrechten)"; GroupDescription: "Fehlende Voraussetzung:"; Check: not TesseractInstalled

[Files]
Source: "..\dist\pdf-ocr\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}\PDF-OCR (Ordner wählen)"; Filename: "{app}\{#AppExe}"; Parameters: "--pick"
Name: "{autoprograms}\{#AppName}\PDF-OCR Voraussetzungen prüfen"; Filename: "{app}\{#AppExe}"; Parameters: "--check --pause"
Name: "{autoprograms}\{#AppName}\Protokoll-Ordner"; Filename: "{localappdata}\PDF-OCR"
Name: "{autoprograms}\{#AppName}\PDF-OCR deinstallieren"; Filename: "{uninstallexe}"

[Registry]
; --- PDF-Dateien (auch Mehrfachauswahl; MultiSelectModel=Player erlaubt >15 Dateien)
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\PdfOcr"; ValueType: string; ValueName: ""; ValueData: "OCR hinzufügen (PDF-OCR)"; Tasks: contextmenu; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\PdfOcr"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#AppExe}"",0"; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\PdfOcr"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\PdfOcr\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --queue ""%1"""; Tasks: contextmenu

; --- Rechtsklick auf einen Ordner
Root: HKCU; Subkey: "Software\Classes\Directory\shell\PdfOcr"; ValueType: string; ValueName: ""; ValueData: "OCR für PDFs in diesem Ordner"; Tasks: contextmenu; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Directory\shell\PdfOcr"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#AppExe}"",0"; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\Directory\shell\PdfOcr\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --queue ""%1"""; Tasks: contextmenu

Root: HKCU; Subkey: "Software\Classes\Directory\shell\PdfOcrRecursive"; ValueType: string; ValueName: ""; ValueData: "OCR für PDFs in diesem Ordner inkl. Unterordner"; Tasks: contextmenu; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Directory\shell\PdfOcrRecursive"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#AppExe}"",0"; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\Directory\shell\PdfOcrRecursive\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --queue --recursive ""%1"""; Tasks: contextmenu

; --- Rechtsklick in den leeren Bereich eines geöffneten Ordners
Root: HKCU; Subkey: "Software\Classes\Directory\Background\shell\PdfOcr"; ValueType: string; ValueName: ""; ValueData: "OCR für PDFs in diesem Ordner"; Tasks: contextmenu; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Directory\Background\shell\PdfOcr"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#AppExe}"",0"; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\Directory\Background\shell\PdfOcr\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --queue ""%V"""; Tasks: contextmenu

[Run]
Filename: "{app}\{#AppExe}"; Parameters: "--check --pause"; Description: "Voraussetzungen jetzt prüfen (zeigt, was gefunden wurde)"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\PDF-OCR"

[Code]
const
  WingetArgs = 'install -e --id UB-Mannheim.TesseractOCR --accept-package-agreements --accept-source-agreements';

function TesseractInstalled(): Boolean;
var
  Dir: string;
begin
  Result :=
    (RegQueryStringValue(HKLM, 'SOFTWARE\Tesseract-OCR', 'InstallDir', Dir) and FileExists(AddBackslash(Dir) + 'tesseract.exe')) or
    (RegQueryStringValue(HKCU, 'SOFTWARE\Tesseract-OCR', 'InstallDir', Dir) and FileExists(AddBackslash(Dir) + 'tesseract.exe')) or
    FileExists(ExpandConstant('{commonpf64}\Tesseract-OCR\tesseract.exe')) or
    FileExists(ExpandConstant('{commonpf32}\Tesseract-OCR\tesseract.exe')) or
    FileExists(ExpandConstant('{localappdata}\Programs\Tesseract-OCR\tesseract.exe'));
end;

function WingetAvailable(): Boolean;
var
  Code: Integer;
begin
  Result := Exec(ExpandConstant('{cmd}'), '/c where winget >nul 2>nul', '', SW_HIDE, ewWaitUntilTerminated, Code) and (Code = 0);
end;

procedure InstallTesseract();
var
  Code: Integer;
begin
  if not WingetAvailable() then
  begin
    MsgBox('winget (Windows-Paketmanager) wurde nicht gefunden.' + #13#10#13#10 +
      'Bitte Tesseract OCR manuell installieren:' + #13#10 +
      'https://github.com/UB-Mannheim/tesseract/wiki' + #13#10#13#10 +
      'PDF-OCR selbst ist installiert und findet Tesseract danach automatisch.',
      mbInformation, MB_OK);
    exit;
  end;

  MsgBox('Jetzt wird Tesseract OCR installiert (die eigentliche Texterkennung).' + #13#10#13#10 +
    'Warum fragt Windows gleich nach Administratorrechten?' + #13#10 +
    'Tesseract ist ein eigenständiges Open-Source-Programm (Apache-2.0) der UB Mannheim ' +
    'und installiert sich systemweit nach "C:\Program Files\Tesseract-OCR". Dafür braucht ' +
    'Windows die Bestätigung eines Administrators.' + #13#10#13#10 +
    'PDF-OCR selbst braucht KEINE Adminrechte. Die deutschen und englischen ' +
    'Sprachdaten bringt PDF-OCR selbst mit.' + #13#10#13#10 +
    'Es öffnet sich ein Konsolenfenster mit dem Befehl:' + #13#10 +
    'winget ' + WingetArgs,
    mbInformation, MB_OK);

  Exec(ExpandConstant('{cmd}'), '/c winget ' + WingetArgs, '', SW_SHOWNORMAL, ewWaitUntilTerminated, Code);

  if not TesseractInstalled() then
    MsgBox('Tesseract wurde nicht installiert (abgebrochen, Adminrechte verweigert oder Fehler, Code ' + IntToStr(Code) + ').' + #13#10#13#10 +
      'PDF-OCR ist trotzdem installiert, kann aber ohne Tesseract keine Texterkennung machen.' + #13#10 +
      'Nachholen in einer Eingabeaufforderung:' + #13#10 +
      'winget ' + WingetArgs,
      mbError, MB_OK);
end;

procedure WarnOldContextMenu();
begin
  if RegKeyExists(HKLM, 'SOFTWARE\Classes\*\shell\AddOCR') then
    MsgBox('Hinweis: Es gibt noch einen alten Kontextmenü-Eintrag "AddOCR" (ocr.bat) unter' + #13#10 +
      'HKEY_LOCAL_MACHINE\SOFTWARE\Classes\*\shell\AddOCR.' + #13#10#13#10 +
      'Er ist von PDF-OCR unabhängig. Entfernen in einer Eingabeaufforderung als Administrator:' + #13#10 +
      'reg delete "HKLM\SOFTWARE\Classes\*\shell\AddOCR" /f',
      mbInformation, MB_OK);
end;

procedure EnvAddPath(Path: string);
var
  Paths: string;
begin
  if not RegQueryStringValue(HKCU, 'Environment', 'Path', Paths) then Paths := '';
  if Pos(';' + Uppercase(Path) + ';', ';' + Uppercase(Paths) + ';') > 0 then exit;
  if (Paths <> '') and (Copy(Paths, Length(Paths), 1) <> ';') then Paths := Paths + ';';
  RegWriteExpandStringValue(HKCU, 'Environment', 'Path', Paths + Path);
end;

procedure EnvRemovePath(Path: string);
var
  Paths: string;
  P: Integer;
begin
  if not RegQueryStringValue(HKCU, 'Environment', 'Path', Paths) then exit;
  P := Pos(';' + Uppercase(Path) + ';', ';' + Uppercase(Paths) + ';');
  if P = 0 then exit;
  if P = 1 then
    Delete(Paths, 1, Length(Path) + 1)   { erster Eintrag: Pfad + folgendes ';' }
  else
    Delete(Paths, P - 1, Length(Path) + 1); { sonst: vorangehendes ';' + Pfad }
  RegWriteExpandStringValue(HKCU, 'Environment', 'Path', Paths);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if WizardIsTaskSelected('addtopath') then EnvAddPath(ExpandConstant('{app}'));
    if WizardIsTaskSelected('tesseract') then InstallTesseract();
    WarnOldContextMenu();
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then EnvRemovePath(ExpandConstant('{app}'));
end;
