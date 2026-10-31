# Intento 3: la prueba del panel docente buscaba textos anteriores

`frontend/tests/docente.mjs` esperaba el título «Acceso para docentes» y el enlace «Panel docente». Al hacer los
grupos (HU-014), Rodrigo los renombró a «Acceso al Panel Doctor» y «Panel Doctor» sin actualizar la prueba, que ya
fallaba en su rama. Se actualizaron los dos textos esperados; la corrida válida es `ejecucion/07_regresion_panel_docente`.
