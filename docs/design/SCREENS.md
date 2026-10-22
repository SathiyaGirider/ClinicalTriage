# LifeLine Clinical Screen Specifications (Phase 1)

This document specifies the responsive layouts and content hierarchy for every screen in the application across mobile (360px), tablet (768px), and desktop (1280px).

---

## 1. Authentication & Common Screens

### 1.1 Login & Register (360px / 768px / 1280px)
- **Header:** LifeLine title, language toggle (English / தமிழ்), synthetic demo banner.
- **Form:**
  - Login: Email, Password, submit button, link to Register.
  - Register: Full name, Email, Password (min 10 chars), Age or DOB, Language selector, Area. Note: "We do not ask for phone numbers or national ID numbers."
  - Field errors tied via `aria-describedby` and `aria-invalid`.
- **403 Forbidden & 404 Not Found Screens:**
  - 403: "Access Restricted: You do not have permission to view this page." with a button returning to the role's home view.
  - 404: "Page Not Found: The requested clinical resource does not exist or has moved." with a button returning home.

---

## 2. Patient Application (Mobile 360px First, Scalable to Desktop)

### 2.1 Patient Home
- Top welcome header: "Hello, {Name}" with language toggle.
- Two primary action cards:
  - "Book an appointment": Hospital, specialty, doctor, session pickers.
  - "Start with your symptoms": Direct intake flow to recommend department.
- Navigation bar / tabs: Home, My Appointments, My Records, Privacy, Profile.

### 2.2 Hospital, Doctor & Session Pickers
- **Step 1 Hospital:** Cards showing Hospital Name, Area, Address, Distance in km.
- **Step 2 Department:** Clean selectable chips (e.g. General Medicine, Cardiology, Paediatrics).
- **Step 3 Doctor:** Doctor card with Name, Specialty, Room, Bio, and Next Available Session.
- **Step 4 Session:** Morning / Afternoon session slots with open tokens left count (e.g. "8 tokens left").
- **Double Submit Guard:** Selection triggers an atomic 10-minute hold with disabled button during reservation.

### 2.3 Intake Flow & Safety Disclosures
- **Pre-Questions Disclosure (ICMR Aligned):**
  - "An automated tool helps prepare information for your care team. A nurse or doctor makes every decision. You can skip these questions and speak to the staff instead."
  - Primary button: "Begin questions"
  - Secondary button: "Skip to staff check-in" (Marks booking as "not pre-screened").
- **Question Wizard:**
  - One question per screen with large tap targets (minimum 48px).
  - Progress indicator: "Question 2 of 5".
  - Clear "Back" button to previous answers.
  - Microphone voice-entry button with fallback if unsupported.
  - Big "None of these" button on emergency safety screening.
- **Confirmation Screen:**
  - Shows patient's understood answers in plain language.
  - Direct inline "Edit" button for each answer.
  - "Looks right, continue" button.

### 2.4 The Three Outcome Screens
1. **Routine Outcome (Green Header / Neutral Card):**
   - Large token badge: `M-07`.
   - Approximate call time: `10:15 AM - 10:45 AM` with explicit badge `Approximate`.
   - Reassurance copy: "Doctors can run late when urgent cases arrive. Please arrive 20 minutes before your estimated time."
   - Action buttons: "Add to Calendar (.ics)", "Directions", "View My Appointments".
2. **Visit Today Outcome (Amber Header / Urgent Card):**
   - Alert banner: "A doctor or nurse should see you today."
   - Available same-day sessions listed with reserve tokens.
   - If no sessions open: Walk-in guidance with hospital OPD hours and walk-in window details.
3. **Emergency Outcome (Solid Red Header / Direct Reassurance):**
   - Calm, non-alarmist, high-clarity instructions: "Please go to the Emergency department now."
   - Emergency contact numbers in large font (`112`, `108`).
   - Hospital Emergency Department address and 24x7 entrance details.
   - Plain statement: "No appointment or token has been booked. Emergency staff will assist you on arrival."

### 2.5 My Appointments & Live Status
- List of upcoming and past appointments.
- Upcoming Live Card:
  - Token badge (`M-07`) alongside "Now serving: M-04".
  - Live auto-refreshing polling (every 10s) with live region.
  - "I'm here" button (active on the day of appointment):
    - Sub-dialog: "Since you booked, is anything worse or new?" (Options: No change, Better, Worse, New symptom).
    - Status updates to "Waiting for nurse to confirm".
  - Actions: "Change session" (reschedule) and "Cancel booking" (with in-app modal confirmation).

