# knowledge/

Fuentes de conocimiento clínico general (protocolos, guías, buenas prácticas) que el RAG podría usar, según la sugerencia del docente.

**Pendiente de decisión.** Antes de usarla hay que definir:

- qué fuentes, con qué licencia y quién las revisa;
- si alimentan a los agentes en la conversación o solo a la evaluación;
- cómo se evita que un protocolo delate el diagnóstico del caso activo.

No agregar contenido hasta que exista esa decisión en `docs/decisions/`.

## Registro para la etapa Indexar

Cuando exista una decisión aprobada, los documentos Markdown locales pueden registrarse en
`registry.json` sin descargarlos desde el indexador:

```json
{
  "sources": [
    {
      "id": "identificador-estable",
      "path": "approved/documento.md",
      "license": "licencia verificada",
      "reviewed_by": "revisor responsable",
      "scope": "conversation",
      "approved": true
    }
  ]
}
```

`scope` solo admite `conversation` o `evaluation`. El indexador lee únicamente entradas con
`approved: true`, restringe `path` a un Markdown directo dentro de `approved/` y falla si falta
licencia, revisor, alcance o archivo. La ausencia del registro produce cero documentos de
conocimiento; este repositorio no incorpora todavía registro ni fuentes aprobadas.
