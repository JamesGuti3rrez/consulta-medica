# Familias de casos sintéticos

Casos diseñados para comprobar que el simulador funciona de punta a punta: que revela el dato correcto
ante la pregunta correcta, que no deja escapar el diagnóstico y que no inventa síntomas. Se agrupan en
**familias**: varios pacientes llegan con el mismo motivo de consulta y lo que separa sus diagnósticos
solo aparece si el estudiante pregunta, examina o pide exámenes. Así, con cada respuesta, el estudiante
puede descartar hipótesis.

- **Fuente:** `source.dataset = "sintetico"`, `source.method = "generado_ia"` y `source.item_id =
  "familia/diagnostico"`. Licencia CC BY 4.0 (propia del proyecto). Esquema 1.1.0.
- **Numeración:** a partir de 101 (EME-101), para no confundirlos con los 10 casos de MedQA (001–010).
- **Dónde están:** en `data/cases/curated/`, como los demás: el simulador los usa sin cambios.
- **Cómo se generan:** cada familia es un módulo de `backend/case_preparation/familias/` que contiene la
  tabla de diferencias y escribe los JSON. Una prueba (`tests/test_familias_sinteticas.py`) comprueba que
  los JSON versionados son exactamente los que genera el módulo.
- **Revisión clínica:** pendiente. El contenido sigue las guías citadas abajo, pero ninguna persona con
  formación médica lo ha revisado todavía.

## Reglas adicionales (solo para casos sintéticos)

| Regla | Qué exige | Por qué |
| --- | --- | --- |
| R15 | Cada diferencial cita al menos un dato que lo descarta. | Si una hipótesis no se puede descartar, el caso no sirve para practicar el descarte. En MedQA solo 29 de 39 lo tenían. |
| R16 | Los datos que descartan están en `on_request`. | Si fueran visibles desde el inicio, el estudiante descartaría sin preguntar. |
| R17 | `source.item_id` tiene la forma `familia/diagnostico`. | Para agrupar la familia. |
| R18 | Los casos de una familia comparten el motivo de consulta y cada uno tiene como diferenciales los diagnósticos de los demás. | Es la definición de la familia. |

## Familia 1 · Dolor torácico agudo (Emergencias)

Motivo de consulta común: «Dolor en el pecho que empezó hace unas 2 horas y no se le pasa.» Los tres
pacientes son varones de 56 a 61 años con signos vitales parecidos.

| Caso | Paciente | Diagnóstico |
| --- | --- | --- |
| EME-101 | Carlos Mendoza, 58 años | Infarto agudo de miocardio con elevación del ST (cara inferior) |
| EME-102 | Luis Ramírez, 56 años | Tromboembolia pulmonar aguda |
| EME-103 | Víctor Chávez, 61 años | Disección aórtica aguda tipo A |

Diferencial común a los tres: pericarditis aguda.

### Tabla de diferencias

