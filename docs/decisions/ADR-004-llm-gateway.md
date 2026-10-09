# ADR-004 — LLM Gateway

Los agentes no conocen API keys ni proveedores. El gateway distribuye solicitudes entre credenciales/proveedores autorizados y aplica fallback ante errores retryable (429, timeout, 5xx).
