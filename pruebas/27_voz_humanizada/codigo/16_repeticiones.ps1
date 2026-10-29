# Corre tres veces seguidas la prueba de navegador de la voz y deja el resultado de cada una.
# Uso, desde la raíz: .\pruebas\27_voz_humanizada\codigo\16_repeticiones.ps1
foreach ($n in 1..3) {
    node pruebas\27_voz_humanizada\codigo\03_navegador_voz.cjs "pruebas\27_voz_humanizada\resultados\repeticion_$n" | Tee-Object -FilePath "pruebas\27_voz_humanizada\ejecucion\16_repeticion_$n.txt"
    "Corrida $n terminada con codigo $LASTEXITCODE"
    ""
}
