"""Captura ventanas propias de PowerShell que muestran los registros originales de las pruebas."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import hashlib
import json
from pathlib import Path
import subprocess
import time

from PIL import ImageGrab

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
user32 = ctypes.windll.user32
try:
    user32.SetProcessDPIAware()
except Exception:
    pass
CALLBACK = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def find_window(title):
    matches = []
    @CALLBACK
    def callback(hwnd, parameter):
        length = user32.GetWindowTextLengthW(hwnd)
        text = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, text, length + 1)
        if title in text.value and user32.IsWindowVisible(hwnd):
            matches.append(hwnd)
        return True
    user32.EnumWindows(callback, 0)
    return matches[0] if matches else None


def main():
    result = []
    for name in ("pytest", "supabase-real", "navegador"):
        source = HERE / "terminal" / (name + ".txt")
        if not source.exists():
            raise SystemExit("Falta el registro " + name)
        title = "TA012-CAPTURA-" + name
        process = subprocess.Popen([
            "conhost.exe", "powershell.exe", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", str(HERE / "mostrar_registro.ps1"), "-Registro", str(source), "-Titulo", title,
        ], cwd=ROOT)
        hwnd = None
        try:
            for _ in range(100):
                hwnd = find_window(title)
                if hwnd:
                    break
                time.sleep(.1)
            if not hwnd:
                raise RuntimeError("No se encontró la ventana propia de PowerShell.")
            # Solo se coloca y captura la ventana temporal creada por este script.
            user32.ShowWindow(hwnd, 9)
            screen_width, screen_height = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
            desired_height = {"pytest": 550, "supabase-real": 650, "navegador": 350}[name]
            width, height = min(1370, screen_width - 50), min(desired_height, screen_height - 70)
            user32.SetWindowPos(hwnd, 0, 20, 20, width, height, 0x0040)
            user32.SetForegroundWindow(hwnd)
            time.sleep(2.5)
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            # DWM excluye los bordes transparentes de la ventana para no incluir otras aplicaciones.
            ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(rect), ctypes.sizeof(rect))
            image = ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom), all_screens=True)
            target = HERE / "capturas" / ("terminal-" + name + ".png")
            target.parent.mkdir(exist_ok=True)
            image.save(target)
            result.append({"registro": str(source.relative_to(ROOT)), "captura": str(target.relative_to(ROOT)),
                "origen": "ventana nativa propia de PowerShell mostrando el registro original",
                "sha256_registro": hashlib.sha256(source.read_bytes()).hexdigest(),
                "dimensiones": list(image.size)})
            print("Captura nativa guardada: " + target.name, flush=True)
        finally:
            if hwnd:
                user32.PostMessageW(hwnd, 0x0010, 0, 0)
            try:
                process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                process.terminate()
    (HERE / "terminal/capturas.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

