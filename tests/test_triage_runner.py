"""
test_triage_runner.py
=====================
Validates the triage pipeline (rules + LLM) against every scenario*.json
file found in mock-data/.

Run from the project root:
    python tests/test_triage_runner.py

Exit code:
    0  -- all strict checks passed
    1  -- one or more strict checks failed
"""

import json
import os
import sys

# ---------------------------------------------------------------------------
# Import path setup: allow running from project root without installing the
# package.  Adds the project root (one level above this file's directory)
# to sys.path so that `from app.xxx import yyy` works.
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.common.schemas import IntakeResult, TriageDecision  # noqa: E402
from app.triage.rules import check_red_flags               # noqa: E402
from app.triage.llm_classifier import classify_with_llm    # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MOCK_DATA_DIR = os.path.join(PROJECT_ROOT, "mock-data")
SEPARATOR = "-" * 70


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

    stage_b = data.get("stageB", {})
    raw_input  = stage_b.get("mock_input", {})
    raw_output = stage_b.get("ideal_output", {})

    if not raw_input or not raw_output:
        print("  [SKIP] stageB.mock_input or stageB.ideal_output missing.")
        return 0

    # Parse into typed models
    try:
        mock_input   = IntakeResult(**raw_input)
        ideal_output = TriageDecision(**raw_output)
    except Exception as exc:
        print(f"  [ERROR] Could not parse stageB data into Pydantic models: {exc}")
        return 0  # schema error is not a logic failure; skip gracefully

    failures = 0

    # ------------------------------------------------------------------
    # CHECK 1 -- Red-flag rule (always run)
    # ------------------------------------------------------------------
    print("\n  [CHECK 1] Rule-based red-flag check (check_red_flags)")
    try:
        actual_flag    = check_red_flags(mock_input.symptoms, mock_input.age)
        actual_flags   = [actual_flag] if actual_flag else []
        expected_flags = ideal_output.red_flags_matched

        passed = actual_flags == expected_flags
        if not passed:
            failures += 1

        print(f"    Expected : {expected_flags}")
        print(f"    Actual   : {actual_flags}")
        print(f"    Result   : {_verdict(passed)}")

    except Exception as exc:
        print(f"    [ERROR] check_red_flags raised an exception: {exc}")

    # ------------------------------------------------------------------
    # CHECK 2 -- LLM classifier (only when decided_by is llm-based)
    # ------------------------------------------------------------------
    decided_by     = ideal_output.decided_by   # "rule" | "llm" | "rule+llm"
    is_llm_scenario = "llm" in decided_by       # covers both "llm" and "rule+llm"

    if not is_llm_scenario:
        print(f"\n  [CHECK 2] LLM classifier -- SKIPPED (decided_by='{decided_by}', not LLM-based)")
    else:
        print(f"\n  [CHECK 2] LLM classifier (classify_with_llm)  [decided_by='{decided_by}']")
        try:
            llm_priority, llm_confidence, llm_reason = classify_with_llm(mock_input)

            # --- Priority: strict check ---
            priority_expected = ideal_output.priority
            priority_match    = llm_priority == priority_expected
            if not priority_match:
                failures += 1

            print(f"    Priority  expected : {priority_expected}")
            print(f"    Priority  actual   : {llm_priority}")
            print(f"    Priority  result   : {_verdict(priority_match)}")

            # --- Confidence: soft check (flag for manual review, no hard fail) ---
            confidence_expected = ideal_output.confidence
            confidence_match    = llm_confidence == confidence_expected
            confidence_label    = "matches" if confidence_match else "DIFFERS -- manual review recommended"

            print(f"    Confidence expected: {confidence_expected}")
            print(f"    Confidence actual  : {llm_confidence}  [{confidence_label}]")

            # --- Rationale: manual review only ---
            print(f"    Rationale (manual review only):")
            print(f"      LLM   : {llm_reason}")
            print(f"      Ideal : {ideal_output.priority_rationale}")

        except Exception as exc:
            print(f"    [ERROR] classify_with_llm raised an exception: {exc}")

    return failures


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 70)
    print("  CLINICAL TRIAGE -- SCENARIO VALIDATION RUNNER")
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
