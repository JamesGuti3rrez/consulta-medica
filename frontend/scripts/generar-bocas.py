"""Capas de la boca y de la cabeza de los avatares de la escena (sincronía de labios por sílaba).

Las bocas se generan deformando los labios de la propia imagen quieta, así siempre quedan derechas y
alineadas con ella:
1. Ubica la línea entre los labios y sus comisuras (color de labios + línea oscura).
2. Para cada forma deforma la zona de la boca: el labio superior sube un poco, el inferior y el mentón
   bajan; para la O se estrecha hacia el centro y para la E se estira.
3. Dibuja el interior de la boca (sombra, lengua y un borde de dientes superiores suave).

Cada capa es un WebP transparente del mismo tamaño que la imagen quieta (1280x720): en la página se
apila con el mismo object-fit y coincide al píxel con cualquier ancho de pantalla.
- <personaje>-boca-<forma>.webp: la boca abierta en esa forma (pequena, A, E, O). Cerrada = imagen quieta.
- <personaje>-cabeza.webp: la cabeza y el cuello con bordes suaves, para el leve balanceo al hablar.
  Imprime el pivote (el cuello) que usa simulacion.js en AVATAR_PIVOTS.

Se ejecuta solo al cambiar una imagen quieta (después de npm run build:images); sus resultados se guardan
en el repositorio. Necesita Python con opencv-python, numpy y Pillow:
  python frontend/scripts/generar-bocas.py
"""
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

AVATARS = Path(__file__).resolve().parents[1] / "public" / "assets" / "avatars"
casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

# gap: apertura en el centro (fracción del ancho de la boca); sx: escala horizontal de los labios;
# k: perfil de la abertura (menor = más redonda); dientes: alto del borde de dientes (fracción de la abertura).
# ow: ancho de la abertura respecto de la boca (O es angosta).
SHAPES = {
    "pequena": dict(gap=0.07, sx=1.00, k=1.0, ow=0.62, dientes=0.0, lengua=0.0),
    "A":       dict(gap=0.24, sx=0.97, k=0.8, ow=0.78, dientes=0.18, lengua=0.30),
    "E":       dict(gap=0.12, sx=1.05, k=1.0, ow=0.82, dientes=0.40, lengua=0.0),
    "O":       dict(gap=0.22, sx=0.84, k=0.55, ow=0.46, dientes=0.0, lengua=0.25),
}


def find_mouth(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    fx, fy, fw, fh = max(casc.detectMultiScale(gray, 1.1, 5, minSize=(80, 80)), key=lambda r: r[2] * r[3])
    x0, x1, y0, y1 = int(fx + .2 * fw), int(fx + .8 * fw), int(fy + .62 * fh), int(fy + .95 * fh)
    roi = img[y0:y1, x0:x1]
    lab = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB).astype(np.float32)
    a = cv2.GaussianBlur(lab[..., 1], (0, 0), 1.5)
    mask = cv2.morphologyEx((a > np.percentile(a, 85)).astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, cc, stats, cent = cv2.connectedComponentsWithStats(mask)
    best = max(range(1, n), key=lambda i: stats[i, cv2.CC_STAT_AREA] - abs(cent[i][0] - roi.shape[1] / 2) * 3)
    lips = cv2.morphologyEx((cc == best).astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 9), np.uint8))
    ys, xs = np.nonzero(lips)
    L = cv2.GaussianBlur(lab[..., 0], (0, 0), 1.0)
    xc = int(np.median(xs))
    col = np.nonzero(lips[:, xc])[0]
    sy = col.min() + int(np.argmin(L[col.min():col.max() + 1, xc]))
    seam = {xc: sy}
    # Seguir la línea oscura hacia cada comisura mientras sea más oscura que la piel de arriba y abajo.
    for step in (-1, 1):
        y, x = sy, xc
        while 0 < x + step < roi.shape[1] - 1:
            x += step
            cand = range(max(1, y - 2), min(roi.shape[0] - 1, y + 3))
            y = min(cand, key=lambda yy: L[yy, x])
            skin = (L[max(0, y - 7), x] + L[min(roi.shape[0] - 1, y + 7), x]) / 2
            if L[y, x] > skin - 6 and abs(x - xc) > (xs.max() - xs.min()) / 2:
                break
            seam[x] = y
    margin = 0.08 * (xs.max() - xs.min())
    lim_l, lim_r = xs.min() - margin, xs.max() + margin
    seam = {x: y for x, y in seam.items() if lim_l <= x <= lim_r}
    xl, xr = min(seam), max(seam)
    xs_seam = np.arange(xl, xr + 1)
    ys_seam = np.array([seam[x] for x in xs_seam], float)
    ys_seam = cv2.GaussianBlur(ys_seam.reshape(1, -1), (0, 0), 2).ravel()
    return dict(xl=xl + x0, xr=xr + x0, xs=xs_seam + x0, ys=ys_seam + y0,
                top=ys.min() + y0, bottom=ys.max() + y0, xc=xc + x0)


