# Ensayo inicial durante el desarrollo

Este XML conserva una ejecución intermedia con cuatro fallos tras los primeros cambios:
faltaban alias explícitos de examen físico, electroencefalograma y angiotomografía, y
el campo opcional de exámenes sintéticos alteraba el contrato de reportes sin exámenes.

Se corrigieron los alias y se conservó el contrato previo cuando no hay resultados
sintéticos. No es el resultado final ni una medición del código anterior al desarrollo.
La evidencia válida de cierre es `pruebas/Sprint2/regresion.xml`: 688 pruebas aprobadas.