| Lo que pide el estudiante | Quién responde | EME-101 · Infarto | EME-102 · Tromboembolia | EME-103 · Disección |
| --- | --- | --- | --- | --- |
| Características del dolor | Paciente | Opresivo, al brazo izquierdo y la mandíbula | Punzante, empeora al respirar y toser | Desgarrante, migra entre los omóplatos, el peor de su vida |
| Inicio | Paciente | Al subir escaleras; angina de esfuerzo la semana previa | Brusco, al levantarse, con falta de aire | Brusco y máximo desde el inicio, al cargar peso |
| Síntomas acompañantes | Paciente | Sudor frío, náuseas | Falta de aire, tos, flema con hilos de sangre | Casi se desmaya, sudor frío |
| Antecedentes | Paciente | Diabetes, hipertensión, colesterol alto | Cáncer de próstata en tratamiento | Hipertensión mal controlada |
| Medicación | Paciente | Metformina, enalapril | Leuprolida, losartán | Amlodipino, abandonado hace 4 meses |
| Hábitos y viajes | Paciente | Fuma 30 años | Viaje de 20 horas en bus hace 5 días | Fuma, alcohol los fines de semana |
| Alergias | Paciente | No | Penicilina | No |
| Exploración física | Médico asistente | Pálido y sudoroso; pulsos y presión simétricos | Pantorrilla derecha hinchada y dolorosa; segundo ruido pulmonar aumentado | Presión 174/98 en brazo derecho y 132/80 en izquierdo; soplo diastólico |
| Electrocardiograma | Laboratorio | Elevación del ST en II, III y aVF | Taquicardia, S1Q3T3, T negativas V1–V3 | Crecimiento del ventrículo izquierdo, sin cambios del ST |
| Troponina I ultrasensible | Laboratorio | 2850 ng/L (alta) | 38 ng/L (algo alta) | 18 ng/L (normal) |
| Dímero D | Laboratorio | 420 ng/mL (normal) | 3200 ng/mL (alto) | 2400 ng/mL (alto) |
| Radiografía de tórax | Radiología | Normal | Sin hallazgos importantes | Mediastino ensanchado (8,5 cm) |
| Angiotomografía de tórax | Radiología | Normal | Defectos de llenado en la arteria pulmonar derecha | Colgajo intimal desde la aorta ascendente |

### Qué descarta cada hipótesis

| Caso | Diferencial | Datos que lo descartan |
| --- | --- | --- |
| EME-101 | Tromboembolia pulmonar | Sin viaje ni inmovilización; piernas normales; dímero D normal; angiotomografía normal |
| EME-101 | Disección aórtica | Dolor opresivo, no desgarrante; presión igual en ambos brazos; mediastino normal; aorta normal |
| EME-101 | Pericarditis | No cambia con la postura ni la respiración; sin roce; elevación del ST localizada con cambios recíprocos |
| EME-102 | Infarto | Dolor pleurítico; sin elevación del ST |
| EME-102 | Disección aórtica | Dolor pleurítico; presión igual en ambos brazos; aorta normal |
| EME-102 | Pericarditis | No mejora al inclinarse; sin roce; sin elevación difusa del ST |
| EME-103 | Infarto | Sin elevación del ST; troponina normal |
| EME-103 | Tromboembolia pulmonar | Piernas normales; arterias pulmonares sin defectos |
| EME-103 | Pericarditis | Dolor desgarrante que no cambia con la postura; sin elevación difusa del ST |

### Trampas de aprendizaje

- **El dímero D no separa la tromboembolia de la disección:** está alto en las dos (EME-102 y EME-103).
  Solo descarta la tromboembolia cuando es normal, como en EME-101.
- **La troponina también sube en la tromboembolia** (EME-102, 38 ng/L) por sobrecarga del ventrículo
  derecho: no basta para diagnosticar un infarto.
- **En la disección, tratar como infarto puede ser mortal:** EME-103 registra la contraindicación de
  antiagregantes, anticoagulantes y fibrinolíticos. La pregunta clave de medir la presión en ambos brazos
  está marcada como «negligencia» si se omite.

### Valores de referencia usados

- Troponina I ultrasensible: < 26 ng/L (percentil 99; varía según el ensayo de cada laboratorio).
- Dímero D: < 500 ng/mL (unidades equivalentes de fibrinógeno).

### Fuentes

- Byrne RA, et al. 2023 ESC Guidelines for the management of acute coronary syndromes. *Eur Heart J*. 2023;44:3720–3826.
- Konstantinides SV, et al. 2019 ESC Guidelines for the diagnosis and management of acute pulmonary embolism. *Eur Heart J*. 2020;41:543–603.
- Mazzolai L, et al. 2024 ESC Guidelines for the management of peripheral arterial and aortic diseases. *Eur Heart J*. 2024;45:3538–3700.
- Adler Y, et al. 2015 ESC Guidelines for the diagnosis and management of pericardial diseases. *Eur Heart J*. 2015;36:2921–2964.
- StatPearls (NCBI Bookshelf): «ST Segment Elevation Myocardial Infarction», «Pulmonary Embolism» y «Aortic Dissection».
