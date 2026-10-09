# ADR-001 — Topología SMA en estrella

**Decisión:** usar un orquestador central conectado a agentes especializados.

**Motivo:** la consulta es dinámica y no debe forzarse a un pipeline lineal. La estrella reduce comunicación lateral, facilita aislamiento, trazabilidad y control del contexto.

**Alternativas consideradas:** cadena, malla e híbrida.
