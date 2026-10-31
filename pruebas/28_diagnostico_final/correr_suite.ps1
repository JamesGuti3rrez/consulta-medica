# Ejecuta la suite de HU-006 (proponer y registrar diagnóstico final) y guarda la salida completa con fecha, comando y código de salida.
#
# Uso, desde la raíz del repositorio (o dentro de captura_terminal.ps1 para la foto real):
#   .\pruebas\28_diagnostico_final\correr_suite.ps1 -Fase local_antes
#   .\pruebas\28_diagnostico_final\correr_suite.ps1 -Fase vivo_despues -Modo vivo -BaseUrl http://127.0.0.1:3100 -LogServidor <archivo>
#
# Los JSON de cada caso quedan en resultados\<Fase>\logs y la salida en ejecucion\<Fase>_pytest.txt.
param(
    [Parameter(Mandatory = $true)][string]$Fase,
    [ValidateSet("local", "vivo")][string]$Modo = "local",
    [string]$BaseUrl = "",
    [string]$LogServidor = "",
    [string]$Filtro = ""
)

$carpeta = Split-Path -Parent $MyInvocation.MyCommand.Path
$raiz = (Resolve-Path (Join-Path $carpeta "..\..")).Path
$evidencia = Join-Path $carpeta "resultados\$Fase"
$salida = Join-Path $carpeta "ejecucion\$($Fase)_pytest.txt"
if (Test-Path "$evidencia\logs") { Remove-Item -Recurse -Force "$evidencia\logs" }
New-Item -ItemType Directory -Force $evidencia, (Split-Path $salida) | Out-Null

# La preparación es la de TA-011 (TA011_MODO, TA011_BASE_URL...); la evidencia va a HU006_EVIDENCIA.
$env:HU006_EVIDENCIA = $evidencia
# La limpieza del modo vivo (de la preparación de TA-011) deja limpieza.json en la misma carpeta.
$env:TA011_EVIDENCIA = $evidencia
$env:TA011_MODO = $Modo
$env:TA011_FASE = $Fase
$env:TA011_BASE_URL = $BaseUrl
$env:TA011_SERVER_LOG = $LogServidor
$env:PYTHONIOENCODING = "utf-8"
# Sin trazas: con el cupo de LangSmith agotado, cada llamada queda esperando (intento 4).
$env:LANGSMITH_TRACING = "false"
# El modo local es en memoria aunque el .env apunte las sesiones y los casos a Supabase.
if ($Modo -eq "local") {
    $env:SESSION_STORE = "memoria"
    $env:CASE_STORE = "local"
    $env:RAG_BACKEND = "local"
    $env:SYNTHETIC_CASE_DATA = "false"
}

$marcas = if ($Filtro) { $Filtro } elseif ($Modo -eq "local") { "not vivo" } else { "" }
$argumentos = @("-m", "pytest", "tests/security/test_hu006_final_diagnosis.py", "-v", "--tb=no", "-rN", "-p", "no:cacheprovider")
if ($marcas) { $argumentos += @("-m", $marcas) }
$comando = ".venv\Scripts\python.exe " + ($argumentos -join " ")

Write-Host "HU-006 | fase: $Fase | modo: $Modo | servidor: $(if ($BaseUrl) { $BaseUrl } else { 'TestClient en proceso' })"
Write-Host "commit: $(git -C $raiz rev-parse --short HEAD) | evidencia: $evidencia"
Write-Host $comando
Push-Location (Join-Path $raiz "backend")
$inicio = Get-Date
& .\.venv\Scripts\python.exe @argumentos 2>&1 | ForEach-Object { "$_" } | Tee-Object -Variable capturado
$codigo = $LASTEXITCODE
Pop-Location

$cabecera = @(
    "FASE: $Fase", "MODO: $Modo", "SERVIDOR: $(if ($BaseUrl) { $BaseUrl } else { 'TestClient en proceso' })",
    "DIRECTORIO: $raiz\backend", "COMANDO: $comando",
    "COMMIT: $(git -C $raiz rev-parse --short HEAD)",
    "FECHA: $($inicio.ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss')) UTC",
    "CODIGO_SALIDA: $codigo", ""
)
($cabecera + $capturado) | Out-File -Encoding utf8 $salida
Write-Host ""
Write-Host "Salida guardada en $salida (codigo $codigo)"

exit $codigo
