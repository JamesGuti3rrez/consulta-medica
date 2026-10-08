// Ventanas de inicio de sesión y creación de cuenta.
const dialogs = {
  login: document.querySelector('[data-role="login-panel"]'),
  signup: document.querySelector('[data-role="signup-panel"]')
};
let activeDialog = null;
let lastOpener = null;

function showDialog(name, opener) {
  const dialog = dialogs[name];
  if (!dialog) return;
  if (activeDialog && activeDialog !== dialog) hideDialog(false);
  if (opener) lastOpener = opener;
  if (name === 'signup') showSignupForm();
  dialog.hidden = false;
  dialog.classList.remove('hidden');
  dialog.classList.add('flex');
  activeDialog = dialog;
  dialog.querySelector('input, button')?.focus();
}

function hideDialog(restoreFocus = true) {
  if (!activeDialog) return;
  activeDialog.hidden = true;
  activeDialog.classList.add('hidden');
  activeDialog.classList.remove('flex');
  activeDialog = null;
  if (restoreFocus) lastOpener?.focus();
}

document.querySelectorAll('[data-open]').forEach((button) => {
  button.addEventListener('click', () => showDialog(button.dataset.open, button));
});
document.querySelectorAll('[data-close-dialog]').forEach((button) => {
  button.addEventListener('click', () => hideDialog());
});
Object.values(dialogs).forEach((dialog) => {
  dialog?.addEventListener('click', (event) => {
    if (event.target === dialog) hideDialog();
  });
});
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && activeDialog) hideDialog();
});

// Cuentas con Supabase Auth: iniciar sesión, crear cuenta y cerrar sesión.
const loginForm = document.querySelector('[data-role="login-form"]');
const signupForm = document.querySelector('[data-role="signup-form"]');
const signupFields = document.querySelector('[data-role="signup-fields"]');
const signupDone = document.querySelector('[data-role="signup-done"]');

// La ventana de crear cuenta alterna entre el formulario y el aviso de "revisa tu correo".
function showSignupForm() {
  if (signupFields) signupFields.hidden = false;
  if (signupDone) signupDone.hidden = true;
}

function showSignupDone(email) {
  const emailLabel = document.querySelector('[data-role="signup-email"]');
  if (emailLabel) emailLabel.textContent = email;
  if (signupFields) signupFields.hidden = true;
  if (signupDone) signupDone.hidden = false;
  document.querySelector('[data-role="signup-done-title"]')?.focus();
}

const unavailableMessage = 'El inicio de sesión no está disponible en este momento. Verifica la configuración de acceso.';

function showFeedback(form, message, isError = false) {
  const feedback = form.querySelector('[data-role="auth-feedback"]');
  if (!feedback) return;
  feedback.textContent = message;
  feedback.classList.toggle('is-error', isError);
  feedback.hidden = false;
  feedback.focus();
}

function setBusy(form, busy, busyLabel) {
  const button = form.querySelector('button[type="submit"]');
  if (!button) return;
  if (busy) {
    button.dataset.label = button.textContent;
    button.textContent = busyLabel;
  } else if (button.dataset.label) {
    button.textContent = button.dataset.label;
  }
  button.disabled = busy;
}

// Campos vacíos o inválidos: se marca el primero con un mensaje claro, sin enviar nada.
function firstInvalidField(form) {
  const invalid = [...form.elements].find((field) => field.willValidate && !field.checkValidity());
  if (!invalid) return null;
  const messages = {
    nombres: 'Escribe tus nombres.',
    apellidos: 'Escribe tus apellidos.',
    correo: 'Escribe un correo válido, por ejemplo nombre@universidad.edu.pe.',
    clave: invalid.minLength > 0 ? 'La contraseña debe tener al menos 8 caracteres.' : 'Escribe tu contraseña.',
  };
  return { field: invalid, message: messages[invalid.name] || 'Revisa los campos marcados.' };
}

