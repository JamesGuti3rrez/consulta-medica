document.addEventListener('DOMContentLoaded', () => {
  const micBtn = document.querySelector('[aria-label="Micrófono"]');
  const startBtn = document.querySelector('[data-role="start-simulation"]');
  const diagBtn = [...document.querySelectorAll('button')].find(b =>
    b.textContent.includes('Realizar Diagnóstico')
  );
  const diagnosisPanel = document.querySelector('[data-role="diagnosis-panel"]');
  const diagnosisInput = document.querySelector('[data-role="diagnosis-input"]');
  const diagnosisMic = document.querySelector('[data-role="diagnosis-mic"]');
  const saveDiagnosis = document.querySelector('[data-role="save-diagnosis"]');
  const closeDiagnosis = document.querySelector('[data-role="close-diagnosis"]');
  const diagnosisFeedback = document.querySelector('[data-role="diagnosis-feedback"]');
  const evaluationPanel = document.querySelector('[data-role="evaluation-panel"]');
  const closeEvaluation = document.querySelector('[data-role="close-evaluation"]');
  const evaluationScore = document.querySelector('[data-role="evaluation-score"]');
  const evaluationStrengths = document.querySelector('[data-role="evaluation-strengths"]');
  const evaluationMissing = document.querySelector('[data-role="evaluation-missing"]');
  const evaluationRecommendations = document.querySelector('[data-role="evaluation-recommendations"]');
  const doctorStatus = document.querySelector('[data-role="doctor-status"]');
  const doctorText = document.querySelector('[data-role="doctor-text"]');
  const doctorBubble = document.querySelector('[data-role="doctor-bubble"]');
  const patientStatus = document.querySelector('[data-role="patient-status"]');
  const patientText = document.querySelector('[data-role="patient-text"]');
  const patientBubble = document.querySelector('[data-role="patient-bubble"]');
  const conversationHistory = document.querySelector('[data-role="conversation-history"]');
  const studentTranscript = conversationHistory;
  const patientTranscript = conversationHistory;
  const conversationStatus = document.querySelector('[data-role="conversation-status"]');
  const nextPrompt = document.querySelector('[data-role="next-prompt"]');
  const recordEmpty = document.querySelector('[data-role="record-empty"]');
  const patientRecord = document.querySelector('[data-role="patient-record"]');
  const recordName = document.querySelector('[data-role="record-name"]');
  const recordDemographics = document.querySelector('[data-role="record-demographics"]');
  const recordChief = document.querySelector('[data-role="record-chief"]');
  const hypothesesPanel = document.querySelector('[data-role="hypotheses-panel"]');
  const hypothesesCount = document.querySelector('[data-role="hypotheses-count"]');
  const hypothesesHint = document.querySelector('[data-role="hypotheses-hint"]');
  const hypothesisInput = document.querySelector('[data-role="hypothesis-input"]');
  const hypothesisMic = document.querySelector('[data-role="hypothesis-mic"]');
  const addHypothesisBtn = document.querySelector('[data-role="add-hypothesis"]');
  const hypothesesList = document.querySelector('[data-role="hypotheses-list"]');
  const hypothesesFeedback = document.querySelector('[data-role="hypotheses-feedback"]');
  const evaluationReasoning = document.querySelector('[data-role="evaluation-reasoning"]');
  const tabButtons = [...document.querySelectorAll('[data-tab]')];
  const tabPanels = [...document.querySelectorAll('[data-tab-panel]')];
  const consultaTab = tabButtons.find(button => button.dataset.tab === 'consulta');

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const recognition = SpeechRecognition ? new SpeechRecognition() : null;
  const diagnosisRecognition = SpeechRecognition ? new SpeechRecognition() : null;
  let isRunning = false;
  let isListening = false;
  let cancelListening = false;
  let sessionToken = 0;
  let finalTranscript = '';
  let studentPreview = null;
  let scriptedCase = [];
  let turnIndex = 0;
  let hypotheses = [];
  let discardingIndex = null;
  let consultationClosed = false;

  if (recognition) {
    recognition.lang = 'es-ES';
    recognition.continuous = false;
    recognition.interimResults = true;
  }

  if (diagnosisRecognition) {
    diagnosisRecognition.lang = 'es-ES';
    diagnosisRecognition.continuous = false;
    diagnosisRecognition.interimResults = false;
    diagnosisRecognition.onresult = event => {
      const transcript = event.results[0][0].transcript;
      if (diagnosisInput) diagnosisInput.value = `${diagnosisInput.value} ${transcript}`.trim();
    };
    diagnosisRecognition.onstart = () => {
      if (diagnosisFeedback) diagnosisFeedback.textContent = 'Escuchando el diagnóstico...';
      diagnosisMic?.classList.add('bg-red-100', 'text-red-700');
    };
    diagnosisRecognition.onend = () => {
      if (diagnosisFeedback) diagnosisFeedback.textContent = 'Dictado terminado.';
      diagnosisMic?.classList.remove('bg-red-100', 'text-red-700');
    };
    diagnosisRecognition.onerror = () => {
      if (diagnosisFeedback) diagnosisFeedback.textContent = 'No se pudo usar el micrófono.';
      diagnosisMic?.classList.remove('bg-red-100', 'text-red-700');
    };
  }

  const wait = milliseconds => new Promise(resolve => {
    window.setTimeout(resolve, milliseconds);
  });

  const speak = text => new Promise(resolve => {
    if (!('speechSynthesis' in window)) {
      wait(1400).then(resolve);
      return;
    }

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'es-ES';
    utterance.rate = 0.95;
    utterance.onend = resolve;
    utterance.onerror = resolve;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  });

  const setStatus = (element, text) => {
    if (!element) return;
    const textNode = [...element.childNodes].find(node => node.nodeType === Node.TEXT_NODE);
    if (textNode) textNode.nodeValue = ` ${text}`;
  };

  const setSpeaker = (speaker, text) => {
    const doctorIsSpeaking = speaker === 'doctor';
    if (micBtn && isRunning && !isListening) micBtn.title = 'Interrumpir y hablar';
    doctorBubble?.classList.toggle('hidden', !doctorIsSpeaking);
    patientBubble?.classList.toggle('hidden', doctorIsSpeaking);
    setStatus(doctorStatus, doctorIsSpeaking ? 'Hablando' : 'En espera');
    setStatus(patientStatus, doctorIsSpeaking ? 'En espera' : 'Hablando');

    if (doctorIsSpeaking && doctorText) doctorText.textContent = text;
    if (!doctorIsSpeaking && patientText) patientText.textContent = text;
    if (conversationStatus) conversationStatus.textContent = doctorIsSpeaking ? 'Doctor hablando' : 'Paciente respondiendo';
  };

  // Pestañas de la tablilla: Ficha, Consulta e Hipótesis.
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
    if (name === 'consulta' && conversationHistory) conversationHistory.scrollTop = conversationHistory.scrollHeight;
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

  const resetHistory = () => {
    if (!conversationHistory) return;
    conversationHistory.textContent = '';
    conversationHistory.dataset.started = 'true';
  };

  const appendHistory = (history, text, speaker) => {
    if (!history) return;
    if (history.dataset.started !== 'true') resetHistory();

    // Cada personaje con su avatar, su nombre y su color.
    const speakers = {
      doctor: { name: 'Doctor', role: 'Voz sintetizada', icon: 'stethoscope' },
      patient: { name: 'Carlos Eduardo', role: 'Paciente', icon: 'person' },
      student: { name: 'Tú', role: 'Médico en formación', icon: 'mic' }
    };
    const who = speakers[speaker] || speakers.student;
    const entry = document.createElement('div');
    entry.className = `chat-row chat-${speaker in speakers ? speaker : 'student'}`;
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
    history.appendChild(entry);
    history.scrollTop = history.scrollHeight;
    if (consultaTab && !consultaTab.classList.contains('is-active')) consultaTab.classList.add('has-news');
  };

  const removeStudentPreview = () => {
    studentPreview?.remove();
    studentPreview = null;
  };

  const renderList = (element, items) => {
    if (!element) return;
    element.textContent = '';
    items.forEach(item => {
      const listItem = document.createElement('li');
      listItem.textContent = item;
      element.appendChild(listItem);
    });
  };

  const dictate = (input, feedback) => {
    if (!SpeechRecognition) {
      if (feedback) feedback.textContent = 'El dictado requiere Chrome o Edge.';
      return;
    }
    const dictation = new SpeechRecognition();
    dictation.lang = 'es-ES';
    dictation.continuous = false;
    dictation.interimResults = false;
    dictation.onstart = () => {
      if (feedback) feedback.textContent = 'Escuchando...';
    };
    dictation.onresult = event => {
      input.value = `${input.value} ${event.results[0][0].transcript}`.trim();
      if (feedback) feedback.textContent = 'Dictado terminado.';
    };
    dictation.onerror = () => {
      if (feedback) feedback.textContent = 'No se pudo usar el micrófono.';
    };
    dictation.start();
  };

  const renderHypotheses = () => {
    if (!hypothesesList) return;
    hypothesesList.textContent = '';
    const activeCount = hypotheses.filter(hypothesis => !hypothesis.descartada).length;
    if (hypothesesCount) hypothesesCount.textContent = `${activeCount} ${activeCount === 1 ? 'activa' : 'activas'}`;

    hypotheses.forEach((hypothesis, index) => {
      const item = document.createElement('li');
      item.className = 'bg-surface border border-slate-200 rounded-xl p-3 flex flex-col gap-2';

      const header = document.createElement('div');
      header.className = 'flex items-center justify-between gap-2';
      const name = document.createElement('span');
      name.className = hypothesis.descartada
        ? 'flex items-center gap-2 text-sm font-medium text-slate-500 line-through'
        : 'flex items-center gap-2 text-sm font-semibold text-slate-900';
      const dot = document.createElement('span');
      dot.className = `w-2 h-2 shrink-0 rounded-full ${hypothesis.descartada ? 'bg-slate-300' : 'bg-brand-600'}`;
      name.append(dot, hypothesis.nombre);
      header.appendChild(name);

      const actions = document.createElement('div');
      actions.className = 'flex items-center gap-1.5';
      if (!hypothesis.id) {
        const badge = document.createElement('span');
        badge.className = 'text-[12px] font-medium text-amber-800 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full';
        badge.textContent = 'No reconocida';
        actions.appendChild(badge);
      }
      if (!hypothesis.descartada && !consultationClosed && discardingIndex !== index) {
        const discardBtn = document.createElement('button');
        discardBtn.type = 'button';
        discardBtn.className = 'rounded-lg px-2 py-1 text-[13px] font-semibold text-slate-600 hover:bg-red-50 hover:text-red-700 transition-colors';
        discardBtn.textContent = 'Descartar';
        discardBtn.addEventListener('click', () => {
          discardingIndex = index;
          renderHypotheses();
        });
        actions.appendChild(discardBtn);
      }
      header.appendChild(actions);
      item.appendChild(header);

      if (hypothesis.descartada && hypothesis.motivo) {
        const reason = document.createElement('p');
        reason.className = 'text-[13px] text-slate-600 italic leading-relaxed';
        reason.textContent = `Descartada: ${hypothesis.motivo}`;
        item.appendChild(reason);
      }

      if (discardingIndex === index) {
        const form = document.createElement('div');
        form.className = 'flex flex-wrap items-center gap-1.5';
        const reasonInput = document.createElement('input');
        reasonInput.type = 'text';
        reasonInput.placeholder = '¿Por qué la descartas?';
        reasonInput.className = 'h-10 flex-1 min-w-0 rounded-lg border border-slate-300 bg-surface px-2.5 text-sm text-slate-900 outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-100';
        const micButton = document.createElement('button');
        micButton.type = 'button';
        micButton.title = 'Dictar motivo';
        micButton.className = 'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200';
        micButton.innerHTML = '<span class="material-symbols-outlined text-lg">mic</span>';
        micButton.addEventListener('click', () => dictate(reasonInput, hypothesesFeedback));
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
          hypothesis.descartada = true;
          hypothesis.descartadaEnTurno = turnIndex;
          hypothesis.motivo = reasonText;
          discardingIndex = null;
          if (hypothesesFeedback) hypothesesFeedback.textContent = `Descartaste ${hypothesis.nombre}.`;
          renderHypotheses();
        };
        confirmButton.addEventListener('click', confirmDiscard);
        reasonInput.addEventListener('keydown', event => {
          if (event.key === 'Enter') confirmDiscard();
        });
        cancelButton.addEventListener('click', () => {
          discardingIndex = null;
          renderHypotheses();
        });

        form.append(reasonInput, micButton, confirmButton, cancelButton);
        item.appendChild(form);
        window.setTimeout(() => reasonInput.focus(), 0);
      }

      hypothesesList.appendChild(item);
    });
  };

  const addHypothesis = async () => {
    if (!hypothesisInput || consultationClosed) return;
    const text = hypothesisInput.value.trim();
    if (!text) {
      if (hypothesesFeedback) hypothesesFeedback.textContent = 'Escribe o dicta una hipótesis.';
      return;
    }

    let match = null;
    try {
      const response = await fetch('/api/hipotesis', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ texto: text })
      });
      if (!response.ok) throw new Error(`API respondió con HTTP ${response.status}`);
      const payload = await response.json();
      if (payload.reconocida) match = payload;
    } catch (error) {
      console.warn('No se pudo verificar la hipótesis:', error.message);
    }

    const existing = match
      ? hypotheses.find(hypothesis => hypothesis.id === match.id)
      : hypotheses.find(hypothesis => !hypothesis.id && hypothesis.texto.toLowerCase() === text.toLowerCase());

    if (existing && !existing.descartada) {
      if (hypothesesFeedback) hypothesesFeedback.textContent = `${existing.nombre} ya está en tu lista.`;
      return;
    }

    if (existing) {
      existing.texto = text;
      existing.descartada = false;
      existing.descartadaEnTurno = null;
      existing.motivo = '';
      if (hypothesesFeedback) hypothesesFeedback.textContent = `Retomaste ${existing.nombre} como hipótesis activa.`;
    } else {
      hypotheses.push({
        texto: text,
        id: match?.id || null,
        nombre: match?.nombre || text,
        agregadaEnTurno: turnIndex,
        descartada: false,
        descartadaEnTurno: null,
        motivo: ''
      });
      if (hypothesesFeedback) {
        hypothesesFeedback.textContent = match
          ? `Agregaste ${match.nombre}.`
          : 'Hipótesis agregada, pero no se reconoció entre los diferenciales del caso.';
      }
    }

    hypothesisInput.value = '';
    if (hypothesesHint) hypothesesHint.textContent = 'Actualiza tus hipótesis a medida que obtengas nuevos datos.';
    renderHypotheses();
  };

  const renderReasoning = async diagnosis => {
    if (!evaluationReasoning) return;
    evaluationReasoning.textContent = '';
    const loading = document.createElement('li');
    loading.textContent = 'Evaluando tu razonamiento...';
    evaluationReasoning.appendChild(loading);

    let items;
    try {
      const response = await fetch('/api/evaluar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hipotesis: hypotheses, diagnostico: diagnosis })
      });
      if (!response.ok) throw new Error(`API respondió con HTTP ${response.status}`);
      items = (await response.json()).razonamiento;
    } catch (error) {
      console.warn('No se pudo evaluar el razonamiento:', error.message);
      items = [{ tipo: 'aviso', texto: 'No se pudo evaluar el razonamiento. Verifica que el servidor esté en ejecución.' }];
    }

    const colors = { ok: 'text-slate-700', aviso: 'text-amber-700', error: 'text-red-700' };
    evaluationReasoning.textContent = '';
    items.forEach(item => {
      const listItem = document.createElement('li');
      listItem.className = colors[item.tipo] || colors.ok;
      listItem.textContent = item.texto;
      evaluationReasoning.appendChild(listItem);
    });
  };

  const renderEvaluation = () => {
    const completedTurns = Math.min(turnIndex, scriptedCase.length);
    const totalTurns = scriptedCase.length;
    const percentage = totalTurns ? Math.round((completedTurns / totalTurns) * 100) : 0;
    const strengths = scriptedCase.slice(0, completedTurns).map(turn => turn.sugerencia_alumno.replace(/^Pregúntale /i, 'Preguntaste '));
    const missing = scriptedCase.slice(completedTurns).map(turn => turn.sugerencia_alumno);
    const recommendations = [];

    if (completedTurns === 0) {
      strengths.push('No se completó ningún turno del interrogatorio.');
    } else if (completedTurns === totalTurns) {
      recommendations.push('Completaste todos los temas previstos en el guion. Revisa siempre los signos de alarma antes de cerrar una consulta.');
    } else {
      recommendations.push('Completa la anamnesis antes de establecer un diagnóstico.');
      recommendations.push('Prioriza antecedentes, medicación, alergias y signos de alarma.');
    }

    if (evaluationScore) evaluationScore.textContent = `${percentage}/100`;
    renderList(evaluationStrengths, strengths);
    renderList(evaluationMissing, missing.length ? missing : ['No quedaron preguntas pendientes del guion.']);
    renderList(evaluationRecommendations, recommendations);
    if (completedTurns === 0) evaluationStrengths?.firstElementChild?.classList.add('is-empty');
    evaluationPanel?.classList.remove('hidden');
    evaluationPanel?.classList.add('flex');
    if (evaluationPanel) evaluationPanel.hidden = false;
  };

  // Encabezado de la hoja de evaluación con los datos de la consulta.
  const fillEvaluationHeader = diagnosis => {
    const fields = {
      'evaluation-patient': recordName?.textContent.trim(),
      'evaluation-chief': recordChief?.textContent.trim(),
      'evaluation-diagnosis': diagnosis,
      'evaluation-date': new Date().toLocaleDateString('es-PE', { day: 'numeric', month: 'long', year: 'numeric' })
    };
    Object.entries(fields).forEach(([role, value]) => {
      const element = document.querySelector(`[data-role="${role}"]`);
      if (element && value) element.textContent = value;
    });
  };

  const startSimulation = async () => {
    if (!startBtn || isRunning) return;
    isRunning = true;
    sessionToken += 1;
    const currentSession = sessionToken;
    turnIndex = 0;
    hypotheses = [];
    discardingIndex = null;
    renderHypotheses();
    startBtn.disabled = true;
    startBtn.innerHTML = '<span class="material-symbols-outlined text-lg">hourglass_top</span> Presentando caso...';
    if (micBtn) micBtn.disabled = true;
    if (diagBtn) diagBtn.disabled = true;
    if (recordEmpty) recordEmpty.hidden = true;
    showTab('ficha');
    resetHistory();
    if (patientRecord) {
      patientRecord.hidden = false;
      patientRecord.classList.remove('hidden');
    }

    let clinicalCase;
    try {
      const response = await fetch('/api/caso');
      if (!response.ok) throw new Error('No se pudo cargar el caso');
      clinicalCase = await response.json();
    } catch (error) {
      console.warn('Se usaran los datos visibles de la demo:', error.message);
      clinicalCase = {
        paciente: {
          nombre: 'Carlos Eduardo Ramos',
          edad: 28,
          sexo: 'masculino',
          motivo_consulta: 'Dolor de cabeza de 3 días de evolución',
          antecedentes: 'Niega enfermedades crónicas conocidas',
          alergias: 'Niega alergias medicamentosas conocidas',
          medicacion_previa: 'Paracetamol 1 g con mejoría parcial y transitoria'
        },
        guion_conversacion: []
      };
    }

    scriptedCase = clinicalCase.guion_conversacion || [];
    if (nextPrompt && scriptedCase[0]) nextPrompt.textContent = `Sugerencia: ${scriptedCase[0].sugerencia_alumno}`;

    if (recordName) recordName.textContent = clinicalCase.paciente.nombre;
    if (recordDemographics) recordDemographics.textContent = `${clinicalCase.paciente.edad} años • ${clinicalCase.paciente.sexo}`;
    if (recordChief) recordChief.textContent = clinicalCase.paciente.motivo_consulta;

    const recordSections = patientRecord ? [...patientRecord.children] : [];
    recordSections.forEach(section => { section.hidden = true; });
    const presentation = [
      {
        text: `${clinicalCase.paciente.nombre}, de ${clinicalCase.paciente.edad} años, sexo ${clinicalCase.paciente.sexo}, consulta por ${clinicalCase.paciente.motivo_consulta}.`,
        section: 0
      },
      {
        text: `El dolor es pulsátil y predomina detrás del ojo derecho. También presenta molestia con la luz y náuseas leves.`,
        section: 1
      },
      {
        text: 'Sus signos vitales son: presión arterial de 120 sobre 80 milímetros de mercurio, frecuencia cardíaca de 74 latidos por minuto, temperatura de 36.8 grados Celsius y saturación de oxígeno de 98 por ciento.',
        section: 2
      },
    ];

    for (const step of presentation) {
      if (currentSession !== sessionToken) return;
      if (recordSections[step.section]) recordSections[step.section].hidden = false;
      appendHistory(conversationHistory, step.text, 'doctor');
      setSpeaker('doctor', step.text);
      await speak(step.text);
    }

    if (currentSession !== sessionToken) return;
    const readyMessage = 'Doctor, puede comenzar con el interrogatorio.';
    appendHistory(conversationHistory, readyMessage, 'doctor');
    setSpeaker('doctor', readyMessage);
    await speak(readyMessage);
    setStatus(doctorStatus, 'Listo');
    setStatus(patientStatus, 'Listo');
    startBtn.hidden = true;
    if (micBtn) {
      micBtn.classList.remove('hidden');
      micBtn.disabled = false;
    }
    if (diagBtn) {
      diagBtn.classList.remove('hidden');
      diagBtn.disabled = false;
    }
    if (hypothesesPanel) {
      hypothesesPanel.hidden = false;
      hypothesesPanel.classList.remove('hidden');
    }
    showTab('consulta');
    isRunning = false;
  };

  const respondToStudent = async (question, currentSession) => {
    if (!question) return;
    const turn = scriptedCase[turnIndex];
    if (!turn) {
      setSpeaker('doctor', 'El guion de este caso ha terminado. Ya puedes realizar el diagnóstico.');
      setStatus(doctorStatus, 'Listo');
      setStatus(patientStatus, 'Listo');
      isRunning = false;
      return;
    }

    let doctorQuestion = turn.pregunta_doctor;
    let patientAnswer = turn.respuesta_paciente;

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, turnIndex })
      });

      if (!response.ok) throw new Error(`API respondió con HTTP ${response.status}`);
      const payload = await response.json();
      if (payload.doctorQuestion) doctorQuestion = payload.doctorQuestion;
      if (payload.answer) patientAnswer = payload.answer;
      if (nextPrompt) {
        nextPrompt.textContent = payload.nextPrompt
          ? `Sugerencia: ${payload.nextPrompt}`
          : 'Guion completo. Puedes realizar el diagnóstico.';
      }
    } catch (error) {
      console.warn('Se usará la respuesta local de demo:', error.message);
    }

    if (currentSession !== sessionToken) return;

    appendHistory(conversationHistory, doctorQuestion, 'doctor');
    setSpeaker('doctor', doctorQuestion);
    await speak(doctorQuestion);
    if (currentSession !== sessionToken) return;

    if (patientBubble && patientText) {
      doctorBubble?.classList.add('hidden');
      patientBubble.classList.remove('hidden');
      patientText.innerHTML = '<span class="typing-dots" aria-label="El paciente está pensando"><i></i><i></i><i></i></span>';
      setStatus(patientStatus, 'Pensando');
      await wait(700);
      if (currentSession !== sessionToken) return;
    }

    appendHistory(conversationHistory, patientAnswer, 'patient');
    turnIndex += 1;
    if (hypothesesHint) hypothesesHint.textContent = '¿Este dato cambia alguna de tus hipótesis?';
    setSpeaker('patient', patientAnswer);
    await speak(patientAnswer);
    if (currentSession !== sessionToken) return;

    setStatus(doctorStatus, 'Listo');
    setStatus(patientStatus, 'Listo');
    isRunning = false;
  };

  if (recognition) {
    recognition.onstart = () => {
      finalTranscript = '';
      cancelListening = false;
      isRunning = true;
      isListening = true;
      showTab('consulta');
      doctorBubble?.classList.add('hidden');
      patientBubble?.classList.add('hidden');
      micBtn.title = 'Escuchando...';
      micBtn.classList.add('bg-red-600', 'hover:bg-red-700', 'is-listening');
      micBtn.classList.remove('bg-brand-600', 'hover:bg-brand-700');
      setStatus(doctorStatus, 'En espera');
      setStatus(patientStatus, 'Escuchando');
      removeStudentPreview();
      if (studentTranscript) {
        studentPreview = document.createElement('p');
        studentPreview.className = 'chat-preview';
        studentPreview.textContent = 'Escuchándote...';
        studentTranscript.appendChild(studentPreview);
      }
    };

    recognition.onresult = event => {
      let visibleTranscript = '';

      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const text = event.results[index][0].transcript;
        visibleTranscript += text;
        if (event.results[index].isFinal) finalTranscript += text;
      }

      if (studentTranscript && visibleTranscript.trim()) {
        if (!studentPreview) {
          studentPreview = document.createElement('p');
          studentPreview.className = 'chat-preview';
          studentTranscript.appendChild(studentPreview);
        }
        studentPreview.textContent = visibleTranscript.trim();
      }
    };

    recognition.onerror = event => {
      cancelListening = false;
      isRunning = false;
      isListening = false;
      micBtn.title = 'Hablar / Siguiente Intervención';
      micBtn.classList.remove('bg-red-600', 'hover:bg-red-700', 'is-listening');
      micBtn.classList.add('bg-brand-600', 'hover:bg-brand-700');
      setStatus(patientStatus, 'Listo');

      if (event.error !== 'aborted') {
        window.alert('No se pudo usar el micrófono. Revisa el permiso del navegador.');
      }
    };

    recognition.onend = async () => {
      isListening = false;
      micBtn.title = 'Hablar / Siguiente Intervención';
      micBtn.classList.remove('bg-red-600', 'hover:bg-red-700', 'is-listening');
      micBtn.classList.add('bg-brand-600', 'hover:bg-brand-700');

      if (cancelListening) {
        cancelListening = false;
        isRunning = false;
        setStatus(doctorStatus, 'Listo');
        setStatus(patientStatus, 'Listo');
        removeStudentPreview();
        return;
      }

      removeStudentPreview();
      const question = finalTranscript.trim();
      if (question) {
        appendHistory(studentTranscript, question, 'student');
        await respondToStudent(question, sessionToken);
      } else {
        setStatus(doctorStatus, 'Listo');
        setStatus(patientStatus, 'Listo');
        isRunning = false;
      }
    };
  }

  const startListening = () => {
    if (!recognition || isListening) return;
    sessionToken += 1;
    recognition.start();
  };

  const interruptConversation = () => {
    sessionToken += 1;
    window.speechSynthesis?.cancel();
    isRunning = false;
    setStatus(doctorStatus, 'Interrumpido');
    setStatus(patientStatus, 'Escuchando');
    startListening();
  };

  startBtn?.addEventListener('click', startSimulation);

  micBtn?.addEventListener('click', () => {
    if (!recognition) {
      window.alert('El reconocimiento de voz no está disponible. Usa Chrome o Edge con permiso para el micrófono.');
      return;
    }

    if (isListening) {
      cancelListening = true;
      sessionToken += 1;
      window.speechSynthesis?.cancel();
      recognition.stop();
      return;
    }
    if (isRunning) {
      interruptConversation();
      return;
    }

    startListening();
  });

  diagBtn?.addEventListener('click', () => {
    showTab('hipotesis');
    diagnosisPanel?.classList.remove('hidden');
    if (diagnosisPanel) diagnosisPanel.hidden = false;
    diagnosisInput?.focus();
  });

  closeDiagnosis?.addEventListener('click', () => {
    diagnosisPanel?.classList.add('hidden');
    if (diagnosisPanel) diagnosisPanel.hidden = true;
  });

  closeEvaluation?.addEventListener('click', () => {
    evaluationPanel?.classList.add('hidden');
    evaluationPanel?.classList.remove('flex');
    if (evaluationPanel) evaluationPanel.hidden = true;
  });

  diagnosisMic?.addEventListener('click', () => {
    if (!diagnosisRecognition) {
      if (diagnosisFeedback) diagnosisFeedback.textContent = 'El dictado requiere Chrome o Edge.';
      return;
    }
    diagnosisRecognition.start();
  });

  saveDiagnosis?.addEventListener('click', () => {
    const diagnosis = diagnosisInput?.value.trim();
    if (!diagnosis) {
      if (diagnosisFeedback) diagnosisFeedback.textContent = 'Escribe o dicta un diagnóstico antes de guardar.';
      return;
    }
    if (diagnosisFeedback) diagnosisFeedback.textContent = 'Diagnóstico guardado. Consulta finalizada.';
    if (saveDiagnosis) saveDiagnosis.disabled = true;
    if (diagnosisMic) diagnosisMic.disabled = true;
    consultationClosed = true;
    discardingIndex = null;
    [hypothesisInput, hypothesisMic, addHypothesisBtn].forEach(element => {
      if (element) element.disabled = true;
    });
    renderHypotheses();
    fillEvaluationHeader(diagnosis);
    renderEvaluation();
    renderReasoning(diagnosis);
  });

  addHypothesisBtn?.addEventListener('click', addHypothesis);
  hypothesisInput?.addEventListener('keydown', event => {
    if (event.key === 'Enter') addHypothesis();
  });
  hypothesisMic?.addEventListener('click', () => dictate(hypothesisInput, hypothesesFeedback));
});