def render(img, m, p):
    H, W = img.shape[:2]
    Wm = m["xr"] - m["xl"]
    half = Wm / 2
    xc = (m["xl"] + m["xr"]) / 2
    # Zona de trabajo
    bx0, bx1 = int(m["xl"] - 0.7 * Wm), int(m["xr"] + 0.7 * Wm)
    by0, by1 = int(m["top"] - 0.6 * Wm), int(m["bottom"] + 1.1 * Wm)
    X, Y = np.meshgrid(np.arange(bx0, bx1, dtype=np.float32), np.arange(by0, by1, dtype=np.float32))
    seam_at = np.interp(X[0], m["xs"], m["ys"])               # línea media por columna (constante fuera)
    S = np.broadcast_to(seam_at, X.shape)
    upper_th = max(4.0, float(np.median(m["ys"]) - m["top"]))  # grosor labio superior
    lower_th = max(4.0, float(m["bottom"] - np.median(m["ys"])))

    # 1) Escala horizontal (O se cierra hacia el centro, E se estira), solo cerca de la boca.
    wy = np.exp(-((Y - S) / (1.3 * max(upper_th, lower_th))) ** 2)
    wxr = np.clip(1.6 - np.abs(X - xc) / half, 0, 1)
    wx = wy * (wxr * wxr * (3 - 2 * wxr))
    srcX = X + (xc + (X - xc) / p["sx"] - X) * wx

    # 2) Abertura vertical por columna (en coordenadas ya escaladas).
    u = np.clip((srcX[0] - xc) / (half * p["ow"]), -1, 1)
    prof = np.clip(1 - u ** 2, 0, 1) ** p["k"]
    g = (p["gap"] * Wm * prof)[None, :]
    up, dn = 0.3 * g, 0.7 * g
    te, be = S - up, S + dn                                   # bordes de la abertura en la imagen de salida
    Ru, Rd = upper_th * 1.8, lower_th * 1.6 + 0.6 * Wm        # hasta dónde llega el movimiento (nariz / mentón)
    srcY = Y.copy()
    above, below = Y <= te, Y >= be
    w_up = np.clip(1 - (te - Y) / Ru, 0, 1)
    w_dn = np.clip(1 - (Y - be) / Rd, 0, 1)
    srcY[above] = (Y + up * w_up)[above]
    srcY[below] = (Y - dn * w_dn)[below]
    out = cv2.remap(img, srcX.astype(np.float32), srcY.astype(np.float32), cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)

    # 3) Interior de la boca con bordes suaves.
    inside = np.clip(np.minimum(Y - te, be - Y) / 1.4 + 0.3, 0, 1) * np.clip(g - 0.4, 0, 1)
    depth = np.clip((Y - te) / np.maximum(be - te, 1), 0, 1)
    shade = np.array([22, 24, 46], np.float32)                 # BGR: sombra marrón rojiza oscura
    shade = shade * (0.75 + 0.25 * depth)[..., None]            # más oscura arriba, bajo el labio superior
    tongue = np.array([72, 78, 140], np.float32)
    tw = (np.clip((depth - (1 - p["lengua"])) / max(p["lengua"], 1e-3), 0, 1) * (p["lengua"] > 0)) ** 1.5
    interior = shade + (tongue - shade) * tw[..., None]
    if p["dientes"] > 0:
        teeth_h = p["dientes"] * (be - te)
        tmask = np.clip(te + teeth_h - Y + 0.5, 0, 1) * np.clip(1 - np.abs((srcX - xc) / (half * 0.7)) ** 4, 0, 1)
        teeth = np.array([168, 182, 196], np.float32) * (0.70 + 0.25 * np.clip((Y - te) / np.maximum(teeth_h, 1), 0, 1))[..., None]
        tmask = cv2.GaussianBlur(tmask.astype(np.float32), (0, 0), 0.8) * 0.85
        interior = interior * (1 - tmask[..., None]) + teeth * tmask[..., None]
    out = out.astype(np.float32)
    out = out * (1 - inside[..., None]) + interior * inside[..., None]
    # Sombra suave en el borde interno de los labios para dar profundidad.
    edge = np.exp(-((Y - te) / 1.6) ** 2) + np.exp(-((Y - be) / 1.6) ** 2)
    out *= (1 - 0.18 * np.clip(edge, 0, 1) * (g > 0.6))[..., None]
    out = np.clip(out, 0, 255).astype(np.uint8)

    # 4) Alfa: opaco en el centro y suave hacia el borde de la zona (ahí la imagen no cambió).
    alpha = np.zeros(X.shape, np.float32)
    cv2.ellipse(alpha, (int(xc - bx0), int(np.median(m["ys"]) - by0 + 0.25 * Wm)),
                (int(0.62 * (bx1 - bx0)) // 2 * 2 // 2, int(0.9 * (by1 - by0)) // 2), 0, 0, 360, 1.0, -1)
    alpha = cv2.GaussianBlur(alpha, (0, 0), 0.08 * Wm)
    return out, alpha, (bx0, by0)


def head_layer(img):
    """Cabeza y cuello opacos con un borde que se desvanece: al inclinarse no se nota el corte."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    fx, fy, fw, fh = max(casc.detectMultiScale(gray, 1.1, 5, minSize=(80, 80)), key=lambda r: r[2] * r[3])
    cx, cy = fx + fw / 2, fy + fh / 2 + 0.15 * fh
    rx, ry = 0.95 * fw, 1.15 * fh
    H, W = img.shape[:2]
    X, Y = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    r = np.sqrt(((X - cx) / rx) ** 2 + ((Y - cy) / ry) ** 2)
    alpha = np.clip((1 - r) / (1 - 0.62), 0, 1)
    pivot = ((fx + fw / 2) / W * 100, (fy + fh / 2 + 1.05 * fh) / H * 100)
    return alpha, pivot


def save_layer(path, bgr, alpha):
    rgba = np.dstack([cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB), (np.clip(alpha, 0, 1) * 255).round().astype(np.uint8)])
    rgba[rgba[..., 3] == 0, :3] = 0
    Image.fromarray(rgba).save(path, "WEBP", quality=90, method=6)
    print(f"  {path.name}  {path.stat().st_size / 1024:.0f} KB")


for name in ["doctor", "paciente-hombre", "paciente-mujer"]:
    img = cv2.imread(str(AVATARS / f"{name}-1280.webp"))
    m = find_mouth(img)
    print(f"{name}: comisuras {m['xl']}..{m['xr']}, linea media y={np.median(m['ys']):.0f}")
    for label, p in SHAPES.items():
        patch, alpha, (bx, by) = render(img, m, p)
        full = np.zeros_like(img)
        full_alpha = np.zeros(img.shape[:2], np.float32)
        h, w = patch.shape[:2]
        full[by:by + h, bx:bx + w] = patch
        full_alpha[by:by + h, bx:bx + w] = alpha
        save_layer(AVATARS / f"{name}-boca-{label}.webp", full, full_alpha)
    alpha, pivot = head_layer(img)
    save_layer(AVATARS / f"{name}-cabeza.webp", img, alpha)
    print(f"  pivote del balanceo: {pivot[0]:.1f}% {pivot[1]:.1f}%")
