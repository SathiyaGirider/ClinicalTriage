# Red-flag rules (prototype)

**Every rule below needs clinician review before any real use.** Source: `app/triage/rules.py` (`RULES`) and signal vocabulary in `app/common/symptom_vocab.py`. A rule fires on canonical tags OR transcript keywords (English, Tamil script, transliterated Tamil) OR safety-screen chips OR vitals. Rationales are fixed templates.

## Emergency tier → "Please go to the Emergency department now", no booking, no token

| Rule id | Fires when |
|---|---|
| chest_pain_with_breathlessness | chest pain + (breathlessness or severe breathing difficulty) |
| stroke_signs | one-sided weakness/numbness, facial droop, or slurred speech |
| severe_bleeding | severe / uncontrolled bleeding |
| unresponsive | unconscious / not responding |
| active_seizure | seizure happening now (incl. safety-screen "seizure" chip, which asks "right now") |
| pediatric_seizure | any seizure mention and age < 18 (kept from Person B) |
| respiratory_distress | severe breathing difficulty (incl. "trouble breathing" chip) |
| swelling_with_breathing_trouble | face/lip/tongue/throat swelling + breathing trouble |
| vomiting_blood | vomiting blood |
| head_injury_with_confusion | head injury + confusion or reduced responsiveness |
| low_oxygen | SpO2 < 92 % (vitals) |
| poisoning | poison, pesticide, overdose (kept from Person B) |
| abdominal_pain_with_instability | abdominal pain + fainting (kept from Person B) |
| legacy `check_red_flags` ids | Person B's original substring rules on symptom strings still run; any hit is emergency |

## Urgent tier → same-day, `flag_for_nurse=true`

| Rule id | Fires when |
|---|---|
| repeated_fainting | fainting more than once |
| fainting_older_adult | fainting and age ≥ 60 |
| chest_pain | chest pain alone |
| palpitations_with_dizziness | palpitations + dizziness/fainting |
| sudden_severe_headache | sudden / worst / thunderclap headache |
| black_stool | black or tarry stool |
| high_fever_vulnerable_age | high fever (or temp ≥ 39.0 °C) and age < 5 or ≥ 65 |
| pregnancy_bleeding | pregnant + bleeding |
| seizure_reported | any recent seizure (adult, resolved) |
| abnormal_vitals | pulse > 130 or < 40, systolic ≥ 180 or < 90 |
| safety_screen_positive | any safety-screen chip ticked |

## Open questions for the clinician review
- Age cut-offs (< 5, ≥ 60, ≥ 65), SpO2 92 %, pulse/BP limits.
- Whether chest pain alone should be emergency.
- English negation handling; Tamil negation deliberately ignored.
- Tamil and transliterated keyword lists need a native speaker.
