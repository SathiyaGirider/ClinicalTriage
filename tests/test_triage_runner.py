"""
test_triage_runner.py
=====================
Validates the triage pipeline (rules + LLM) against every scenario*.json
file found in mock-data/.

Run from the project root:
    python tests/test_triage_runner.py

A scenario counts as PASSED only if every check that ran actually matched.
A scenario that raised an exception (e.g. LLM timeout) is counted separately
as ERRORED — NOT the same as passed, since the check never actually completed.

Exit code:
    0  -- all scenarios passed, no errors
    1  -- one or more strict failures or errors occurred
"""

# Script, not a pytest module (run: python tests/test_triage_runner.py).
__test__ = False

import json
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

print("DEBUG - PROJECT_ROOT:", PROJECT_ROOT)
print("DEBUG - sys.path:", sys.path)

from app.common.schemas import IntakeResult, TriageDecision  # noqa: E402

from app.common.schemas import IntakeResult, TriageDecision  # noqa: E402
from app.triage.rules import check_red_flags               # noqa: E402
from app.triage.llm_classifier import classify_with_llm    # noqa: E402

MOCK_DATA_DIR = os.path.join(PROJECT_ROOT, "mock-data")
SEPARATOR = "-" * 70


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


def test_scenario(fname: str, data: dict) -> tuple[int, bool]:
    """
    Run all applicable checks for one scenario.

    Returns (failures, errored):
        failures -- number of strict-check mismatches (0 = all matched)
        errored  -- True if any check raised an exception and could not
                    be verified at all (counted separately from failures)
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
        return 0, False

    try:
        mock_input   = IntakeResult(**raw_input)
        ideal_output = TriageDecision(**raw_output)
    except Exception as exc:
        print(f"  [ERROR] Could not parse stageB data into Pydantic models: {exc}")
        return 0, True  # can't verify anything -- counts as errored

    failures = 0
    errored  = False

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
        errored = True

    # ------------------------------------------------------------------
    # CHECK 2 -- LLM classifier (only when decided_by is llm-based)
    # ------------------------------------------------------------------
    decided_by      = ideal_output.decided_by   # "rule" | "llm" | "rule+llm"
    is_llm_scenario = "llm" in decided_by

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
            # The check never actually completed -- this is NOT a pass,
            # and NOT necessarily a wrong answer either. Track separately.
            print(f"    [ERROR] classify_with_llm raised an exception: {exc}")
            print(f"    [UNVERIFIED] This scenario's LLM check could not be completed.")
            errored = True

    return failures, errored


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

    total         = len(scenarios)
    passed        = 0
    errored_count = 0
    failed_count  = 0

    for fname, data in scenarios:
        try:
            failures, errored = test_scenario(fname, data)
            if errored:
                errored_count += 1
            elif failures == 0:
                passed += 1
            else:
                failed_count += 1
        except Exception as exc:
            print(f"\n  [FATAL ERROR] Unhandled exception in '{fname}': {exc}")
            errored_count += 1

    print(f"\n{'=' * 70}")
    print("  SUMMARY")
    print(f"{'=' * 70}")
    print(f"  Scenarios tested     : {total}")
    print(f"  Passed               : {passed} / {total}")
    if failed_count:
        print(f"  Failed (wrong answer): {failed_count} / {total}")
    if errored_count:
        print(f"  Errored (unverified) : {errored_count} / {total}  <-- re-run these, not counted as passed")
    print("=" * 70)

    sys.exit(1 if (failed_count or errored_count) else 0)


if __name__ == "__main__":
    main()