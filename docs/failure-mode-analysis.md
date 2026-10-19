# Failure-mode analysis: what happens when the AI is wrong

| Failure | Direction | What limits the harm | Residual risk |
|---|---|---|---|
| LLM rates a dangerous case "routine" | under-triage | Red-flag rules run first and cannot be lowered; safety-screen chips are always asked at booking; rules also scan the raw transcript in EN/Tamil, so an extractor miss does not hide a flag; check-in asks "worse or new?" and re-triages; vitals (SpO2 < 92) raise to emergency; nurses can flag and fast-track. | A dangerous presentation that matches no rule, no chip, and is described mildly. The rule list is a prototype and needs clinician review. |
| LLM rates a mild case "same-day" | over-triage | Outcome is "visit today" + nurse check, not an ER visit. Nurse can change priority with a reason. | Extra load on nurses, alert fatigue. |
| LLM output malformed / timeout / no key | unknown | Fail-safe: same-day, escalated, flagged, `llm_fallback_used`. | Over-triage during outages. |
| LLM writes a diagnosis or drug name | unsafe content | Output filter replaces it with a template (`output_filtered`). Patients never see LLM text at all. | Paraphrases the filter's word lists miss (staff-facing only). |
| Prompt injection in patient text | manipulation | Detected (EN/Tamil/transliterated patterns, role-play, encoded blobs, length) ⇒ escalated; rules run on original text; LLM gets only a structured subset inside a data block. | Novel injection wording that slips past detection can at most influence the LLM's routine/same-day call for cases with no red flag. |
| Extractor misreads Tamil | both | Rules match Tamil script and transliteration directly; low recognition ⇒ low input confidence ⇒ escalated. Confirm screen lets the patient correct. | Dialect words not in the vocabulary. |
| Rule false positive ("no chest pain" style) | over-triage | English negation inside the same clause is honoured; Tamil negation is deliberately not parsed (errs toward caution). | Some false emergency screens in Tamil. |
| Speech recognition error | both | Text is never auto-submitted; the patient confirms or edits. Typing always available. | Patient confirms a wrong transcript. |
| Queue manipulated by AI | fairness | Not possible: ordering code takes only token order + nurse positions. | — |
| Server error anywhere in triage/pipeline | unknown | Returns flagged same-day, never a 500 or routine. | — |
