# Ampliación del catálogo · 16 de octubre de 2026

Se añaden **30 casos**, seis por especialidad, a los 13 existentes: **43 casos en total**.
La serie sintética empieza en 101, como EME-101 a EME-103; Emergencias continúa desde
EME-104. No se renumeran los anteriores.

Son pacientes ficticios con historia, medicación, hábitos, impacto funcional, signos vitales,
exploración y, cuando están indicados, estudios con resultados. Cada familia comparte el motivo
de consulta y tiene tres diagnósticos distintos con evidencia para distinguirlos.
La información clínica se revela bajo solicitud; el diagnóstico, los diferenciales y el
tratamiento de referencia permanecen en `protected`.

**Revisión clínica humana pendiente.** El estado técnico `curado` permite usarlos en el
simulador y no acredita revisión médica. La procedencia registra explícitamente validación
automática; no se atribuye la revisión a una persona. Usar para pruebas docentes supervisadas.

| Identificadores | Especialidad | Familia | Diagnósticos de referencia |
| --- | --- | --- | --- |
| EME-104 a EME-106 | emergencias | disnea aguda adulto | Exacerbación asmática; Exacerbación aguda de EPOC; Edema agudo de pulmón cardiogénico |
| EME-107 a EME-109 | emergencias | cefalea adulto | Migraña sin aura; Meningitis bacteriana aguda; Hemorragia subaracnoidea aneurismática |
| CIR-101 a CIR-103 | cirugia general | dolor abdominal quirurgico | Apendicitis aguda; Colecistitis aguda litiásica; Ureterolitiasis |
| CIR-104 a CIR-106 | cirugia general | distension y vomitos adulto | Obstrucción intestinal por adherencias; Íleo paralítico posoperatorio; Vólvulo de sigmoides |
| MED-101 a MED-103 | medicina interna | cansancio persistente adulto | Hipotiroidismo primario manifiesto; Anemia ferropénica; Diabetes mellitus tipo 2 |
| MED-104 a MED-106 | medicina interna | tos adulto | Neumonía adquirida en la comunidad; Bronquitis aguda; Tuberculosis pulmonar |
| GOB-101 a GOB-103 | ginecologia obstetricia | sangrado gestacion temprana | Embarazo ectópico tubárico; Amenaza de aborto; Aborto diferido |
| GOB-104 a GOB-106 | ginecologia obstetricia | flujo vaginal adulta | Candidiasis vulvovaginal; Vaginosis bacteriana; Tricomoniasis vaginal |
| PED-101 a PED-103 | pediatria | tos y dificultad respiratoria pediatrica | Exacerbación asmática pediátrica; Bronquiolitis aguda; Neumonía adquirida en la comunidad pediátrica |
| PED-104 a PED-106 | pediatria | dolor abdominal y vomitos pediatrico | Gastroenteritis aguda viral; Invaginación intestinal ileocólica; Apendicitis aguda pediátrica |

## Archivos y reproducción

- JSON listos para importar: `data/cases/curated/<ID>.json`.
- Diseño y referencias por familia: [ampliacion_2026_10_16.json](ampliacion_2026_10_16.json).
- Generador reproducible: `backend/case_preparation/familias/ampliacion.py`.
- Pruebas: `backend/tests/test_ampliacion_casos.py`.

Desde la raíz, en la terminal integrada de VS Code (PowerShell):

```powershell
Push-Location backend
.\.venv\Scripts\python.exe -m case_preparation.familias.ampliacion
Pop-Location
npm run test:cases
```

El generador valida esquema, reglas y familias antes de escribir. Rechaza sobrescribir un
identificador si ya contiene un caso distinto. Se puede ejecutar otra vez sin cambiar los casos.

## Carga en Supabase

Los archivos nuevos no actualizan por sí solos el catálogo remoto. Con el `.env` configurado,
ejecutar desde la raíz:

```powershell
npm run import:cases
```

El importador añade identificadores ausentes y verifica el catálogo; conserva los casos existentes
y el contenido adicional de pacientes. Si un ID remoto tiene otro contenido, lo informa para
resolverlo de forma explícita. Reiniciar el servidor después de importar y comprobar
`/api/status`: catálogo esperado de 43 casos, con 8 por especialidad y 11 en Emergencias.

