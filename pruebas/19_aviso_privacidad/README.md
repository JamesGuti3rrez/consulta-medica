# 19. Aviso de privacidad

## Objetivo

Desde la fase 16, el sistema guarda datos de los alumnos con cuenta: puntaje, diagnóstico, hipótesis y
duración de cada consulta. `backend/supabase/README.md` ya advertía que eso requiere aviso de privacidad y
consentimiento (Ley N.º 29733, Ley de Protección de Datos Personales del Perú), y no había ninguno.

## Qué se hizo

| Commit | Cambio |
| --- | --- |
| `97716b9` | Página [privacidad.html](../../frontend/public/privacidad.html), enlace en el pie de la portada y casilla obligatoria al crear cuenta. La cuenta guarda `privacidad_version` y `privacidad_aceptada_en` |
| `a95a294` | «Mis simulaciones» enlaza al aviso |
| `7d75566` | [probar_aviso.cjs](probar_aviso.cjs): prueba en el navegador |

El aviso describe solo lo que el sistema guarda de verdad:

- **Cuenta:** nombres, apellidos, correo, contraseña cifrada y fecha de aceptación del aviso.
- **Consultas terminadas con sesión:** especialidad, puntaje, diagnóstico, hipótesis, duración, datos clave y
  alertas.
- **Conversación de cada consulta.**

También explica:

- para qué se usan los datos;
- quién los procesa: Supabase, Vercel y Groq (Groq solo recibe el texto de las preguntas, no el nombre ni el
  correo);
- cuánto tiempo se conservan;
- cómo ejercer los derechos ARCO.

Usar el simulador sin cuenta no exige aceptarlo, porque no se guarda nada que identifique al alumno.

## Comandos

Con el servidor local en el puerto 3000, desde la raíz:

```powershell
node pruebas/19_aviso_privacidad/probar_aviso.cjs
```

La prueba no crea cuentas reales: intercepta el pedido de registro a Supabase, lee lo que se enviaría y lo
corta.

## Resultados

| Comprobación | Resultado |
| --- | --- |
| Enlace al aviso en el pie de la portada | Sí |
| Crear cuenta sin aceptar | No se envía nada; aparece «Para crear la cuenta, acepta el aviso de privacidad.» |
| Marcar la casilla | El mensaje de error desaparece |
| Crear cuenta aceptando | Se envían nombres, apellidos, `privacidad_version: "1"` y la fecha de aceptación |
| Página del aviso | Menciona la Ley N.º 29733, Supabase, Groq, «Mis simulaciones» y los derechos ARCO |
| Errores de consola | Ninguno |

Evidencia: `ejecucion/01_aviso_navegador.txt`, `_terminal.png` y las capturas `resultados/*.png`. Las fotos
(`.png`) se guardan en el equipo y no se suben a GitHub.

## Intento fallido

En la primera corrida, al marcar la casilla el mensaje rojo seguía visible hasta volver a enviar, y la
casilla salía azul en lugar del color del sitio, porque el plugin de formularios la colorea con el color del
texto. Se corrigió en el mismo commit `97716b9`: el mensaje se oculta al marcarla y la casilla usa
`text-brand-600`.

## Observaciones

- **Contacto para los derechos ARCO:** el aviso remite al responsable de datos (James Gutiérrez) a través del
  docente del curso. No se publicó un correo; si el equipo define uno, conviene agregarlo al aviso.
- **Cuentas creadas antes del aviso:** no tienen la fecha de aceptación. Si se quiere, se les puede pedir que
  lo acepten al iniciar sesión.
- **Borrar el historial:** hoy el alumno no puede hacerlo por su cuenta (no hay política de borrado en
  `intentos`). Se atiende como pedido ARCO, o al eliminar la cuenta, que borra el historial en cascada.
