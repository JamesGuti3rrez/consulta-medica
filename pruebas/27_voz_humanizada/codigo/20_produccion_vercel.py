"""La voz neuronal en producción (Vercel, TTS_PROVIDER=edge) después de subir la rama James a main.

Comprueba que el servidor publicado sigue sirviendo los casos, que /api/voz/estado dice activa, que cada
personaje recibe un mp3 real (código 200, audio/mpeg, cabecera MPEG y más de 5 KB) y que el navegador recibe
el simulacion.js nuevo (el punto seguido de más texto se lee como coma). Un personaje no permitido da 422.
"""

from __future__ import annotations

import sys
import time

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "https://consulta-medica-three.vercel.app"
FRASES = [
    ("doctor", "masculino", "Martín Rojas, de 28 años. Motivo de consulta: dolor abdominal intenso."),
    ("doctor", "femenino", "Lucía Paredes, de 34 años. Motivo de consulta: fiebre y tos."),
    ("patient", "masculino", "Doctor, me duele mucho aquí abajo, a la derecha, desde anoche."),
    ("patient", "femenino", "Sí, doctora, tengo náuseas y no he podido comer nada desde ayer."),
    ("laboratorio", None, "Hemoglobina: 9 coma 8 gramos por decilitro. Leucocitos: 14 500 por milímetro cúbico."),
    ("radiologia", None, "Ecografía abdominal: apéndice no compresible de 9 milímetros."),
    ("especialista", None, "Sugiero valoración quirúrgica urgente y control en seis horas."),
]

fallos = 0


def comprobar(nombre: str, ok: bool, detalle: str) -> None:
    global fallos
    fallos += 0 if ok else 1
    print(f"  {'PASA' if ok else 'FALLA'}  {nombre}: {detalle}")


with httpx.Client(base_url=BASE, timeout=60) as cliente:
    print(f"Servidor: {BASE}\n")
    estado = cliente.get("/api/status").json()
    comprobar("casos publicados", estado.get("availableCases", 0) > 0,
              f"{estado.get('availableCases')} casos, caseStore={estado.get('caseStore')}")
    voz = cliente.get("/api/voz/estado").json()
    comprobar("voz activa", voz == {"activa": True}, str(voz))

    print("\nAudio por personaje:")
    for personaje, sexo, texto in FRASES:
        params = {"texto": texto, "personaje": personaje} | ({"sexo": sexo} if sexo else {})
        inicio = time.perf_counter()
        r = cliente.get("/api/voz", params=params)
        segundos = time.perf_counter() - inicio
        mp3 = r.content[:2] in (b"\xff\xf3", b"\xff\xfb", b"\xff\xf2") or r.content[:3] == b"ID3"
        ok = r.status_code == 200 and r.headers.get("content-type") == "audio/mpeg" and mp3 and len(r.content) > 5000
        comprobar(f"{personaje} {sexo or ''}".strip(), ok,
                  f"HTTP {r.status_code}, {len(r.content)} bytes, {segundos:.2f} s")

    r = cliente.get("/api/voz", params={"texto": "hola", "personaje": "intruso"})
    comprobar("personaje no permitido", r.status_code == 422, f"HTTP {r.status_code}")

    js = cliente.get("/js/simulacion.js").text
    comprobar("simulacion.js nuevo", r".replace(/\.(?=\s+\S)/g, ',')" in js,
              "el punto seguido de más texto se lee como coma")

print(f"\n{'TODO PASA' if not fallos else f'{fallos} FALLAN'}")
sys.exit(1 if fallos else 0)
