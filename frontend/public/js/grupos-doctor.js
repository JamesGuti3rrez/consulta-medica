/* HU-014: el servidor verifica identidad, ownership y métricas; la interfaz solo las presenta. */
(() => {
  const $ = id => document.getElementById(id);
  const node = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; };
  const api = async (path, options = {}) => (await window.auth.api('/api/grupos' + path, options)).json();
  const send = (path, body, method = 'POST') => api(path, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const error = message => { $('groups-status').textContent = message; $('groups-status').hidden = !message; $('groups-status').classList.toggle('is-error', Boolean(message)); };
  const date = value => value ? new Date(value).toLocaleString('es-PE') : '—';
  const time = value => value == null ? '—' : `${Math.floor(value / 60)} min ${Math.round(value % 60)} s`;
  const grade = value => value == null ? '—' : `${Number(value.toFixed(2))}/100`;
  const STATE = { sin_iniciar: 'Sin iniciar', en_curso: 'En curso', finalizada: 'Finalizada', pendiente_revision: 'Revisión pendiente', correct: 'Correcto', incorrect: 'Incorrecto', empty: 'Sin respuesta', ambiguous: 'Ambiguo' };
  let selected = null, detail = null, catalog = null, version = 0, listVersion = 0, ready = false, loading = null;

  async function run(button, work) {
    const text = button.textContent; button.disabled = true; button.textContent = 'Procesando…'; error('');
    try { await work(); } catch (e) { error(e.message); } finally { button.disabled = false; button.textContent = text; }
  }
  function field(label, control) { const wrapper = node('label', 'group-field', label); wrapper.append(control); return wrapper; }
  function input(id, placeholder, max) { const n = node('input'); n.id = id; n.placeholder = placeholder; n.maxLength = max; n.required = true; return n; }

  async function loadGroups(selectId = selected) {
    const current = ++listVersion;
    const data = await api('/doctor');
    if (current !== listVersion) return;
    $('group-list').replaceChildren(...data.grupos.map(group => {
      const button = node('button', 'group-card' + (group.id === selectId ? ' is-selected' : ''));
      button.type = 'button'; button.dataset.groupId = group.id;
      button.append(node('strong', '', group.nombre), node('small', '', `${group.alumnos} ${group.alumnos === 1 ? 'alumno' : 'alumnos'} · ${group.actividades} ${group.actividades === 1 ? 'actividad' : 'actividades'}`));
      button.addEventListener('click', () => selectGroup(group.id));
      return button;
    }));
    if (!data.grupos.length) $('group-list').append(node('p', 'group-subtitle', 'Tus grupos aparecerán aquí.'));
    if (selectId && data.grupos.some(g => g.id === selectId)) await selectGroup(selectId);
  }
  function fillCases(picker) {
    const value = picker.value;
    picker.replaceChildren(new Option('Selecciona un caso…', ''), ...(catalog || []).map(c => new Option(c.case_id + ' · ' + c.paciente.alias, c.case_id)));
    picker.value = value;
  }
  async function selectGroup(id) {
    selected = id; const current = ++version;
    $('group-list').querySelectorAll('button').forEach(b => b.classList.toggle('is-selected', b.dataset.groupId === id));
    $('group-detail').setAttribute('aria-busy', 'true');
    try {
      const data = await api('/doctor/' + encodeURIComponent(id));
      if (version !== current) return;
      detail = data; renderDetail(data);
    } catch (e) { if (version === current) error(e.message); }
    finally { if (version === current) $('group-detail').setAttribute('aria-busy', 'false'); }
  }
  function renderDetail(data) {
    const target = $('group-detail'); target.replaceChildren();
    const header = node('section', 'panel');
    header.append(node('span', 'eyebrow', 'GRUPO DE APRENDIZAJE'), node('h2', '', data.grupo.nombre), node('p', 'group-subtitle', data.grupo.descripcion || 'Aprendemos resolviendo casos juntos.'));
    const edit = node('details'); edit.append(node('summary', '', 'Editar nombre y descripción'));
    const editForm = node('form', 'group-form');
    const name = input('edit-group-name', 'Nombre del grupo', 100); name.value = data.grupo.nombre;
    const description = node('textarea'); description.maxLength = 1000; description.value = data.grupo.descripcion; description.rows = 2;
    const save = node('button', 'button secondary', 'Guardar cambios'); save.type = 'submit';
    editForm.append(field('Nombre', name), field('Descripción', description), save);
    editForm.addEventListener('submit', e => { e.preventDefault(); run(save, async () => {
      await send('/doctor/' + data.grupo.id, { nombre: name.value, descripcion: description.value }, 'PATCH'); await loadGroups(data.grupo.id);
    }); });
    edit.append(editForm); header.append(edit); target.append(header);

    const members = node('section', 'panel'); members.append(node('h3', '', 'Alumnos del grupo'), node('p', 'group-subtitle', 'Incorpora una cuenta registrada por su correo. El alumno deberá iniciar sesión para resolver las actividades.'));
    const form = node('form', 'group-inline'); const email = input('member-email', 'alumno@universidad.edu.pe', 254); email.type = 'email';
    const add = node('button', 'button primary', 'Añadir alumno'); add.type = 'submit';
    form.append(field('Correo del alumno', email), add);
    form.addEventListener('submit', e => { e.preventDefault(); run(add, async () => {
      await send('/doctor/' + data.grupo.id + '/miembros', { email: email.value }); await loadGroups(data.grupo.id);
    }); });
    members.append(form);
    const list = node('ul', 'group-member-list');
    for (const member of data.miembros) {
      const item = node('li', 'group-member' + (!member.activo ? ' is-inactive' : ''));
      const identity = node('div'); identity.append(node('strong', '', member.nombre || member.email), node('small', '', member.email)); item.append(identity);
      if (member.activo) {
        const remove = node('button', 'quiet', 'Retirar'); remove.type = 'button'; remove.setAttribute('aria-label', 'Retirar a ' + member.email);
        remove.addEventListener('click', () => {
          if (!window.confirm(`¿Retirar a ${member.email}? Se conservarán sus resultados y perderá acceso a las actividades del grupo.`)) return;
          run(remove, async () => { await api('/doctor/' + data.grupo.id + '/miembros/' + member.alumno_id, { method: 'DELETE' }); await loadGroups(data.grupo.id); });
        }); item.append(remove);
      } else item.append(node('span', 'group-state', 'Retirado'));
      list.append(item);
    }
    if (!data.miembros.length) list.append(node('li', 'group-subtitle', 'Aún no hay alumnos. Puedes asignar casos ahora e incorporarlos después.'));
    members.append(list); target.append(members);

    const activities = node('section', 'panel'); activities.append(node('h3', '', 'Asigna una experiencia clínica'));
    const assignForm = node('form', 'group-form'); const picker = node('select'); picker.id = 'assign-case'; picker.required = true;
    fillCases(picker);
    const title = input('assignment-title', 'Ej. Reto de evaluación inicial', 150);
    const assign = node('button', 'button primary', 'Asignar caso al grupo'); assign.type = 'submit';
    assignForm.append(field('Caso curado', picker), field('Título para el alumno · evita revelar la solución', title), assign);
    assignForm.addEventListener('submit', e => { e.preventDefault(); run(assign, async () => {
      await send('/doctor/' + data.grupo.id + '/actividades', { casos: [{ case_id: picker.value, titulo: title.value }] }); await loadGroups(data.grupo.id);
    }); });
    activities.append(assignForm); target.append(activities);

    const comparison = node('section', 'panel'); comparison.append(node('h3', '', 'Seguimiento y comparativa'));
    const activityPicker = node('select'); activityPicker.id = 'activity-filter';
    for (const a of data.actividades) activityPicker.append(new Option(a.titulo + ' · ' + a.case_id, a.id));
    const last = sessionStorage.getItem('grupo-actividad:' + data.grupo.id);
    if (data.actividades.some(a => a.id === last)) activityPicker.value = last;
    const result = node('div'); result.id = 'group-results';
    comparison.append(field('Comparar la misma actividad', activityPicker), result);
    activityPicker.addEventListener('change', () => {
      sessionStorage.setItem('grupo-actividad:' + data.grupo.id, activityPicker.value); renderResults(result, data.actividades.find(a => a.id === activityPicker.value));
    });
    renderResults(result, data.actividades.find(a => a.id === activityPicker.value));
    target.append(comparison);
  }

  function renderResults(target, activity) {
    target.replaceChildren();
    if (!activity) { target.append(node('p', 'group-subtitle', 'Asigna el primer caso para empezar a acompañar al grupo.')); return; }
    const top = node('div', 'section-row');
    top.append(node('p', 'group-subtitle', activity.activa ? 'Actividad abierta · Una entrega por alumno' : 'Actividad cerrada · Se conservan las consultas iniciadas'));
    const toggle = node('button', 'quiet', activity.activa ? 'Cerrar actividad' : 'Reabrir actividad'); toggle.type = 'button';
    toggle.addEventListener('click', () => run(toggle, async () => {
      await send('/doctor/actividades/' + activity.id, { activa: !activity.activa }, 'PATCH'); await selectGroup(selected);
    })); top.append(toggle); target.append(top);
    const s = activity.resumen, stats = node('div', 'group-stats');
    for (const [label, value, note] of [
      ['Entregas', `${s.finalizados}/${s.asignados}`, 'alumnos activos'],
      ['Acierto diagnóstico', s.tasa_acierto == null ? '—' : s.tasa_acierto + '%', `${s.aciertos}/${s.entregas_evaluadas} entregas evaluadas`],
      ['Tiempo promedio', time(s.tiempo_promedio_segundos), 'entregas finalizadas'],
      ['Revisión pendiente', s.pendientes_revision, 'entregas ambiguas o sin calificar'],
    ]) { const card = node('article', 'group-stat'); card.append(node('span', '', label), node('strong', '', value), node('small', '', note)); stats.append(card); }
    target.append(stats);
    const scroll = node('div', 'table-scroll'), table = node('table', 'group-comparison');
    const caption = node('caption', 'sr-only', 'Resultados individuales para ' + activity.titulo); table.append(caption);
    const head = node('thead'), hr = node('tr');
    for (const label of ['Alumno', 'Estado', 'Diagnóstico entregado', 'Acierto', 'Tiempo', 'Diagnóstico', 'Proceso']) { const th = node('th', '', label); th.scope = 'col'; hr.append(th); }
    head.append(hr); table.append(head); const body = node('tbody');
    for (const row of activity.resultados) {
      const tr = node('tr'); tr.dataset.studentId = row.alumno_id;
      const identity = node('td'); identity.append(node('strong', '', row.nombre), node('small', '', row.email + (!row.miembro_activo ? ' · Retirado' : ''))); tr.append(identity);
      const state = node('td'); state.append(node('span', 'group-state ' + row.estado, STATE[row.estado])); tr.append(state);
      const diagnosis = node('td', '', row.diagnostico == null ? '—' : row.diagnostico || 'Sin respuesta');
      if (row.motivo) diagnosis.append(node('small', '', row.motivo)); tr.append(diagnosis);
      const accuracy = node('td'); if (row.acierto) accuracy.append(node('span', 'group-state ' + row.acierto, STATE[row.acierto] || 'Revisar')); else accuracy.textContent = '—'; tr.append(accuracy);
      const elapsed = node('td', '', time(row.duracion_segundos)); elapsed.title = `Inicio: ${date(row.iniciado_en)} · Entrega: ${date(row.finalizado_en)}`; tr.append(elapsed);
      for (const score of [row.puntaje_diagnostico, row.puntaje_proceso]) {
        const cell = node('td', '', grade(score)); if (score != null) { const track = node('div', 'group-score-track'), bar = node('i'); bar.style.width = Math.min(100, Math.max(0, score)) + '%'; track.append(bar); cell.append(track); } tr.append(cell);
      }
      body.append(tr);
    }
    table.append(body); scroll.append(table); target.append(scroll);
    if (!activity.resultados.length) target.append(node('p', 'group-subtitle', 'Incorpora alumnos para activar el seguimiento.'));
    target.append(node('p', 'group-rules', 'Tiempo total transcurrido, incluidas pausas. Diagnóstico y proceso tienen notas independientes. Los pendientes de revisión no se cuentan como errores definitivos; los alumnos sin entregar no reciben un cero. Los retirados se conservan como historial y se excluyen de los promedios.'));
    target.append(node('p', 'group-subtitle', `Promedio diagnóstico: ${grade(s.puntaje_diagnostico_promedio)} · Promedio del proceso: ${grade(s.puntaje_proceso_promedio)}`));
  }

  $('show-groups').addEventListener('click', async () => {
    $('catalog-workspace').hidden = true; $('groups-workspace').hidden = false;
    $('show-groups').classList.add('is-current'); $('show-catalog').classList.remove('is-current');
    $('show-groups').setAttribute('aria-pressed', 'true'); $('show-catalog').setAttribute('aria-pressed', 'false');
    if (!ready || loading) return;
    error(''); $('group-list').setAttribute('aria-busy', 'true');
    loading = (async () => {
      // El catálogo puede demorar o fallar sin impedir consultar los grupos vacíos.
      const results = await Promise.allSettled([
        loadGroups(),
        (async () => {
          if (!catalog) catalog = (await (await window.auth.api('/api/docente/casos')).json()).casos;
          const picker = $('assign-case'); if (picker) fillCases(picker);
        })(),
      ]);
      for (const result of results) if (result.status === 'rejected') error(result.reason.message);
      $('group-list').setAttribute('aria-busy', 'false'); loading = null;
    })(); await loading;
  });
  $('show-catalog').addEventListener('click', () => {
    $('groups-workspace').hidden = true; $('catalog-workspace').hidden = false;
    $('show-catalog').classList.add('is-current'); $('show-groups').classList.remove('is-current');
    $('show-catalog').setAttribute('aria-pressed', 'true'); $('show-groups').setAttribute('aria-pressed', 'false');
  });
  $('refresh-groups').addEventListener('click', e => run(e.currentTarget, () => loadGroups()));
  $('create-group-form').addEventListener('submit', e => { e.preventDefault(); run(e.submitter, async () => {
    const created = await send('/doctor', { nombre: $('group-name').value, descripcion: $('group-description').value });
    $('create-group-form').reset(); await loadGroups(created.id);
  }); });
  function onDoctorReady() {
    if (ready) return;
    ready = true;
    if (!$('groups-workspace').hidden || new URLSearchParams(location.search).get('seccion') === 'grupos') $('show-groups').click();
  }
  document.addEventListener('doctor:ready', onDoctorReady);
  if (window.doctorProfile?.panel_docente) onDoctorReady();
})();
