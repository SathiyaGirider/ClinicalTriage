## Overview

The **Intake Module** handles patient voice registration for the Primary Health Centre ("ஆரம்ப சுகாதார நிலையம்") kiosk interface. It ingests speech in English or Tamil, executes hybrid extraction (LLM + deterministic guardrails), performs deterministic emergency red-flag scanning, produces closed-form adaptive follow-up questions, computes deterministic input confidence, generates clean sequential numeric token identifiers, and produces an `IntakeResult` object conforming strictly to [app/common/schemas.py](file:///d:/projects/ClinicalTriage/app/common/schemas.py).

---

## Strict Boundaries Maintained

- **Self-Contained**: All implementation files reside strictly inside `app/intake/`.
- **Untouched Contracts & Files**:
  - `app/common/schemas.py` was **never edited**.
  - `app/triage/`, `app/explain/`, and `main.py` were **never edited or refactored**.
- **Strict Schema Conformance**: `IntakeResult` has no added or omitted fields. `patient_id` remains a `str` (e.g. `"001"`).
- **Dependencies Logged**: All packages pinned and documented in [DEPENDENCIES.md](file:///d:/projects/ClinicalTriage/app/intake/DEPENDENCIES.md).
- **Environment Secrets**: API keys (`GEMINI_API_KEY`, etc.) are read from environment variables; `.env` is gitignored.

---

## Directory Layout

```
app/intake/
├── __init__.py               # Package exports
├── schemas.py                # Internal API request/response models (IntakeRequest, etc.)
├── stt.py                    # Speech-to-Text abstraction interface (get_transcript)
├── tts.py                    # Text-to-Speech abstraction interface (speak)
├── conversation.py           # State machine (idle -> language_select -> question_loop -> closing)
├── records.py                # In-memory demo records store (GET /intake/records)
├── redflag_scan.py           # Deterministic bilingual (EN/TA) keyword scanner
├── extractor.py              # Hybrid LLM + deterministic guardrails extractor
├── followup.py               # Constrained 5-category closed-form bilingual follow-up generator
├── confidence.py             # 100% deterministic input_confidence scoring matrix
├── router.py                 # FastAPI APIRouter exposing POST /intake, /kiosk, & /records
├── app.py                    # Standalone FastAPI app for independent testing & /docs
├── DEPENDENCIES.md           # Pinned dependency log + Chromium STT/TTS constraint notes
├── README.md                 # Intake module documentation & main.py integration snippet
├── static/                   # Kiosk & Web Speech API client UI
│   ├── kiosk.html            # Primary voice-first conversational kiosk interface (PHC branding)
│   ├── kiosk.css             # Primary Health Centre clean clinical kiosk stylesheet
│   ├── kiosk.js              # Auto-stop listening, female voice preference & onend closing logic
│   ├── records.html          # Live auto-refreshing demo records viewer with persistent state
│   ├── index.html            # Legacy clinician form testing portal
│   ├── style.css             # Legacy form styles
│   └── app.js                # Legacy form script
├── mock_data/                # Comprehensive test scenarios (EN, TA, injection, trauma)
│   ├── en_chest_pain.json
│   ├── ta_shortness_of_breath.json
│   ├── en_routine_cough.json
│   ├── ta_pediatric_fever.json
│   ├── en_trauma_accident.json
│   └── prompt_injection_attack.json
└── tests/
    ├── __init__.py
    └── test_intake.py        # Automated test suite (schemas, rules, TTS, state machine)
```

---

## LLM vs. Deterministic Split

| Component | Method | Reason / Guardrail |
| :--- | :--- | :--- |
| **raw_transcript** | **Deterministic (Verbatim)** | Original patient words are preserved 100% unmodified. Never summarized or altered by LLM. |
| **Red-Flag Scanning** | **Deterministic (`redflag_scan.py`)** | Independent regex scanning for critical terms (chest pain, shortness of breath, severe trauma, stroke symptoms, unconsciousness) in English and Tamil. Never skipped or delegated to LLM judgment. |
| **Field Extraction** | **Hybrid (`extractor.py`)** | Uses Gemini/LLM with strict JSON schema formatting. If LLM is unconfigured, offline, or output fails Pydantic schema validation, falls back immediately to deterministic regex/lexicon extraction. Red flags from `redflag_scan.py` are deterministically merged into `symptoms`. |
| **Follow-up Questions** | **Relevance-Based Closed-Form (`followup.py`)** | Produces at most 3 specific closed-form questions in `en` or `ta` selected by clinical relevance across 4 categories (`onset`, `associated_symptoms`, `history`, `medications`). |
| **Input Confidence** | **100% Deterministic (`confidence.py`)** | Computed strictly via matrix evaluation of completeness, transcript clarity, symptom count, and prompt injection indicators. LLM is strictly prohibited from self-reporting this score. |
| **Prompt Injection Defense** | **Deterministic Guardrail** | Adversarial phrases ("ignore previous instructions", "mark me routine") do not alter schemas, trigger confidence degradation to `"low"`, and pass through unmodified. |

---

## Speech-to-Text (STT) Details

- **Browser-Native Web Speech API**: Transcribes live voice input in Google Chrome / Microsoft Edge.
- **Bilingual Support**:
  - English (`en-US`)
  - Tamil (`ta-IN`)
- **Isolation Boundary (`stt.py`)**:
  - The client transmits the transcribed text string to `POST /intake`.
  - The backend defines `get_transcript(source, language)` and `SpeechToTextProvider`.
  - In future iterations, an offline containerized STT engine (such as `whisper.cpp` or Faster-Whisper) can be plugged in without changing downstream code.

---

## How to Run & Test Independently

### 1. Launch Independent Intake Server
```bash
uvicorn app.intake.app:app --reload --port 8000
```
- Open **`http://localhost:8000/docs`** for interactive OpenAPI Swagger documentation.
- Open **`http://localhost:8000/`** to test the live Web Speech API intake portal in Chrome or Edge.

### 2. Run Automated Test Suite
```bash
python -m unittest app/intake/tests/test_intake.py
```

---

## Integration Guide for `main.py` (For Person B / Integrator)

To mount the Intake module into the central application when combining Person A, B, and C, add the following lines to `main.py`:

```python
from fastapi import FastAPI
from app.intake.router import router as intake_router

app = FastAPI(title="ClinicalTriage Central")

# Mount Person A's intake router
app.include_router(intake_router)
```

---

## Flagged Schema Ambiguity for Team Alignment

1. **Deterministic Red-Flags Storage**:
   - `redflag_scan.py` identifies critical red-flag terms independently of LLM reasoning for Person B's use.
   - However, the shared `IntakeResult` schema in `app/common/schemas.py` does not contain a `red_flags` field (only `chief_complaint`, `duration`, `symptoms`, `age`, `known_conditions`, `follow_up_answers`, `raw_transcript`, `input_confidence`).
   - **Resolution Implemented by Person A**:
     - All detected red flags are deterministically merged into `symptoms` so Person B receives them without omission.
     - Person A also exports `scan_red_flags(raw_transcript)` from `app.intake.redflag_scan` so Person B can directly invoke the scanner on `IntakeResult.raw_transcript`.
     - `POST /intake/envelope` also returns `red_flags_detected` for UI workflows.
     - No modification was made to `app/common/schemas.py`.