## Referencias clínicas

Las historias y cifras son inventadas para simulación; estas fuentes orientan los patrones
clínicos y el manejo general. No se copian historias de pacientes de las guías.

1. [ginasthma.org/reports/](https://ginasthma.org/reports/)
2. [www.nice.org.uk/guidance/ng115/chapter/Recommendations](https://www.nice.org.uk/guidance/ng115/chapter/Recommendations)
3. [www.nice.org.uk/guidance/cg187/chapter/Recommendations](https://www.nice.org.uk/guidance/cg187/chapter/Recommendations)
4. [www.nice.org.uk/guidance/cg150/chapter/Recommendations](https://www.nice.org.uk/guidance/cg150/chapter/Recommendations)
5. [www.nice.org.uk/guidance/ng240/chapter/Recommendations](https://www.nice.org.uk/guidance/ng240/chapter/Recommendations)
6. [www.nice.org.uk/guidance/ng228/chapter/Recommendations](https://www.nice.org.uk/guidance/ng228/chapter/Recommendations)
7. [www.wses.org.uk/scientific-resources/guidelines](https://www.wses.org.uk/scientific-resources/guidelines)
8. [www.nice.org.uk/guidance/cg188/chapter/Recommendations](https://www.nice.org.uk/guidance/cg188/chapter/Recommendations)
9. [www.niddk.nih.gov/health-information/urologic-diseases/kidney-stones/diagnosis](https://www.niddk.nih.gov/health-information/urologic-diseases/kidney-stones/diagnosis)
10. [www.nice.org.uk/guidance/ng145/chapter/Recommendations](https://www.nice.org.uk/guidance/ng145/chapter/Recommendations)
11. [www.niddk.nih.gov/health-information/diabetes/overview/tests-diagnosis](https://www.niddk.nih.gov/health-information/diabetes/overview/tests-diagnosis)
12. [www.nhlbi.nih.gov/health/anemia/iron-deficiency-anemia](https://www.nhlbi.nih.gov/health/anemia/iron-deficiency-anemia)
13. [www.nice.org.uk/guidance/ng250/chapter/Recommendations](https://www.nice.org.uk/guidance/ng250/chapter/Recommendations)
14. [www.nice.org.uk/guidance/ng120/chapter/Recommendations](https://www.nice.org.uk/guidance/ng120/chapter/Recommendations)
15. [www.who.int/publications-detail-redirect/9789240089501](https://www.who.int/publications-detail-redirect/9789240089501)
16. [www.nice.org.uk/guidance/NG126/chapter/diagnosis-of-viable-intrauterine-pregnancy-and-of-tubal-ectopic-pregnancy](https://www.nice.org.uk/guidance/NG126/chapter/diagnosis-of-viable-intrauterine-pregnancy-and-of-tubal-ectopic-pregnancy)
17. [www.cdc.gov/std/treatment-guidelines/candidiasis.htm](https://www.cdc.gov/std/treatment-guidelines/candidiasis.htm)
18. [www.cdc.gov/std/treatment-guidelines/BV.htm](https://www.cdc.gov/std/treatment-guidelines/BV.htm)
19. [www.cdc.gov/std/treatment-guidelines/trichomoniasis.htm](https://www.cdc.gov/std/treatment-guidelines/trichomoniasis.htm)
20. [www.nice.org.uk/guidance/ng9/chapter/Recommendations](https://www.nice.org.uk/guidance/ng9/chapter/Recommendations)
21. [www.rch.org.au/clinicalguide/guideline_index/Abdominal_pain/](https://www.rch.org.au/clinicalguide/guideline_index/Abdominal_pain/)
22. [www.rch.org.au/clinicalguide/guideline_index/intussusception/](https://www.rch.org.au/clinicalguide/guideline_index/intussusception/)
23. [www.nice.org.uk/guidance/cg84/chapter/Recommendations](https://www.nice.org.uk/guidance/cg84/chapter/Recommendations)

