import ctypes
from ctypes import wintypes
import os
from pathlib import Path

user = ctypes.WinDLL("user32", use_last_error=True)
callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def bind(name, result, *arguments):
    function = getattr(user, name)
    function.restype = result
    function.argtypes = arguments
    return function


enum = bind("EnumWindows", wintypes.BOOL, callback_type, wintypes.LPARAM)
visible = bind("IsWindowVisible", wintypes.BOOL, wintypes.HWND)
minimized = bind("IsIconic", wintypes.BOOL, wintypes.HWND)
title = bind("GetWindowTextW", ctypes.c_int, wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
pid = bind("GetWindowThreadProcessId", wintypes.DWORD, wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
activate = bind("SetForegroundWindow", wintypes.BOOL, wintypes.HWND)
restore = bind("ShowWindowAsync", wintypes.BOOL, wintypes.HWND, ctypes.c_int)
dwm = ctypes.WinDLL("dwmapi")
dwm.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]


def open_windows():
    items = []

    @callback_type
    def visit(hwnd, _):
        process = wintypes.DWORD()
        pid(hwnd, ctypes.byref(process))
        if not visible(hwnd) or process.value == os.getpid():
            return True
        cloak = wintypes.DWORD()
        dwm.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloak), ctypes.sizeof(cloak))
        if not cloak.value:
            text = ctypes.create_unicode_buffer(512)
            title(hwnd, text, len(text))
            if text.value and text.value != "Program Manager":
                items.append((text.value, hwnd))
        return True

    enum(visit, 0)
    return items


def focus_window(hwnd):
    if minimized(hwnd):
        restore(hwnd, 9)
    return bool(activate(hwnd))


def installed_apps():
    shortcuts = {}
    for variable in ("APPDATA", "PROGRAMDATA"):
        root = Path(os.environ[variable]) / "Microsoft/Windows/Start Menu/Programs"
        for path in root.rglob("*"):
            if path.suffix.lower() in {".lnk", ".appref-ms"} and path.is_file():
                shortcuts.setdefault(path.stem, str(path))
    return sorted(shortcuts.items(), key=lambda item: item[0].casefold())
