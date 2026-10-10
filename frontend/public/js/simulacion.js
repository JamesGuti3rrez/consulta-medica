document.addEventListener('DOMContentLoaded', async () => {
  const statusMessage = document.querySelector('[data-role="case-status"]');
  const simulatorStatus = document.querySelector('[data-role="simulator-status"]');
  const recordStatus = document.querySelector('[data-role="record-status"]');
  const startButton = document.querySelector('[data-role="start-simulation"]');
  const specialtySelect = document.querySelector('[data-role="specialty-select"]');
  const doctorBubble = document.querySelector('[data-role="doctor-bubble"]');
  const doctorText = document.querySelector('[data-role="doctor-text"]');
  const doctorStatus = document.querySelector('[data-role="doctor-status"]');
  const conversation = document.querySelector('[data-role="conversation-history"]');
  const conversationStatus = document.querySelector('[data-role="conversation-status"]');
  const nextPrompt = document.querySelector('[data-role="next-prompt"]');
  const record = document.querySelector('[data-role="patient-record"]');
  const emptyRecord = document.querySelector('[data-role="record-empty"]');
  const recordHistory = document.querySelector('[data-role="record-history"]');
  const tabButtons = [...document.querySelectorAll('[data-tab]')];
  const tabPanels = [...document.querySelectorAll('[data-tab-panel]')];
  const consultaTab = tabButtons.find(button => button.dataset.tab === 'consulta');
  let caseAvailable = false;
  // Cada inicio aumenta el número de sesión: una narración anterior que siga en curso se detiene.
  let session = 0;

  // La especialidad puede venir en la URL (simulacion.html?especialidad=pediatria).
  const urlSpecialty = new URLSearchParams(window.location.search).get('especialidad');
  if (specialtySelect && urlSpecialty) specialtySelect.value = urlSpecialty;
  const caseUrl = () => {
    const specialty = specialtySelect?.value;
    return specialty ? `/api/caso?especialidad=${encodeURIComponent(specialty)}` : '/api/caso';
  };

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
    if (name === 'consulta' && conversation) conversation.scrollTop = conversation.scrollHeight;
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

  const setPill = (element, text) => {
    if (!element) return;
    const textNode = [...element.childNodes].find(node => node.nodeType === Node.TEXT_NODE);
    if (textNode) textNode.nodeValue = ` ${text}`;
  };

  const wait = milliseconds => new Promise(resolve => window.setTimeout(resolve, milliseconds));

  // La voz lee las unidades completas; el texto en pantalla no cambia.
  const spokenText = text => text
    .replace(/(\d+)\/(\d+) mmHg/g, '$1 sobre $2 milímetros de mercurio')
    .replace(/mmHg/g, 'milímetros de mercurio')
    .replace(/(\d+)\/min/g, '$1 por minuto')
    .replace(/°C/g, 'grados')
    .replace(/(\d+) %/g, '$1 por ciento')
    .replace(/(\d+),(\d+)/g, '$1 coma $2')
    .replace(/ × /g, ' por ');

  // Tiempo de lectura estimado: se usa sin voz y como límite si el navegador nunca avisa del final.
  const readingTime = text => Math.min(9000, 1500 + text.length * 45);

  const speak = text => new Promise(resolve => {
    if (!('speechSynthesis' in window)) {
      wait(readingTime(text)).then(resolve);
      return;
    }
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      resolve();
    };
    const utterance = new SpeechSynthesisUtterance(spokenText(text));
    utterance.lang = 'es-ES';
    utterance.rate = 0.95;
    utterance.onend = finish;
    utterance.onerror = finish;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
    wait(readingTime(text) * 2).then(finish);
  });

  const appendChat = (text, speaker) => {
    if (!conversation) return;
    const speakers = {
      doctor: { name: 'Doctor', role: 'Médico asistente', icon: 'stethoscope' },
      patient: { name: 'Paciente', role: 'Paciente', icon: 'person' },
      student: { name: 'Tú', role: 'Médico en formación', icon: 'mic' },
    };
    const who = speakers[speaker];
    const entry = document.createElement('div');
    entry.className = `chat-row chat-${speaker}`;
    const avatar = document.createElement('span');
    avatar.className = 'chat-avatar material-symbols-outlined';
    avatar.setAttribute('aria-hidden', 'true');
    avatar.textContent = who.icon;
    const body = document.createElement('div');
    body.className = 'chat-msg';
    const header = document.createElement('p');
    header.className = 'chat-name';
    const name = document.createElement('strong');
    name.textContent = who.name;
    const role = document.createElement('span');
    role.textContent = who.role;
    header.append(name, role);
    const message = document.createElement('p');
    message.className = 'chat-text';
    message.textContent = text;
    body.append(header, message);
    entry.append(avatar, body);
    conversation.appendChild(entry);
    conversation.scrollTop = conversation.scrollHeight;
    if (consultaTab && !consultaTab.classList.contains('is-active')) consultaTab.classList.add('has-news');
  };

  // El doctor dice una frase: burbuja sobre la escena, mensaje en el historial y voz.
  const doctorSays = async text => {
    doctorBubble?.classList.remove('hidden');
    if (doctorText) doctorText.textContent = text;
    setPill(doctorStatus, 'Hablando');
    if (conversationStatus) conversationStatus.textContent = 'Doctor hablando';
    appendChat(text, 'doctor');
    await speak(text);
  };

  const recordSection = (label, text) => {
    const section = document.createElement('section');
    section.className = 'flex flex-col gap-1.5';
    const title = document.createElement('span');
    title.className = 'record-label';
    title.textContent = label;
    const body = document.createElement('p');
    body.className = 'text-sm text-slate-700 bg-slate-50 border border-slate-200/80 rounded-lg px-3 py-2 leading-relaxed';
    body.textContent = text;
    section.append(title, body);
    return section;
  };

  // Ficha vacía al iniciar: se completa a medida que el doctor presenta el caso.
  const resetRecord = patientCase => {
    document.querySelector('[data-role="record-name"]').textContent = patientCase.patient.alias;
    document.querySelector('[data-role="record-demographics"]').textContent =
      `${patientCase.patient.age_years} años · ${patientCase.patient.sex}`;
    document.querySelector('[data-role="record-chief"]').textContent = patientCase.chief_complaint.text;
    document.querySelector('[data-role="record-allergies"]').textContent = patientCase.allergies_recorded
      ? patientCase.allergies.join(', ')
      : 'No documentadas; deben preguntarse.';
    recordHistory.replaceChildren();
    [...record.children].forEach(section => { section.hidden = true; });
    emptyRecord.hidden = true;
    record.hidden = false;
    record.classList.remove('hidden');
    conversation.replaceChildren();
  };

  const reveal = element => { if (element) element.hidden = false; };

  const presentCase = async (patientCase, current) => {
    const [header, chief, history, allergies] = record.children;
    const { alias, age_years: age, sex } = patientCase.patient;
    const steps = [
      {
        show: [header, chief],
        text: `${alias}, de ${age} años, sexo ${sex}. Motivo de consulta: ${patientCase.chief_complaint.text}`,
      },
      ...patientCase.items.map(item => ({
        show: [history],
        add: recordSection(item.label, item.text),
        text: `${item.label}: ${item.text}`,
      })),
      {
        show: [allergies],
        text: patientCase.allergies_recorded
          ? `Alergias registradas: ${patientCase.allergies.join(', ')}.`
          : 'No hay alergias documentadas en la ficha.',
      },
    ];

    for (const step of steps) {
      if (current !== session) return false;
      step.show.forEach(reveal);
      if (step.add) recordHistory.append(step.add);
      await doctorSays(step.text);
    }
    if (current !== session) return false;
    await doctorSays('Doctor, puede comenzar con el interrogatorio.');
    return current === session;
  };

  const startSimulation = async () => {
    session += 1;
    const current = session;
    window.speechSynthesis?.cancel();
    startButton.disabled = true;
    startButton.lastChild.textContent = ' Cargando caso...';

    let patientCase;
    try {
      const response = await fetch(caseUrl());
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || `API respondió con HTTP ${response.status}`);
      }
      patientCase = await response.json();
    } catch (error) {
      console.error('No se pudo cargar un caso curado:', error);
      setStatus('No se pudo cargar el caso. Verifica la conexión e inténtalo de nuevo.', true);
      startButton.disabled = !caseAvailable;
      startButton.lastChild.textContent = caseAvailable ? ' Reintentar carga' : ' Sin casos disponibles';
      return;
    }

    resetRecord(patientCase);
    showTab('ficha');
    simulatorStatus.textContent = 'Presentación del caso';
    recordStatus.lastChild.textContent = `Caso ${patientCase.case_id}`;
    if (nextPrompt) nextPrompt.textContent = 'Escucha la presentación del caso.';
    setStatus(`Caso ${patientCase.case_id} cargado. El doctor presenta al paciente.`);
    // Se puede pedir otro caso en cualquier momento: la narración en curso se detiene.
    startButton.disabled = false;
    startButton.lastChild.textContent = ' Cargar otro caso';

    const finished = await presentCase(patientCase, current);
    if (!finished) return;
    setPill(doctorStatus, 'Listo');
    if (conversationStatus) conversationStatus.textContent = 'Presentación terminada';
    simulatorStatus.textContent = 'Listo para el interrogatorio';
    if (nextPrompt) {
      nextPrompt.textContent = 'Presentación terminada. El interrogatorio con el paciente estará disponible al conectar los agentes.';
    }
    setStatus(`Caso ${patientCase.case_id}: presentación terminada. Revisa la ficha y la consulta.`);
    showTab('consulta');
  };

  if (startButton) startButton.disabled = true;
  if (!statusMessage || !startButton || !record || !emptyRecord || !recordHistory || !conversation) return;
  startButton.addEventListener('click', startSimulation);

  try {
    const response = await fetch('/api/status');
    if (!response.ok) throw new Error(`API respondió con HTTP ${response.status}`);
    const status = await response.json();
    caseAvailable = status.caseConfigured && status.availableCases > 0;
    startButton.disabled = !caseAvailable;
    startButton.lastChild.textContent = caseAvailable ? ' Iniciar simulación' : ' Sin casos disponibles';
    simulatorStatus.textContent = caseAvailable
      ? `${status.availableCases} casos curados disponibles`
      : 'Sin casos curados';
    setStatus(caseAvailable
      ? `${status.availableCases} casos curados disponibles. Elige una especialidad e inicia: el doctor te presentará un caso al azar.`
      : 'Aún no hay casos clínicos curados disponibles.');
  } catch (error) {
    console.error('No se pudo comprobar la disponibilidad de casos clínicos:', error);
    setStatus('No se pudo comprobar el estado del simulador. Verifica que el servidor esté en ejecución.', true);
    simulatorStatus.textContent = 'Servidor no disponible';
    startButton.disabled = true;
    startButton.lastChild.textContent = ' Servidor no disponible';
  }
});
