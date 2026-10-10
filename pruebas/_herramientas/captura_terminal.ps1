# Ejecuta un comando en una ventana real de PowerShell y guarda capturas de TODA su salida.
#
# La ventana se abre con 1440 px de ancho y el alto de la pantalla. Al terminar el comando, la consola
# vuelve al inicio de la salida y se captura página por página; las páginas se unen en una sola
# imagen (<salida>.png). Con -ConservarPaginas también se guardan sueltas (<salida>_p1.png, _p2.png...).
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File pruebas\_herramientas\captura_terminal.ps1 `
#     -Comando "python -V" -Directorio backend -Salida pruebas\...\captura_terminal.png
param(
    [Parameter(Mandatory = $true)][string]$Comando,
    [string]$Directorio = ".",
    [Parameter(Mandatory = $true)][string]$Salida,
    [int]$Ancho = 1440,
    [int]$EsperaMaxima = 600,
    [switch]$ConservarPaginas
)

Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class Ventana {
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
    [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref POINT p);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr h, int x, int y, int w, int a, bool repintar);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
    [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
}
"@
[void][Ventana]::SetProcessDPIAware()

$raiz = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$dir = (Resolve-Path (Join-Path $raiz $Directorio)).Path
$salidaAbs = if ([IO.Path]::IsPathRooted($Salida)) { $Salida } else { Join-Path $raiz $Salida }
New-Item -ItemType Directory -Force (Split-Path $salidaAbs) | Out-Null
$base = [IO.Path]::Combine((Split-Path $salidaAbs), [IO.Path]::GetFileNameWithoutExtension($salidaAbs))

$id = [guid]::NewGuid().ToString().Substring(0, 8)
$titulo = "Evidencia consulta-medica $id"
$senal = Join-Path $env:TEMP "captura_terminal_$id"
New-Item -ItemType Directory -Force $senal | Out-Null

function Esperar([string]$archivo) {
    $limite = (Get-Date).AddSeconds($EsperaMaxima)
    while (-not (Test-Path $archivo)) {
        if ((Get-Date) -gt $limite) { throw "Tiempo agotado esperando $archivo" }
        Start-Sleep -Milliseconds 200
    }
}

# Guion de la ventana: espera a que se ajuste el tamaño, ejecuta el comando y luego recorre la
# salida página por página, avisando en cada una para que se tome la foto.
$guion = @"
`$Host.UI.RawUI.WindowTitle = '$titulo'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
`$env:PYTHONUTF8 = '1'
while (-not (Test-Path '$senal\iniciar')) { Start-Sleep -Milliseconds 200 }
Clear-Host
Set-Location '$dir'
Write-Host ('PS ' + (Get-Location).Path + '> ') -NoNewline
Write-Host '$($Comando.Replace("'", "''"))'
$Comando
Write-Host ''
Write-Host ('Codigo de salida: ' + `$LASTEXITCODE + '   ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))
`$ui = `$Host.UI.RawUI
`$total = `$ui.CursorPosition.Y + 1
`$alto = `$ui.WindowSize.Height
`$paginas = [Math]::Max(1, [Math]::Ceiling(`$total / `$alto))
Set-Content '$senal\alto' `$alto
Set-Content '$senal\paginas' `$paginas
for (`$p = 0; `$p -lt `$paginas; `$p++) {
    `$y = [Math]::Min(`$p * `$alto, [Math]::Max(0, `$total - `$alto))
    `$ui.WindowPosition = New-Object Management.Automation.Host.Coordinates 0, `$y
    Set-Content "$senal\y_`$p" `$y
    New-Item -ItemType File "$senal\lista_`$p" | Out-Null
    while (-not (Test-Path "$senal\foto_`$p")) { Start-Sleep -Milliseconds 200 }
}
"@
$codificado = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($guion))

# conhost fuerza una ventana de consola clásica cuya posición y tamaño se pueden controlar.
$proceso = Start-Process conhost.exe -ArgumentList "powershell.exe -NoExit -NoProfile -EncodedCommand $codificado" -PassThru

