document.addEventListener('DOMContentLoaded', async () => {
  const statusMessage = document.querySelector('[data-role="case-status"]');
  const simulatorStatus = document.querySelector('[data-role="simulator-status"]');
  const recordStatus = document.querySelector('[data-role="record-status"]');
  const startButton = document.querySelector('[data-role="start-simulation"]');
  const tabButtons = [...document.querySelectorAll('[data-tab]')];
  const tabPanels = [...document.querySelectorAll('[data-tab-panel]')];
  let caseAvailable = false;

  const showTab = name => {
    tabButtons.forEach(button => {
      const active = button.dataset.tab === name;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-selected', String(active));
      button.tabIndex = active ? 0 : -1;
      if (active) button.classList.remove('has-news');
    });
    tabPanels.forEach(panel => {
      panel.hidden = panel.dataset.tabPanel !== name;
    });
  };

  const setStatus = (message, isError = false) => {
    if (!statusMessage) return;
    statusMessage.textContent = message;
    statusMessage.classList.toggle('border-amber-200', !isError);
    statusMessage.classList.toggle('bg-amber-50', !isError);
    statusMessage.classList.toggle('text-amber-900', !isError);
    statusMessage.classList.toggle('border-red-200', isError);
    statusMessage.classList.toggle('bg-red-50', isError);
    statusMessage.classList.toggle('text-red-900', isError);
  };

  tabButtons.forEach((button, index) => {
    button.addEventListener('click', () => showTab(button.dataset.tab));
    button.addEventListener('keydown', event => {
      if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
      const step = event.key === 'ArrowRight' ? 1 : -1;
      const next = tabButtons[(index + step + tabButtons.length) % tabButtons.length];
      showTab(next.dataset.tab);
      next.focus();
    });
  });

  const renderCase = patientCase => {
    const record = document.querySelector('[data-role="patient-record"]');
    const emptyRecord = document.querySelector('[data-role="record-empty"]');
    if (!record || !emptyRecord) return;

    document.querySelector('[data-role="record-name"]').textContent = patientCase.patient.alias;
    document.querySelector('[data-role="record-demographics"]').textContent =
      `${patientCase.patient.age_years} años · ${patientCase.patient.sex}`;
    document.querySelector('[data-role="record-chief"]').textContent =
      patientCase.chief_complaint.text;
    document.querySelector('[data-role="record-allergies"]').textContent =
      patientCase.allergies_recorded
        ? patientCase.allergies.join(', ')
        : 'No documentadas; deben preguntarse.';

    const history = document.querySelector('[data-role="record-history"]');
    history.replaceChildren();
    patientCase.items.forEach(item => {
      const section = document.createElement('section');
      section.className = 'flex flex-col gap-1.5';
      const label = document.createElement('span');
      label.className = 'record-label';
      label.textContent = item.label;
      const text = document.createElement('p');
      text.className = 'text-sm text-slate-700 bg-slate-50 border border-slate-200/80 rounded-lg px-3 py-2 leading-relaxed';
      text.textContent = item.text;
      section.append(label, text);
      history.append(section);
    });

    emptyRecord.hidden = true;
    record.hidden = false;
    record.classList.remove('hidden');
    simulatorStatus.textContent = 'Demo con caso cargado';
    recordStatus.lastChild.textContent = 'Caso cargado · demo';
    document.querySelector('[data-role="conversation-status"]').textContent = 'Caso cargado · demo';
    document.querySelector('[data-role="next-prompt"]').textContent =
      'Expediente demostrativo cargado. La conversación clínica interactiva todavía no está implementada.';
    const conversation = document.querySelector('[data-role="conversation-history"]');
    const note = document.createElement('p');
    note.className = 'text-slate-500 text-[13px]';
    note.textContent = `Se cargó el caso ${patientCase.case_id}. Esta demo muestra únicamente información pública del expediente.`;
    conversation.replaceChildren(note);
    setStatus(`Caso ${patientCase.case_id} cargado. Puedes revisar la ficha; el diálogo clínico aún está pendiente.`);
    startButton.disabled = false;
    startButton.lastChild.textContent = ' Cargar otro caso';
  };

  if (startButton) startButton.disabled = true;
  if (!statusMessage || !startButton) return;

  startButton.addEventListener('click', async () => {
    startButton.disabled = true;
    startButton.lastChild.textContent = ' Cargando caso...';
    try {
      const response = await fetch('/api/caso');
      if (!response.ok) {
        const body = await response.json();
        throw new Error(body.detail || `API respondió con HTTP ${response.status}`);
      }
      renderCase(await response.json());
    } catch (error) {
      console.error('No se pudo cargar un caso curado:', error);
      setStatus('No se pudo cargar el caso. Verifica la conexión e inténtalo de nuevo.', true);
      startButton.disabled = !caseAvailable;
      startButton.lastChild.textContent = caseAvailable ? ' Reintentar carga' : ' Sin casos disponibles';
    }
  });

  try {
    const response = await fetch('/api/status');
    if (!response.ok) throw new Error(`API respondió con HTTP ${response.status}`);
    const status = await response.json();
    caseAvailable = status.caseConfigured && status.availableCases > 0;
    startButton.disabled = !caseAvailable;
    startButton.lastChild.textContent = caseAvailable ? ' Iniciar simulación demo' : ' Sin casos disponibles';
    simulatorStatus.textContent = caseAvailable
      ? `${status.availableCases} casos curados disponibles`
      : 'Sin casos curados';
    setStatus(caseAvailable
      ? `${status.availableCases} casos curados disponibles. Inicia para cargar un expediente de demostración. El diálogo clínico aún está pendiente.`
      : 'Aún no hay casos clínicos curados disponibles.');
  } catch (error) {
    console.error('No se pudo comprobar la disponibilidad de casos clínicos:', error);
    setStatus('No se pudo comprobar el estado del simulador. Verifica que el servidor esté en ejecución.', true);
    simulatorStatus.textContent = 'Servidor no disponible';
    startButton.disabled = true;
    startButton.lastChild.textContent = ' Servidor no disponible';
  }
});
