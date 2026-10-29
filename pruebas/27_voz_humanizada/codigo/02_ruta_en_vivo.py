"""POST /api/voz contra el servidor local en marcha (TTS_PROVIDER=edge), con edge-tts real.

Pide una frase por personaje, mide cuánto tarda cada audio y guarda los .mp3 en resultados/.
Comprueba además que un personaje no permitido se rechace con 422.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3000"
SALIDA = Path(__file__).resolve().parent.parent / "resultados"
FRASES = [
    ("doctor", "masculino", "Martín Rojas, de 28 años, sexo masculino. Motivo de consulta: dolor abdominal intenso."),
    ("patient", "masculino", "Doctor, me duele mucho aquí abajo, a la derecha, desde anoche."),
    ("patient", "femenino", "Sí, doctora, tengo náuseas y no he podido comer nada desde ayer."),
    ("laboratorio", None, "Hemoglobina: 9 coma 8 gramos por decilitro. Leucocitos: 14 500 por milímetro cúbico."),
    ("radiologia", None, "Ecografía abdominal: apéndice no compresible de 9 milímetros con líquido periapendicular."),
    ("especialista", None, "Sugiero valoración quirúrgica urgente y control de la hemoglobina en seis horas."),
]


def main() -> int:
    SALIDA.mkdir(parents=True, exist_ok=True)
    fallos = 0
    with httpx.Client(base_url=BASE, timeout=30) as client:
        for indice, (personaje, sexo, texto) in enumerate(FRASES, start=1):
            inicio = time.perf_counter()
            r = client.post("/api/voz", json={"texto": texto, "personaje": personaje, "sexo": sexo})
            segundos = time.perf_counter() - inicio
            ok = r.status_code == 200 and r.headers.get("content-type") == "audio/mpeg" and len(r.content) > 1000
            fallos += not ok
            nombre = f"02_{indice}_{personaje}_{sexo or 'na'}.mp3"
            if ok:
                (SALIDA / nombre).write_bytes(r.content)
            print(f"[{'OK' if ok else 'FALLA'}] {personaje:<12} {str(sexo):<9} HTTP {r.status_code}  "
                  f"{len(r.content):>6} bytes  {segundos:.2f} s  {nombre if ok else r.text[:80]}")

        r = client.post("/api/voz", json={"texto": "Hola", "personaje": "student"})
        ok = r.status_code == 422
        fallos += not ok
        print(f"[{'OK' if ok else 'FALLA'}] personaje no permitido (student) -> HTTP {r.status_code} (esperado 422)")

    print(f"\nResultado: {'todo correcto' if not fallos else f'{fallos} falla(s)'}")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
