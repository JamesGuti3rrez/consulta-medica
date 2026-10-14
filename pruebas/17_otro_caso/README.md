# 17. Probar otro caso o cerrar el simulador

## Objetivo

Al terminar una consulta, la hoja de evaluación ofrece dos salidas:

- **Probar otro caso**: abre otro paciente de la **misma especialidad**, sin repetir el que acaba de
  atender.
- **Cerrar simulador**: vuelve a la portada.

## Cómo funciona

- El simulador recuerda los casos que el estudiante ya vio en la pestaña (`sessionStorage`, el actual
  primero) y los envía a `GET /api/caso?especialidad=...&excluir=...`. No van en la URL, para que el
  estudiante no vea códigos de caso.
- El servidor elige al azar entre los casos de la especialidad que no estén en esa lista. Si ya los vio
  todos, solo evita el actual, así nunca se repite el mismo paciente seguido.
- «Probar otro caso» reinicia el simulador en la misma página, sin recargar: limpia el chat, la ficha, las
  hipótesis y el diagnóstico, y el doctor presenta al nuevo paciente. Al no recargar, el clic del
  estudiante permite que la voz del doctor suene en la nueva presentación.
- Si la consulta venía de un caso de prueba (`?caso=MED-008`) o sin especialidad elegida, sigue con la
  especialidad del caso actual, y la URL pasa a `?especialidad=...`.
- Cada consulta nueva sigue las reglas de la fase 16: con la sesión iniciada se guarda en «Mis simulaciones».

## Commits

| Commit | Cambio |
| --- | --- |
| `b2c9dcc` | `/api/caso` acepta `excluir` (casos ya vistos), con dos pruebas nuevas |
| `3b9a154` | Botones «Probar otro caso» y «Cerrar simulador» en la hoja de evaluación |
| `27f053b` | Corrección de la hoja: con 0 datos clave, «Lo que hiciste bien» decía «No obtuviste ninguno...» con un visto verde; ahora dice que completó la consulta y registró un diagnóstico (las omisiones siguen en «Lo que faltó preguntar») |

## Comandos

Desde `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Con el servidor local en el puerto 3000 (modo local, sin Groq), desde la raíz:

```powershell
node pruebas/17_otro_caso/probar_otro_caso.cjs
```

## Resultados

| Ejecución | Resultado | Evidencia |
| --- | --- | --- |
| Pruebas del backend | 161 aprobadas (2 nuevas de `excluir`) | `ejecucion/01_pruebas_backend.txt`, `_terminal.png` |
| Navegador | Pediatría, tres rondas seguidas: Mateo Quispe, Valeria Torres, Mateo Quispe (con solo dos casos, vuelve al primero pero nunca repite el anterior). Desde `?caso=MED-008` (Patricia Vargas), el siguiente es Alberto Núñez, también de medicina interna, y la URL queda `?especialidad=medicina_interna`. El chat empieza limpio en cada ronda. «Cerrar simulador» lleva a `/index.html`. Sin errores de consola | `ejecucion/02_otro_caso_navegador.txt`, `_terminal.png`, `resultados/*.png` |

Las fotos (`.png`) se guardan en el equipo y no se suben a GitHub.

## Prueba en Vercel (producción)

Tras el push del commit `62afe63`, la misma prueba en `https://consulta-medica-three.vercel.app`:

```powershell
$env:BASE_URL = 'https://consulta-medica-three.vercel.app'
node pruebas/17_otro_caso/probar_otro_caso.cjs pruebas/17_otro_caso/vercel
```

Pediatría alternó Valeria Torres, Mateo Quispe y Valeria Torres; desde `?caso=MED-008` (Patricia Vargas)
siguió Alberto Núñez; «Cerrar simulador» llevó a `/index.html`; sin errores de consola. Evidencia:
`vercel/03_otro_caso_vercel.txt`, `_terminal.png` y las capturas `vercel/*.png`.

## Observaciones

- Las especialidades con dos casos (todas menos emergencias, que tiene cinco) alternan entre sus dos
  pacientes. Con más casos curados por especialidad, la rotación es más larga.
- Al preparar los commits, el cambio de los botones y la corrección de la hoja quedaron por error en un
  solo commit. Se separaron antes de subirlos, para mantener un commit por cambio.
