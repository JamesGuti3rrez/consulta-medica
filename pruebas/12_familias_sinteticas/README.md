# Fase 12 · Familias de casos sintéticos: piloto de dolor torácico (2026-10-11)

## Objetivo

Comprobar que todo el sistema funciona con casos diseñados para eso: tres pacientes llegan con el mismo
motivo de consulta y lo que separa sus diagnósticos solo aparece si el estudiante pregunta, examina o
pide exámenes. Con cada respuesta, las hipótesis se van descartando. Este piloto cubre la familia de
dolor torácico (Emergencias); después se harán las otras cuatro especialidades con el mismo método.

El diseño completo (tabla de diferencias, qué descarta cada hipótesis, trampas y fuentes clínicas) está
en [data/cases/familias/README.md](../../data/cases/familias/README.md).

| Caso | Paciente | Diagnóstico |
| --- | --- | --- |
| EME-101 | Carlos Mendoza, 58 años | Infarto agudo de miocardio con elevación del ST |
| EME-102 | Luis Ramírez, 56 años | Tromboembolia pulmonar aguda |
| EME-103 | Víctor Chávez, 61 años | Disección aórtica aguda tipo A |

## Cambios

| Cambio | Archivos | Commit |
| --- | --- | --- |
| Esquema 1.1.0: fuente `sintetico` y método `generado_ia` | `schemas/caso.schema.json`, `rules.py` | `d0b6fa2` |
| Reglas R15 a R18 para las familias | `backend/server/cases/rules.py` | `40fd12f` |
| Vocabulario de electrocardiograma, troponina, dímero D y angiotomografía | `policy.py`, `router.py` | `d13dd80` |
| Diseño de la familia y los 3 casos | `backend/case_preparation/familias/dolor_toracico.py`, `data/cases/curated/EME-10[1-3].json`, `data/cases/familias/README.md` | `1a4c63f` |
| Pruebas de la familia y del catálogo con 13 casos | `backend/tests/` | `775643d` |
| Verificación de casos con MedQA y sintéticos por separado | `pruebas/03_validacion/verificar_casos.py` | `1be0bba` |
| Resultados de laboratorio con su valor de referencia | generador y casos | `f521f89` |
| Medicación de EME-103 redactada como la diría el paciente | generador y EME-103 | ver `git log` |
| Instrucción al paciente: contar completo el dato que responde | `prompts/paciente.md` | ver `git log` |

## Batería con el modelo real

[01_bateria_dolor_toracico/bateria_familia.py](01_bateria_dolor_toracico/bateria_familia.py) aplica el
mismo guion de 14 pedidos a los tres casos (características del dolor, inicio, síntomas, antecedentes,
medicación, alergias, hábitos, familia, exploración, electrocardiograma, troponina, dímero D,
radiografía y angiotomografía) con Groq (`openai/gpt-oss-20b`) y la misma configuración que el sitio
publicado. En cada turno comprueba el agente y el dato, las fugas del diagnóstico, los síntomas
inventados y la fidelidad (las cifras del dato deben aparecer en la respuesta), y sigue el estado de
cada hipótesis: «menos probable» cuando aparece un dato en contra y «descartada» cuando aparecen todos.

| Comprobación | Resultado |
| --- | --- |
| Agente y dato correctos | 42 de 42 |
| Respuestas que nombran el diagnóstico o un diferencial | 0 |
| Respuestas con síntomas inventados | 0 |
| Respuestas que omiten cifras del dato | 0 |
| Respuestas bloqueadas por el filtro de salida | 0 |
| Pedidos con respuesta distinta en los 3 casos | 13 de 14 (el que coincide es «¿Tiene alergias?»: EME-101 y EME-103 no tienen alergias) |
| Casos en que al final solo queda el diagnóstico correcto | 3 de 3 |

Cómo caen las hipótesis:

| Caso | Pedido | Cambio |
| --- | --- | --- |
| EME-101 | Características del dolor | Disección y pericarditis: menos probables |
| EME-101 | Hábitos y viajes | Tromboembolia: menos probable |
| EME-101 | Electrocardiograma | Pericarditis: descartada |
| EME-101 | Angiotomografía | Tromboembolia y disección: descartadas |
| EME-102 | Características del dolor | Infarto, disección y pericarditis: menos probables |
| EME-102 | Electrocardiograma | Infarto y pericarditis: descartados |
| EME-102 | Angiotomografía | Disección: descartada |
| EME-103 | Características del dolor | Pericarditis: menos probable |
| EME-103 | Exploración física | Tromboembolia: menos probable |
| EME-103 | Electrocardiograma | Infarto: menos probable; pericarditis: descartada |
| EME-103 | Troponina | Infarto: descartado |
| EME-103 | Angiotomografía | Tromboembolia: descartada |

Evidencia: [bateria_familia_terminal.png](01_bateria_dolor_toracico/bateria_familia_terminal.png)
(foto real de la terminal, 4 páginas unidas) y
[resultados_bateria.json](01_bateria_dolor_toracico/resultados_bateria.json) (las 42 respuestas).

## Intentos

1. [intentos/01_omision_de_la_medicacion](01_bateria_dolor_toracico/intentos/01_omision_de_la_medicacion/README.md):
   la batería pasaba, pero en EME-103 el paciente respondió «No, no estoy tomando ningún medicamento» y
   omitió que había abandonado el amlodipino hace 4 meses. La batería no medía la fidelidad.
2. [intentos/02_solo_el_prompt_no_basta](01_bateria_dolor_toracico/intentos/02_solo_el_prompt_no_basta/README.md):
   con la comprobación de fidelidad y una instrucción nueva al paciente, la omisión seguía; se corrigió
   redactando el dato como lo diría el paciente.

## Pendiente

- Revisión clínica de la familia por una persona con formación médica.
- Las otras cuatro familias (cirugía, ginecología y obstetricia, medicina interna y pediatría).
- El índice LightRAG local no incluye los casos nuevos: en local, con `RAG_EMBEDDED=true`, hay que
  reconstruirlo. El sitio publicado no usa ese índice.
