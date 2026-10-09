# Motor de evaluación

Este módulo es determinístico y es uno de los dos únicos puntos autorizados a leer `protected`.
La migración de la evaluación clínica del prototipo legado se realizará aquí sin exponer `protected`
a `orchestration/`, `rag/`, `ai/` ni al frontend.
