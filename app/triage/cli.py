"""
python -m app.triage.cli  [--live]

Runs every mock-data/scenario-*.json through the full triage pipeline and
prints PASS/FAIL against mock-data/expected.json. By default the LLM is a
fake client returning the canned reply from expected.json, so no API key is
needed. --live uses the configured client (falls back safely without a key).
"""

import argparse
import json
import sys
from pathlib import Path

from app.common.llm import FakeLLMClient, get_llm_client
from app.common.schemas import IntakeResult
from app.triage.service import triage

ROOT = Path(__file__).resolve().parents[2]
MOCK = ROOT / "mock-data"


def load_scenarios() -> list[tuple[str, dict]]:
    return [(p.name, json.loads(p.read_text(encoding="utf-8-sig"))) for p in sorted(MOCK.glob("scenario-*.json"))]


def load_expected() -> dict:
    return json.loads((MOCK / "expected.json").read_text(encoding="utf-8"))


def run_scenario(name: str, data: dict, exp: dict, live: bool = False):
    intake = IntakeResult.model_validate(data["stageB"]["mock_input"])
    client = get_llm_client() if live else FakeLLMClient(json.dumps(exp["fake_llm"]) if exp.get("fake_llm") else None)
    decision = triage(intake, client=client)
    problems = []
    if decision.priority != exp["priority"]:
        problems.append(f"priority {decision.priority} != {exp['priority']}")
    if not live and decision.decided_by != exp["decided_by"]:
        problems.append(f"decided_by {decision.decided_by} != {exp['decided_by']}")
    for f in exp.get("red_flags_include", []):
        if f not in decision.red_flags_matched:
            problems.append(f"missing red flag {f}")
    for n in exp.get("audit_notes_include", []):
        if n not in decision.audit_notes:
            problems.append(f"missing audit note {n}")
    if exp.get("fake_llm") is None and not live and isinstance(client, FakeLLMClient) and client.calls:
        problems.append("LLM was called on a rule-decided case")
    return decision, problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--live", action="store_true", help="use the configured LLM instead of the fake client")
    args = ap.parse_args(argv)
    expected = load_expected()
    failures = 0
    scenarios = load_scenarios()
    for name, data in scenarios:
        decision, problems = run_scenario(name, data, expected[name], args.live)
        status = "PASS" if not problems else "FAIL"
        failures += bool(problems)
        print(f"{status}  {name:18s} {data['scenario_id']:36s} priority={decision.priority:9s} decided_by={decision.decided_by:8s} flags={decision.red_flags_matched}")
        for p in problems:
            print(f"      - {p}")
    print(f"\n{len(scenarios) - failures}/{len(scenarios)} scenarios passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
