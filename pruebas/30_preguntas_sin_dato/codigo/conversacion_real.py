"""Conversación real (modelo de lenguaje y datos sintéticos del .env) con las preguntas que antes salían raras.

Uso: python conversacion_real.py <servidor> <caso> [pregunta ...]. Imprime agente, intención y respuesta, y falla
si el paciente responde «No entendí bien» a una pregunta clara, si el doctor pide al estudiante describir hallazgos
o si el inicio de la molestia actual se responde con el diagnóstico de un antecedente.
"""
import sys

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3100"
CASO = sys.argv[2] if len(sys.argv) > 2 else "CIR-005"
PREGUNTAS = sys.argv[3:] or ["Realizo exploración física", "¿Desde cuándo tiene el dolor?",
                             "¿Ha tenido fiebre o vómitos?", "¿Dónde le duele exactamente?", "¿Qué medicamentos toma?"]
RARAS = ("no entendí bien", "describe los hallazgos", "describe lo que", "indícame los hallazgos")

fallos = 0
with httpx.Client(base_url=BASE, timeout=120) as cliente:
    inicio = cliente.post("/api/ai/sessions", json={"case_id": CASO}).json()
    cabeceras = {"X-Session-Token": inicio["session_token"]}
    print(f"Caso {CASO} en {BASE}\n")
    for pregunta in PREGUNTAS:
        r = cliente.post(f"/api/ai/sessions/{inicio['session_id']}/message", json={"message": pregunta},
                         headers=cabeceras).json()
        rara = any(marca in r["response"].lower() for marca in RARAS)
        # «¿Desde cuándo tiene la molestia?» no se responde con el año de un antecedente.
        sobre_molestia = any(p in pregunta.lower() for p in ("desde cuándo", "hace cuánto")) and any(
            m in pregunta.lower() for m in ("molestia", "dolor", "duele", "lesión", "fiebre"))
        rara = rara or (sobre_molestia and "diagnostic" in r["response"].lower())
        fallos += rara
        print(f"{'FALLA' if rara else 'PASA '}  {pregunta}\n       [{r['agent']} / {r['intent']} / {r['data_source']}] {r['response']}\n")
print("TODO PASA" if not fallos else f"{fallos} respuestas raras")
sys.exit(1 if fallos else 0)
