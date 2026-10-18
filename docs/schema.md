# Shared contract additions (`app/common/schemas.py`)

All original fields and types are unchanged. Every addition is optional with a default.

| Contract | Added field | Why |
|---|---|---|
| IntakeResult | `symptom_tags: list[str]` | canonical tags (`symptom_vocab.py`, unknown → `other`); `symptoms` stays free text for the scenarios |
| IntakeResult | `safety_screen: list[str]` | fixed 7-chip screen answers (`none` or chip keys) |
| IntakeResult | `language: "en"\|"ta"` | patient language |
| IntakeResult | `assisted: bool` | nurse-run intake |
| IntakeResult | `addenda: list[IntakeAddendum]` | check-in "worse/new symptom" re-checks with timestamp |
| TriageDecision | `decided_by` adds `"fallback"`, `"human"` | LLM unusable; nurse/doctor override |
| TriageDecision | `flag_for_nurse`, `audit_notes`, `suggested_department`, `rule_tier` | flags, notes (`injection_suspected`, `llm_fallback_used`, `output_filtered`, `low_input_confidence`, ...), deterministic department, which tier fired |
| DoctorSummary | `decided_by`, `audit_notes`, `input_confidence`, `summary_source` | shown to the doctor |
| new | `IntakeAddendum`, `PatientAdvice`, `DoctorRecommendation`, `QueueEntry` | patient outcome, doctor cards, nurse/doctor queue rows |
