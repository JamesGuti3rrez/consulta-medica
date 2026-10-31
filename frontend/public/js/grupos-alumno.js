(() => {
  const $ = id => document.getElementById(id);
  const node = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; };
  const labels = { sin_iniciar: 'Por comenzar', en_curso: 'En curso', finalizada: 'Finalizada' };
  let version = 0, accountId = null;
  async function load() {
    const current = ++version;
    $('refresh-student-groups').disabled = true;
    $('student-groups-status').hidden = false; $('student-groups-status').textContent = 'Cargando tus actividades…';
    try {
      const profile = await window.auth.profile();
      if (current !== version) return;
      accountId = profile.id; $('student-account').textContent = profile.email;
      const { grupos } = await (await window.auth.api('/api/grupos/mios')).json();
      if (current !== version) return;
      $('student-groups-list').replaceChildren(...grupos.map(group => {
        const section = node('section', 'panel student-group-card'); section.append(node('h2', '', group.nombre), node('p', 'group-subtitle', group.descripcion));
        const grid = node('div', 'student-activities');
        for (const activity of group.actividades) {
          const card = node('article', 'student-activity'); card.append(node('span', 'group-state ' + activity.estado, labels[activity.estado]), node('h3', '', activity.titulo));
          if (!activity.activa) card.append(node('small', 'muted', 'Actividad cerrada · Puedes consultar o continuar tu entrega existente.'));
          const link = node('a', 'button secondary', activity.estado === 'finalizada' ? 'Ver mi resultado' : activity.estado === 'en_curso' ? 'Continuar caso' : 'Resolver caso');
          link.href = 'simulacion.html?actividad=' + encodeURIComponent(activity.id); card.append(link); grid.append(card);
        }
        if (!group.actividades.length) grid.append(node('p', 'group-subtitle', 'El doctor aún no ha asignado actividades.'));
        section.append(grid); return section;
      }));
      $('student-groups-status').textContent = grupos.length ? 'Solo se muestran tus grupos y tus propias actividades.' : 'Aún no perteneces a un grupo. Pide al doctor que añada el correo de tu cuenta.';
      $('refresh-student-groups').hidden = false; $('groups-login').hidden = true;
    } catch (e) {
      if (current !== version) return;
      $('student-groups-list').replaceChildren(); $('student-groups-status').textContent = e.message;
      $('groups-login').hidden = e.status !== 401 && e.message !== 'Inicia sesión para continuar.';
    } finally { $('refresh-student-groups').disabled = false; }
  }
  window.auth.ready.then(client => client?.auth.onAuthStateChange((event, session) => {
    if (event === 'SIGNED_OUT' || !session) {
      version += 1; accountId = null;
      $('student-groups-list').replaceChildren(); $('student-account').textContent = '';
      $('student-groups-status').hidden = false; $('student-groups-status').textContent = 'Inicia sesión para consultar tus grupos.';
      $('groups-login').hidden = false; $('refresh-student-groups').hidden = true;
    } else if (accountId && session.user?.id !== accountId) {
      $('student-groups-list').replaceChildren(); $('student-account').textContent = ''; load();
    }
  }));
  $('refresh-student-groups').addEventListener('click', load); load();
})();
