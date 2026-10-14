# 23. Numeración de los casos por especialidad

## Objetivo

Los códigos de los casos no seguían un orden claro: Pediatría estaba en 007 y 010, con Medicina interna (008
y 009) en medio. Además, `data/README.md` decía que el número era la posición del caso en el lote y que
«Paciente 1» era EME-001, y ninguna de las dos cosas era cierta: el lote estaba en otro orden y los pacientes
tienen nombres desde la fase 10.

## Decisión

Agrupar por especialidad renombrando solo 3 casos (lo eligió el equipo entre tres opciones):

| Antes | Ahora | Paciente | Diagnóstico |
| --- | --- | --- | --- |
| MED-008 | MED-007 | Patricia Vargas | Enfermedad de Lyme |
| MED-009 | MED-008 | Alberto Núñez | Carcinoma basocelular |
| PED-007 | PED-009 | Mateo Quispe | Enfermedad de Legg-Calvé-Perthes |

Resultado: EME 001-002, GOB 003-004, CIR 005-006, MED 007-008 y PED 009-010; los sintéticos siguen en
EME-101 a EME-103. El sufijo vuelve a ser la posición del caso en el lote, que ahora está ordenado por número.
No choca con los casos rechazados, que usan otros prefijos para esos números (CIR-007, CIR-008, EME-009,
EME-010).

Se descartaron:

- **Numerar desde 001 en cada especialidad:** renombraba casi todo y repetía IDs de casos rechazados
  (MED-001, PED-003).
- **No renombrar:** dejaba Pediatría partida.

## Qué se hizo

| Commit | Cambio |
| --- | --- |
| `0eace5b` | [renumerar_casos.py](renumerar_casos.py): aplica la renumeración con marcadores intermedios (MED-008 pasa a ser otro caso), ordena el lote por número y mueve los archivos con `git mv` para conservar su historial |
| `a8e3231` | Datos regenerados con `curation` (casos curados y validados, selección final e índices de revisión) y pruebas con los códigos nuevos |
| `7fc24a4` | Decisión 0002 y documento de traspaso con los códigos nuevos |
| `43d08ce` | Scripts de prueba de las fases 7, 11, 13, 15, 16, 17 y 18, y captura del frontend, con los códigos nuevos |
| `39193c2` | `data/README.md`: regla de numeración correcta y tabla de equivalencias |
| `25944ee` | Nota de equivalencias al inicio de los README de fases anteriores que nombran los códigos viejos |

No se cambió:

- **La evidencia de fases anteriores** (`.txt`, `.json` y README): registra lo que pasó con los códigos de su
  momento. Sus README llevan la nota de equivalencias.
- **`Entregables/`:** no está en el repositorio y se entrega aparte.
- **Supabase:** no había ningún intento guardado con esos códigos, así que ningún historial quedó apuntando a
  otro caso.

Después se reconstruyó el índice local del RAG (13 casos, 103 documentos).

## Comprobación

| Ejecución | Resultado | Evidencia |
| --- | --- | --- |
| Contenido de cada caso | Los 13 archivos con su código, su paciente y su diagnóstico; ningún `evidence_id` con el código de otro caso | sección «Verificación» abajo |
| Pruebas del backend | 175 aprobadas | `ejecucion/02_pruebas_backend.txt`, `_terminal.png` |
| Recorrido completo (fases 1-4, 14, 15, 17, 18, 19 y 20) | 14 de 14 sin errores (2026-10-14, 12:18 UTC). La captura del frontend ya muestra MED-007 y PED-009, y «Probar otro caso» pasa de Patricia Vargas (MED-007) a Alberto Núñez | `ejecucion/01_recorrido_completo_terminal.png`, `../05_recorrido_completo/resumen_recorrido.txt`, `../21_cierre_sprint1/recorrido/` |

## Verificación

```
EME-001  Jorge Salazar     Golpe de calor por esfuerzo
EME-002  Ricardo Medina    Hemorragia subaracnoidea
GOB-003  Lucía Paredes     Infarto hipofisario posparto (síndrome de Sheehan)
GOB-004  Andrea Castillo   Tricomoniasis vulvovaginal
CIR-005  Martín Rojas      Hemofilia A
CIR-006  Rosa Villanueva   Sepsis posoperatoria
MED-007  Patricia Vargas   Enfermedad de Lyme con eritema migrans
MED-008  Alberto Núñez     Carcinoma basocelular
PED-009  Mateo Quispe      Enfermedad de Legg-Calvé-Perthes
PED-010  Valeria Torres    Síndrome de McCune-Albright
EME-101  Carlos Mendoza    Infarto agudo de miocardio con elevación del ST
EME-102  Luis Ramírez      Tromboembolia pulmonar aguda
EME-103  Víctor Chávez     Disección aórtica aguda tipo A
```

Las fotos (`.png`) se guardan en el equipo y no se suben a GitHub.

## Intento fallido

La primera corrida del recorrido tras la renumeración (`intentos/01_sinonimos_con_nombres_viejos/`) se detuvo
en la fase 20. El script de sinónimos contaba los de la versión anterior pidiendo a git cada archivo con su
nombre actual, y `MED-007.json` no existía en esa versión. Corrección (`68b875b`): recorre los archivos de esa
versión con los nombres que tenían entonces.

## Observaciones

- Quien tenga el índice del RAG en su equipo debe reconstruirlo (`python -m case_preparation index`). Aun sin
  hacerlo, desde la fase 18 los datos autorizados salen del caso.
- Las sesiones abiertas en Supabase antes del cambio con MED-008 apuntarían ahora a otro paciente. Son
  temporales y no afectan el historial.
