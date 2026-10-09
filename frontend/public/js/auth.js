// Sesión con Supabase Auth, compartida por las páginas.
// Requiere vendor/supabase.js antes de este archivo. Expone window.auth.ready: una promesa con el
// cliente de Supabase, o null si el servidor no tiene configurado el inicio de sesión.
(() => {
  const ready = (async () => {
    if (!window.supabase) return null;
    try {
      const response = await fetch('/api/config');
      if (!response.ok) return null;
      const config = await response.json();
      if (!config.auth) return null;
      return window.supabase.createClient(config.supabaseUrl, config.supabaseKey);
    } catch (error) {
      console.warn('No se pudo preparar el inicio de sesión:', error.message);
      return null;
    }
  })();

  // Nombre para mostrar: el que se guardó al registrarse o el que entrega Google.
  const displayName = user => {
    const meta = user?.user_metadata || {};
    const fullName = [meta.nombres, meta.apellidos].filter(Boolean).join(' ') || meta.full_name || meta.name;
    return fullName || user?.email || '';
  };

  // Mensajes de Supabase traducidos a lo que el alumno puede hacer.
  const errorMessage = error => {
    const messages = {
      invalid_credentials: 'Correo o contraseña incorrectos.',
      email_not_confirmed: 'Aún no confirmas tu correo. Abre el enlace que te enviamos y vuelve a intentarlo.',
      user_already_exists: 'Ya existe una cuenta con ese correo. Inicia sesión.',
      email_exists: 'Ya existe una cuenta con ese correo. Inicia sesión.',
      weak_password: 'La contraseña es muy débil. Usa al menos 8 caracteres combinando letras y números.',
      over_email_send_rate_limit: 'Se enviaron demasiados correos. Espera unos minutos y vuelve a intentarlo.',
      over_request_rate_limit: 'Demasiados intentos seguidos. Espera un momento y vuelve a intentarlo.',
      email_address_invalid: 'Ese correo no es válido. Revísalo y vuelve a intentarlo.',
    };
    return messages[error?.code] || 'No se pudo completar. Revisa tu conexión y vuelve a intentarlo.';
  };

  window.auth = { ready, displayName, errorMessage };
})();
