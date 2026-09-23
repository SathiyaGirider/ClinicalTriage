# Intake Module Dependencies & Environment Constraints

## Dependency Log

All packages are pinned to the user-specified versions in `requirements.txt`:

| Package | Version | Purpose & Rationale |
| :--- | :--- | :--- |
| `fastapi` | `0.141.1` | Web framework to expose the `POST /intake` API endpoint, validation handling, and interactive OpenAPI documentation at `/docs`. |
| `uvicorn` | `0.34.0` | High-performance ASGI web server for running the FastAPI application (standard stable version for production backwards compatibility). |
| `pydantic` | `2.13.4` | Modern data validation and serialization library for strictly enforcing schema conformity against `IntakeResult`. |
| `httpx` | `0.28.1` | Asynchronous/synchronous HTTP client used for robust LLM API communication and integration test fixtures. |
| `python-dotenv` | `1.0.1` | Environment variable loader allowing safe configuration of `GEMINI_API_KEY`, `OPENAI_API_KEY`, etc. without hardcoding secrets. |
| `google-genai` | `2.23.0` | Official Google GenAI SDK for Gemini structured output extraction and adaptive follow-up question generation. |

---

## Speech-to-Text (STT) Environment Constraints

### Client-Side Browser Native Speech Recognition
Speech-to-text (STT) in this phase utilizes the browser-native **Web Speech API** (`window.SpeechRecognition` / `window.webkitSpeechRecognition`).

### Known Environment Constraints (Not a Bug)
1. **Chromium Requirement**:
   - The Web Speech API is natively supported and reliable in **Chromium-based browsers** (Google Chrome, Microsoft Edge, Brave, Opera).
   - It is **not supported** in Mozilla Firefox or Apple Safari without experimental or third-party polyfills.
   - This is an intentional environment constraint for demo and controlled triage workstations.
2. **Microphone & Internet Access**:
   - Chromium's implementation of the Web Speech API routes audio through Google's speech recognition cloud services. As a result, an active internet connection and microphone access permissions are required.
3. **Containerization Implications**:
   - The Web Speech API executes entirely in the end-user's browser on the client machine, **not** inside any future backend Docker container.
   - Containerizing the backend with Docker/Kubernetes does not remove or alter this client-side requirement.
4. **Offline / Future Containerized STT**:
   - To support fully offline or containerized speech recognition in future iterations, the backend architecture encapsulates STT behind an isolated interface (`app.intake.stt.get_transcript(source)`).
   - This allows seamless replacement with an offline containerized STT engine (e.g., `whisper.cpp`, Faster-Whisper) without modifying any downstream extraction, red-flag scanning, follow-up generation, or confidence scoring logic.

---

## Text-to-Speech (TTS) & Kiosk Voice Activity Constraints

### Browser-Native SpeechSynthesis (Zero Paid Cloud Cost)
Text-to-Speech (TTS) for the conversational kiosk runs entirely client-side via the browser-native **`window.speechSynthesis`** API, adhering strictly to the "single controlled workstation with zero paid APIs" constraint.

### Voice Availability & Tamil TTS Observations
1. **English Synthesis (`en-US`)**:
   - Natively supported across all modern Windows installations (Microsoft David, Zira, Mark, or Edge Natural voices). Clean, fluid, and highly intelligible.
2. **Tamil Synthesis (`ta-IN`)**:
   - **System Dependency**: Tamil voice synthesis in `window.speechSynthesis` depends on whether a Tamil voice pack (e.g. "Microsoft Valluvar" in Windows 10/11 or Google Tamil in Chrome) is installed on the host system.
   - **Observed Behavior & Fallback**:
     - When a Tamil voice pack is present, the kiosk automatically selects the `ta-IN` voice with an adjusted speaking rate (`0.92x`) for optimal clinical comprehension.
     - When no Tamil voice pack is installed on the local OS, the browser defaults to the system default voice. To prevent patient confusion, the kiosk displays prominent bilingual captions (`kioskSpeechText`) on screen alongside audio and renders a visual notification advising that on-screen Tamil text is displayed.
3. **Voice-Activity Silence Auto-Stop**:
   - Instead of requiring manual button taps to stop listening, the kiosk implements hybrid silence detection:
     1. Natural speech boundary finalization via `SpeechRecognition.onresult` (`isFinal == true`) and `onspeechend`.
     2. A fallback silence watchdog timer (`1800ms` window): every spoken token resets the timer; if 1.8 seconds elapse without new speech, the recognition session automatically closes and submits the utterance.

---

## Demo Records Store (In-Memory)

### Purpose & Persistence Notice
- An in-memory store is provided in `app.intake.records` to capture completed `IntakeResult` records along with timestamps for live demonstration and verification.
- Accessible via:
  - `GET /intake/records`: JSON list of all captured intake records (most recent first).
  - `GET /records`: Interactive live-polling HTML viewer (`app/intake/static/records.html`).
- **Persistence Constraint**: This store uses an in-memory Python list with zero external database dependencies. It is non-persistent and resets completely whenever the application server restarts.