### 2.6 Privacy & Consent (ABDM Simulation)
- Heading: "Privacy & Health Record Access".
- Sub-banner: "ABDM simulation. Not connected to ABDM."
- Synthetic ABHA profile display (e.g. `ashakumar@abdm`).
- **Access Requests Inbox:**
  - Lists pending requests from outside doctors: Doctor Name, Specialty, Hospital, Purpose ("Care and treatment"), Requested Types, Date Range.
  - Actions: "Approve" (choose 24h, 7d, or 30d expiry) or "Deny".
- **Active Consents List:**
  - List of active permissions with a prominent "Revoke Access" button.
- **Access Log:**
  - Timestamped audit of every staff view: Who, Hospital, Scope of data accessed, and Date/Time.

---

## 3. Nurse Dashboard (Tablet 768px Optimized, Scalable to Desktop)

### 3.1 Header Strip
- Assigned Doctor: `Dr. Meena Raghavan · General Medicine · Room 101`.
- Session badge: `Morning Session (09:00 - 12:00)`.
- Now serving: `M-03`.
- Unassigned state: If no doctor is assigned, an explicit clinical warning card is shown and actions are locked.

### 3.2 Top Panel: Needs Attention
- High-priority clinical alert cards for flagged patients (amber or red background).
- Shows: Token, Patient Name, Chief Complaint, Red flags matched, Time waiting.
- Accessible text buttons: "Acknowledge", "Send to ER", "Fast-track", "Change priority", "Open details".

### 3.3 Main Area: Present Queue Table
- High-density table:
  - Columns: Token, Patient Name, Age, Chief Complaint, Wait Time, Status Chip, Flag, Actions.
  - Order modes: "Token order" or "Nurse order" (allows dragging or Up/Down buttons).
  - Quick action: "With doctor" (marks patient into consultation room).

### 3.4 Collapsible Section: Booked, Not Arrived
- Shows patients expected today who have not arrived yet.
- Highlights patients with "Self-reported arrival" badge ("Confirm arrival" button).
- Action: "Mark no-show".

### 3.5 Check-In Desk & Patient Drawer (Slide-Over Panel)
- Quick safety screening chips (Chest pain, Trouble breathing, Fainting, etc.).
- 4-Outcome Check-in: "No change", "Better", "Worse", "New symptom".
- If "Worse" or "New symptom": triggers short assisted re-check wizard.
- Vitals Entry: Systolic BP, Diastolic BP, Temp (°C), SpO2 (%), Pulse.
- Triage Summary display: 5-line clinical summary. Notice: "Nurses see the triage summary only, never diagnosis history or prescriptions."

---

## 4. Doctor Workspace (Desktop 1280px Optimized)

### 4.1 Today List View
- Header: Doctor Name, Specialty, Hospital, Room, Assigned Nurse.
- "With you now" active card with direct "Open workspace" button.
- "Next patient" card with "Call in" button.
- "Present patients" waiting list with priority chips and token labels.

### 4.2 Patient Workspace (3-Column / Pane Layout)
- **Top Context Bar:** Patient Name, Age, Token, Arrival Status, "Change priority" button.
- **Left Column: Triage Summary & Decision Support:**
  - One-line headline summary (expandable): e.g. "Severe throat pain for 3 days · No red flags".
  - Section A: **What the patient told us** (Raw transcript in quotes, duration, age, conditions).
  - Section B: **Decision support (AI-assisted). Confirm before acting.**
    - Priority rationale and rule trigger audit trail.
    - Input confidence score.
    - Vitals summary.
    - One-tap feedback widget: "Was this summary useful?" [Thumbs Up: Useful] [Thumbs Down: Not useful] with optional reason.
- **Center Column: Consultation & Prescription Form:**
  - Labelled clinical fields (nothing AI-autofilled):
    - Diagnosis text (required, doctor-typed).
    - ICD-10 Code (optional).
    - Clinical notes (textarea).
    - Multi-row prescription builder: Drug name, Dose, Frequency, Duration, Instructions, "+ Add medicine".
    - Follow-up date picker.
  - Primary button: "Complete consultation" (with confirmation dialog).
- **Right Column: Encounter History:**
  - "Your encounters with this patient": Full history authored by this doctor.
  - "Outside doctors":
    - If no valid consent: "Patient has not consented to sharing outside records." + "Request access to history" button (triggers ABDM mock request).
    - If valid consent active: Displays outside records matching approved types and date range with clear badge "Shared via ABDM consent. Diagnoses only."
