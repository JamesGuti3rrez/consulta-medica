// Ventanas de la portada: elegir caso, iniciar sesión y crear cuenta.
const dialogs = {
  case: document.querySelector('[data-role="case-picker-panel"]'),
  login: document.querySelector('[data-role="login-panel"]'),
  signup: document.querySelector('[data-role="signup-panel"]')
};
const casePickerForm = document.querySelector('[data-role="case-picker"]');
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

const unavailableMessage = 'El inicio de sesión no está disponible en este momento. Puedes practicar sin cuenta.';

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

// El encabezado lo maneja perfil.js; aquí solo lo propio de la portada.
function renderSession(user) {
  const signedIn = Boolean(user);
  const guestNote = document.querySelector('[data-role="guest-note"]');
  if (guestNote) guestNote.hidden = signedIn;
  if (!signedIn) return;

  // La ventana de elección de caso ya conoce al alumno.
  const meta = user.user_metadata || {};
  const { nombres, apellidos } = casePickerForm.elements;
  if (!nombres.value && meta.nombres) nombres.value = meta.nombres;
  if (!apellidos.value && meta.apellidos) apellidos.value = meta.apellidos;
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

window.auth.ready.then(async (client) => {
  if (!client) return;
  const { data } = await client.auth.getSession();
  renderSession(data.session?.user);
  client.auth.onAuthStateChange((_event, session) => renderSession(session?.user));
});

// Enlaces que abren una ventana al llegar: ?nuevo=1 (elegir caso) y ?cuenta=login (desde la simulación).
const params = new URLSearchParams(window.location.search);
const dialogFromUrl = params.get('nuevo') === '1' ? 'case' : { login: 'login', registro: 'signup' }[params.get('cuenta')];
if (dialogFromUrl) {
  window.history.replaceState(null, '', window.location.pathname);
  window.setTimeout(() => showDialog(dialogFromUrl), 300);
}

// Los nombres quedan en la sesión del navegador; en la URL solo viaja la especialidad.
casePickerForm.addEventListener('submit', (event) => {
  event.preventDefault();
  const { nombres, apellidos, especialidad } = casePickerForm.elements;
  const student = { nombres: nombres.value.trim(), apellidos: apellidos.value.trim() };

  if (!student.nombres || !student.apellidos) {
    (student.nombres ? apellidos : nombres).focus();
    return;
  }

  try {
    sessionStorage.setItem('estudiante', JSON.stringify(student));
  } catch {
    // Sin almacenamiento disponible la simulación funciona igual, solo sin el nombre.
  }
  window.location.href = `simulacion.html?especialidad=${encodeURIComponent(especialidad.value)}`;
});

// Diálogo de muestra en la portada: recorre algunos turnos del guion del caso de demostración.
const demoTurns = [
  ['¿Dónde le duele y desde cuándo empezó?',
    'Empezó ayer alrededor del ombligo y ahora me duele más abajo, a la derecha.'],
  ['¿Ha tenido fiebre, náuseas o vómitos?',
    'Anoche tuve fiebre y vomité una vez. Desde entonces no tengo hambre.'],
  ['¿El dolor aumenta al caminar o al toser?',
    'Sí, cuando camino o toso me duele mucho más.'],
  ['¿Ha tomado algo para el dolor?',
    'Solo una pastilla para los gases, pero no me hizo nada.']
];
const demoDoctorBubble = document.querySelector('[data-role="demo-doctor-bubble"]');
const demoPatientBubble = document.querySelector('[data-role="demo-patient-bubble"]');
const demoDoctorText = document.querySelector('[data-role="demo-doctor"]');
const demoPatientText = document.querySelector('[data-role="demo-patient"]');
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
const DEMO_READ_TIME = 6500;
const DEMO_FADE_TIME = 500;
const DEMO_REPLY_DELAY = 1200;
let demoTurn = 0;

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function showNextDemoTurn() {
  demoDoctorBubble.classList.add('is-hidden');
  demoPatientBubble.classList.add('is-hidden');
  await wait(DEMO_FADE_TIME);

  demoTurn = (demoTurn + 1) % demoTurns.length;
  const [question, answer] = demoTurns[demoTurn];
  demoDoctorText.textContent = question;
  demoPatientText.textContent = answer;

  demoDoctorBubble.classList.remove('is-hidden');
  await wait(DEMO_REPLY_DELAY);
  demoPatientBubble.classList.remove('is-hidden');
}

async function runDemoConversation() {
  while (true) {
    await wait(DEMO_READ_TIME);
    // Con la pestaña oculta o con movimiento reducido el diálogo se queda en el turno actual.
    if (document.hidden || reducedMotion.matches) continue;
    await showNextDemoTurn();
  }
}

if (demoDoctorBubble && demoPatientBubble) runDemoConversation();

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
