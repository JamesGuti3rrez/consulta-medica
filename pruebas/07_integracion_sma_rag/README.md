# Fase 7 · Integración del sistema multiagente y del RAG (2026-10-09)

> Numeración: este README usa los códigos de casos anteriores a la fase 23. Equivalencias actuales: MED-008 → MED-007 (Patricia Vargas), MED-009 → MED-008 (Alberto Núñez) y PED-007 → PED-009 (Mateo Quispe).

## Objetivo

Revisar el trabajo de la rama `Rodrigo` (commit `9493e8b`): sistema multiagente (SMA) y RAG, este
último basado en el indexado con LightRAG de la rama `feature/rag-light-rag-sprint1` (Julio).
Comprobar si funciona y adaptarlo a la estructura actual del repositorio (`backend/`, `frontend/`)
y a los datos corregidos en la auditoría (fase 6), sin modificar las ramas de origen.

La rama `Rodrigo` se creó antes de la auditoría: trae la estructura anterior (`server/` y `public/`
en la raíz) y la primera versión del pipeline y de los casos. De ella se toma solo el SMA y el RAG;
el pipeline y los casos se quedan en su versión corregida.

## Revisión previa (en una copia aparte de la rama `Rodrigo`)

- Sus 53 pruebas pasan, el índice LightRAG se construye y la API responde sin clave de LLM.
- La IA nunca recibe `protected`; las decisiones (a qué agente va el mensaje, qué se revela, en
  qué fase está la consulta) las toma el código, no el LLM.

## Qué se integró y dónde

| Paso | Commit | Qué | Evidencia |
| --- | --- | --- | --- |
| 1 | `d74d83e` | Corrección propia: el esquema admite datos con `value` y `unit` en lugar de `text` (como los signos vitales del caso de Rodrigo); el aviso W01 y la ficha del estudiante fallaban con ellos | [01_datos_con_valor_y_unidad/](01_datos_con_valor_y_unidad/) |
| 2 | `95ddc11` | Dependencias (`langgraph`, `langsmith`, `numpy`, extra `indexing` con `lightrag-hku`) y variables de `.env.example`; trazas y registro del RAG en `backend/logs/` | [02_dependencias/](02_dependencias/) |
| 3 | `5a7fab9` | Acceso por rol (`engine/disclosure`), máquina de estados, filtro de salida y repositorio de casos. El repositorio valida con nuestro esquema y las reglas R01–R13 | [03_motor_y_repositorio/](03_motor_y_repositorio/) |
| 4 | `148481e` | Capa de IA: gateway de LLM (Groq, varias claves), cinco agentes y embeddings | [04_capa_ia/](04_capa_ia/) |
| 5 | `edecd78` | RAG: comando `index` (solo indexa casos que pasan las Quality Gates) y rutas `/api/v1/rag` | [05_rag/](05_rag/) |
| 6 | `95b72f8` | Orquestador en estrella, trazas y API `/api/ai` | [06_orquestador/](06_orquestador/) |
| 7 | (este paso) | Seguridad: `/api/v1/rag/*/search` y `reload` aceptaban `allowed_evidence_ids` del cliente, así que cualquiera podía leer todo el `on_request` de un caso saltándose el acceso por rol (`protected` no estaba expuesto). Ahora exigen el token entre servicios `RAG_HTTP_TOKEN` (cabecera `X-RAG-Token`); sin token configurado no se atienden. El SMA usa el RAG dentro del mismo proceso y no las necesita; `health` sigue pública | [07_rag_http_con_token/](07_rag_http_con_token/) |
| 8 | (este paso) | Seguridad: `POST /api/ai/sessions` usaba el `case_id` del cliente como nombre de archivo, así que un valor con `../` cargaba un caso fuera del catálogo. Ahora solo se aceptan IDs con el patrón del esquema (`^[A-Z]{3,5}-\d{3}$`); cualquier otro responde 404 | [08_case_id_sin_rutas/](08_case_id_sin_rutas/) |
| 9 | (este paso) | Casos repartidos de la rama del pipeline (fase 8). Para que el SMA funcione con ellos: el caso de prueba MED-900 usa los temas del contrato de Julio (la regla R14 lo exige); `DisclosurePolicy` reconoce esos temas con sinónimos (había dos claves duplicadas, `medicacion` y `alergias`, y la segunda anulaba a la primera); el router reconoce los exámenes de los casos (coagulación, pH vaginal, función tiroidea, edad ósea); y el RAG embebido ya no descarta por puntaje un dato que el acceso por rol autorizó (`min_score` de 0,0 a -1,0) | [09_casos_repartidos/](09_casos_repartidos/) |

