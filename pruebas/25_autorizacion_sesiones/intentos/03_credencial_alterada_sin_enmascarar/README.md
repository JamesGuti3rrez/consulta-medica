# Intento 3: una credencial alterada quedó sin enmascarar en la evidencia

**Qué pasó.** La corrida «local después» (commit `9aa930f`) pasó los 37 casos, pero al generar las capturas
el verificador de `generar_capturas.py` encontró en `TA017-18.json` una cadena de 43 caracteres sin enmascarar
(`verificacion_capturas.txt`: `N2dqZD…`).

**Causa.** TA017-18 altera un carácter de la credencial de SN2 y la envía en `X-Session-Token`. La prueba
registraba como secreto la credencial alterada de SN1, pero no la de SN2, así que esa no se enmascaró. No es
una credencial válida (el servidor la rechazó con 404), pero la regla es que ningún token aparezca completo.

**Corrección.** Commit `TA-017: el caso 18 enmascara tambien la credencial alterada de SN2`: la prueba registra
las dos credenciales alteradas. La corrida se repitió completa con el commit corregido.

Archivos conservados sin modificar: foto de la terminal, salida de pytest, los 37 JSON y el resultado del
verificador. Estos archivos solo están en el equipo: las fotos no se suben a GitHub, y esta carpeta
contiene el token alterado.
