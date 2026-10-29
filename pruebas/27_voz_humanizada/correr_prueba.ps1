# Corre un comando de pytest de la voz humanizada con el entorno fijo y guarda la salida y la foto real de la terminal.
#
# Uso, desde la raíz del repositorio:
#   .\pruebas\27_voz_humanizada\correr_prueba.ps1 -Nombre t1_red -Pytest "tests/unit/test_voice_choice.py -q"
#
# Deja ejecucion\tdd\<Nombre>.txt (con fecha, commit, comando y código de salida) y <Nombre>_terminal.png.
# El entorno se fija aquí porque el .env apunta al Supabase de producción (hallazgo D-10 de TA-011).
param(
    [Parameter(Mandatory = $true)][string]$Nombre,
    [Parameter(Mandatory = $true)][string]$Pytest,
    [string]$Carpeta = "ejecucion\tdd"
)

$fase = Split-Path -Parent $MyInvocation.MyCommand.Path
$raiz = (Resolve-Path (Join-Path $fase "..\..")).Path
$destino = Join-Path $fase $Carpeta
New-Item -ItemType Directory -Force $destino | Out-Null
$txt = Join-Path $destino "$Nombre.txt"
$png = Join-Path $destino "$($Nombre)_terminal.png"

$comando = @"
`$env:SESSION_STORE='memoria'; `$env:CASE_STORE='local'; `$env:RAG_BACKEND='local'; `$env:SYNTHETIC_CASE_DATA='false'; `$env:LANGSMITH_TRACING='false'; `$env:PYTHONIOENCODING='utf-8'; git log -1 --oneline; `$inicio = (Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss'); & .venv\Scripts\python.exe -m pytest $Pytest -p no:cacheprovider 2>&1 | ForEach-Object { "`$_" } | Tee-Object -Variable salida; `$codigo = `$LASTEXITCODE; @("COMANDO: python -m pytest $Pytest", "COMMIT: `$(git rev-parse --short HEAD)", "FECHA: `$inicio UTC", "CODIGO_SALIDA: `$codigo", "") + `$salida | Out-File -Encoding utf8 '$txt'; `$global:LASTEXITCODE = `$codigo
"@

& (Join-Path $raiz "pruebas\_herramientas\captura_terminal.ps1") -Comando $comando -Directorio backend -Salida $png
Get-Content $txt -Tail 3