Adaptaciones hechas al código de Rodrigo:

- Rutas de la raíz del proyecto ajustadas a `backend/`.
- El repositorio de casos usa la validación del catálogo (`validator.py` y `rules.py`) en lugar de
  un validador propio sin reglas cruzadas.
- Su caso escrito a mano `CARD-001` pasa a `backend/tests/fixtures/cases/MED-900.json`: el prefijo
  CARD no corresponde a `medicina_interna` (regla R01) y no es un caso de MedQA, así que no entra al
  catálogo curado. Las pruebas del SMA lo usan porque es el único con datos para los cinco roles.
- Las rutas `/api/ai` y `/api/v1/rag` se registran antes de la respuesta 404 de `api/routes.py`,
  que las tapaba.
- La prueba de la API del SMA ya no depende de si hay un índice LightRAG construido en el equipo.
- No se tomaron: la copia vieja del pipeline y de los casos, `clinical_case.py` y el caso demo,
  los `CHANGESET_*.md`, los informes `.docx` ni los experimentos SP-001 y SP-003.

Resultado: `pytest` pasa 95 pruebas (las 45 anteriores, la nueva de valor y unidad, 39 del SMA y
del RAG, 3 del token del RAG y 7 del formato de `case_id`); `verificar_casos.py` pasa todas sus comprobaciones.

## Consulta simulada

[06_orquestador/consulta_simulada.py](06_orquestador/consulta_simulada.py), sin clave de LLM
(los agentes devuelven el texto exacto de la evidencia autorizada):

- **MED-900:** responden los cinco roles y cada uno revela solo su dato; preguntar por el
  diagnóstico no lo revela.
- **Casos curados (paso 9), con el índice LightRAG:** en EME-001, MED-008 y CIR-005 cada pregunta
  revela su dato: medicación, antecedentes, exploración al examinar, alergia, exposición, antecedentes
  familiares y pruebas de coagulación. Pedir un examen que el caso no tiene («Solicito un hemograma» en
  EME-001) o preguntar por el diagnóstico no revela nada.
- **Antes del paso 9,** EME-001 no revelaba nada: la historia estaba en `public` y `on_request` solo
  tenía un marcador con `al_preguntar`.

## Lo que queda pendiente

| Qué | Por qué | Quién |
| --- | --- | --- |
| Revisar los sinónimos de `DisclosurePolicy` y del router | Se añadieron sinónimos para los temas del contrato, pero la comparación busca el texto en cualquier parte de la frase (por ejemplo, «tac» coincide dentro de «contacto»); con un LLM, la intención se podría clasificar mejor | Rodrigo |
| Prompt del paciente para casos sin paciente que conteste | En EME-001, EME-002 y CIR-006 el paciente no puede hablar y en PED-007 y PED-010 es un menor: el rol `paciente` representa al acompañante o a la historia clínica | Rodrigo |
| Reforzar el filtro de salida | Solo bloquea el término exacto, no variantes ni el término en inglés | Julio |
| Evaluación del diagnóstico y del tratamiento propuestos | El médico asistente solo repite lo revelado | Julio |
| Conectar el chat del frontend a `/api/ai` | El simulador todavía no usa el SMA | Quien lleve el frontend |
| Volver a indexar cuando cambien los casos | El SMA usa el índice si existe; si queda desactualizado, no encuentra la evidencia nueva | Quien prepare el despliegue |
