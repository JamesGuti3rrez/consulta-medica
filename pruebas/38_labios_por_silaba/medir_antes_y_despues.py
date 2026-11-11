"""Mide el problema que corrige la fase 38 y arma las figuras del informe.

Antes: los videos de LivePortrait (commit f9fc8eb, TA-020) se alternaban con la imagen quieta en cada pausa de la voz.
Dentro del video la cabeza se acerca, se aleja y gira, así que al volver a la imagen quieta «salta». Para cada
fotograma se estima la transformación de semejanza (escala, giro y desplazamiento) entre la cabeza de la imagen quieta
y la del video, con puntos ORB y RANSAC (cv2.estimateAffinePartial2D).

Después: la cabeza es una capa idéntica a la imagen quieta y la boca solo cambia su propia zona. Se comprueba al píxel.

Uso, desde la raíz del repo:  python pruebas/38_labios_por_silaba/medir_antes_y_despues.py
Salidas en pruebas/38_labios_por_silaba/resultados/00_antes_y_despues/.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
SALIDA = AQUI / 'resultados' / '00_antes_y_despues'
PROTOTIPOS = AQUI / 'prototipos'
AVATARES = RAIZ / 'frontend' / 'public' / 'assets' / 'avatars'
COMMIT_ANTES = 'f9fc8eb'
PERSONAJES = ['doctor', 'paciente-hombre', 'paciente-mujer']
NOMBRES = {'doctor': 'Doctor', 'paciente-hombre': 'Paciente hombre', 'paciente-mujer': 'Paciente mujer'}
BOCAS = ['pequena', 'A', 'E', 'O']
FUENTE = ImageFont.truetype('arial.ttf', 22)
FUENTE_CHICA = ImageFont.truetype('arial.ttf', 18)


def caja_cabeza(gris: np.ndarray) -> tuple[int, int, int, int]:
    detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    caras = detector.detectMultiScale(gris, 1.1, 5, minSize=(120, 120))
    x, y, w, h = max(caras, key=lambda c: c[2] * c[3])
    # La cara de Haar va de cejas a mentón; se amplía para incluir pelo, orejas y mentón.
    cx, cy = x + w / 2, y + h / 2
    lado = int(w * 1.6)
    return int(cx - lado / 2), int(cy - lado * 0.55), lado, lado


def medir_video(nombre: str) -> dict:
    quieta = cv2.imread(str(AVATARES / f'{nombre}-1280.webp'))
    gris_q = cv2.cvtColor(quieta, cv2.COLOR_BGR2GRAY)
    x, y, w, h = caja_cabeza(gris_q)
    mascara = np.zeros_like(gris_q)
    mascara[max(0, y):y + h, max(0, x):x + w] = 255
    orb = cv2.ORB_create(3000)
    kq, dq = orb.detectAndCompute(gris_q, mascara)
    emparejador = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

    with tempfile.TemporaryDirectory() as carpeta:
        video = Path(carpeta) / f'{nombre}.mp4'
        video.write_bytes(subprocess.run(['git', 'show', f'{COMMIT_ANTES}:frontend/public/assets/avatars/{nombre}-hablando.mp4'],
                                         cwd=RAIZ, capture_output=True, check=True).stdout)
        captura = cv2.VideoCapture(str(video))
        fps = captura.get(cv2.CAP_PROP_FPS)
        filas, fotogramas = [], []
        while True:
            ok, cuadro = captura.read()
            if not ok:
                break
            gris = cv2.cvtColor(cuadro, cv2.COLOR_BGR2GRAY)
            kv, dv = orb.detectAndCompute(gris, mascara)
            pares = sorted(emparejador.match(dq, dv), key=lambda m: m.distance)[:400]
            origen = np.float32([kq[m.queryIdx].pt for m in pares])
            destino = np.float32([kv[m.trainIdx].pt for m in pares])
            matriz, _ = cv2.estimateAffinePartial2D(origen, destino, method=cv2.RANSAC, ransacReprojThreshold=2.0)
            a, b = matriz[0, 0], matriz[1, 0]
            filas.append({'escala_pct': (np.hypot(a, b) - 1) * 100, 'giro_grados': np.degrees(np.arctan2(b, a)),
                          'dx': matriz[0, 2], 'dy': matriz[1, 2]})
            fotogramas.append(cuadro)
        captura.release()

    escalas = np.array([f['escala_pct'] for f in filas])
    giros = np.abs([f['giro_grados'] for f in filas])
    peor = int(np.argmax(escalas))
    diferencia_inicio = float(np.mean(cv2.absdiff(fotogramas[0], quieta)))
    return {
        'personaje': nombre, 'fotogramas': len(filas), 'fps': round(fps, 2),
        'escala_media_pct': round(float(escalas.mean()), 2), 'escala_max_pct': round(float(escalas.max()), 2),
        'giro_max_grados': round(float(giros.max()), 2), 'tamano_cabeza_px': w,
        'salto_max_px': round(float(escalas.max()) / 100 * w, 1),
        'diferencia_primer_fotograma': round(diferencia_inicio, 2),
        '_peor': fotogramas[peor], '_peor_indice': peor, '_quieta': quieta, '_caja': (x, y, w, h),
    }


def figura_salto(mediciones: list[dict]) -> Path:
    """Imagen quieta y fotograma con la cabeza más grande, con las mismas guías horizontales."""
    paneles = []
    for m in mediciones:
        x, y, w, h = m['_caja']
        margen = int(w * 0.12)
        arriba = max(0, y - margen)  # sin salirse del borde superior de la imagen
        recorte = (x - margen, arriba, x + w + margen, arriba + h + 2 * margen)
        fila = []
        for titulo, imagen in (('Imagen quieta', m['_quieta']), (f"Video, fotograma {m['_peor_indice']} (+{m['escala_max_pct']:.1f} %)", m['_peor'])):
            panel = Image.fromarray(cv2.cvtColor(imagen, cv2.COLOR_BGR2RGB)).crop(recorte).resize((300, 300))
            dibujo = ImageDraw.Draw(panel)
            for guia in (0.16, 0.86):  # coronilla y mentón aproximados de la imagen quieta
                dibujo.line([(0, 300 * guia), (300, 300 * guia)], fill=(255, 210, 0), width=2)
            lienzo = Image.new('RGB', (300, 336), 'white')
            lienzo.paste(panel, (0, 36))
            ImageDraw.Draw(lienzo).text((4, 6), titulo, fill=(30, 41, 59), font=FUENTE_CHICA)
            fila.append(lienzo)
        paneles.append((m['personaje'], fila))
    # Una fila por personaje: imagen quieta y fotograma del video lado a lado.
    figura = Image.new('RGB', (180 + 2 * 310, 3 * 346 + 10), 'white')
    for i, (nombre, (izq, der)) in enumerate(paneles):
        figura.paste(izq, (180, i * 346 + 5))
        figura.paste(der, (180 + 310, i * 346 + 5))
        ImageDraw.Draw(figura).text((10, i * 346 + 170), NOMBRES[nombre], fill=(15, 23, 42), font=FUENTE)
    ruta = SALIDA / 'figura_salto_de_la_cabeza.png'
    figura.save(ruta)
    return ruta


def capa(nombre: str, sufijo: str) -> Image.Image:
    return Image.open(AVATARES / f'{nombre}-{sufijo}.webp').convert('RGBA')


def escala_entre(quieta: np.ndarray, otra: np.ndarray) -> tuple[float, float]:
    """Escala (%) y giro (grados) de la cabeza de «otra» frente a la imagen quieta, con el método de medir_video."""
    gris_q, gris_o = (cv2.cvtColor(i, cv2.COLOR_BGR2GRAY) for i in (quieta, otra))
    x, y, w, h = caja_cabeza(gris_q)
    mascara = np.zeros_like(gris_q)
    mascara[max(0, y):y + h, max(0, x):x + w] = 255
    orb = cv2.ORB_create(3000)
    kq, dq = orb.detectAndCompute(gris_q, mascara)
    ko, do = orb.detectAndCompute(gris_o, mascara)
    pares = sorted(cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(dq, do), key=lambda m: m.distance)[:400]
    matriz, _ = cv2.estimateAffinePartial2D(np.float32([kq[m.queryIdx].pt for m in pares]),
                                            np.float32([ko[m.trainIdx].pt for m in pares]), method=cv2.RANSAC,
                                            ransacReprojThreshold=2.0)
    a, b = matriz[0, 0], matriz[1, 0]
    return (np.hypot(a, b) - 1) * 100, np.degrees(np.arctan2(b, a))


def comprobar_despues() -> list[dict]:
    """La capa de la cabeza tiene la escala de la imagen quieta y cada boca solo toca su propia zona."""
    resultados = []
    for nombre in PERSONAJES:
        quieta = Image.open(AVATARES / f'{nombre}-1280.webp').convert('RGBA')
        base = np.asarray(quieta, dtype=np.int16)[..., :3]
        capa_cabeza = capa(nombre, 'cabeza')
        con_cabeza = np.asarray(Image.alpha_composite(quieta, capa_cabeza), dtype=np.int16)[..., :3]
        # Diferencia dentro de la capa (alfa > 0): la compresión WebP cambia algunos niveles en los bordes.
        dentro = np.asarray(capa_cabeza)[..., 3] > 0
        diferencia = np.abs(con_cabeza - base).max(axis=2)[dentro]
        escala, giro = escala_entre(cv2.cvtColor(base.astype(np.uint8), cv2.COLOR_RGB2BGR),
                                    cv2.cvtColor(con_cabeza.astype(np.uint8), cv2.COLOR_RGB2BGR))
        fila = {'personaje': nombre, 'cabeza_escala_pct': round(float(escala), 3), 'cabeza_giro_grados': round(float(giro), 3),
                'cabeza_diferencia_media': round(float(diferencia.mean()), 2),
                'cabeza_diferencia_p99': int(np.percentile(diferencia, 99)), 'cabeza_diferencia_max': int(diferencia.max())}
        for boca in BOCAS:
            capa_boca = capa(nombre, f'boca-{boca}')
            alfa = np.asarray(capa_boca)[..., 3]
            filas_y, cols_x = np.nonzero(alfa)
            compuesta = np.asarray(Image.alpha_composite(quieta, capa_boca), dtype=np.int16)[..., :3]
            fuera = np.ones(alfa.shape, bool)
            fuera[filas_y.min():filas_y.max() + 1, cols_x.min():cols_x.max() + 1] = False
            fila[f'boca_{boca}'] = {'zona_px': [int(cols_x.max() - cols_x.min() + 1), int(filas_y.max() - filas_y.min() + 1)],
                                    'cambio_fuera_de_la_zona': int(np.abs(compuesta - base)[fuera].max())}
        resultados.append(fila)
    return resultados


def recorte_boca(nombre: str, imagen: Image.Image) -> Image.Image:
    meta = json.loads((PROTOTIPOS / f'{nombre}-boca.json').read_text(encoding='utf-8'))
    cx, cy = meta['x'] + meta['w'] / 2, meta['y'] + meta['h'] / 2
    return imagen.crop((int(cx - 110), int(cy - 80), int(cx + 110), int(cy + 80))).resize((220, 160))


def figura_versiones(nombre: str) -> Path:
    """La boca «A» y la «E» en cada versión del prototipo y en la versión final, sobre la misma imagen quieta."""
    quieta = Image.open(PROTOTIPOS / f'{nombre}-quieta.jpg').convert('RGBA')
    meta_v12 = json.loads((PROTOTIPOS / f'{nombre}-boca.json').read_text(encoding='utf-8'))
    def pegar(parche: str, x: int, y: int, w: int, h: int) -> Image.Image:
        imagen = quieta.copy()
        imagen.alpha_composite(Image.open(PROTOTIPOS / parche).convert('RGBA').resize((w, h)), (x, y))
        return imagen
    caja = (meta_v12['x'], meta_v12['y'], meta_v12['w'], meta_v12['h'])
    filas = [
        (['v1: del video,', 'una forma por letra'], [pegar(f'{nombre}-boca-abierta.png', *caja), pegar(f'{nombre}-boca-media.png', *caja)]),
        (['v2: del video,', 'una forma por sílaba'], [pegar(f'{nombre}-v2-A.png', *caja), pegar(f'{nombre}-v2-E.png', *caja)]),
        (['Final: generadas desde', 'la imagen quieta'], [Image.alpha_composite(Image.open(AVATARES / f'{nombre}-1280.webp').convert('RGBA'), capa(nombre, f'boca-{b}')) for b in ('A', 'E')]),
    ]
    figura = Image.new('RGB', (40 + 3 * 250, 66 + 2 * 170), 'white')
    dibujo = ImageDraw.Draw(figura)
    for c, (titulo, imagenes) in enumerate(filas):
        for linea, texto in enumerate(titulo):
            dibujo.text((20 + c * 250, 6 + linea * 24), texto, fill=(15, 23, 42), font=FUENTE_CHICA)
        for r, imagen in enumerate(imagenes):
            figura.paste(recorte_boca(nombre, imagen).convert('RGB'), (20 + c * 250, 62 + r * 170))
    ruta = SALIDA / f'figura_versiones_de_la_boca_{nombre}.png'
    figura.save(ruta)
    return ruta


def figura_bocas_finales() -> Path:
    """Reposo y las cuatro bocas de cada personaje, tal como se ven en la escena."""
    columnas = ['reposo'] + BOCAS
    figura = Image.new('RGB', (170 + 5 * 230, 50 + 3 * 170), 'white')
    dibujo = ImageDraw.Draw(figura)
    for c, titulo in enumerate(['Reposo (imagen quieta)', 'Pequeña', 'A', 'E / I', 'O / U']):
        dibujo.text((170 + c * 230, 14), titulo, fill=(15, 23, 42), font=FUENTE_CHICA)
    for r, nombre in enumerate(PERSONAJES):
        dibujo.text((10, 50 + r * 170 + 70), NOMBRES[nombre], fill=(15, 23, 42), font=FUENTE_CHICA)
        quieta = Image.open(AVATARES / f'{nombre}-1280.webp').convert('RGBA')
        for c, boca in enumerate(columnas):
            imagen = quieta if boca == 'reposo' else Image.alpha_composite(quieta, capa(nombre, f'boca-{boca}'))
            figura.paste(recorte_boca(nombre, imagen).convert('RGB'), (170 + c * 230, 50 + r * 170))
    ruta = SALIDA / 'figura_bocas_finales.png'
    figura.save(ruta)
    return ruta


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    mediciones = [medir_video(nombre) for nombre in PERSONAJES]
    figuras = [figura_salto(mediciones), figura_bocas_finales(), figura_versiones('paciente-hombre'), figura_versiones('doctor')]
    despues = comprobar_despues()
    limpio = [{k: v for k, v in m.items() if not k.startswith('_')} for m in mediciones]
    (SALIDA / 'medicion.json').write_text(json.dumps({'antes_commit': COMMIT_ANTES, 'antes': limpio, 'despues': despues},
                                                     ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'ANTES (videos de LivePortrait, commit {COMMIT_ANTES}): tamaño de la cabeza en el video frente a la imagen quieta')
    for m in limpio:
        print(f"  {NOMBRES[m['personaje']]:16} {m['fotogramas']} fotogramas: media {m['escala_media_pct']:+.2f} %, máximo "
              f"{m['escala_max_pct']:+.2f} % (unos {m['salto_max_px']} px en una cabeza de {m['tamano_cabeza_px']} px), giro hasta {m['giro_max_grados']}°")
    print('\nDESPUÉS (capas de la fase 38): diferencia con la imagen quieta, en niveles de color de 0 a 255')
    for d in despues:
        bocas = ', '.join(f"{b} {d[f'boca_{b}']['cambio_fuera_de_la_zona']}" for b in BOCAS)
        print(f"  {NOMBRES[d['personaje']]:16} capa de cabeza: escala {d['cabeza_escala_pct']:+.2f} %, giro {d['cabeza_giro_grados']:+.2f}°; "
              f"diferencia de color media {d['cabeza_diferencia_media']} (percentil 99: {d['cabeza_diferencia_p99']}, "
              f"máximo {d['cabeza_diferencia_max']}, por la compresión WebP)")
        print(f"  {'':16} fuera de la zona de la boca: {bocas}")
    ok = all(abs(d['cabeza_escala_pct']) < 0.1 and abs(d['cabeza_giro_grados']) < 0.1
             and all(d[f'boca_{b}']['cambio_fuera_de_la_zona'] == 0 for b in BOCAS) for d in despues)
    print(f"\n{'PASA ' if ok else 'FALLA'}  la capa de la cabeza tiene la escala y el giro de la imagen quieta (menos de 0,1) "
          f"y cada boca solo cambia su zona")
    print('Figuras: ' + ', '.join(f.name for f in figuras))
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main()