$limite = (Get-Date).AddSeconds(30)
do {
    Start-Sleep -Milliseconds 200
    $ventana = Get-Process | Where-Object { $_.MainWindowTitle -eq $titulo } | Select-Object -First 1
} while (-not $ventana -and (Get-Date) -lt $limite)
if (-not $ventana) { Write-Error "No se encontró la ventana de la terminal."; exit 1 }
$hwnd = $ventana.MainWindowHandle

# Pantalla completa en alto, 1440 px de ancho (vista de escritorio).
$area = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
[void][Ventana]::MoveWindow($hwnd, $area.Left, $area.Top, [Math]::Min($Ancho, $area.Width), $area.Height, $true)
[void][Ventana]::SetForegroundWindow($hwnd)
Start-Sleep -Milliseconds 600
New-Item -ItemType File "$senal\iniciar" | Out-Null

Esperar "$senal\paginas"
$paginas = [int](Get-Content "$senal\paginas")
$fotos = @()
for ($p = 0; $p -lt $paginas; $p++) {
    Esperar "$senal\lista_$p"
    Start-Sleep -Milliseconds 400
    $r = New-Object Ventana+RECT
    [void][Ventana]::GetWindowRect($hwnd, [ref]$r)
    $bmp = New-Object System.Drawing.Bitmap ($r.Right - $r.Left), ($r.Bottom - $r.Top)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $hdc = $g.GetHdc()
    [void][Ventana]::PrintWindow($hwnd, $hdc, 2)
    $g.ReleaseHdc($hdc); $g.Dispose()
    if ($ConservarPaginas) { $bmp.Save("$($base)_p$($p + 1).png", [System.Drawing.Imaging.ImageFormat]::Png) }
    $fotos += $bmp
    New-Item -ItemType File "$senal\foto_$p" | Out-Null
}

# Imagen completa: la primera página entera y, de las siguientes, solo las líneas que no se vieron.
$cliente = New-Object Ventana+RECT
[void][Ventana]::GetClientRect($hwnd, [ref]$cliente)
# Distancia del borde superior de la ventana al área de texto (barra de título y borde).
$ventanaRect = New-Object Ventana+RECT
[void][Ventana]::GetWindowRect($hwnd, [ref]$ventanaRect)
$origenTexto = New-Object Ventana+POINT
[void][Ventana]::ClientToScreen($hwnd, [ref]$origenTexto)
$marco = $origenTexto.Y - $ventanaRect.Top
$altoConsola = [int](Get-Content "$senal\alto")
$altoLinea = [Math]::Floor($cliente.Bottom / [double]$altoConsola)   # píxeles por línea
$ancho = $fotos[0].Width
$tramos = @()                                         # (página, fila inicial de píxeles, alto)
$tramos += , @(0, 0, ($marco + $altoConsola * $altoLinea))
$visto = [int](Get-Content "$senal\y_0") + $altoConsola
for ($p = 1; $p -lt $paginas; $p++) {
    $yPagina = [int](Get-Content "$senal\y_$p")
    $saltar = [Math]::Max(0, $visto - $yPagina)       # líneas ya incluidas en la página anterior
    $tramos += , @($p, ($marco + $saltar * $altoLinea), (($altoConsola - $saltar) * $altoLinea))
    $visto = $yPagina + $altoConsola
}
$altoTotal = ($tramos | ForEach-Object { $_[2] } | Measure-Object -Sum).Sum
$completa = New-Object System.Drawing.Bitmap $ancho, $altoTotal
$g = [System.Drawing.Graphics]::FromImage($completa)
$y = 0
foreach ($t in $tramos) {
    $origen = New-Object System.Drawing.Rectangle 0, $t[1], $ancho, $t[2]
    $destino = New-Object System.Drawing.Rectangle 0, $y, $ancho, $t[2]
    $g.DrawImage($fotos[$t[0]], $destino, $origen, [System.Drawing.GraphicsUnit]::Pixel)
    $y += $t[2]
}
$g.Dispose()
$completa.Save($salidaAbs, [System.Drawing.Imaging.ImageFormat]::Png)
$completa.Dispose(); $fotos | ForEach-Object { $_.Dispose() }

Stop-Process -Id $ventana.Id -Force -ErrorAction SilentlyContinue
Stop-Process -Id $proceso.Id -Force -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force $senal -ErrorAction SilentlyContinue
Write-Output "Captura guardada en $Salida ($paginas página(s))"
