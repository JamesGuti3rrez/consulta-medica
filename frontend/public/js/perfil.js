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
    const existingLink = document.querySelector('[data-role="teacher-panel"]');
    if (existingLink) existingLink.hidden = true;
    if (signedIn) window.setTimeout(async () => {
      try {
        const profile = await window.auth.profile();
        if (!profile.panel_docente || profile.id !== user.id || !menu) return;
        let link = document.querySelector('[data-role="teacher-panel"]');
        if (!link) {
          link = document.createElement('a');
          link.dataset.role = 'teacher-panel';
          link.className = 'menu-item';
          link.href = 'docente.html';
          link.textContent = 'Panel docente';
          menu.querySelector('[data-role="logout"]')?.parentElement.before(link);
        }
        link.hidden = false;
      } catch {
        // El enlace se ofrece solo tras verificar permisos en el servidor.
      }
    }, 0);
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

  // Mis simulaciones: las consultas guardadas del alumno. Supabase solo le entrega las suyas (RLS).
  // No se muestra el código del caso, igual que en el simulador.
  const SPECIALTIES = {
    emergencias: 'Emergencias',
    medicina_interna: 'Medicina interna',
    pediatria: 'Pediatría',
    ginecologia_obstetricia: 'Ginecología y obstetricia',
    cirugia_general: 'Cirugía general',
  };
  let history = null;

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function buildHistory() {
    const overlay = element('div', 'history-overlay');
    overlay.hidden = true;
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-labelledby', 'history-title');
    overlay.dataset.role = 'history-dialog';
    const panel = element('div', 'history-panel');
    const header = element('div', 'history-header');
    const titles = element('div');
    const title = element('h2', 'history-title', 'Mis simulaciones');
    title.id = 'history-title';
    const subtitle = element('p', 'history-subtitle', 'Tus consultas guardadas, de la más reciente a la más antigua. ');
    const privacy = element('a', 'history-privacy', 'Aviso de privacidad');
    privacy.href = 'privacidad.html';
    subtitle.append(privacy);
    titles.append(title, subtitle);
    const close = element('button', 'history-close');
    close.type = 'button';
    close.setAttribute('aria-label', 'Cerrar');
    close.append(element('span', 'material-symbols-outlined', 'close'));
    header.append(titles, close);
    const status = element('p', 'history-status');
    status.setAttribute('aria-live', 'polite');
    const list = element('ul', 'history-list');
    panel.append(header, status, list);
    overlay.append(panel);
    document.body.append(overlay);

    const hide = () => {
      overlay.hidden = true;
      toggle?.focus();
    };
    close.addEventListener('click', hide);
    overlay.addEventListener('click', (event) => { if (event.target === overlay) hide(); });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && !overlay.hidden) hide();
    });
    return { overlay, close, status, list };
  }

  function historyItem(attempt) {
    const item = element('li', 'history-item');
    const top = element('div', 'history-row');
    const date = new Date(attempt.creado_en).toLocaleDateString('es-PE', {
      day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit',
    });
    const heading = element('div');
    heading.append(
      element('p', 'history-specialty', SPECIALTIES[attempt.especialidad] || 'Consulta'),
      element('p', 'history-date', date),
    );
    top.append(heading, element('span', 'history-score', `${attempt.puntaje}%`));
    item.append(top);
    if (attempt.diagnostico) item.append(element('p', 'history-detail', `Diagnóstico: ${attempt.diagnostico}`));
    const report = attempt.reporte || {};
    const facts = [];
    if (report.total_questions) facts.push(`${report.completed_questions} de ${report.total_questions} datos clave`);
    if (attempt.duracion_segundos) facts.push(`${Math.max(1, Math.round(attempt.duracion_segundos / 60))} min`);
    if (report.safety_alerts?.length) facts.push('con alerta de seguridad');
    if (facts.length) item.append(element('p', 'history-facts', facts.join(' · ')));
    return item;
  }

  async function openHistory() {
    closeMenu();
    history ??= buildHistory();
    history.list.replaceChildren();
    history.status.textContent = 'Cargando tus simulaciones...';
    history.overlay.hidden = false;
    history.close.focus();
    const client = await window.auth.ready;
    const { data, error } = client
      ? await client.from('intentos')
        .select('creado_en, especialidad, puntaje, diagnostico, duracion_segundos, reporte')
        .order('creado_en', { ascending: false })
        .limit(50)
      : { data: null, error: true };
    if (error) {
      history.status.textContent = 'No se pudieron cargar tus simulaciones. Revisa tu conexión e inténtalo de nuevo.';
      return;
    }
    history.status.textContent = data.length
      ? `${data.length} ${data.length === 1 ? 'consulta guardada' : 'consultas guardadas'}.`
      : 'Aún no tienes simulaciones guardadas. Termina una consulta con tu sesión iniciada y aparecerá aquí.';
    history.list.replaceChildren(...data.map(historyItem));
  }

  // El menú solo ofrece «Mis simulaciones» si el servidor guarda el historial.
  const historyButtons = [...document.querySelectorAll('[data-role="open-history"]')];
  historyButtons.forEach((button) => {
    button.hidden = true;
    button.addEventListener('click', openHistory);
  });
  window.auth.historyEnabled.then((enabled) => {
    historyButtons.forEach((button) => { button.hidden = !enabled; });
  });

  window.auth.ready.then(async (client) => {
    if (!client) return;
    const { data } = await client.auth.getSession();
    renderSession(data.session?.user);
    client.auth.onAuthStateChange((_event, session) => renderSession(session?.user));
  });
})();
