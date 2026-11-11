"""Ejecuta un comando en una ventana real de PowerShell y guarda su salida y una foto de la ventana.

La ventana se titula «Evidencia consulta-medica <commit>», muestra el comando y su salida completa, y termina con el
código de salida y la hora. La salida queda en ejecucion/<nombre>.txt y la foto en ejecucion/<nombre>_terminal.png.
La foto se toma con PrintWindow, así que sale bien aunque otra ventana tape la consola.

Uso, desde la raíz del repo:
  python pruebas/38_labios_por_silaba/ejecutar_en_terminal.py <nombre> "<comando de PowerShell>"
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import Path
import subprocess
import sys
import time

from PIL import Image

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
EJECUCION = AQUI / 'ejecucion'
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
user32.SetProcessDPIAware()
CALLBACK = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def buscar_ventana(titulo: str):
    encontradas = []

    @CALLBACK
    def revisar(hwnd, _):
        texto = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, texto, 512)
        if texto.value == titulo and user32.IsWindowVisible(hwnd):
            encontradas.append(hwnd)
        return True

    user32.EnumWindows(revisar, 0)
    return encontradas[0] if encontradas else None


def fotografiar(hwnd) -> Image.Image:
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    ancho, alto = rect.right - rect.left, rect.bottom - rect.top
    dc_ventana = user32.GetWindowDC(hwnd)
    dc = gdi32.CreateCompatibleDC(dc_ventana)
    mapa = gdi32.CreateCompatibleBitmap(dc_ventana, ancho, alto)
    gdi32.SelectObject(dc, mapa)
    user32.PrintWindow(hwnd, dc, 2)  # PW_RENDERFULLCONTENT

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [('biSize', wintypes.DWORD), ('biWidth', wintypes.LONG), ('biHeight', wintypes.LONG),
                    ('biPlanes', wintypes.WORD), ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
                    ('biSizeImage', wintypes.DWORD), ('biXPelsPerMeter', wintypes.LONG),
                    ('biYPelsPerMeter', wintypes.LONG), ('biClrUsed', wintypes.DWORD), ('biClrImportant', wintypes.DWORD)]

    cabecera = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), ancho, -alto, 1, 32, 0, 0, 0, 0, 0, 0)
    datos = ctypes.create_string_buffer(ancho * alto * 4)
    gdi32.GetDIBits(dc, mapa, 0, alto, datos, ctypes.byref(cabecera), 0)
    gdi32.DeleteObject(mapa)
    gdi32.DeleteDC(dc)
    user32.ReleaseDC(hwnd, dc_ventana)
    return Image.frombuffer('RGB', (ancho, alto), datos, 'raw', 'BGRX', 0, 1)


def recortar_vacio(imagen: Image.Image) -> Image.Image:
    """Quita el fondo negro que sobra debajo de la última línea escrita (deja un margen)."""
    gris = imagen.convert('L')
    ancho, alto = gris.size
    ultima = 0
    for y in range(alto - 30, 40, -1):
        if max(gris.crop((8, y, ancho - 40, y + 1)).getdata()) > 90:
            ultima = y
            break
    return imagen.crop((0, 0, ancho, min(alto, ultima + 40)))


def main():
    nombre, comando = sys.argv[1], sys.argv[2]
    EJECUCION.mkdir(parents=True, exist_ok=True)
    salida = EJECUCION / f'{nombre}.txt'
    foto = EJECUCION / f'{nombre}_terminal.png'
    listo = EJECUCION / f'.{nombre}.listo'
    for archivo in (salida, listo):
        archivo.unlink(missing_ok=True)
    commit = subprocess.run(['git', 'rev-parse', '--short=8', 'HEAD'], cwd=RAIZ, capture_output=True, text=True).stdout.strip()
    titulo = f'Evidencia consulta-medica {commit}'
    comando_simple = comando.replace("'", "''")
    script = f"""
$Host.UI.RawUI.WindowTitle = '{titulo}'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$OutputEncoding = [Text.Encoding]::UTF8
$ancho = [Math]::Min(160, $Host.UI.RawUI.MaxPhysicalWindowSize.Width)
$alto = [Math]::Min(56, $Host.UI.RawUI.MaxPhysicalWindowSize.Height - 2)
try {{ $Host.UI.RawUI.BufferSize = New-Object Management.Automation.Host.Size($ancho, 3000) }} catch {{}}
try {{ $Host.UI.RawUI.WindowSize = New-Object Management.Automation.Host.Size($ancho, $alto) }} catch {{}}
try {{ $Host.UI.RawUI.BufferSize = New-Object Management.Automation.Host.Size($ancho, 3000) }} catch {{}}
Set-Location '{RAIZ}'
$comando = @'
{comando} | Tee-Object -Variable registro
'@
Write-Host ("PS " + (Get-Location).Path + "> " + $comando)
Invoke-Expression $comando
$codigo = $LASTEXITCODE
$fin = "`nCodigo de salida: $codigo   " + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
Write-Host $fin
$texto = (@('PS> {comando_simple}') + @($registro | ForEach-Object {{ "$_" }}) + @($fin)) -join "`r`n"
[IO.File]::WriteAllText('{salida}', $texto, (New-Object Text.UTF8Encoding $false))
New-Item -ItemType File -Path '{listo}' | Out-Null
Start-Sleep -Seconds 3600
"""
    archivo_ps = EJECUCION / f'.{nombre}.ps1'
    archivo_ps.write_text(script, encoding='utf-8-sig')
    proceso = subprocess.Popen(['conhost.exe', 'powershell.exe', '-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                                '-File', str(archivo_ps)], cwd=RAIZ)
    hwnd = None
    try:
        for _ in range(100):
            hwnd = buscar_ventana(titulo)
            if hwnd:
                break
            time.sleep(0.1)
        if not hwnd:
            raise SystemExit('No apareció la ventana de PowerShell.')
        user32.SetWindowPos(hwnd, None, 20, 20, 0, 0, 0x0045)  # SWP_NOSIZE | SWP_NOZORDER | SWP_SHOWWINDOW
        while not listo.exists():
            if proceso.poll() is not None:
                raise SystemExit('La ventana de PowerShell se cerró antes de terminar.')
            time.sleep(1)
        time.sleep(1.5)
        recortar_vacio(fotografiar(hwnd)).save(foto)
        texto = salida.read_text(encoding='utf-8', errors='replace') if salida.exists() else ''
        print(texto.strip().splitlines()[-1] if texto.strip() else '(sin salida)')
        print(f'Foto: {foto.relative_to(RAIZ)}')
    finally:
        if hwnd:
            user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
        try:
            proceso.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proceso.kill()
        for archivo in (listo, archivo_ps):
            archivo.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
