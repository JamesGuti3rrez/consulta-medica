"""Capturas nativas de registros originales; no se captura el escritorio del usuario."""
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
user32.SetProcessDPIAware()
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                              ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.SetWindowPos.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
CALLBACK = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def find_window(title):
    matches = []
    @CALLBACK
    def callback(hwnd, parameter):
        text = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, text, 512)
        if text.value == title and user32.IsWindowVisible(hwnd):
            matches.append(hwnd)
        return True
    user32.EnumWindows(callback, 0)
    return matches[0] if matches else None


def main():
    captures = []
    tasks = [(task, HERE / task / 'terminal.txt', HERE / task / 'capturas/terminal.png', 320)
             for task in ('TA-017', 'TA-007', 'TA-027', 'HU-004', 'EN-013')]
    tasks.append(('SERVICIOS-REALES', HERE / 'servicios_reales.txt', HERE / 'capturas/servicios-reales.png', 650))
    for label, source, target, desired_height in tasks:
        if not source.exists():
            raise SystemExit('Falta registro: ' + str(source))
        title = 'SPRINT2-' + label
        process = subprocess.Popen(['conhost.exe', 'powershell.exe', '-NoLogo', '-NoProfile',
            '-ExecutionPolicy', 'Bypass', '-File', str(HERE / 'mostrar_registro.ps1'),
            '-Registro', str(source), '-Titulo', title, '-Filas', '32' if label == 'SERVICIOS-REALES' else '14'], cwd=ROOT)
        hwnd = None
        try:
            for _ in range(100):
                hwnd = find_window(title)
                if hwnd:
                    break
                time.sleep(.1)
            if not hwnd:
                raise RuntimeError('No se encontró la ventana propia de PowerShell.')
            # La ventana se titula antes de que PowerShell termine de ajustar el buffer.
            time.sleep(1.5)
            user32.ShowWindow(hwnd, 9)
            width = min(1370, user32.GetSystemMetrics(0) - 50)
            height = min(desired_height, user32.GetSystemMetrics(1) - 70)
            # Mantener el tamaño de caracteres preparado por PowerShell evita reflujo de líneas.
            if not user32.SetWindowPos(hwnd, wintypes.HWND(-1), 20, 20, width, height, 0x0041):
                raise RuntimeError('No se pudo ajustar la ventana propia de PowerShell.')
            user32.SetForegroundWindow(hwnd)
            time.sleep(2)
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(rect), ctypes.sizeof(rect))
            # Capturar solo la región de la ventana que contiene el registro; excluir espacio vacío.
            bitmap = ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, min(rect.bottom, rect.top + desired_height)), all_screens=True)
            target.parent.mkdir(parents=True, exist_ok=True)
            bitmap.save(target)
            captures.append({'tarea': label, 'registro': str(source.relative_to(ROOT)),
                'captura': str(target.relative_to(ROOT)), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                'procedencia': 'Ventana nativa de PowerShell mostrando la salida original registrada', 'dimensiones': list(bitmap.size)})
            print('[PASA] Captura nativa: ' + label, flush=True)
        finally:
            if hwnd:
                user32.PostMessageW(hwnd, 0x0010, 0, 0)
            try:
                process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                process.terminate()
    (HERE / 'capturas_terminal.json').write_text(json.dumps(captures, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
