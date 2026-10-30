param([string]$Registro,[string]$Titulo,[int]$Filas=14)
$ErrorActionPreference='Stop'
$Host.UI.RawUI.WindowTitle='Preparando registro de evidencia'
$Host.UI.RawUI.BackgroundColor='Black'
$Host.UI.RawUI.ForegroundColor='Gray'
try {
    $Host.UI.RawUI.BufferSize=New-Object System.Management.Automation.Host.Size(140,2000)
    $Host.UI.RawUI.WindowSize=New-Object System.Management.Automation.Host.Size(140,$Filas)
} catch { }
Clear-Host
Write-Host ('SPRINT 2 | '+$Titulo+' | REGISTRO ORIGINAL DE EJECUCION') -ForegroundColor Cyan
Write-Host ('Archivo: '+[IO.Path]::GetFileName($Registro)) -ForegroundColor DarkGray
Write-Host ''
Get-Content -LiteralPath $Registro | ForEach-Object { Write-Host $_ }
Write-Host ''
Write-Host 'Fin del registro original. Captura de esta ventana propia de PowerShell.' -ForegroundColor Cyan
$Host.UI.RawUI.WindowTitle=$Titulo
Start-Sleep -Seconds 90
