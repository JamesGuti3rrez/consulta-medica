"""Las pruebas no heredan servicios y credenciales del .env personal.

Se configura antes de importar los módulos de pruebas y del servidor. No cambia
el archivo .env ni el comportamiento de la aplicación fuera de pytest.
"""
import os


TEST_ENVIRONMENT = {
    "LANGSMITH_TRACING": "false", "LANGSMITH_TRACING_V2": "false",
    "LANGCHAIN_TRACING": "false", "LANGCHAIN_TRACING_V2": "false",
    "RAGAS_DO_NOT_TRACK": "true",
    "LANGSMITH_API_KEY": "", "GROQ_API_KEYS": "", "GROQ_API_KEY": "", "RAGAS_API_KEY": "",
    "SUPABASE_URL": "", "SUPABASE_PUBLISHABLE_KEY": "", "SUPABASE_SECRET_KEY": "",
    "CASE_STORE": "local", "SESSION_STORE": "memoria", "RAG_BACKEND": "local",
    "RAG_SERVICE_URL": "", "RAG_EMBEDDED": "false",
    "SYNTHETIC_CASE_DATA": "false", "HISTORIAL_ALUMNOS": "false",
}

# Las suites en vivo de TA-011, HU-006 y HU-007 (TA011_MODO=vivo) prueban contra el servidor y el Supabase
# reales a propósito: conservan las credenciales y el almacenamiento del .env; la telemetría sigue apagada.
LIVE_KEEP = {"SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_SECRET_KEY", "CASE_STORE", "SESSION_STORE",
             "RAG_BACKEND", "RAG_SERVICE_URL", "RAG_EMBEDDED", "SYNTHETIC_CASE_DATA", "HISTORIAL_ALUMNOS"}
if os.getenv("TA011_MODO") == "vivo":
    TEST_ENVIRONMENT = {key: value for key, value in TEST_ENVIRONMENT.items() if key not in LIVE_KEEP}

# python-dotenv conserva estas variables del proceso: no las repone desde .env.
# Las pruebas de servicios remotos suministran sus propios transportes y datos ficticios.
os.environ.update(TEST_ENVIRONMENT)