loginForm?.addEventListener('submit', async (event) => {
  event.preventDefault();
  const invalid = firstInvalidField(loginForm);
  if (invalid) {
    showFeedback(loginForm, invalid.message, true);
    invalid.field.focus();
    return;
  }
  const client = await window.auth.ready;
  if (!client) {
    showFeedback(loginForm, unavailableMessage, true);
    return;
  }

  setBusy(loginForm, true, 'Ingresando...');
  const { correo, clave } = loginForm.elements;
  const { error } = await client.auth.signInWithPassword({ email: correo.value.trim(), password: clave.value });
  setBusy(loginForm, false);

  if (error) {
    showFeedback(loginForm, window.auth.errorMessage(error), true);
    return;
  }
  loginForm.reset();
  loginForm.querySelector('[data-role="auth-feedback"]').hidden = true;
  hideDialog();
});

signupForm?.addEventListener('submit', async (event) => {
  event.preventDefault();
  const invalid = firstInvalidField(signupForm);
  if (invalid) {
    showFeedback(signupForm, invalid.message, true);
    invalid.field.focus();
    return;
  }
  const client = await window.auth.ready;
  if (!client) {
    showFeedback(signupForm, unavailableMessage, true);
    return;
  }

  setBusy(signupForm, true, 'Creando cuenta...');
  const { nombres, apellidos, correo, clave } = signupForm.elements;
  const email = correo.value.trim();
  const { data, error } = await client.auth.signUp({
    email,
    password: clave.value,
    options: {
      data: { nombres: nombres.value.trim(), apellidos: apellidos.value.trim() },
      emailRedirectTo: window.location.origin,
    },
  });
  setBusy(signupForm, false);

  if (error) {
    showFeedback(signupForm, window.auth.errorMessage(error), true);
    return;
  }
  // Con la confirmación por correo activa, un correo ya registrado vuelve sin identidades.
  if (data.user && data.user.identities?.length === 0) {
    showFeedback(signupForm, window.auth.errorMessage({ code: 'user_already_exists' }), true);
    return;
  }
  if (data.session) {
    signupForm.reset();
    hideDialog();
    return;
  }
  signupForm.reset();
  signupForm.querySelector('[data-role="auth-feedback"]').hidden = true;
  showSignupDone(email);
});

// Enlaces que abren una ventana al llegar: ?cuenta=login o ?cuenta=registro.
const params = new URLSearchParams(window.location.search);
const dialogFromUrl = { login: 'login', registro: 'signup' }[params.get('cuenta')];
if (dialogFromUrl) {
  window.history.replaceState(null, '', window.location.pathname);
  window.setTimeout(() => showDialog(dialogFromUrl), 300);
}

// Apariciones al entrar en pantalla: cada elemento con data-reveal se anima una sola vez.
const revealTargets = document.querySelectorAll('[data-reveal]');

if ('IntersectionObserver' in window) {
  const revealObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add('is-visible');
      revealObserver.unobserve(entry.target);
    });
  }, { threshold: 0.2, rootMargin: '0px 0px -40px 0px' });
  revealTargets.forEach((element) => revealObserver.observe(element));

  // Pasos de "Cómo funciona": se encienden en orden cuando la lista está a la vista.
  const stepsList = document.querySelector('.steps');
  if (stepsList) {
    const stepsObserver = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return;
      stepsList.classList.add('is-lit');
      stepsObserver.disconnect();
    }, { threshold: 0.4 });
    stepsObserver.observe(stepsList);
  }

  // Sombra del encabezado en cuanto la página deja de estar arriba del todo.
  const siteHeader = document.querySelector('[data-role="site-header"]');
  const topSentinel = document.querySelector('[data-role="top-sentinel"]');
  if (siteHeader && topSentinel) {
    new IntersectionObserver(([entry]) => {
      siteHeader.classList.toggle('is-scrolled', !entry.isIntersecting);
    }).observe(topSentinel);
  }
} else {
  revealTargets.forEach((element) => element.classList.add('is-visible'));
}
