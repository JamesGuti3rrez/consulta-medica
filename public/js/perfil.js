// Encabezado con la sesión, compartido por la portada y la simulación:
// botón para invitados, menú de perfil (tema claro u oscuro y cerrar sesión).
// Requiere auth.js. El tema guardado ya se aplicó en el <head> antes de pintar la página.
(() => {
  const guest = document.querySelector('[data-role="auth-guest"]');
  const account = document.querySelector('[data-role="auth-user"]');
  const toggle = document.querySelector('[data-role="profile-toggle"]');
  const menu = document.querySelector('[data-role="profile-menu"]');
  const themeButtons = [...document.querySelectorAll('[data-theme-option]')];

  const fill = (role, text) => {
    document.querySelectorAll(`[data-role="${role}"]`).forEach((element) => {
      element.textContent = text;
    });
  };

  function renderSession(user) {
    const signedIn = Boolean(user);
    if (guest) guest.hidden = signedIn;
    if (account) account.hidden = !signedIn;
    if (!signedIn) {
      closeMenu();
      return;
    }
    const name = window.auth.displayName(user);
    fill('user-initial', name.charAt(0).toUpperCase());
    fill('menu-initial', name.charAt(0).toUpperCase());
    fill('user-name', name);
    fill('menu-name', name);
    fill('menu-email', user.email || '');
  }

  // Menú: se abre con el botón y se cierra al hacer clic fuera, con Escape o al cerrar sesión.
  function closeMenu(restoreFocus = false) {
    if (!menu || menu.hidden) return;
    menu.hidden = true;
    toggle?.setAttribute('aria-expanded', 'false');
    if (restoreFocus) toggle?.focus();
  }

  toggle?.addEventListener('click', () => {
    const opening = menu.hidden;
    menu.hidden = !opening;
    toggle.setAttribute('aria-expanded', String(opening));
  });

  document.addEventListener('click', (event) => {
    if (!menu || menu.hidden) return;
    if (!menu.contains(event.target) && !toggle.contains(event.target)) closeMenu();
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && menu && !menu.hidden) closeMenu(true);
  });

  document.querySelector('[data-role="logout"]')?.addEventListener('click', async () => {
    closeMenu();
    const client = await window.auth.ready;
    await client?.auth.signOut();
  });

  // Tema: claro, oscuro o el del sistema. Se recuerda en este navegador y vale para todas las páginas.
  function applyTheme(theme) {
    if (theme === 'system') delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = theme;
    try {
      if (theme === 'system') localStorage.removeItem('tema');
      else localStorage.setItem('tema', theme);
    } catch {
      // Sin almacenamiento el tema dura hasta recargar la página.
    }
    themeButtons.forEach((button) => {
      button.setAttribute('aria-checked', String(button.dataset.themeOption === theme));
    });
  }

  themeButtons.forEach((button) => {
    button.addEventListener('click', () => applyTheme(button.dataset.themeOption));
  });
  applyTheme(document.documentElement.dataset.theme || 'system');

  window.auth.ready.then(async (client) => {
    if (!client) return;
    const { data } = await client.auth.getSession();
    renderSession(data.session?.user);
    client.auth.onAuthStateChange((_event, session) => renderSession(session?.user));
  });
})();
