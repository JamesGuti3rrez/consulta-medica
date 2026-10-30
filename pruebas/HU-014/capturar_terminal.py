"""Capturas de ventanas nativas propias mostrando los registros originales de HU-014."""
from pathlib import Path
import importlib.util
import ctypes
import hashlib
import json
import subprocess
import time

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('terminal_helper',ROOT/'pruebas/Sprint2/fotografiar_terminal.py')
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)


def main():
    records=[]
    for label,name in [('REGRESION','regresion'),('SQL','sql'),('SUPABASE','supabase_real'),('NAVEGADOR','navegador'),('CARGA-GRUPOS','carga_grupos')]:
        source=HERE/(name+'.txt');title='HU014-'+label;hwnd=None
        if not source.exists():raise SystemExit('Falta registro: '+name)
        proc=subprocess.Popen(['conhost.exe','powershell.exe','-NoLogo','-NoProfile','-ExecutionPolicy','Bypass',
          '-File',str(ROOT/'pruebas/Sprint2/mostrar_registro.ps1'),'-Registro',str(source),'-Titulo',title,'-Filas','32'],cwd=ROOT)
        try:
            for _ in range(100):
                hwnd=helper.find_window(title)
                if hwnd:break
                time.sleep(.1)
            if not hwnd:raise RuntimeError('No se encontró la ventana propia de PowerShell.')
            time.sleep(1.5)
            helper.user32.ShowWindow(hwnd,9)
            if not helper.user32.SetWindowPos(hwnd,helper.wintypes.HWND(-1),20,20,0,0,0x0041):raise RuntimeError('No se pudo preparar la ventana de captura.')
            helper.user32.SetForegroundWindow(hwnd);time.sleep(2)
            rect=helper.wintypes.RECT();helper.user32.GetWindowRect(hwnd,ctypes.byref(rect))
            ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd,9,ctypes.byref(rect),ctypes.sizeof(rect))
            picture=helper.ImageGrab.grab(bbox=(rect.left,rect.top,rect.right,rect.bottom),all_screens=True)
            target=HERE/'capturas'/('terminal-'+name+'.png');picture.save(target)
            records.append({'registro':str(source.relative_to(ROOT)),'captura':str(target.relative_to(ROOT)),
                            'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'origen':'Ventana nativa propia de PowerShell con registro original'})
            print('[PASA] Captura nativa '+label,flush=True)
        finally:
            if hwnd:helper.user32.PostMessageW(hwnd,0x0010,0,0)
            try:proc.wait(timeout=4)
            except subprocess.TimeoutExpired:proc.terminate()
    (HERE/'capturas_terminal.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
