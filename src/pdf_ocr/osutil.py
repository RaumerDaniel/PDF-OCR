"""Betriebssystem-Helfer: Datenordner, Datei-Zeitstempel, Konsole, Sperrdatei.

Zielplattform ist Windows; die Fallbacks für andere Systeme existieren nur,
damit sich das Tool auch unter Linux/macOS testen lässt.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from pdf_ocr import APP_ID

IS_WINDOWS = os.name == "nt"


# --------------------------------------------------------------------------
# Ordner
# --------------------------------------------------------------------------

def data_dir() -> Path:
    """%LOCALAPPDATA%\\PDF-OCR (Log, Warteschlange)."""
    if IS_WINDOWS:
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    d = base / APP_ID
    d.mkdir(parents=True, exist_ok=True)
    return d


def app_dir() -> Path:
    """Ordner, in dem die Anwendung liegt (bei PyInstaller: neben der .exe)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def resource_dir() -> Path:
    """Ordner mit mitgelieferten Daten (tessdata, Lizenzen)."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", app_dir()))
    # Beim Start aus dem Quellcode: Projektwurzel
    return Path(__file__).resolve().parents[2]


def is_portable_build() -> bool:
    """True, wenn es die Einzeldatei-Variante (pdf-ocr-portable.exe) ist.

    Bei PyInstaller-onefile wird in ein Temp-Verzeichnis entpackt, _MEIPASS
    liegt dann *nicht* neben der .exe.
    """
    if not getattr(sys, "frozen", False):
        return False
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass is None:
        return False
    # onedir (installiert): _MEIPASS = <exe-Ordner>\_internal  -> nicht portabel
    # onefile (portabel):   _MEIPASS = %TEMP%\_MEIxxxxx        -> portabel
    mp, ad = Path(meipass).resolve(), app_dir()
    return mp != ad and ad not in mp.parents


# --------------------------------------------------------------------------
# Zeitstempel (Erstellt + Geändert) sichern und wiederherstellen
# --------------------------------------------------------------------------

@dataclass
class FileTimes:
    created_ns: int | None
    modified_ns: int
    accessed_ns: int


def get_times(path: Path) -> FileTimes:
    st = os.stat(path)
    created = getattr(st, "st_birthtime_ns", None)
    if created is None and IS_WINDOWS:
        created = st.st_ctime_ns  # unter Windows < Py3.12 = Erstellzeit
    return FileTimes(created, st.st_mtime_ns, st.st_atime_ns)


def set_times(path: Path, t: FileTimes) -> None:
    os.utime(path, ns=(t.accessed_ns, t.modified_ns))
    if IS_WINDOWS and t.created_ns is not None:
        _win_set_creation_time(path, t.created_ns)


def _win_set_creation_time(path: Path, created_ns: int) -> None:
    import ctypes
    from ctypes import wintypes

    # FILETIME = 100-ns-Intervalle seit 1601-01-01
    ft_value = created_ns // 100 + 116444736000000000
    ft = wintypes.FILETIME(ft_value & 0xFFFFFFFF, ft_value >> 32)

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    ]
    kernel32.SetFileTime.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME),
    ]
    FILE_WRITE_ATTRIBUTES = 0x100
    OPEN_EXISTING = 3
    FILE_SHARE_ALL = 0x7
    handle = kernel32.CreateFileW(
        str(path), FILE_WRITE_ATTRIBUTES, FILE_SHARE_ALL, None, OPEN_EXISTING, 0, None
    )
    if handle in (None, wintypes.HANDLE(-1).value):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if not kernel32.SetFileTime(handle, ctypes.byref(ft), None, None):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel32.CloseHandle(handle)


# --------------------------------------------------------------------------
# Konsole
# --------------------------------------------------------------------------

def owns_console() -> bool:
    """True, wenn das Konsolenfenster nur für uns geöffnet wurde.

    Dann wurde das Tool per Doppelklick/Kontextmenü gestartet und sollte am
    Ende auf einen Tastendruck warten, damit man die Ausgabe lesen kann.
    Wurde es aus einer vorhandenen cmd/PowerShell gestartet: kein Warten.
    """
    if not IS_WINDOWS:
        return False
    try:
        import ctypes

        arr = (ctypes.c_uint * 4)()
        n = ctypes.windll.kernel32.GetConsoleProcessList(arr, 4)
        return n <= 1
    except Exception:
        return False


def set_console_title(title: str) -> None:
    if IS_WINDOWS:
        try:
            import ctypes

            ctypes.windll.kernel32.SetConsoleTitleW(title)
        except Exception:
            pass


def wait_for_key(prompt: str) -> None:
    try:
        if IS_WINDOWS:
            import msvcrt

            print(prompt, end="", flush=True)
            msvcrt.getwch()
            print()
        else:
            input(prompt)
    except (EOFError, KeyboardInterrupt):
        pass


# --------------------------------------------------------------------------
# Sperrdatei (nur ein Arbeitsfenster gleichzeitig)
# --------------------------------------------------------------------------

class FileLock:
    """Nicht-blockierende, prozessübergreifende Sperre über eine Datei.

    Das Betriebssystem gibt die Sperre automatisch frei, wenn der Prozess
    endet (auch bei Absturz), es bleiben also keine "hängenden" Sperren.
    """

    def __init__(self, path: Path):
        self.path = path
        self._fh = None

    def acquire(self) -> bool:
        fh = open(self.path, "a+b")
        try:
            if IS_WINDOWS:
                import msvcrt

                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            return False
        self._fh = fh
        return True

    def release(self) -> None:
        if self._fh is None:
            return
        try:
            if IS_WINDOWS:
                import msvcrt

                self._fh.seek(0)
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        finally:
            self._fh.close()
            self._fh = None
