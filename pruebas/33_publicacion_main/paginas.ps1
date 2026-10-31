# Código HTTP de las páginas, la API y las imágenes de la escena en producción.
param([string]$Base = 'https://consulta-medica-three.vercel.app')
$fallos = 0
foreach ($u in '/', '/simulacion.html', '/grupos.html', '/docente.html', '/api/status', '/api/ai/status',
               '/api/voz/estado', '/assets/avatars/doctor-800.webp', '/assets/avatars/paciente-hombre-800.webp',
               '/assets/avatars/paciente-mujer-800.webp') {
    $codigo = curl.exe -s -o NUL -w '%{http_code}' ($Base + $u)
    if ($codigo -ne '200') { $fallos++ }
    "{0}  {1}" -f $codigo, $u
}
if ($fallos) { "$fallos rutas fallan" } else { 'TODO PASA' }
