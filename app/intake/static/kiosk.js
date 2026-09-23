/**
 * Primary Health Centre (PHC) Patient Check-In — Conversational Kiosk Client
 * 
 * Features:
 * 1. Tap-based language selection (English / தமிழ்) with 100% full language lock-in.
 * 2. Zero spoken-language inference: language is only ever set by a tap.
 * 3. Affirming 'nodding' audio cue (Web Audio API) immediately upon silence auto-stop.
 * 4. Strict mic activation timing: recognition strictly starts only after utterance.onend.
 * 5. Two-strike silence freeze handling with schema-valid blank generation.
 * 6. Mid-conversation red-flag emergency short-circuit with immediate token announcement.
 * 7. Speaks token number out loud in closing TTS with full keep-alive anti-cutoff protection.
 * 8. Audited for PHC wording (நிலையம் / பணியாளர்), zero 'மருத்துவமனை'.
 */

document.addEventListener('DOMContentLoaded', () => {
  // State
  let sessionId = null;
  let currentLanguage = 'en'; // 'en' or 'ta'
  let isListening = false;
  let isSpeaking = false;
  let accumulatedSpeech = '';
  let silenceTimer = null;
  let recognition = null;
  let voices = [];
  let silenceStrikes = 0;
  let ttsKeepAliveTimer = null;

  // DOM Elements
  const idleView = document.getElementById('idleView');
  const languageView = document.getElementById('languageView');
  const conversationView = document.getElementById('conversationView');
  const closingView = document.getElementById('closingView');

  const btnStartSession = document.getElementById('btnStartSession');
  const btnSelectEn = document.getElementById('btnSelectEn');
  const btnSelectTa = document.getElementById('btnSelectTa');
  const sessionLangBadge = document.getElementById('sessionLangBadge');
  const kioskNotice = document.getElementById('kioskNotice');

  const statusPip = document.getElementById('statusPip');
  const statusLabelText = document.getElementById('statusLabelText');
  const questionStepTag = document.getElementById('questionStepTag');
  const btnRepeatQuestion = document.getElementById('btnRepeatQuestion');
  const repeatBtnText = document.getElementById('repeatBtnText');

  const kioskSpeechCaption = document.getElementById('kioskSpeechCaption');
  const patientSpeechCaption = document.getElementById('patientSpeechCaption');

  const micIconBox = document.getElementById('micIconBox');
  const micPulseRing = document.getElementById('micPulseRing');

  const closingCard = document.querySelector('.closing-card');
  const closingHeaderBadge = document.getElementById('closingHeaderBadge');
  const closingBadgeText = document.getElementById('closingBadgeText');
  const closingMainTitle = document.getElementById('closingMainTitle');
  const closingInstruction = document.getElementById('closingInstruction');
  const phcTokenBox = document.querySelector('.phc-token-box');
  const closingTokenValue = document.getElementById('closingTokenValue');
  const closingProgressBar = document.getElementById('closingProgressBar');

  // Load SpeechSynthesis Voices
  function loadVoices() {
    if ('speechSynthesis' in window) {
      voices = window.speechSynthesis.getVoices();
    }
  }
  loadVoices();
  if ('speechSynthesis' in window && window.speechSynthesis.onvoiceschanged !== undefined) {
    window.speechSynthesis.onvoiceschanged = loadVoices;
  }

  // Speech Recognition Check
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    kioskNotice.textContent = 'Notice: Voice input requires a Chromium browser (Google Chrome or Microsoft Edge) on this workstation.';
    kioskNotice.classList.remove('hidden');
  }

  // View Switching Helper
  function switchView(viewName) {
    idleView.classList.add('hidden');
    languageView.classList.add('hidden');
    conversationView.classList.add('hidden');
    closingView.classList.add('hidden');

    if (viewName === 'idle') {
      idleView.classList.remove('hidden');
      sessionLangBadge.classList.add('hidden');
    } else if (viewName === 'language') {
      languageView.classList.remove('hidden');
      sessionLangBadge.classList.add('hidden');
    } else if (viewName === 'conversation') {
      conversationView.classList.remove('hidden');
      sessionLangBadge.classList.remove('hidden');
    } else if (viewName === 'closing') {
      closingView.classList.remove('hidden');
      sessionLangBadge.classList.remove('hidden');
    }
  }

  // Set Status Strip (speaking / listening / processing)
  function setStatus(state, label) {
    statusPip.className = 'status-pip ' + state;
    statusLabelText.textContent = label;
  }

  // Visual Microphone State Updater (static line icon, no container shape or pulse ring)
  function updateMicVisual(active) {
    if (micIconBox) {
      micIconBox.classList.toggle('listening', active);
    }
  }

  // Affirming 'Nodding' Audio Feedback (Instant gentle chime on silence auto-stop)
  function playNoddingChime() {
    try {
      const AudioCtxClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtxClass) return;
      const audioCtx = new AudioCtxClass();
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();

      osc.type = 'sine';
      osc.frequency.setValueAtTime(587.33, audioCtx.currentTime); // D5
      osc.frequency.exponentialRampToValueAtTime(880, audioCtx.currentTime + 0.12); // A5

      gain.gain.setValueAtTime(0.15, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.28);

      osc.connect(gain);
      gain.connect(audioCtx.destination);

      osc.start();
      osc.stop(audioCtx.currentTime + 0.28);
    } catch (e) {
      console.warn('AudioContext chime blocked or not supported:', e);
    }
  }

  // Smooth Caption Transition Helper
  function updateCaptionSmoothly(newText) {
    kioskSpeechCaption.classList.remove('fade-in');
    kioskSpeechCaption.classList.add('fade-out');

    setTimeout(() => {
      kioskSpeechCaption.textContent = `"${newText}"`;
      kioskSpeechCaption.classList.remove('fade-out');
      kioskSpeechCaption.classList.add('fade-in');
    }, 220);
  }

  // Active audio element for remote/streamed TTS fallback
  let activeAudio = null;

  function stopAllSpeech() {
    if (activeAudio) {
      try {
        activeAudio.pause();
        activeAudio.currentTime = 0;
      } catch (e) {}
      activeAudio = null;
    }
    if ('speechSynthesis' in window) {
      try {
        window.speechSynthesis.cancel();
      } catch (e) {}
    }
    if (ttsKeepAliveTimer) {
      clearInterval(ttsKeepAliveTimer);
      ttsKeepAliveTimer = null;
    }
    window._activeUtterance = null;
    isSpeaking = false;
  }

  // Text-To-Speech with Tamil Audio Proxy Fallback & Anti-Cutoff Protection
  function kioskSpeak(text, lang, onDone) {
    stopAllSpeech();

    if (!text || !text.trim()) {
      if (onDone) onDone();
      return;
    }

    isSpeaking = true;
    setStatus('speaking', lang === 'ta' ? 'கியோஸ்க் பேசுகிறது...' : 'Kiosk Speaking...');

    // Ensure voices are loaded
    if (!voices || voices.length === 0) {
      loadVoices();
    }

    // Check if a native Tamil voice is installed on this workstation
    const hasTamilVoice = voices && voices.some(v => v.lang.startsWith('ta') || v.name.toLowerCase().includes('tamil'));

    // If Tamil is requested and no local Tamil voice is available, use the high-fidelity server TTS proxy
    if (lang === 'ta' && !hasTamilVoice) {
      const audioUrl = '/intake/tts?lang=ta&text=' + encodeURIComponent(text.trim());
      const audio = new Audio(audioUrl);
      activeAudio = audio;

      let finished = false;
      const finishAudio = () => {
        if (finished) return;
        finished = true;
        isSpeaking = false;
        activeAudio = null;
        if (onDone) onDone();
      };

      audio.onended = finishAudio;
      audio.onerror = (e) => {
        console.warn('Tamil audio proxy error, falling back to browser synthesis:', e);
        fallbackBrowserSynthesis(text, lang, finishAudio);
      };

      // Play audio
      audio.play().catch((playErr) => {
        console.warn('Audio playback error:', playErr);
        fallbackBrowserSynthesis(text, lang, finishAudio);
      });
      return;
    }

    // Standard Browser SpeechSynthesis path
    fallbackBrowserSynthesis(text, lang, onDone);
  }

  function fallbackBrowserSynthesis(text, lang, onDone) {
    if (!('speechSynthesis' in window)) {
      isSpeaking = false;
      if (onDone) setTimeout(onDone, 800);
      return;
    }

    // Unpause in case Chromium was left in suspended state
    try { window.speechSynthesis.resume(); } catch (e) {}

    const utterance = new SpeechSynthesisUtterance(text);
    const targetLang = lang === 'ta' ? 'ta-IN' : 'en-US';
    utterance.lang = targetLang;
    utterance.rate = lang === 'ta' ? 0.92 : 1.0;
    utterance.pitch = 1.0;

    if (voices && voices.length > 0) {
      if (lang === 'ta') {
        const taVoice = voices.find(v => v.lang.startsWith('ta') || v.name.toLowerCase().includes('tamil'));
        if (taVoice) utterance.voice = taVoice;
      } else {
        const femaleVoiceNames = ['zira', 'google us english', 'samantha', 'jenny', 'aria', 'sonia', 'female', 'victoria', 'karen'];
        let enVoice = voices.find(v => {
          if (!v.lang.startsWith('en')) return false;
          const nameLower = v.name.toLowerCase();
          return femaleVoiceNames.some(candidate => nameLower.includes(candidate));
        });
        if (!enVoice) {
          enVoice = voices.find(v => v.lang.startsWith('en'));
        }
        if (enVoice) utterance.voice = enVoice;
      }
    }

    function cleanup() {
      if (ttsKeepAliveTimer) {
        clearInterval(ttsKeepAliveTimer);
        ttsKeepAliveTimer = null;
      }
      window._activeUtterance = null;
      isSpeaking = false;
    }

    let finished = false;
    const safeDone = () => {
      if (finished) return;
      finished = true;
      cleanup();
      if (onDone) onDone();
    };

    // Safety timeout in case utterance neither ends nor errors (Chromium bug)
    const maxSpeechDurationMs = Math.max(3000, text.length * 90);
    const safetyTimer = setTimeout(() => {
      if (isSpeaking) {
        console.warn('TTS safety timeout reached, forcing transition.');
        safeDone();
      }
    }, maxSpeechDurationMs);

    utterance.onend = () => {
      clearTimeout(safetyTimer);
      safeDone();
    };
    utterance.onerror = (e) => {
      clearTimeout(safetyTimer);
      console.warn('SpeechSynthesis error event:', e);
      safeDone();
    };

    if (ttsKeepAliveTimer) clearInterval(ttsKeepAliveTimer);
    ttsKeepAliveTimer = setInterval(() => {
      if ('speechSynthesis' in window && window.speechSynthesis.speaking) {
        window.speechSynthesis.pause();
        window.speechSynthesis.resume();
      } else {
        clearInterval(ttsKeepAliveTimer);
        ttsKeepAliveTimer = null;
      }
    }, 10000);

    window._activeUtterance = utterance;
    try {
      window.speechSynthesis.speak(utterance);
    } catch (e) {
      console.error('window.speechSynthesis.speak error:', e);
      clearTimeout(safetyTimer);
      safeDone();
    }
  }




  // Auto-Stop Voice-Activity Listening (Strictly activates ONLY after TTS finishes)
  function startListening(listenLang, onCompleteUtterance) {
    if (!SpeechRecognition) return;

    if (isListening && recognition) {
      try { recognition.abort(); } catch (e) {}
    }

    accumulatedSpeech = '';
    const promptMsg = listenLang.startsWith('ta')
      ? 'பேசவும்... நீங்கள் பேசி முடித்ததும் தானாகவே பதிவு செய்யப்படும்.'
      : 'Listening... Please speak your answer. Recording stops automatically when you finish.';

    patientSpeechCaption.textContent = promptMsg;
    setStatus('listening', listenLang.startsWith('ta') ? 'உங்கள் பதிலைக் கேட்கிறது...' : 'Listening to patient...');
    updateMicVisual(true);

    recognition = new SpeechRecognition();
    recognition.lang = listenLang;
    recognition.continuous = true;
    recognition.interimResults = true;

    isListening = true;

    function resetSilenceTimer() {
      if (silenceTimer) clearTimeout(silenceTimer);
      // Auto-stop when speech pauses for 1.8 seconds
      silenceTimer = setTimeout(() => {
        stopAndSubmit();
      }, 1800);
    }

    function stopAndSubmit() {
      if (!isListening) return;
      isListening = false;
      if (silenceTimer) clearTimeout(silenceTimer);

      try {
        recognition.stop();
      } catch (e) {}

      updateMicVisual(false);
      playNoddingChime(); // Instant audio cue before proceeding

      const speechOutput = accumulatedSpeech.trim();
      const isRepeatClient = /^(?:please\s+)?repeat(?:\s+again|\s+please|\s+that)?$|^again$|^pardon|^மறுபடியும்|^திருப்பியும்|^திரும்பவும்/i.test(speechOutput);
      setStatus('processing', isRepeatClient ? (listenLang.startsWith('ta') ? 'மீண்டும் கேட்கப்படுகிறது...' : 'Repeating question...') : 'Processing...');

      // Handling "The Freeze" (Absolute Silence timeout)
      if (!speechOutput) {
        silenceStrikes++;
        if (silenceStrikes === 1) {
          // Strike 1: Re-prompt gently, remain on same question
          const strikePrompt = listenLang.startsWith('ta')
            ? 'நீங்கள் பேசுவது எனக்கு கேட்கவில்லை. உதவி தேவைப்பட்டால், நிலையப் பணியாளர்களை அணுகவும்.'
            : 'I did not hear you. If you need help, please see the staff.';
          updateCaptionSmoothly(strikePrompt);
          kioskSpeak(strikePrompt, listenLang.startsWith('ta') ? 'ta' : 'en', () => {
            // Re-listen for same question strictly after TTS finishes
            startListening(listenLang, onCompleteUtterance);
          });
          return;
        } else {
          // Strike 2: Gracefully close session, issue token, and build valid blank IntakeResult
          sendPatientSpeech('', true);
          return;
        }
      }

      // Valid response captured: reset strike count
      silenceStrikes = 0;
      if (onCompleteUtterance) {
        onCompleteUtterance(speechOutput);
      }
    }

    recognition.onresult = (event) => {
      let interim = '';
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          accumulatedSpeech += ' ' + transcript;
        } else {
          interim += transcript;
        }
      }

      const displayTranscript = (accumulatedSpeech + ' ' + interim).trim();
      if (displayTranscript) {
        patientSpeechCaption.textContent = `"${displayTranscript}"`;
      }

      resetSilenceTimer();
    };

    recognition.onspeechend = () => {
      resetSilenceTimer();
    };

    recognition.onerror = (event) => {
      if (event.error === 'no-speech') {
        resetSilenceTimer();
      }
    };

    recognition.onend = () => {
      if (isListening) {
        stopAndSubmit();
      }
    };

    try {
      recognition.start();
      // Baseline 8s guard if patient says nothing at all
      silenceTimer = setTimeout(() => {
        stopAndSubmit();
      }, 8000);
    } catch (err) {
      console.error('Recognition start error:', err);
      updateMicVisual(false);
      setStatus('processing', 'Standby');
    }
  }

  // Handle Server Step Response
  function handleStepResponse(resp) {
    if (resp.state === 'closing') {
      handleClosingScreen(resp);
      return;
    }

    // Lock in current language
    currentLanguage = resp.selected_language || currentLanguage;
    sessionLangBadge.textContent = currentLanguage === 'ta' ? 'தமிழ் (TA)' : 'English (EN)';

    if (repeatBtnText) {
      repeatBtnText.textContent = currentLanguage === 'ta' ? 'மீண்டும் கேள்' : 'Repeat';
    }

    // Step counter
    if (resp.question_index) {
      if (resp.is_repeat && resp.repeat_count) {
        questionStepTag.textContent = currentLanguage === 'ta'
          ? `கேள்வி ${resp.question_index} (மீண்டும் ${resp.repeat_count}/2)`
          : `Question ${resp.question_index} (Repeat ${resp.repeat_count}/2)`;
      } else {
        questionStepTag.textContent = currentLanguage === 'ta'
          ? `கேள்வி ${resp.question_index}`
          : `Question ${resp.question_index}`;
      }
    }

    // If server indicated this was a repeat of the current question
    if (resp.is_repeat) {
      patientSpeechCaption.textContent = currentLanguage === 'ta'
        ? 'கேள்வி மீண்டும் கேட்கப்படுகிறது...'
        : 'Repeating question...';
    }

    // Smooth caption change
    updateCaptionSmoothly(resp.display_text);

    // Speak question strictly, then start auto-stop listening ONLY after TTS ends
    kioskSpeak(resp.spoken_text, currentLanguage, () => {
      const listenTag = currentLanguage === 'ta' ? 'ta-IN' : 'en-US';
      startListening(listenTag, (patientSpeech) => {
        sendPatientSpeech(patientSpeech, false);
      });
    });
  }

  // Send Patient Utterance to Backend
  async function sendPatientSpeech(speech, isSilenceFreeze = false) {
    try {
      const response = await fetch('/intake/kiosk/step', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          user_speech: speech,
          is_silence_freeze: isSilenceFreeze,
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error(`Backend error ${response.status}:`, errorText);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const data = await response.json();
      handleStepResponse(data);
    } catch (err) {
      console.error('Error advancing kiosk state:', err);
      setStatus('processing', 'Standby');
      kioskNotice.textContent = 'Connection error. Please speak again or tap to retry.';
      kioskNotice.classList.remove('hidden');
    }
  }

  // Calm Closing Screen (Reads Token Out Loud & Waits Strictly for utterance.onend)
  function handleClosingScreen(resp) {
    switchView('closing');

    const result = resp.intake_result;
    const issuedToken = (result && result.patient_id) || resp.patient_id || '001';
    closingTokenValue.textContent = issuedToken;

    // Check for Mid-Conversation Red-Flag Emergency State
    if (resp.is_red_flag) {
      if (closingCard) closingCard.classList.add('emergency');
      if (phcTokenBox) phcTokenBox.classList.add('emergency');
      if (closingHeaderBadge) {
        closingHeaderBadge.classList.add('emergency');
        closingBadgeText.textContent = 'EMERGENCY / அவசர எச்சரிக்கை';
      }
      if (currentLanguage === 'ta') {
        closingMainTitle.textContent = 'உடனடி மருத்துவ கவனிப்பு தேவை';
        closingInstruction.textContent = 'அவசர நிலை கண்டறியப்பட்டுள்ளது. தயவுசெய்து உடனடியாக நிலையப் பணியாளர்களை அல்லது மருத்துவரைக் காணவும்!';
      } else {
        closingMainTitle.textContent = 'Immediate Medical Attention Needed';
        closingInstruction.textContent = 'Critical symptom pattern detected. Please report to the health centre staff immediately!';
      }
    } else {
      if (closingCard) closingCard.classList.remove('emergency');
      if (phcTokenBox) phcTokenBox.classList.remove('emergency');
      if (closingHeaderBadge) {
        closingHeaderBadge.classList.remove('emergency');
        closingBadgeText.textContent = 'REGISTRATION CONFIRMED';
      }
      if (currentLanguage === 'ta') {
        closingMainTitle.textContent = 'பதிவு நிறைவடைந்தது';
        closingInstruction.textContent = 'உங்கள் விவரங்கள் பதிவு செய்யப்பட்டுள்ளன. தயவுசெய்து காத்திருப்பு பகுதியில் அமர்ந்திருக்கவும்.';
      } else {
        closingMainTitle.textContent = 'Check-In Completed';
        closingInstruction.textContent = 'Your intake details have been registered. Please take a seat in the waiting area.';
      }
    }

    // Reset progress bar to 0% initially (animation starts strictly after speech ends)
    closingProgressBar.style.transition = 'none';
    closingProgressBar.style.width = '0%';

    let resetInitiated = false;
    let fallbackSafetyTimer = null;

    function beginPostSpeechCountdown() {
      if (resetInitiated) return;
      resetInitiated = true;
      if (fallbackSafetyTimer) {
        clearTimeout(fallbackSafetyTimer);
        fallbackSafetyTimer = null;
      }

      // Start the progress slider animation and countdown ONLY after TTS speech finishes
      const displayMs = 6000;
      closingProgressBar.style.transition = `width ${displayMs / 1000}s linear`;
      setTimeout(() => {
        closingProgressBar.style.width = '100%';
      }, 50);

      // Return to idle start screen only when post-speech display countdown completes
      setTimeout(() => {
        resetToIdle();
      }, displayMs);
    }

    // Speak closing prompt containing the spoken token number out loud
    kioskSpeak(resp.spoken_text, currentLanguage, () => {
      console.log('Closing TTS utterance onend fired cleanly. Starting post-speech countdown.');
      beginPostSpeechCountdown();
    });

    // Safety fallback: only if audio completely fails to start or speech synthesis is not active
    fallbackSafetyTimer = setTimeout(() => {
      if (!resetInitiated) {
        if ('speechSynthesis' in window && window.speechSynthesis.speaking) {
          return;
        }
        beginPostSpeechCountdown();
      }
    }, 45000);
  }

  // Reset to Idle Start Screen
  function resetToIdle() {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    if (recognition && isListening) {
      try { recognition.abort(); } catch (e) {}
    }

    sessionId = null;
    currentLanguage = 'en';
    silenceStrikes = 0;
    updateMicVisual(false);
    switchView('idle');

    closingProgressBar.style.transition = 'none';
    closingProgressBar.style.width = '0%';
    kioskNotice.classList.add('hidden');
    // No idle audio loop — audio only begins after the patient taps the language
  }

  // Start Check-in via Direct Language Tap
  async function startCheckIn(language) {
    silenceStrikes = 0;
    currentLanguage = language;
    switchView('conversation');
    setStatus('processing', 'Starting registration...');
    sessionLangBadge.textContent = language === 'ta' ? 'தமிழ் (TA)' : 'English (EN)';

    const initialPlaceholder = language === 'ta'
      ? 'பதிவு தொடங்குகிறது...'
      : 'Starting your check-in...';
    kioskSpeechCaption.textContent = `"${initialPlaceholder}"`;
    patientSpeechCaption.textContent = '...';

    try {
      const response = await fetch('/intake/kiosk/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: null,
          language: language,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error ${response.status}`);
      }

      const data = await response.json();
      sessionId = data.session_id;
      handleStepResponse(data);
    } catch (err) {
      console.error('Kiosk start error:', err);
      kioskNotice.textContent = 'Unable to connect to health centre server. Please try again.';
      kioskNotice.classList.remove('hidden');
    }
  }

  // ── Button Listeners ──
  // Step 1: Tap to Begin → show visual language selection immediately with zero audio playing
  if (btnStartSession) {
    btnStartSession.addEventListener('click', () => {
      if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
      }
      switchView('language');
    });
  }

  // Repeat Question Actions
  function triggerRepeatAction() {
    if (isSpeaking) return;
    if (isListening && recognition) {
      try { recognition.stop(); } catch (e) {}
      isListening = false;
      if (silenceTimer) clearTimeout(silenceTimer);
      updateMicVisual(false);
    }
    const repeatPhrase = currentLanguage === 'ta' ? 'மறுபடியும் சொல்லுங்க' : 'please repeat';
    patientSpeechCaption.textContent = `"${repeatPhrase}"`;
    setStatus('processing', currentLanguage === 'ta' ? 'மீண்டும் கேட்கப்படுகிறது...' : 'Repeating question...');
    sendPatientSpeech(repeatPhrase, false);
  }

  if (btnRepeatQuestion) {
    btnRepeatQuestion.addEventListener('click', triggerRepeatAction);
  }
  if (kioskSpeechCaption) {
    kioskSpeechCaption.addEventListener('click', () => {
      if (isListening) {
        triggerRepeatAction();
      }
    });
  }

  // Step 2: Language selection → begin voice check-in
  btnSelectEn.addEventListener('click', () => startCheckIn('en'));
  btnSelectTa.addEventListener('click', () => startCheckIn('ta'));

  // No audio on load — audio starts only after language selection
});
