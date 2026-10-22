# LifeLine Red-Flag Clinical Rules

> **PROTOTYPE LIST — REQUIRES MULTIDISCIPLINARY CLINICIAN REVIEW**:
> The rules documented below are an educational prototype adaptation of the Emergency Severity Index (ESI) framework, collapsed into a 3-tier operational model (Emergency, Same-day/Urgent, Routine).
> **These rules have NOT been clinically validated. They must NOT be used for real patient triage without formal review, adaptation, and approval by licensed emergency medicine and primary care clinicians.**

---

## 1. Overview of the Rule Engine

- **Deterministic & Authoritative:** Hardcoded rules execute directly on the patient's verbatim transcript, structured chips, and clinical vitals. They run *prior* to any AI/LLM invocation.
- **Unidirectional Escalation:** The LLM can maintain or raise an assigned urgency tier, but can **never** lower a priority below a matched red-flag rule.
- **Multilingual Substring & Token Mapping:** Matching evaluates canonical clinical tags derived from English text, Tamil script, Tamil transliteration, and fixed safety chips.

---

## 2. Emergency Tier Rules (Immediate Assessment Required)

Patients matching an Emergency rule bypass outpatient queue booking and receive immediate instructions to proceed to the nearest emergency department.

| Rule Identifier | Short Clinical Label | Clinical Rationale / Fixed Template | Trigger Conditions (Signals & Keywords) |
| :--- | :--- | :--- | :--- |
| `chest_pain_with_breathlessness` | Chest pain with breathing difficulty | Chest pain reported together with breathing difficulty. Needs immediate emergency assessment. | Presence of `chest_pain` AND (`breathlessness` OR `severe_breathing_difficulty`). |
| `stroke_signs` | One-sided weakness, facial droop or slurred speech | Sudden one-sided weakness or numbness, facial droop, or slurred speech reported. Needs immediate emergency assessment. | Any of: `one_sided_weakness`, `facial_droop`, `slurred_speech`. |
| `severe_bleeding` | Severe bleeding | Severe or uncontrolled bleeding reported. Needs immediate emergency assessment. | Presence of `severe_bleeding` or `heavy_bleeding`. |
| `unresponsive` | Unconscious or not responding | Patient described as unconscious or not responding. Needs immediate emergency assessment. | Presence of `unconscious` or `unresponsive`. |
| `active_seizure` | Seizure happening now | A seizure is reported as happening now. Needs immediate emergency assessment. | Presence of `seizure_now` or `ongoing_seizure`. |
| `pediatric_seizure` | Seizure in a child | A seizure was reported in a child. Needs immediate emergency assessment. | Presence of `seizure` AND patient age < 18 years. |
| `respiratory_distress` | Severe breathing difficulty | Severe difficulty breathing reported. Needs immediate emergency assessment. | Presence of `severe_breathing_difficulty` or `gasping`. |
| `swelling_with_breathing_trouble` | Face/lip/throat swelling with breathing trouble | Swelling of the face, lips or throat together with breathing trouble. Needs immediate emergency assessment. | Presence of `face_lip_swelling` AND (`breathlessness` OR `severe_breathing_difficulty`). |
| `vomiting_blood` | Vomiting blood | Vomiting blood reported. Needs immediate emergency assessment. | Presence of `vomiting_blood` or `hematemesis`. |
| `head_injury_with_confusion` | Head injury with confusion | Head injury reported together with confusion or reduced responsiveness. Needs immediate emergency assessment. | Presence of `head_injury` AND (`confusion` OR `unconscious`). |
| `low_oxygen` | SpO2 below safe threshold | Measured SpO2 below 92%. Needs immediate emergency assessment. | Objective vital `spo2 < 92%`. |
| `poisoning` | Possible poisoning or overdose | Swallowing poison, pesticide or an overdose of tablets reported. Needs immediate emergency assessment. | Presence of `poisoning` or `overdose`. |
| `abdominal_pain_with_instability` | Abdominal pain with fainting | Abdominal pain reported together with fainting. Needs immediate emergency assessment. | Presence of `abdominal_pain` AND `fainting`. |

---

## 3. Urgent Tier Rules (Same-Day OPD Visit, Flagged for Nurse Attention)

Patients matching an Urgent rule receive same-day priority tokens or expedited walk-in slots, and are flagged on the nurse dashboard for in-person assessment.

| Rule Identifier | Short Clinical Label | Clinical Rationale / Fixed Template | Trigger Conditions (Signals & Keywords) |
| :--- | :--- | :--- | :--- |
| `repeated_fainting` | Repeated fainting | Fainting more than once reported. A nurse should see the patient today. | Presence of `repeated_fainting`. |
| `fainting_older_adult` | Fainting at age 60 or above | Fainting reported in a patient aged 60 or above. A nurse should see the patient today. | Presence of `fainting` AND patient age >= 60 years. |
| `chest_pain` | Chest pain | Chest pain reported. A nurse should see the patient today. | Presence of `chest_pain` without acute respiratory distress. |
| `palpitations_with_dizziness` | Palpitations with dizziness | Palpitations reported together with dizziness or fainting. A nurse should see the patient today. | Presence of `palpitations` AND (`dizziness` OR `fainting`). |
| `sudden_severe_headache` | Sudden severe headache | A sudden, severe headache reported. A nurse should see the patient today. | Presence of `sudden_severe_headache` or "thunderclap headache". |
| `black_stool` | Black stool | Black or tarry stool reported. A nurse should see the patient today. | Presence of `black_stool` or `melena`. |
| `high_fever_vulnerable_age` | High fever in young child or older adult | High fever reported in a child under 5 or an adult aged 65 or above. A nurse should see the patient today. | Presence of `high_fever` (or temp >= 39.0°C) AND (age < 5 OR age >= 65). |
| `pregnancy_bleeding` | Bleeding in pregnancy | Bleeding reported during pregnancy. A nurse should see the patient today. | Presence of `pregnant` AND (`bleeding` OR `severe_bleeding`). |
| `seizure_reported` | Seizure reported | A recent seizure was reported. A nurse should see the patient today. | Presence of `seizure` in adult without active ongoing fit. |
| `abnormal_vitals` | Pulse or BP outside safe range | Measured pulse or blood pressure outside the safe range. A nurse should see the patient today. | Objective vitals: `pulse > 130`, `pulse < 40`, `bp_sys > 180`, or `bp_sys < 90`. |
| `safety_screen_positive` | Safety screen answered yes | The patient ticked at least one item on the safety screen. A nurse should see the patient today. | Explicit affirmation on multi-select safety screen chips. |

---

*LifeLine Red-Flag Decision Support Rules Reference.*
