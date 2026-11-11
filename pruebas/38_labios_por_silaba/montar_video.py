"""Monta el video de demostración «antes y después» a partir de dos grabaciones de grabar_video.cjs.

Para cada grabación busca el destello magenta en el video (el primer fotograma que lo muestra) y con él convierte la
hora de inicio de cada audio en su posición dentro del video. El resultado es un MP4 (H.264 + AAC) con:
  1. Rótulo «Antes» y la grabación con los videos de LivePortrait (commit f9fc8eb).
  2. Rótulo «Después» y la grabación con la boca por sílaba y el balanceo (fase 38).
  3. Rótulo «Acercamiento» y la misma grabación del después, ampliada a la cara.

Necesita ffmpeg (variable FFMPEG o en el PATH) y OpenCV.
Además guarda en <carpeta_evidencia> montaje.json (duraciones y sincronía) y dos fotogramas para el informe.
Uso: python pruebas/38_labios_por_silaba/montar_video.py <carpeta_antes> <carpeta_despues> <salida.mp4> <carpeta_evidencia>
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FFMPEG = os.environ.get('FFMPEG', 'ffmpeg')
ANCHO, ALTO, FPS = 1280, 800, 25


def buscar_destello(video: Path) -> float:
    captura = cv2.VideoCapture(str(video))
    while True:
        ok, cuadro = captura.read()
        if not ok:
            raise SystemExit(f'No se encontró el destello en {video}')
        b, g, r = (float(cuadro[..., i].mean()) for i in range(3))
        if r > 200 and b > 200 and g < 60:
            ms = captura.get(cv2.CAP_PROP_POS_MSEC)
            captura.release()
            return ms


def preparar(carpeta: Path, destino: Path, acercar: bool = False, maximo_s: float | None = None) -> tuple[Path, dict]:
    """Recorta desde el fin del destello, agrega el audio en su sitio y normaliza a 1280x800 a 25 fps."""
    linea = json.loads((carpeta / 'linea_de_tiempo.json').read_text(encoding='utf-8'))
    video = carpeta / 'pantalla.webm'
    destello_ms = buscar_destello(video)
    desfase = destello_ms - linea['destello']  # milisegundos del video menos hora del reloj
    sonidos = [s for s in linea['sonidos'] if s['evento'] == 'playing' and s.get('archivo')]
    # Desde 2 s antes de la primera voz (se salta la espera inicial), nunca antes del fin del destello (400 ms).
    inicio_ms = destello_ms + 600
    if sonidos:
        inicio_ms = max(inicio_ms, min(s['inicio'] for s in sonidos) + desfase - 2000)
    entradas = ['-ss', f'{inicio_ms / 1000:.3f}', '-i', str(video)]
    filtros, etiquetas = [], []
    for i, sonido in enumerate(sonidos, start=1):
        retraso = int(sonido['inicio'] + desfase - inicio_ms)
        entradas += ['-i', str(carpeta / 'audios' / sonido['archivo'])]
        filtros.append(f'[{i}:a]aresample=48000,adelay={max(retraso, 0)}:all=1[a{i}]')
        etiquetas.append(f'[a{i}]')
    duracion = (linea['fin'] + desfase - inicio_ms) / 1000
    if maximo_s:
        duracion = min(duracion, maximo_s)
    primer_sonido_s = min(int(s['inicio'] + desfase - inicio_ms) for s in sonidos) / 1000 if sonidos else None
    if acercar:
        x, y, w, h = linea['escena']
        # Un recuadro de 16:10 centrado en la cara (algo arriba del centro de la escena).
        cw = int(w * 0.42)
        ch = int(cw * ALTO / ANCHO)
        cx, cy = x + w // 2, y + int(h * 0.40)
        imagen = f'[0:v]crop={cw}:{ch}:{cx - cw // 2}:{max(0, cy - ch // 2)},scale={ANCHO}:{ALTO}:flags=lanczos,fps={FPS},setsar=1[v]'
    else:
        imagen = f'[0:v]scale={ANCHO}:{ALTO},fps={FPS},setsar=1[v]'
    filtros.append(imagen)
    if etiquetas:
        filtros.append(f"{''.join(etiquetas)}amix=inputs={len(etiquetas)}:normalize=0,apad[a]")
    else:
        filtros.append('anullsrc=r=48000:cl=stereo[a]')
    subprocess.run([FFMPEG, '-v', 'error', '-y', *entradas, '-filter_complex', ';'.join(filtros),
                    '-map', '[v]', '-map', '[a]', '-t', f'{duracion:.3f}', '-c:v', 'libx264', '-preset', 'medium',
                    '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-ar', '48000', '-ac', '2',
                    str(destino)], check=True)
    return destino, {'destello_ms': round(destello_ms), 'audios': len(sonidos), 'duracion_s': round(duracion, 1),
                     'primer_sonido_s': primer_sonido_s, 'escena': linea['escena']}


def tira_primer_sonido(video: Path, detalle: dict, destino: Path) -> None:
    """Boca ampliada, fotograma a fotograma, desde 240 ms antes hasta 400 ms después del primer sonido."""
    x, y, w, h = detalle['escena']
    # Centro de la boca del doctor dentro de la escena (medido en la imagen de 1280x720 con object-fit: cover).
    cx, cy = int(x + w * 0.4993), int(y + h * 0.4755)
    # El cero es el primer sonido audible de la pista (el MP3 empieza con un silencio corto), no el inicio del audio.
    crudo = subprocess.run([FFMPEG, '-v', 'error', '-i', str(video), '-ac', '1', '-ar', '8000', '-f', 's16le', '-'],
                           capture_output=True, check=True).stdout
    muestras = np.frombuffer(crudo, dtype=np.int16).astype(float)
    por_cuadro = 8000 // FPS
    volumen = np.array([np.sqrt(np.mean(muestras[i:i + por_cuadro] ** 2)) for i in range(0, len(muestras) - por_cuadro, por_cuadro)])
    cero = int(np.argmax(volumen > volumen.max() * 0.08))
    detalle['primer_sonido_audible_s'] = round(cero / FPS, 2)
    captura = cv2.VideoCapture(str(video))
    fuente = ImageFont.truetype('arial.ttf', 16)
    tira = Image.new('RGB', (6 * 240, 3 * 204), 'white')
    for i, k in enumerate(range(-6, 11)):
        captura.set(cv2.CAP_PROP_POS_FRAMES, cero + k)
        ok, cuadro = captura.read()
        if not ok:
            break
        recorte = Image.fromarray(cv2.cvtColor(cuadro[cy - 28:cy + 32, cx - 40:cx + 40], cv2.COLOR_BGR2RGB)).resize((240, 180), Image.LANCZOS)
        celda = Image.new('RGB', (240, 204), 'white')
        celda.paste(recorte, (0, 24))
        ImageDraw.Draw(celda).text((4, 3), f'{k * 40:+d} ms', fill='black', font=fuente)
        tira.paste(celda, ((i % 6) * 240, (i // 6) * 204))
    captura.release()
    tira.save(destino)


def rotulo(titulo: str, subtitulo: str, destino: Path, segundos: float = 3.5) -> Path:
    imagen = Image.new('RGB', (ANCHO, ALTO), (15, 23, 42))
    dibujo = ImageDraw.Draw(imagen)
    grande = ImageFont.truetype('arialbd.ttf', 64)
    chica = ImageFont.truetype('arial.ttf', 30)
    dibujo.text((ANCHO // 2, ALTO // 2 - 50), titulo, font=grande, fill='white', anchor='mm')
    y = ALTO // 2 + 30
    for linea in subtitulo.split('\n'):
        dibujo.text((ANCHO // 2, y), linea, font=chica, fill=(203, 213, 225), anchor='mm')
        y += 44
    png = destino.with_suffix('.png')
    imagen.save(png)
    subprocess.run([FFMPEG, '-v', 'error', '-y', '-loop', '1', '-i', str(png), '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo',
                    '-t', str(segundos), '-vf', f'fps={FPS},format=yuv420p,setsar=1', '-c:v', 'libx264', '-preset', 'medium',
                    '-crf', '20', '-c:a', 'aac', '-b:a', '160k', '-ar', '48000', '-ac', '2', str(destino)], check=True)
    return destino


def fotograma(video: Path, destino: Path, inicio_s: float, fin_s: float, boca_abierta: bool) -> None:
    """Guarda un fotograma entre inicio_s y fin_s; con boca_abierta, el de más zona oscura en el centro de la cara."""
    captura = cv2.VideoCapture(str(video))
    captura.set(cv2.CAP_PROP_POS_MSEC, inicio_s * 1000)
    mejor, puntaje = None, -1
    while captura.get(cv2.CAP_PROP_POS_MSEC) <= fin_s * 1000:
        ok, cuadro = captura.read()
        if not ok:
            break
        if not boca_abierta:
            mejor = cuadro
            break
        h, w = cuadro.shape[:2]
        zona = cv2.cvtColor(cuadro[int(h * 0.57):int(h * 0.70), int(w * 0.40):int(w * 0.58)], cv2.COLOR_BGR2GRAY)  # la boca
        oscuros = int((zona < 60).sum())
        if oscuros > puntaje:
            mejor, puntaje = cuadro, oscuros
    captura.release()
    cv2.imwrite(str(destino), mejor)


def main():
    antes, despues, salida = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    evidencia = Path(sys.argv[4])
    evidencia.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        partes, detalle = [], {}
        partes.append(rotulo('Antes', 'Videos de LivePortrait en bucle (TA-020)\nLa boca sigue el volumen y la cabeza cambia de tamaño', tmp / 'r1.mp4'))
        parte, detalle['antes'] = preparar(antes, tmp / 'antes.mp4')
        partes.append(parte)
        partes.append(rotulo('Después', 'Boca por sílaba sobre la imagen quieta\nBalanceo leve de la cabeza (intensidad 0,4)', tmp / 'r2.mp4'))
        parte, detalle['despues'] = preparar(despues, tmp / 'despues.mp4')
        partes.append(parte)
        partes.append(rotulo('Después, de cerca', 'La misma grabación, ampliada a la cara', tmp / 'r3.mp4', 3))
        parte, detalle['acercamiento'] = preparar(despues, tmp / 'cerca.mp4', acercar=True, maximo_s=35)
        partes.append(parte)
        inicio_antes = detalle['antes']['primer_sonido_s'] + 3
        fotograma(tmp / 'antes.mp4', evidencia / 'fotograma_antes.png', inicio_antes, inicio_antes + 1, False)
        inicio_cerca = detalle['acercamiento']['primer_sonido_s']
        fotograma(tmp / 'cerca.mp4', evidencia / 'fotograma_cerca.png', inicio_cerca, inicio_cerca + 15, True)
        tira_primer_sonido(tmp / 'despues.mp4', detalle['despues'], evidencia / 'tira_primer_sonido.png')
        lista = tmp / 'lista.txt'
        lista.write_text(''.join(f"file '{p.as_posix()}'\n" for p in partes), encoding='utf-8')
        salida.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([FFMPEG, '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(lista), '-c', 'copy',
                        '-movflags', '+faststart', str(salida)], check=True)
    detalle['duracion_total_s'] = round(sum(d['duracion_s'] for d in detalle.values()) + 3.5 + 3.5 + 3, 1)
    detalle['archivo'] = salida.name
    (evidencia / 'montaje.json').write_text(json.dumps(detalle, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(detalle, ensure_ascii=False))
    print(f'Video en {salida} ({salida.stat().st_size / 1e6:.1f} MB)')


if __name__ == '__main__':
    main()
