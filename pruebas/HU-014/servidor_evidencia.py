"""API y frontend reales contra PostgreSQL de pruebas; Auth y LLM controlados."""
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
for key,value in {
 'SUPABASE_URL':'http://127.0.0.1:3039','SUPABASE_PUBLISHABLE_KEY':'sb_publishable_hu014_fixture',
 'SUPABASE_SECRET_KEY':'sb_secret_hu014_fixture','CASE_STORE':'local','SESSION_STORE':'supabase',
 'RAG_BACKEND':'local','RAG_EMBEDDED':'false','RAG_SERVICE_URL':'','GROQ_API_KEYS':'',
 'SYNTHETIC_CASE_DATA':'false','SYNTHETIC_EXAM_DATA':'false','HISTORIAL_ALUMNOS':'false',
 'LANGSMITH_TRACING':'false','LANGCHAIN_TRACING_V2':'false',
 # Voz del navegador simulada en las pruebas: la voz neuronal (TA-019) queda apagada aunque el .env la active.
 'TTS_PROVIDER':'',
 'AI_TRACE_PATH':'pruebas/HU-014/auditoria_fixture.jsonl',
}.items():os.environ[key]=value

import uvicorn
from server.main import app
if __name__=='__main__':
 print('HU-014: API real con migración PostgreSQL real local. Identidades y LLM de fixture.',flush=True)
 uvicorn.run(app,host='127.0.0.1',port=3037)
