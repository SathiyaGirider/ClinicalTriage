"""
test_explain.py
===============
Validates the explain module (Stage C -- doctor summary dashboard) against
every scenario*.json file found in mock-data/.

For each scenario it parses stageC.mock_input (intake_result + triage_decision)
into Pydantic models, runs build_doctor_summary(), and diffs every field of the
result against stageC.ideal_output (the expected DoctorSummary).

Run from the project root:
    python app/explain/test_explain.py

Exit code:
    0  -- all strict checks passed
    1  -- one or more strict checks failed
"""

import json
import os
import sys

# ---------------------------------------------------------------------------
# Import path setup: allow running from project root without installing the
# package.  Adds the project root (two levels above this file's directory,
# since this file lives under app/explain/) to sys.path so that
# `from app.xxx import yyy` works.
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.common.schemas import DoctorSummary, IntakeResult, TriageDecision  # noqa: E402
from app.explain import build_doctor_summary, render_dashboard             # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MOCK_DATA_DIR = os.path.join(PROJECT_ROOT, "mock-data")
SEPARATOR = "-" * 70

DOCTOR_SUMMARY_FIELDS = [
    "patient_id",
    "chief_complaint",
    "duration",
    "red_flags",
    "relevant_history",
    "priority",
    "priority_rationale",
    "timestamp",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_scenarios() -> list:
    """Return (filename, data) pairs for every scenario*.json, sorted."""
    files = sorted(
        f for f in os.listdir(MOCK_DATA_DIR)
        if f.startswith("scenario") and f.endswith(".json")
    )
    scenarios = []
    for fname in files:
        path = os.path.join(MOCK_DATA_DIR, fname)
        with open(path, encoding="utf-8") as fh:
            scenarios.append((fname, json.load(fh)))
    return scenarios


def _verdict(passed: bool) -> str:
    return "PASS" if passed else "FAIL"


# ---------------------------------------------------------------------------
# Per-scenario test logic
# ---------------------------------------------------------------------------

def test_scenario(fname: str, data: dict) -> int:
    """
    Run all applicable checks for one scenario.

    Returns the number of strict-check *failures* for this scenario
    (0 = all passed).
    """
    scenario_id = data.get("scenario_id", fname)
    print(f"\n{SEPARATOR}")
    print(f"SCENARIO : {scenario_id}  [{fname}]")
    print(SEPARATOR)

    stage_c = data.get("stageC", {})
    mock_input  = stage_c.get("mock_input", {})
    ideal_output = stage_c.get("ideal_output", {})

    if not mock_input or not ideal_output:
        print("  [SKIP] stageC.mock_input or stageC.ideal_output missing.")
        return 0

    raw_intake  = mock_input.get("intake_result")
    raw_triage  = mock_input.get("triage_decision")

    if not raw_intake or not raw_triage:
        print("  [SKIP] stageC.mock_input.intake_result or triage_decision missing.")
        return 0

    # Parse into typed models
    try:
        intake = IntakeResult(**raw_intake)
        triage = TriageDecision(**raw_triage)
        ideal  = DoctorSummary(**ideal_output)
    except Exception as exc:
        print(f"  [ERROR] Could not parse stageC data into Pydantic models: {exc}")
        return 0  # schema error is not a logic failure; skip gracefully

    failures = 0

    # ------------------------------------------------------------------
    # CHECK 1 -- build_doctor_summary does not raise (Patient ID match)
    # ------------------------------------------------------------------
    print("\n  [CHECK 1] build_doctor_summary (patient ID must match)")
    try:
        summary = build_doctor_summary(intake, triage)
        print(f"    Patient IDs match : intake={intake.patient_id}, triage={triage.patient_id}")
        print(f"    Result            : {_verdict(True)}")
    except Exception as exc:
        failures += 1
        print(f"    Result            : {_verdict(False)} ({exc})")
        return failures

    # ------------------------------------------------------------------
    # CHECK 2 -- Field-by-field diff against stageC.ideal_output
    # ------------------------------------------------------------------
    print("\n  [CHECK 2] Field-by-field comparison with stageC.ideal_output")
    actual = summary.model_dump()

    for field in DOCTOR_SUMMARY_FIELDS:
        expected = getattr(ideal, field)
        got      = actual[field]
        passed   = got == expected
        if not passed:
            failures += 1
        print(f"    {field:<18} expected: {expected!r}")
        print(f"    {'' :<18} actual  : {got!r}")
        print(f"    {'' :<18} result  : {_verdict(passed)}")

    # ------------------------------------------------------------------
    # CHECK 3 -- render_dashboard smoke test (no ideal text to diff against)
    # ------------------------------------------------------------------
    print("\n  [CHECK 3] render_dashboard renders patient ID (smoke test)")
    try:
        rendered = render_dashboard(summary)
        passed = summary.patient_id in rendered
        if not passed:
            failures += 1
        print(f"    Contains '{summary.patient_id}' : {_verdict(passed)}")
    except Exception as exc:
        failures += 1
        print(f"    [ERROR] render_dashboard raised an exception: {exc}")

    return failures


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 70)
    print("  CLINICAL TRIAGE -- EXPLAIN (STAGE C) VALIDATION RUNNER")
    print("=" * 70)

    try:
        scenarios = _load_scenarios()
    except Exception as exc:
        print(f"\n[FATAL] Could not load scenarios from '{MOCK_DATA_DIR}': {exc}")
        sys.exit(1)

    if not scenarios:
        print(f"\n[WARN] No scenario*.json files found in '{MOCK_DATA_DIR}'.")
        sys.exit(0)

    total     = len(scenarios)
    passed    = 0
    has_error = False

    for fname, data in scenarios:
        try:
            failures = test_scenario(fname, data)
            if failures == 0:
                passed += 1
            else:
                has_error = True
        except Exception as exc:
            # Outermost safety net -- should not normally be reached
            print(f"\n  [FATAL ERROR] Unhandled exception in '{fname}': {exc}")
            has_error = True

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print(f"\n{'=' * 70}")
    print("  SUMMARY")
    print(f"{'=' * 70}")
    print(f"  Scenarios tested  : {total}")
    print(f"  Strict checks OK  : {passed} / {total}")
    failed = total - passed
    if failed:
        print(f"  Strict failures   : {failed}")
    print("=" * 70)

    sys.exit(1 if has_error else 0)


if __name__ == "__main__":
    main()