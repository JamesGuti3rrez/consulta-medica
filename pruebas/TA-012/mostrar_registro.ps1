param([Parameter(Mandatory=$true)][string]$Registro, [Parameter(Mandatory=$true)][string]$Titulo)
$ErrorActionPreference = 'Stop'
$Host.UI.RawUI.WindowTitle = $Titulo
$Host.UI.RawUI.BackgroundColor = 'Black'
$Host.UI.RawUI.ForegroundColor = 'Gray'
try {
    $buffer = $Host.UI.RawUI.BufferSize
    $buffer.Width = 130
    $buffer.Height = 2000
    $Host.UI.RawUI.BufferSize = $buffer
    $window = $Host.UI.RawUI.WindowSize
    $window.Width = 130
    $window.Height = 38
    $Host.UI.RawUI.WindowSize = $window
} catch {}
Clear-Host
Write-Host 'TA-012 | SALIDA REAL REGISTRADA DE LA EJECUCION' -ForegroundColor Cyan
Write-Host ('Archivo: ' + (Split-Path $Registro -Leaf)) -ForegroundColor DarkGray
Write-Host ''
Get-Content -LiteralPath $Registro | ForEach-Object { Write-Host $_ }
Write-Host ''
Write-Host 'Fin del registro. La captura corresponde a esta ventana de PowerShell.' -ForegroundColor Cyan
Start-Sleep -Seconds 90
