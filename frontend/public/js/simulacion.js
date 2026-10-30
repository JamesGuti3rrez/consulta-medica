document.addEventListener('DOMContentLoaded', async () => {
  const $ = role => document.querySelector(`[data-role="${role}"]`);
  const statusMessage = $('case-status');
  const simulatorStatus = $('simulator-status');
  const recordStatus = $('record-status');
  const startButton = $('start-simulation');
  const micButton = document.querySelector('[aria-label="Micrófono"]');
  const diagnosisButton = $('diagnosis-button');
  const doctorBubble = $('doctor-bubble');
  const doctorText = $('doctor-text');
  const doctorStatus = $('doctor-status');
  const patientBubble = $('patient-bubble');
  const patientText = $('patient-text');
  const patientStatus = $('patient-status');
  const conversation = $('conversation-history');
  const conversationStatus = $('conversation-status');
  const nextPrompt = $('next-prompt');
  const record = $('patient-record');
  const emptyRecord = $('record-empty');
  const recordHistory = $('record-history');
  const hypothesesPanel = $('hypotheses-panel');
  const hypothesesCount = $('hypotheses-count');
  const hypothesesHint = $('hypotheses-hint');
  const hypothesisInput = $('hypothesis-input');
  const hypothesisMic = $('hypothesis-mic');
  const addHypothesisButton = $('add-hypothesis');
  const hypothesesList = $('hypotheses-list');
  const hypothesesFeedback = $('hypotheses-feedback');
  const diagnosisPanel = $('diagnosis-panel');
  const diagnosisInput = $('diagnosis-input');
  const diagnosisMic = $('diagnosis-mic');
  const saveDiagnosis = $('save-diagnosis');
  const closeDiagnosis = $('close-diagnosis');
  const diagnosisFeedback = $('diagnosis-feedback');
  const evaluationPanel = $('evaluation-panel');
  const closeEvaluation = $('close-evaluation');
  const skipButtons = [...document.querySelectorAll('[data-role="skip-speech"]')];
  const tabButtons = [...document.querySelectorAll('[data-tab]')];
  const tabPanels = [...document.querySelectorAll('[data-tab-panel]')];
  const consultaTab = tabButtons.find(button => button.dataset.tab === 'consulta');

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const recognition = SpeechRecognition ? new SpeechRecognition() : null;
  if (recognition) {
    recognition.lang = 'es-ES';
    recognition.continuous = false;
    recognition.interimResults = true;
  }

  // La especialidad se elige en la portada y llega en la URL (simulacion.html?especialidad=pediatria).
  // El estudiante no ve qué caso le tocó: ni su código ni nada fuera de la ficha pública.
  let specialty = new URLSearchParams(window.location.search).get('especialidad');
  const SPECIALTY_NAMES = {
    emergencias: 'Emergencias',
    medicina_interna: 'Medicina interna',
    pediatria: 'Pediatría',
    ginecologia_obstetricia: 'Ginecología y obstetricia',
    cirugia_general: 'Cirugía general',
  };
  let specialtyName = SPECIALTY_NAMES[specialty];
  // Solo para pruebas: simulacion.html?caso=EME-103 abre ese caso (guía de pruebas en docs/).
  let testCase = new URLSearchParams(window.location.search).get('caso');

  // Casos ya vistos en esta pestaña (el actual primero): «Probar otro caso» no repite paciente.
  // Se guardan en sessionStorage y no en la URL, para que el estudiante no vea códigos de caso.
  const SEEN_KEY = 'casos_vistos';
  const readSeen = () => {
    try {
      const seen = JSON.parse(sessionStorage.getItem(SEEN_KEY) || '[]');
      return Array.isArray(seen) ? seen : [];
    } catch {
      return [];
    }
  };
  const rememberCase = caseId => {
    try {
      sessionStorage.setItem(SEEN_KEY, JSON.stringify([caseId, ...readSeen().filter(id => id !== caseId)]));
    } catch {
      // Sin almacenamiento, el servidor solo puede evitar el caso actual.
    }
  };
  const caseUrl = (excludeSeen = false) => {
    if (testCase) return `/api/caso?caso=${encodeURIComponent(testCase)}`;
    const params = new URLSearchParams();
    if (specialtyName) params.set('especialidad', specialty);
    if (excludeSeen) {
      const seen = readSeen();
      if (seen.length) params.set('excluir', seen.join(','));
    }
    const query = params.toString();
    return query ? `/api/caso?${query}` : '/api/caso';
  };

  let caseAvailable = false;
  // Cada intervención aumenta el número de sesión: lo que siga en curso de una anterior se detiene.
  let session = 0;
  let isRunning = false;
  let isListening = false;
  let cancelListening = false;
  let finalTranscript = '';
  let studentPreview = null;
  let aiSessionId = null;
  // Credencial de capacidad de una consulta de invitado: solo vive en memoria y se envía en cada petición.
  let aiSessionToken = null;
  let hypotheses = [];
  let discardingIndex = null;
  let consultationClosed = false;
  let currentCase = null;

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

  // Los avisos de estado no se muestran al estudiante; el recuadro solo aparece ante un error.
  const setStatus = (message, isError = false) => {
    if (!statusMessage) return;
    statusMessage.textContent = message;
    statusMessage.hidden = !isError;
    statusMessage.classList.toggle('hidden', !isError);
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

  const show = (element, visible = true) => {
    if (!element) return;
    element.hidden = !visible;
    element.classList.toggle('hidden', !visible);
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

  // Velocidad de la voz: 1,3 veces la normal.
  const SPEECH_RATE = 1.3;
  // Tiempo de lectura estimado: se usa sin voz y como límite si el navegador nunca avisa del final.
  const readingTime = text => Math.min(6000, 1000 + text.length * 30);
  // «Saltar» termina la frase en curso y la conversación sigue con la siguiente.
  let skipCurrent = null;
  const setSkipVisible = visible => skipButtons.forEach(button => {
    button.hidden = !visible;
    button.classList.toggle('hidden', !visible);
    button.classList.toggle('inline-flex', visible);
  });
  skipButtons.forEach(button => button.addEventListener('click', () => {
    window.speechSynthesis?.cancel();
    skipCurrent?.();
  }));

  const speak = text => new Promise(resolve => {
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      skipCurrent = null;
      setSkipVisible(false);
      resolve();
    };
    skipCurrent = finish;
    setSkipVisible(true);
    if (!('speechSynthesis' in window)) {
      wait(readingTime(text)).then(finish);
      return;
    }
    const utterance = new SpeechSynthesisUtterance(spokenText(text));
    utterance.lang = 'es-ES';
    utterance.rate = SPEECH_RATE;
    utterance.onend = finish;
    utterance.onerror = finish;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
    wait(readingTime(text) * 2).then(finish);
  });

  const SPEAKERS = {
    doctor: { name: 'Doctor', role: 'Médico asistente', icon: 'stethoscope' },
    patient: { name: 'Paciente', role: 'Paciente', icon: 'person' },
    student: { name: 'Tú', role: 'Médico en formación', icon: 'mic' },
    laboratorio: { name: 'Laboratorio', role: 'Resultados', icon: 'biotech' },
    radiologia: { name: 'Radiología', role: 'Informe de imagen', icon: 'radiology' },
    especialista: { name: 'Especialista', role: 'Interconsulta', icon: 'medical_services' },
  };

  const appendChat = (text, speaker) => {
    if (!conversation) return;
    if (conversation.dataset.started !== 'true') {
      conversation.replaceChildren();
      conversation.dataset.started = 'true';
    }
    const who = SPEAKERS[speaker] || SPEAKERS.doctor;
    // Laboratorio, radiología y especialista usan el estilo del doctor: hablan del lado del equipo.
    const style = ['patient', 'student'].includes(speaker) ? speaker : 'doctor';
    const entry = document.createElement('div');
    entry.className = `chat-row chat-${style}`;
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

  // Una sola burbuja sobre la escena a la vez: la del equipo (doctor) o la del paciente.
  const setSpeaker = (speaker, text) => {
    const doctorSpeaks = speaker !== 'patient';
    show(doctorBubble, doctorSpeaks);
    show(patientBubble, !doctorSpeaks);
    setPill(doctorStatus, doctorSpeaks ? 'Hablando' : 'En espera');
    setPill(patientStatus, doctorSpeaks ? 'En espera' : 'Hablando');
    if (doctorSpeaks && doctorText) doctorText.textContent = text;
    if (!doctorSpeaks && patientText) patientText.textContent = text;
    if (conversationStatus) conversationStatus.textContent = doctorSpeaks ? 'Doctor hablando' : 'Paciente respondiendo';
  };

  const say = async (speaker, text) => {
    appendChat(text, speaker);
    setSpeaker(speaker, text);
    await speak(text);
  };

  const setReady = () => {
    setPill(doctorStatus, 'Listo');
    setPill(patientStatus, 'Listo');
    if (conversationStatus) conversationStatus.textContent = 'Tu turno';
    isRunning = false;
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

  // HU-004 / EN-013: la tablilla recibe únicamente los datos autorizados de la respuesta del servidor.
  const recordEvidenceIds = new Set();
  const addClinicalEvidence = items => {
    for (const item of items || []) {
      if (recordEvidenceIds.has(item.evidence_id)) continue;
      recordEvidenceIds.add(item.evidence_id);
      const section = recordSection(item.label, item.text);
      section.dataset.evidenceId = item.evidence_id;
      section.dataset.synthetic = String(Boolean(item.synthetic));
      if (item.synthetic) {
        const badge = document.createElement('strong');
        badge.className = 'synthetic-exam-badge';
        badge.textContent = 'Sintético educativo · Revisión clínica pendiente';
        section.append(badge);
      }
      recordHistory.append(section);
      recordHistory.hidden = false;
    }
  };

  // Ficha vacía al iniciar: se completa a medida que el doctor presenta el caso.
  const resetRecord = patientCase => {
    $('record-name').textContent = patientCase.patient.alias;
    $('record-demographics').textContent = `${patientCase.patient.age_years} años · ${patientCase.patient.sex}`;
    $('record-chief').textContent = patientCase.chief_complaint.text;
    $('record-allergies').textContent = patientCase.allergies_recorded
      ? patientCase.allergies.join(', ')
      : 'No documentadas; deben preguntarse.';
    recordHistory.replaceChildren();
    recordEvidenceIds.clear();
    [...record.children].forEach(section => { section.hidden = true; });
    emptyRecord.hidden = true;
    show(record);
    conversation.dataset.started = 'false';
  };

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
      step.show.forEach(element => { if (element) element.hidden = false; });
      if (step.add) recordHistory.append(step.add);
      await say('doctor', step.text);
    }
    if (current !== session) return false;
    await say('doctor', 'Doctor, puede comenzar con el interrogatorio.');
    return current === session;
  };

  // La conversación con los agentes (/api/ai) se abre si el servidor la ofrece.
  const openConversation = async caseId => {
    try {
      // La consulta queda a nombre del alumno con sesión iniciada: solo él podrá guardarla al terminar.
      const headers = { 'Content-Type': 'application/json' };
      const token = await accessToken();
      if (token) headers.Authorization = `Bearer ${token}`;
      const response = await fetch('/api/ai/sessions', {
        method: 'POST',
        headers,
        body: JSON.stringify({ case_id: caseId }),
      });
      if (!response.ok) return null;
      const body = await response.json();
      aiSessionToken = body.session_token || null;
      return body.session_id;
    } catch {
      return null;
    }
  };

  // Cada petición sobre la consulta lleva la sesión del alumno o la credencial del invitado: el servidor
  // solo atiende a quien la empezó.
  const conversationHeaders = async () => {
    const headers = { 'Content-Type': 'application/json' };
    const token = await accessToken();
    if (token) headers.Authorization = `Bearer ${token}`;
    if (aiSessionToken) headers['X-Session-Token'] = aiSessionToken;
    return headers;
  };

  const startSimulation = async ({ another = false } = {}) => {
    if (isRunning) return;
    isRunning = true;
    session += 1;
    const current = session;
    hypotheses = [];
    discardingIndex = null;
    consultationClosed = false;
    renderHypotheses();
    startButton.disabled = true;
    startButton.lastChild.textContent = ' Presentando caso...';

    let patientCase;
    try {
      const response = await fetch(caseUrl(another));
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || `API respondió con HTTP ${response.status}`);
      }
      patientCase = await response.json();
    } catch (error) {
      console.error('No se pudo cargar un caso:', error);
      setStatus('No se pudo cargar el caso. Verifica la conexión e inténtalo de nuevo.', true);
      startButton.disabled = !caseAvailable;
      startButton.lastChild.textContent = caseAvailable ? ' Reintentar' : ' Sin casos disponibles';
      isRunning = false;
      return;
    }

    currentCase = patientCase;
    rememberCase(patientCase.case_id);
    aiSessionId = await openConversation(patientCase.case_id);
    resetRecord(patientCase);
    showTab('ficha');
    simulatorStatus.textContent = 'Presentación del caso';
    recordStatus.lastChild.textContent = 'En consulta';
    if (nextPrompt) nextPrompt.textContent = 'Escucha la presentación del caso.';
    setStatus('El doctor te presenta al paciente.');

    const finished = await presentCase(patientCase, current);
    if (!finished) return;
    show(startButton, false);
    show(micButton);
    if (micButton) micButton.disabled = false;
    show(diagnosisButton);
    if (diagnosisButton) diagnosisButton.disabled = false;
    show(hypothesesPanel);
    simulatorStatus.textContent = 'Consulta en curso';
    if (nextPrompt) {
      nextPrompt.textContent = 'Pulsa el micrófono y haz tu primera pregunta: al paciente, al doctor o pide un examen.';
    }
    setStatus('Consulta en curso. Habla con el micrófono; cuando tengas tu diagnóstico, pulsa «Realizar Diagnóstico».');
    showTab('consulta');
    setReady();
  };

  // Respuesta a una intervención del estudiante: el agente que corresponda contesta con su burbuja.
  // Puntos de «pensando» en la burbuja de quien va a hablar.
  const showThinking = speaker => {
    const isPatient = speaker === 'patient';
    const bubble = isPatient ? patientBubble : doctorBubble;
    const text = isPatient ? patientText : doctorText;
    if (!bubble || !text) return;
    show(doctorBubble, !isPatient);
    show(patientBubble, isPatient);
    const dots = document.createElement('span');
    dots.className = 'typing-dots';
    dots.setAttribute('aria-label', 'Pensando');
    dots.append(...[0, 1, 2].map(() => document.createElement('i')));
    text.replaceChildren(dots);
    setPill(isPatient ? patientStatus : doctorStatus, 'Pensando');
  };

  const respondToStudent = async (question, current) => {
    if (!aiSessionId) {
      await say('doctor', 'El interrogatorio con el paciente todavía no está disponible en esta versión.');
      if (current === session) setReady();
      return;
    }
    showThinking('doctor');
    let reply;
    try {
      const response = await fetch(`/api/ai/sessions/${encodeURIComponent(aiSessionId)}/message`, {
        method: 'POST',
        headers: await conversationHeaders(),
        body: JSON.stringify({ message: question }),
      });
      if (!response.ok) {
        // 503: el servidor explica qué pasa (por ejemplo, el modelo de lenguaje no está disponible).
        const body = await response.json().catch(() => ({}));
        const error = new Error(`API respondió con HTTP ${response.status}`);
        error.detail = response.status === 503 ? body.detail : null;
        throw error;
      }
      reply = await response.json();
    } catch (error) {
      console.error('No se pudo obtener la respuesta:', error);
      reply = { agent: 'medico_asistente', response: error.detail || 'No pude procesar tu pregunta. Inténtalo de nuevo.' };
    }
    if (current !== session) return;
    addClinicalEvidence(reply.clinical_evidence);
    // El médico tratante le hace al paciente la pregunta reformulada; luego el paciente responde.
    if (reply.doctor_question) {
      await say('doctor', reply.doctor_question);
      if (current !== session) return;
      showThinking('patient');
    }
    await wait(500);
    if (current !== session) return;
    const speaker = { paciente: 'patient', medico_asistente: 'doctor' }[reply.agent] || reply.agent;
    await say(SPEAKERS[speaker] ? speaker : 'doctor', reply.response);
    if (current !== session) return;
    if (hypothesesHint) hypothesesHint.textContent = '¿Este dato cambia alguna de tus hipótesis?';
    setReady();
    if (Array.isArray(reply.safety_alerts) && reply.safety_alerts.length) {
      setStatus(reply.safety_alerts.map(alert => alert.message).join(' '), true);
    }
  };

  const removeStudentPreview = () => {
    studentPreview?.remove();
    studentPreview = null;
  };

  const setMicListening = listening => {
    if (!micButton) return;
    micButton.title = listening ? 'Escuchando...' : 'Hablar / Siguiente Intervención';
    micButton.classList.toggle('bg-red-600', listening);
    micButton.classList.toggle('hover:bg-red-700', listening);
    micButton.classList.toggle('is-listening', listening);
    micButton.classList.toggle('bg-brand-600', !listening);
    micButton.classList.toggle('hover:bg-brand-700', !listening);
  };

  if (recognition) {
    recognition.onstart = () => {
      finalTranscript = '';
      cancelListening = false;
      isRunning = true;
      isListening = true;
      showTab('consulta');
      show(doctorBubble, false);
      show(patientBubble, false);
      setMicListening(true);
      setPill(doctorStatus, 'En espera');
      setPill(patientStatus, 'Escuchando');
      if (conversationStatus) conversationStatus.textContent = 'Escuchándote';
      removeStudentPreview();
      studentPreview = document.createElement('p');
      studentPreview.className = 'chat-preview';
      studentPreview.textContent = 'Escuchándote...';
      conversation.appendChild(studentPreview);
      conversation.scrollTop = conversation.scrollHeight;
    };

    // Transcripción en vivo de lo que dice el estudiante.
    recognition.onresult = event => {
      let visible = '';
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const text = event.results[index][0].transcript;
        visible += text;
        if (event.results[index].isFinal) finalTranscript += text;
      }
      if (visible.trim() && studentPreview) {
        studentPreview.textContent = visible.trim();
        conversation.scrollTop = conversation.scrollHeight;
      }
    };

    recognition.onerror = event => {
      cancelListening = false;
      isRunning = false;
      isListening = false;
      setMicListening(false);
      setPill(patientStatus, 'Listo');
      removeStudentPreview();
      if (event.error !== 'aborted') {
        window.alert('No se pudo usar el micrófono. Revisa el permiso del navegador.');
      }
    };

    recognition.onend = async () => {
      isListening = false;
      setMicListening(false);
      removeStudentPreview();
      if (cancelListening) {
        cancelListening = false;
        setReady();
        return;
      }
      const question = finalTranscript.trim();
      if (!question) {
        setReady();
        return;
      }
      appendChat(question, 'student');
      await respondToStudent(question, session);
    };
  }

  const startListening = () => {
    if (!recognition || isListening || consultationClosed) return;
    session += 1;
    recognition.start();
  };

  micButton?.addEventListener('click', () => {
    if (!recognition) {
      window.alert('El reconocimiento de voz no está disponible. Usa Chrome o Edge con permiso para el micrófono.');
      return;
    }
    if (isListening) {
      cancelListening = true;
      session += 1;
      window.speechSynthesis?.cancel();
      recognition.stop();
      return;
    }
    // Pulsar mientras alguien habla lo interrumpe y abre el micrófono.
    if (isRunning) {
      session += 1;
      window.speechSynthesis?.cancel();
      isRunning = false;
      setPill(doctorStatus, 'Interrumpido');
    }
    startListening();
  });

  // Dictado de una sola frase para hipótesis, motivos de descarte y diagnóstico.
  const dictate = (input, feedback) => {
    if (!SpeechRecognition) {
      if (feedback) feedback.textContent = 'El dictado requiere Chrome o Edge.';
      return;
    }
    const dictation = new SpeechRecognition();
    dictation.lang = 'es-ES';
    dictation.continuous = false;
    dictation.interimResults = false;
    dictation.onstart = () => { if (feedback) feedback.textContent = 'Escuchando...'; };
    dictation.onresult = event => {
      input.value = `${input.value} ${event.results[0][0].transcript}`.trim();
      if (feedback) feedback.textContent = 'Dictado terminado.';
    };
    dictation.onerror = () => { if (feedback) feedback.textContent = 'No se pudo usar el micrófono.'; };
    dictation.start();
  };

  function renderHypotheses() {
    if (!hypothesesList) return;
    hypothesesList.replaceChildren();
    const activeCount = hypotheses.filter(hypothesis => !hypothesis.discarded).length;
    if (hypothesesCount) hypothesesCount.textContent = `${activeCount} ${activeCount === 1 ? 'activa' : 'activas'}`;

    hypotheses.forEach((hypothesis, index) => {
      const item = document.createElement('li');
      item.className = 'bg-surface border border-slate-200 rounded-xl p-3 flex flex-col gap-2';
      const header = document.createElement('div');
      header.className = 'flex items-center justify-between gap-2';
      const name = document.createElement('span');
      name.className = hypothesis.discarded
        ? 'flex items-center gap-2 text-sm font-medium text-slate-500 line-through'
        : 'flex items-center gap-2 text-sm font-semibold text-slate-900';
      const dot = document.createElement('span');
      dot.className = `w-2 h-2 shrink-0 rounded-full ${hypothesis.discarded ? 'bg-slate-300' : 'bg-brand-600'}`;
      name.append(dot, hypothesis.name);
      header.appendChild(name);

      if (!hypothesis.discarded && !consultationClosed && discardingIndex !== index) {
        const discardButton = document.createElement('button');
        discardButton.type = 'button';
        discardButton.className = 'rounded-lg px-2 py-1 text-[13px] font-semibold text-slate-600 hover:bg-red-50 hover:text-red-700 transition-colors';
        discardButton.textContent = 'Descartar';
        discardButton.addEventListener('click', () => {
          discardingIndex = index;
          renderHypotheses();
        });
        header.appendChild(discardButton);
      }
      item.appendChild(header);

      if (hypothesis.discarded && hypothesis.reason) {
        const reason = document.createElement('p');
        reason.className = 'text-[13px] text-slate-600 italic leading-relaxed';
        reason.textContent = `Descartada: ${hypothesis.reason}`;
        item.appendChild(reason);
      }

      if (discardingIndex === index) {
        const form = document.createElement('div');
        form.className = 'flex flex-wrap items-center gap-1.5';
        const reasonInput = document.createElement('input');
        reasonInput.type = 'text';
        reasonInput.placeholder = '¿Por qué la descartas?';
        reasonInput.className = 'h-10 flex-1 min-w-0 rounded-lg border border-slate-300 bg-surface px-2.5 text-sm text-slate-900 outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-100';
        const reasonMic = document.createElement('button');
        reasonMic.type = 'button';
        reasonMic.title = 'Dictar motivo';
        reasonMic.className = 'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200';
        const reasonMicIcon = document.createElement('span');
        reasonMicIcon.className = 'material-symbols-outlined text-lg';
        reasonMicIcon.textContent = 'mic';
        reasonMic.append(reasonMicIcon);
        reasonMic.addEventListener('click', () => dictate(reasonInput, hypothesesFeedback));
        const confirmButton = document.createElement('button');
        confirmButton.type = 'button';
        confirmButton.className = 'h-10 rounded-lg bg-brand-600 px-3 text-[13px] font-semibold text-white hover:bg-brand-700';
        confirmButton.textContent = 'Confirmar';
        const cancelButton = document.createElement('button');
        cancelButton.type = 'button';
        cancelButton.className = 'h-10 rounded-lg px-2 text-[13px] font-semibold text-slate-600 hover:bg-slate-100';
        cancelButton.textContent = 'Cancelar';
        const confirmDiscard = () => {
          const reasonText = reasonInput.value.trim();
          if (!reasonText) {
            if (hypothesesFeedback) hypothesesFeedback.textContent = 'Indica el motivo del descarte.';
            reasonInput.focus();
            return;
          }
          hypothesis.discarded = true;
          hypothesis.reason = reasonText;
          discardingIndex = null;
          if (hypothesesFeedback) hypothesesFeedback.textContent = `Descartaste ${hypothesis.name}.`;
          renderHypotheses();
        };
        confirmButton.addEventListener('click', confirmDiscard);
        reasonInput.addEventListener('keydown', event => { if (event.key === 'Enter') confirmDiscard(); });
        cancelButton.addEventListener('click', () => {
          discardingIndex = null;
          renderHypotheses();
        });
        form.append(reasonInput, reasonMic, confirmButton, cancelButton);
        item.appendChild(form);
        window.setTimeout(() => reasonInput.focus(), 0);
      }
      hypothesesList.appendChild(item);
    });
  }

  const addHypothesis = () => {
    if (!hypothesisInput || consultationClosed) return;
    const text = hypothesisInput.value.trim();
    if (!text) {
      if (hypothesesFeedback) hypothesesFeedback.textContent = 'Escribe o dicta una hipótesis.';
      return;
    }
    const existing = hypotheses.find(hypothesis => hypothesis.name.toLowerCase() === text.toLowerCase());
    if (existing && !existing.discarded) {
      if (hypothesesFeedback) hypothesesFeedback.textContent = `${existing.name} ya está en tu lista.`;
      return;
    }
    if (existing) {
      existing.discarded = false;
      existing.reason = '';
      if (hypothesesFeedback) hypothesesFeedback.textContent = `Retomaste ${existing.name} como hipótesis activa.`;
    } else {
      hypotheses.push({ name: text, discarded: false, reason: '' });
      if (hypothesesFeedback) hypothesesFeedback.textContent = `Agregaste ${text}.`;
    }
    hypothesisInput.value = '';
    if (hypothesesHint) hypothesesHint.textContent = 'Actualiza tus hipótesis a medida que obtengas nuevos datos.';
    renderHypotheses();
  };

  addHypothesisButton?.addEventListener('click', addHypothesis);
  hypothesisInput?.addEventListener('keydown', event => { if (event.key === 'Enter') addHypothesis(); });
  hypothesisMic?.addEventListener('click', () => dictate(hypothesisInput, hypothesesFeedback));

  // Hoja de evaluación: el reporte final (HU-006) lo arma el servidor solo con datos del caso y de esta
  // consulta, y solo lo entrega al dueño tras el cierre. Todo se escribe como texto, nunca como HTML.
  const TEST_NOTES = { recommended_missing: 'Recomendado, no lo pediste', unnecessary_requested: 'Innecesario en este caso' };
  const fillList = (role, lines) => {
    const list = $(role);
    if (!list) return;
    list.replaceChildren(...lines.map(line => {
      const item = document.createElement('li');
      item.textContent = line;
      return item;
    }));
  };
  const setField = (role, text) => {
    const field = $(role);
    if (field) field.textContent = text;
  };
  const SAVED_MESSAGES = {
    guardado: 'Consulta guardada en «Mis simulaciones».',
    sin_sesion: 'Esta consulta no se guardó: inicia sesión para guardar tus próximas consultas en «Mis simulaciones».',
    iniciada_sin_sesion: 'Esta consulta empezó sin sesión iniciada, así que no se guardó. Las próximas se guardarán.',
    sesion_invalida: 'Tu sesión venció: vuelve a iniciar sesión para guardar tus próximas consultas.',
    otro_usuario: 'Esta consulta la empezó otra cuenta, así que no se guardó en la tuya.',
    no_configurado: 'El guardado de consultas no está disponible en este servidor.',
    error: 'No se pudo guardar esta consulta. La evaluación sigue siendo válida.',
  };
  const accessToken = async () => {
    try {
      const client = await window.auth?.ready;
      const { data } = client ? await client.auth.getSession() : { data: {} };
      return data?.session?.access_token || null;
    } catch {
      return null;
    }
  };
  const openEvaluation = () => {
    if (!evaluationPanel) return;
    evaluationPanel.hidden = false;
    evaluationPanel.classList.remove('hidden');
    evaluationPanel.classList.add('flex');
    closeEvaluation?.focus();
  };
  const hideEvaluation = () => {
    if (!evaluationPanel) return;
    evaluationPanel.hidden = true;
    evaluationPanel.classList.add('hidden');
    evaluationPanel.classList.remove('flex');
    diagnosisButton?.focus();
  };
  closeEvaluation?.addEventListener('click', hideEvaluation);
  evaluationPanel?.addEventListener('click', event => { if (event.target === evaluationPanel) hideEvaluation(); });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && evaluationPanel && !evaluationPanel.hidden) hideEvaluation();
  });

  // Un punto de la hoja: texto principal, etiquetas y una línea de explicación opcional.
  const sheetItem = (text, chips = [], why = '') => {
    const item = document.createElement('li');
    item.append(text);
    chips.forEach(([label, kind]) => {
      const chip = document.createElement('span');
      chip.className = `sheet-chip sheet-chip-${kind}`;
      chip.textContent = label;
      item.append(chip);
    });
    if (why) {
      const line = document.createElement('span');
      line.className = 'sheet-why';
      line.textContent = why;
      item.append(line);
    }
    return item;
  };
  const fillItems = (role, items) => {
    const list = $(role);
    if (list) list.replaceChildren(...items);
  };

  const showEvaluation = (report, diagnosis) => {
    if (currentCase) {
      const { alias, age_years: age } = currentCase.patient;
      setField('evaluation-patient', `${alias}, ${age} años`);
      setField('evaluation-chief', currentCase.chief_complaint.text);
    }
    setField('evaluation-date', new Date().toLocaleDateString('es-PE', { day: 'numeric', month: 'long', year: 'numeric' }));
    setField('evaluation-diagnosis', diagnosis || 'Sin diagnóstico registrado');
    setField('evaluation-student-diagnosis', report?.diagnosis?.student || diagnosis || 'Sin diagnóstico registrado');

    const studentHypotheses = report?.hypotheses || hypotheses;
    const active = studentHypotheses.filter(hypothesis => !hypothesis.discarded);
    const discarded = studentHypotheses.filter(hypothesis => hypothesis.discarded);
    fillList('evaluation-reasoning', [
      active.length ? `Hipótesis activas: ${active.map(hypothesis => hypothesis.name).join(', ')}.` : 'No dejaste hipótesis activas.',
      ...discarded.map(hypothesis => `Descartaste ${hypothesis.name}${hypothesis.reason ? `: ${hypothesis.reason}` : ''}.`),
      'El diagnóstico final se compara con la referencia y los sinónimos del caso al cerrar; su nota es independiente de la anamnesis.',
    ]);

    if (!report) {
      show($('evaluation-diagnosis-result'), false);
      setField('evaluation-score', '—');
      setField('evaluation-reference', '');
      ['evaluation-key-ok', 'evaluation-tests-ok', 'evaluation-tests-warn', 'evaluation-other-indications',
        'evaluation-differentials', 'evaluation-treatment-proposed', 'evaluation-treatment-reference',
        'evaluation-treatment-actions', 'evaluation-revealed', 'evaluation-recommendations'].forEach(role => fillList(role, []));
      fillList('evaluation-key-missing', ['No se pudo obtener el reporte de esta consulta. Verifica la conexión con el servidor.']);
      openEvaluation();
      return;
    }

    const { score, key_questions: keys, tests, treatment } = report;
    setField('evaluation-score', `${score.score}%`);
    setField('evaluation-summary', `Obtuviste ${score.completed_questions} de ${score.total_questions} datos clave del caso.`);
    setField('evaluation-reference', report.diagnosis.reference);
    const grade = report.diagnosis.grading;
    const gradePanel = $('evaluation-diagnosis-result');
    show(gradePanel, Boolean(grade));
    if (grade && gradePanel) {
      const names = { correct: 'Diagnóstico correcto', incorrect: 'Diagnóstico incorrecto',
        empty: 'Sin diagnóstico registrado', ambiguous: 'Respuesta ambigua · Revisión docente' };
      gradePanel.dataset.result = grade.status;
      setField('evaluation-diagnosis-status', names[grade.status] || 'Resultado del diagnóstico');
      setField('evaluation-diagnosis-score', grade.score + '/' + grade.max_score + ' puntos');
      setField('evaluation-diagnosis-reason', grade.reason);
    }

    fillItems('evaluation-key-ok', keys.obtained.map(question => sheetItem(question.topic)));
    fillItems('evaluation-key-missing', keys.missing.map(question => sheetItem(
      question.topic,
      [[question.error_name, question.error_type], ...(question.critical ? [['Crítico', 'critico']] : [])],
      [question.why, question.helps_discard.length ? `Ayudaba a descartar: ${question.helps_discard.join(', ')}.` : '']
        .filter(Boolean).join(' '),
    )));

    fillItems('evaluation-tests-ok', [
      ...tests.recommended_requested.map(test => sheetItem(test.label, [['Recomendado', 'razonamiento_clinico']])),
      ...tests.optional_requested.map(test => sheetItem(test.label, [['Opcional', 'info']])),
    ]);
    fillItems('evaluation-tests-warn', [
      ...tests.recommended_missing.map(test => sheetItem(test.label, [[TEST_NOTES.recommended_missing, 'anamnesis_incompleta']])),
      ...tests.unnecessary_requested.map(test => sheetItem(test.label, [[TEST_NOTES.unnecessary_requested, 'negligencia']])),
    ]);
    fillList('evaluation-other-indications', tests.other_indications);
    fillList('evaluation-differentials', report.differentials);

    fillItems('evaluation-treatment-proposed', treatment.proposed.length
      ? treatment.proposed.map(item => sheetItem(`Propusiste: ${item.message}`,
        item.alerts.length ? [['Alerta de seguridad', 'negligencia']] : []))
      : [sheetItem('No propusiste un tratamiento durante la consulta.')]);
    fillList('evaluation-treatment-reference', [treatment.reference_summary]);
    fillList('evaluation-treatment-actions', treatment.key_actions);

    const syntheticExams = report.synthetic_exams || [];
    setField('evaluation-revealed-summary', `Ver los ${report.revealed_evidence.length + syntheticExams.length} datos revelados`);
    // Algunos datos ya empiezan con su etiqueta («Troponina I ultrasensible: 2850 ng/L»): no se repite.
    fillItems('evaluation-revealed', [
      ...report.revealed_evidence.map(item => sheetItem(
        item.text.startsWith(item.label) ? item.text : `${item.label}: ${item.text}`)),
      ...syntheticExams.map(item => sheetItem(`${item.label}: ${item.text}`,
        [['Sintético · Revisión clínica pendiente', 'info']])),
    ]);
    fillList('evaluation-recommendations', report.recommendations);
    openEvaluation();
  };

  diagnosisButton?.addEventListener('click', () => {
    if (consultationClosed) {
      openEvaluation();
      return;
    }
    showTab('hipotesis');
    show(diagnosisPanel);
    diagnosisInput?.focus();
  });
  closeDiagnosis?.addEventListener('click', () => show(diagnosisPanel, false));
  diagnosisMic?.addEventListener('click', () => dictate(diagnosisInput, diagnosisFeedback));

  saveDiagnosis?.addEventListener('click', async () => {
    const diagnosis = diagnosisInput?.value.trim() || '';
    consultationClosed = true;
    discardingIndex = null;
    session += 1;
    window.speechSynthesis?.cancel();
    if (recognition && isListening) recognition.abort();
    [saveDiagnosis, diagnosisMic, micButton, diagnosisButton, hypothesisInput, hypothesisMic, addHypothesisButton].forEach(element => {
      if (element) element.disabled = true;
    });
    renderHypotheses();
    let report = null;
    let attempt = null;
    if (aiSessionId) {
      // Con la sesión iniciada se envía su token: el servidor lo comprueba y guarda la consulta en
      // «Mis simulaciones». Sin sesión la consulta termina igual, pero no se guarda.
      const response = await fetch(`/api/ai/sessions/${encodeURIComponent(aiSessionId)}/finish`, {
        method: 'POST',
        headers: await conversationHeaders(),
        body: JSON.stringify({
          diagnosis,
          hypotheses: hypotheses.map(({ name, discarded, reason }) => ({ name, discarded, reason: reason || '' })),
        }),
      }).catch(() => null);
      const finished = response?.ok ? await response.json().catch(() => null) : null;
      report = finished?.report || null;
      attempt = finished?.attempt || null;
    }
    show(diagnosisPanel, false);
    showEvaluation(report, diagnosis);
    setField('evaluation-saved', SAVED_MESSAGES[attempt?.saved ? 'guardado' : attempt?.reason] || '');
    // El botón de diagnóstico pasa a reabrir la hoja si el estudiante la cierra.
    if (diagnosisButton) {
      diagnosisButton.disabled = false;
      diagnosisButton.lastChild.textContent = ' Ver hoja de evaluación';
    }
    if (diagnosisFeedback) diagnosisFeedback.textContent = 'Diagnóstico guardado. Consulta finalizada.';
    simulatorStatus.textContent = 'Consulta finalizada';
    recordStatus.lastChild.textContent = 'Finalizada';
    setStatus('Consulta finalizada. En la hoja de evaluación puedes probar otro caso o cerrar el simulador.');
  });

  // «Probar otro caso»: misma especialidad, otro paciente. Se reinicia aquí mismo, sin recargar, para que
  // el clic del estudiante habilite la voz del doctor en la nueva presentación.
  $('another-case')?.addEventListener('click', () => {
    if (currentCase && (testCase || !specialtyName)) {
      // Desde un caso de prueba o sin especialidad elegida, se sigue con la especialidad del caso actual.
      specialty = currentCase.specialty;
      specialtyName = SPECIALTY_NAMES[specialty];
    }
    testCase = null;
    if (specialtyName) {
      window.history.replaceState(null, '', `simulacion.html?especialidad=${encodeURIComponent(specialty)}`);
    }
    hideEvaluation();
    aiSessionId = null;
    aiSessionToken = null;
    isRunning = false;
    [saveDiagnosis, diagnosisMic, hypothesisInput, hypothesisMic, addHypothesisButton].forEach(element => {
      if (element) element.disabled = false;
    });
    if (diagnosisInput) diagnosisInput.value = '';
    if (diagnosisFeedback) diagnosisFeedback.textContent = '';
    if (hypothesesFeedback) hypothesesFeedback.textContent = '';
    if (diagnosisButton) diagnosisButton.lastChild.textContent = ' Realizar Diagnóstico';
    setField('evaluation-saved', '');
    show(diagnosisPanel, false);
    show(hypothesesPanel, false);
    show(micButton, false);
    show(diagnosisButton, false);
    show(startButton);
    simulatorStatus.textContent = specialtyName || 'Cualquier especialidad';
    startSimulation({ another: true });
  });

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
    simulatorStatus.textContent = specialtyName || 'Cualquier especialidad';
    setStatus(caseAvailable
      ? `${specialtyName ? `Especialidad: ${specialtyName}. ` : ''}Pulsa «Iniciar simulación»: el doctor te presentará al paciente.`
      : 'Aún no hay casos clínicos disponibles.');
  } catch (error) {
    console.error('No se pudo comprobar la disponibilidad de casos clínicos:', error);
    setStatus('No se pudo comprobar el estado del simulador. Verifica que el servidor esté en ejecución.', true);
    simulatorStatus.textContent = 'Servidor no disponible';
    startButton.disabled = true;
    startButton.lastChild.textContent = ' Servidor no disponible';
  }
});
