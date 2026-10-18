/* Panel docente: los documentos y las evidencias se consultan mediante la API autorizada. */
(() => {
  const $ = id => document.getElementById(id);
  const SPECIALTIES = {
    medicina_interna: 'Medicina interna', pediatria: 'Pediatría', ginecologia_obstetricia: 'Ginecología y obstetricia',
    cirugia_general: 'Cirugía general', emergencias: 'Emergencias',
  };
  const OWNERS = { public: 'Presentación pública', paciente: 'Paciente', medico_asistente: 'Médico asistente',
    laboratorio: 'Laboratorio', radiologia: 'Radiología', especialista: 'Especialista' };
  const AREA_ICONS = { medicina_interna: 'medicine', pediatria: 'pediatrics',
    ginecologia_obstetricia: 'women', cirugia_general: 'surgery', emergencias: 'emergency' };
  let catalog = [], specialty = '', preview = null, selected = null, detailVersion = 0, busyImport = false;
  let catalogLoad = null;
  let syncingCatalog = false;
  const node = (tag, className, text) => {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  };
  const icon = name => {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', 'icon');
    svg.setAttribute('aria-hidden', 'true');
    svg.setAttribute('focusable', 'false');
    const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
    use.setAttribute('href', 'assets/docente-icons.svg#' + name);
    svg.append(use);
    return svg;
  };
  const initials = name => name.trim().split(/\s+/).filter(Boolean).slice(0, 2).map(part => part.charAt(0)).join('').toLocaleUpperCase('es');
  $('panel-date').textContent = new Date().toLocaleDateString('es-PE', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'America/Lima' });
  const themeToggle = $('toggle-panel-theme');
  const renderPanelTheme = () => {
    const dark = document.documentElement.dataset.theme === 'dark';
    themeToggle.setAttribute('aria-pressed', String(dark));
    themeToggle.setAttribute('aria-label', dark ? 'Cambiar a vista clara' : 'Cambiar a vista oscura');
    themeToggle.title = dark ? 'Cambiar a vista clara' : 'Cambiar a vista oscura';
    themeToggle.replaceChildren(icon(dark ? 'moon' : 'sun'), node('span', '', dark ? 'Oscuro' : 'Claro'));
  };
  themeToggle.addEventListener('click', () => {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem('tema-docente', next); } catch { /* Conserva el cambio durante esta visita. */ }
    renderPanelTheme();
  });
  renderPanelTheme();
  const notice = (id, message, error = false) => {
    const element = $(id);
    element.textContent = message;
    element.classList.toggle('is-error', error);
    element.hidden = !message;
  };
  const json = async (path, options) => (await window.auth.api(path, options)).json();
  const post = (path, payload) => json(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  const busy = async (button, label, work) => {
    const previous = [...button.childNodes];
    button.disabled = true; button.textContent = label;
    try { return await work(); } finally { button.disabled = false; button.replaceChildren(...previous); }
  };
  const block = (title, text) => {
    const section = node('div', 'field-block');
    section.append(node('h3', '', title), node('p', '', text));
    return section;
  };

  function renderCatalog() {
    const query = $('case-search').value.trim().toLocaleLowerCase('es');
    const cases = catalog.filter(item => (!specialty || item.especialidad === specialty) &&
      [item.case_id, item.titulo, item.paciente.alias, item.diagnostico].join(' ').toLocaleLowerCase('es').includes(query));
    $('catalog-title').textContent = SPECIALTIES[specialty] || 'Todos los casos';
    $('catalog-count').textContent = cases.length + (cases.length === 1 ? ' caso disponible' : ' casos disponibles');
    $('empty-catalog').hidden = cases.length > 0;
    $('case-list').replaceChildren(...cases.map(item => {
      const row = node('tr');
      row.dataset.specialty = item.especialidad;
      const patient = node('td');
      const identity = node('div', 'patient-cell');
      const avatar = node('span', 'patient-avatar', initials(item.paciente.alias));
      avatar.setAttribute('aria-hidden', 'true');
      const info = node('div', 'patient-info');
      info.append(node('strong', '', item.paciente.alias), node('small', '', item.case_id + ' · ' + item.paciente.age_years + ' años'));
      identity.append(avatar, info); patient.append(identity);
      const area = node('td');
      area.append(node('span', 'specialty-pill', SPECIALTIES[item.especialidad] || item.especialidad));
      const evidence = node('td');
      const count = node('span', 'evidence-count');
      count.append(icon('layers'), node('span', '', String(item.evidencias)));
      evidence.append(count);
      const actions = node('td');
      const open = node('button', 'text-button case-open', 'Ver ficha');
      open.append(icon('arrow'));
      open.setAttribute('aria-label', 'Ver caso de ' + item.paciente.alias);
      open.addEventListener('click', () => openCase(item.case_id));
      actions.append(open); row.append(patient, area, evidence, actions);
      return row;
    }));
  }
  async function fetchCatalog() {
    let data;
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        data = await json('/api/docente/casos');
        break;
      } catch (error) {
        // Reintentar únicamente esta lectura si falló la conexión o el servidor.
        // Una sesión inválida o la falta de permisos requieren atención del usuario.
        const transient = error instanceof TypeError || error.status >= 500;
        if (attempt > 0 || !transient) throw error;
        await new Promise(resolve => window.setTimeout(resolve, 600));
      }
    }
    catalog = data.casos;
    $('total-cases').textContent = data.total;
    $('total-specialties').textContent = Object.keys(data.por_especialidad).length;
    $('rag-mode').textContent = data.rag_backend === 'supabase_pgvector' ? 'Supabase pgvector' : 'Evidencia del caso';
    $('rag-mode-note').textContent = data.rag_backend === 'supabase_pgvector'
      ? 'Búsqueda vectorial activa en el simulador' : 'El índice pgvector se muestra por separado';
    const options = [['', 'Todos los casos', data.total], ...Object.entries(SPECIALTIES).map(([key, label]) => [key, label, data.por_especialidad[key] || 0])];
    $('specialty-filters').replaceChildren(...options.map(([key, label, count]) => {
      const button = node('button', 'specialty-button');
      button.dataset.specialty = key;
      button.setAttribute('aria-pressed', String(key === specialty));
      button.setAttribute('aria-label', label + ' ' + count);
      const symbol = node('span', 'specialty-symbol'); symbol.append(icon(AREA_ICONS[key] || 'all'));
      button.append(symbol, node('span', 'specialty-name', label), node('span', 'specialty-count', String(count)));
      button.addEventListener('click', () => {
        specialty = key;
        for (const sibling of $('specialty-filters').children) sibling.setAttribute('aria-pressed', String(sibling === button));
        renderCatalog();
      });
      return button;
    }));
    renderCatalog();
    notice('notice', '');
    if (data.case_store !== 'supabase') notice('notice', 'El panel muestra Supabase, pero el simulador está configurado con casos locales. Activa CASE_STORE=supabase para usar los casos publicados.');
  }

  function loadCatalog() {
    if (catalogLoad) return catalogLoad;
    const button = $('refresh');
    button.disabled = true;
    button.textContent = 'Cargando…';
    $('catalog-panel').setAttribute('aria-busy', 'true');
    $('catalog-count').textContent = 'Cargando casos desde Supabase…';
    $('empty-catalog').hidden = true;
    catalogLoad = fetchCatalog().catch(error => {
      $('catalog-count').textContent = 'No se pudo cargar el catálogo.';
      throw error;
    }).finally(() => {
      catalogLoad = null;
      button.disabled = false;
      button.textContent = 'Actualizar';
      $('catalog-panel').setAttribute('aria-busy', 'false');
    });
    return catalogLoad;
  }

  function selectPane(name) {
    document.querySelectorAll('[data-pane]').forEach(tab => {
      const active = tab.dataset.pane === name;
      tab.setAttribute('aria-selected', String(active)); tab.tabIndex = active ? 0 : -1;
      $('pane-' + tab.dataset.pane).hidden = !active;
    });
  }
  document.querySelectorAll('[data-pane]').forEach(tab => {
    tab.addEventListener('click', () => selectPane(tab.dataset.pane));
    tab.addEventListener('keydown', event => {
      const tabs = [...document.querySelectorAll('[data-pane]')];
      const index = tabs.indexOf(tab);
      const next = event.key === 'ArrowRight' ? (index + 1) % tabs.length
        : event.key === 'ArrowLeft' ? (index + tabs.length - 1) % tabs.length
        : event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : null;
      if (next !== null) { event.preventDefault(); selectPane(tabs[next].dataset.pane); tabs[next].focus(); }
    });
  });
  function renderEvidence() {
    if (!selected) return;
    const owner = $('owner-filter').value;
    const rows = selected.evidencias_rag.filter(item => !owner || item.owner === owner);
    $('evidence-list').replaceChildren(...rows.map(item => {
      const card = node('article', 'evidence-card');
      card.dataset.owner = item.owner;
      const header = node('header');
      header.append(node('strong', '', item.evidence_id), node('span', 'badge', OWNERS[item.owner] || item.owner));
      card.append(header, node('p', '', item.content),
        node('small', '', 'Categoría: ' + item.category + ' · Se revela con: ' + (item.requires?.join(', ') || 'presentación inicial')),
        node('small', '', 'Embedding: ' + item.embedding_model + ' · Actualizado: ' + new Date(item.updated_at).toLocaleString('es-PE')));
      return card;
    }));
    if (!rows.length) $('evidence-list').append(node('p', 'empty', 'No hay evidencias indexadas para este filtro.'));
  }
  function renderDetail(data) {
    selected = data;
    const { caso: caseData, rag } = data;
    const patient = caseData.public.patient;
    $('detail-code').textContent = caseData.case_id + ' · ' + (SPECIALTIES[caseData.specialty] || caseData.specialty);
    $('detail-title').textContent = patient.alias;
    $('detail-patient').textContent = patient.age_years + ' años · ' + patient.sex + ' · Fuente: ' + caseData.source.dataset;
    const summary = $('case-summary');
    summary.replaceChildren(
      block('Motivo de consulta', caseData.public.chief_complaint.text),
      block('Diagnóstico de referencia · Solo docentes', caseData.protected.diagnosis.name),
      block('Tratamiento de referencia', caseData.protected.treatment_reference.summary),
      block('Diagnósticos diferenciales', caseData.protected.differentials.map(item => item.name).join(' · ')),
    );
    const history = node('div', 'field-block'); history.append(node('h3', '', 'Historia y hallazgos bajo solicitud'));
    const descriptions = node('dl');
    for (const item of caseData.on_request) descriptions.append(node('dt', '', item.label), node('dd', '', item.text || item.value + ' ' + item.unit));
    history.append(descriptions); summary.append(history);
    $('evidence-summary').textContent = rag.indexadas + ' filas en ' + rag.tabla + ' · ' + rag.esperadas + ' esperadas para la versión actual.';
    const problems = rag.faltantes.length + rag.desactualizadas.length;
    notice('evidence-health', problems ? rag.faltantes.length + ' evidencias faltantes y ' + rag.desactualizadas.length + ' desactualizadas. Sincroniza para incorporar la versión actual.'
      : 'Las evidencias esperadas coinciden con el contenido del caso.', problems > 0);
    $('evidence-types').replaceChildren(...Object.entries(rag.por_categoria).map(([key, count]) => node('span', '', key.replaceAll('_', ' ') + ' · ' + count)));
    renderEvidence();
    $('additional-list').replaceChildren(...data.datos_adicionales.map(item => {
      const card = node('article', 'evidence-card');
      card.dataset.review = item.estado_revision;
      const header = node('header');
      header.append(node('strong', '', item.clave), node('span', 'badge', item.estado_revision));
      card.append(header, node('p', '', item.contenido.respuesta), node('small', '', 'Pregunta original: ' + item.pregunta_origen),
        node('small', '', 'Modelo: ' + item.modelo));
      return card;
    }));
    if (!data.datos_adicionales.length) $('additional-list').append(node('p', 'empty', 'Este caso aún no tiene datos adicionales generados.'));
  }
  async function openCase(caseId) {
    const version = ++detailVersion;
    selected = null;
    $('detail-content').hidden = true;
    $('detail-title').textContent = 'Cargando caso…';
    $('detail-code').textContent = caseId;
    $('detail-status').textContent = 'Consultando el caso y sus evidencias en Supabase.';
    $('probe-result').replaceChildren();
    $('owner-filter').value = '';
    selectPane('summary');
    if (!$('case-dialog').open) $('case-dialog').showModal();
    try {
      const data = await json('/api/docente/casos/' + encodeURIComponent(caseId));
      if (version !== detailVersion || !$('case-dialog').open) return;
      renderDetail(data);
      $('detail-status').textContent = '';
      $('detail-content').hidden = false;
    } catch (error) { if (version === detailVersion) $('detail-status').textContent = error.message; }
  }
  $('close-detail').addEventListener('click', () => $('case-dialog').close());
  $('owner-filter').addEventListener('change', renderEvidence);
  $('case-search').addEventListener('input', renderCatalog);
  $('open-upload').addEventListener('click', () => { $('upload-section').hidden = false; $('upload-section').scrollIntoView({ block: 'start', behavior: 'smooth' }); $('case-file').focus({ preventScroll: true }); });
  $('close-upload').addEventListener('click', () => { $('upload-section').hidden = true; $('open-upload').focus(); });
  $('case-file').addEventListener('change', () => {
    preview = null; $('preview').hidden = true; notice('upload-status', '');
    $('upload-section').dataset.stage = 'select';
  });
  const dropzone = document.querySelector('.dropzone');
  dropzone.addEventListener('dragover', event => {
    event.preventDefault();
    if (!busyImport) dropzone.classList.add('is-dragging');
  });
  dropzone.addEventListener('dragleave', event => {
    if (!dropzone.contains(event.relatedTarget)) dropzone.classList.remove('is-dragging');
  });
  dropzone.addEventListener('drop', event => {
    event.preventDefault();
    dropzone.classList.remove('is-dragging');
    if (busyImport) return;
    const files = event.dataTransfer?.files;
    if (!files?.length) return;
    if (files.length !== 1) { notice('upload-status', 'Selecciona un solo archivo por importación.', true); return; }
    $('case-file').files = files;
    $('case-file').dispatchEvent(new Event('change', { bubbles: true }));
  });
  $('refresh').addEventListener('click', async () => {
    try { await loadCatalog(); } catch (error) { notice('notice', error.message, true); }
  });
  $('sync-all-evidence').addEventListener('click', () => {
    if (syncingCatalog) return;
    syncingCatalog = true;
    $('sync-evidence').disabled = true;
    notice('sync-all-status', 'Actualizando las evidencias de todo el catálogo. Esto puede tardar unos segundos…');
    busy($('sync-all-evidence'), 'Actualizando todo el catálogo…', async () => {
      try {
        const result = await post('/api/docente/rag/sincronizar', {});
        notice('sync-all-status', result.casos_sincronizados + ' casos sincronizados y ' + result.evidencias_indexadas + ' evidencias actualizadas en Supabase.');
        await loadCatalog();
        if (selected && $('case-dialog').open) {
          const caseId = selected.caso.case_id;
          const detail = await json('/api/docente/casos/' + encodeURIComponent(caseId));
          if (selected?.caso.case_id === caseId && $('case-dialog').open) renderDetail(detail);
        }
      } catch (error) { notice('sync-all-status', error.message, true); }
      finally { syncingCatalog = false; $('sync-evidence').disabled = false; }
    });
  });
  document.querySelectorAll('[data-template]').forEach(button => button.addEventListener('click', () => busy(button, 'Preparando…', async () => {
    try {
      const response = await window.auth.api('/api/docente/plantilla?formato=' + button.dataset.template);
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement('a'); link.href = url; link.download = 'plantilla_casos.' + button.dataset.template;
      link.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) { notice('upload-status', error.message, true); }
  })));
  $('upload-form').addEventListener('submit', event => {
    event.preventDefault();
    if (busyImport) return;
    const file = $('case-file').files[0];
    if (!file) return;
    preview = null; $('preview').hidden = true;
    if (file.size > 4 * 1024 * 1024) { notice('upload-status', 'El archivo supera los 4 MB.', true); return; }
    busyImport = true; $('case-file').disabled = true;
    busy($('validate-button'), 'Leyendo documento…', async () => {
      try {
        const data = await json('/api/docente/importaciones/validar?archivo=' + encodeURIComponent(file.name), { method: 'POST', body: file });
        if (!data.valido) {
          notice('upload-status', data.errores.map(item => [item.case_id, item.path, item.message].filter(Boolean).join(' · ')).join('\n'), true);
          return;
        }
        preview = data;
        $('upload-section').dataset.stage = 'review';
        notice('upload-status', data.casos.length + ' casos válidos. Revisa la vista previa antes de publicarlos.' + (data.avisos.length ? '\n' + data.avisos.join('\n') : ''));
        $('preview-list').replaceChildren(...data.casos.map(item => {
          const row = node('div', 'preview-item');
          row.append(node('strong', '', item.case_id + ' · ' + item.public.patient.alias),
            node('small', '', SPECIALTIES[item.specialty] + ' · ' + item.protected.diagnosis.name));
          return row;
        }));
        $('preview').hidden = false;
      } catch (error) { notice('upload-status', error.message, true); }
      finally { busyImport = false; $('case-file').disabled = false; }
    });
  });
  $('publish-button').addEventListener('click', () => {
    if (!preview || busyImport) return;
    busyImport = true; $('case-file').disabled = true; $('validate-button').disabled = true;
    $('upload-section').dataset.stage = 'publish';
    busy($('publish-button'), 'Publicando casos…', async () => {
      try {
        const result = await post('/api/docente/importaciones', { casos: preview.casos, archivo: preview.archivo });
        notice('upload-status', result.casos_insertados + ' casos publicados; ' + result.casos_existentes + ' ya existentes. ' + result.evidencias_indexadas + ' evidencias indexadas.');
        preview = null; $('preview').hidden = true; $('upload-form').reset();
        $('upload-section').dataset.stage = 'done';
        await loadCatalog();
      } catch (error) {
        if (preview) $('upload-section').dataset.stage = 'review';
        notice('upload-status', error.message, true);
      }
      finally { busyImport = false; $('case-file').disabled = false; $('validate-button').disabled = false; }
    });
  });
  $('sync-evidence').addEventListener('click', () => busy($('sync-evidence'), 'Sincronizando…', async () => {
    if (syncingCatalog) return;
    if (!selected) return;
    const caseData = selected.caso;
    try {
      await post('/api/docente/importaciones', { casos: [caseData], archivo: 'Sincronización ' + caseData.case_id });
      renderDetail(await json('/api/docente/casos/' + encodeURIComponent(caseData.case_id)));
      $('detail-status').textContent = 'Evidencias sincronizadas con la versión actual del caso.';
    } catch (error) { $('detail-status').textContent = error.message; }
  }));
  $('probe-form').addEventListener('submit', event => {
    event.preventDefault();
    if (!selected) return;
    const caseId = selected.caso.case_id;
    busy($('probe-form').querySelector('button'), 'Consultando…', async () => {
      try {
        const result = await post('/api/docente/casos/' + encodeURIComponent(caseId) + '/probar-rag', { pregunta: $('probe-question').value });
        const target = $('probe-result');
        target.replaceChildren(node('p', '', 'Agente: ' + (OWNERS[result.agente] || result.agente) + ' · Intención: ' + result.intencion),
          node('p', '', 'Temas reconocidos: ' + (result.temas.join(', ') || 'ninguno')),
          node('p', '', 'Evidencias autorizadas: ' + (result.evidencias_autorizadas.join(', ') || 'ninguna')));
        if (result.backend_simulador !== 'supabase_pgvector') target.append(node('p', '', 'Esta prueba consulta pgvector. El simulador sigue usando la evidencia del caso hasta activar ese backend.'));
        if (!result.resultados.length) target.append(node('p', '', 'La búsqueda no devolvió evidencias autorizadas. Revisa los temas, el índice y el modelo de embeddings.'));
        for (const item of result.resultados) target.append(block(item.evidence_id + ' · similitud ' + item.puntaje.toFixed(3), item.texto));
      } catch (error) { $('probe-result').textContent = error.message; }
    });
  });
  $('logout').addEventListener('click', async () => {
    const client = await window.auth.ready;
    await client?.auth.signOut(); window.location.assign('index.html');
  });

  async function initialize() {
    try {
      const profile = await window.auth.profile();
      if (!profile.panel_docente) {
        $('access-title').textContent = 'Acceso para docentes';
        $('access-message').textContent = 'Tu cuenta tiene rol de alumno. Solicita a la administración que te asigne acceso docente.';
        return;
      }
      $('account-name').textContent = profile.email;
      $('account-avatar').textContent = profile.email.slice(0, 2).toLocaleUpperCase('es');
      $('account-role').textContent = profile.rol === 'administrativo' ? 'Administración' : 'Profesor';
      $('logout').hidden = false;
      $('access').hidden = true; $('workspace').hidden = false;
      await loadCatalog();
      const client = await window.auth.ready;
      client?.auth.onAuthStateChange((event, session) => {
        if (event === 'SIGNED_OUT' || !session) {
          catalog = []; selected = null; preview = null;
          $('case-list').replaceChildren(); $('case-summary').replaceChildren();
          $('case-dialog').close(); $('workspace').hidden = true;
          window.location.assign('index.html?cuenta=login');
        }
      });
    } catch (error) {
      if (!$('workspace').hidden) notice('notice', error.message, true);
      else {
        $('access-title').textContent = 'Entra a tu espacio docente';
        $('access-message').textContent = error.message;
        $('login-link').hidden = false;
      }
    }
  }
  initialize();
})();

