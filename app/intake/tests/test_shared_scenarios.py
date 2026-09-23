"""
Test suite validating Intake Extractor against the 8 project-root mock scenarios.

Reads scenario-01.json through scenario-08.json from the shared mock-data/ directory
and feeds stageA.mock_input through extractor.py, validating output structure,
reasonableness, prompt-injection defense, and pediatric age capture.
"""

import json
import unittest
from pathlib import Path

from app.intake.schemas import IntakeRequest
from app.intake.extractor import extract_intake
from app.intake.redflag_scan import scan_red_flags, get_canonical_red_flag_symptoms


def get_mock_data_dir() -> Path:
    """Find repository root mock-data directory."""
    # From app/intake/tests/test_shared_scenarios.py -> up 4 levels to ClinicalTriage root
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    mock_dir = repo_root / "mock-data"
    if not mock_dir.exists():
        # Fallback to relative path
        mock_dir = Path("mock-data").resolve()
    return mock_dir


def parse_known_conditions_raw(raw_cond: str) -> list[str]:
    """Parse comma-separated raw known conditions into a clean string list."""
    if not raw_cond or raw_cond.strip().lower() in ("none", "nil", "no", "-"):
        return []
    return [c.strip() for c in raw_cond.split(",") if c.strip()]


class TestSharedMockScenarios(unittest.TestCase):
    """Automated tests validating extractor against mock-data/scenario-*.json."""

    @classmethod
    def setUpClass(cls):
        cls.mock_dir = get_mock_data_dir()
        cls.scenario_files = sorted(cls.mock_dir.glob("scenario-*.json"))
        cls.execution_reports: list[dict] = []

    def load_scenario(self, filename: str) -> dict:
        file_path = self.mock_dir / filename
        self.assertTrue(file_path.exists(), f"Mock scenario file not found: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def run_stageA_extraction(self, scenario_data: dict) -> tuple[dict, object, list[str]]:
        stageA = scenario_data["stageA"]
        mock_in = stageA["mock_input"]
        ideal_out = stageA["ideal_output"]

        raw_conds = mock_in.get("known_conditions_raw", "")
        parsed_conds = parse_known_conditions_raw(raw_conds)

        req = IntakeRequest(
            patient_id=mock_in.get("patient_id", "P-TEST"),
            raw_transcript=mock_in["raw_transcript"],
            language=mock_in.get("language", "en"),
            age=mock_in.get("age"),
            known_conditions=parsed_conds,
        )

        actual_result = extract_intake(req)
        detected_red_flags = scan_red_flags(mock_in["raw_transcript"])

        return ideal_out, actual_result, detected_red_flags

    def test_scenario_01_emergency_chest_pain(self):
        data = self.load_scenario("scenario-01.json")
        ideal, actual, red_flags = self.run_stageA_extraction(data)

        # 1. Structure & Non-empty
        self.assertTrue(actual.chief_complaint)
        self.assertFalse(any("\u0b80" <= ch <= "\u0bff" for ch in actual.chief_complaint))
        self.assertIn("chest", actual.chief_complaint.lower())

        # 2. Duration extracted
        self.assertNotEqual(actual.duration.lower(), "unspecified")
        self.assertIn("20", actual.duration)

        # 3. Symptoms overlap
        symptoms_str = " ".join(actual.symptoms).lower()
        self.assertTrue("chest" in symptoms_str or "cardiac" in symptoms_str)

        # 4. Age exact match
        self.assertEqual(actual.age, ideal["age"])

        # 5. Known conditions
        cond_str = " ".join(actual.known_conditions).lower()
        self.assertTrue("hypertension" in cond_str or "blood pressure" in cond_str or "diabetes" in cond_str)

        # 6. Red flags detected
        self.assertIn("chest_pain", red_flags)

    def test_scenario_02_emergency_stroke(self):
        data = self.load_scenario("scenario-02.json")
        ideal, actual, red_flags = self.run_stageA_extraction(data)

        self.assertTrue(actual.chief_complaint)
        self.assertNotEqual(actual.duration.lower(), "unspecified")
        self.assertEqual(actual.age, ideal["age"])
        self.assertIn("stroke_symptoms", red_flags)

    def test_scenario_03_same_day_laceration(self):
        data = self.load_scenario("scenario-03.json")
        ideal, actual, red_flags = self.run_stageA_extraction(data)

        self.assertTrue(actual.chief_complaint)
        self.assertNotEqual(actual.duration.lower(), "unspecified")
        self.assertEqual(actual.age, ideal["age"])
        self.assertFalse(any("\u0b80" <= ch <= "\u0bff" for ch in actual.chief_complaint))

    def test_scenario_04_routine_mild_cold(self):
        data = self.load_scenario("scenario-04.json")
        ideal, actual, red_flags = self.run_stageA_extraction(data)

        self.assertTrue(actual.chief_complaint)
        self.assertNotEqual(actual.duration.lower(), "unspecified")
        self.assertEqual(actual.age, ideal["age"])
        # Routine mild cold should have zero emergency red flags
        self.assertEqual(red_flags, [])

    def test_scenario_05_ambiguous_abdominal_pain(self):
        data = self.load_scenario("scenario-05.json")
        ideal, actual, red_flags = self.run_stageA_extraction(data)

        self.assertTrue(actual.chief_complaint)
        self.assertNotEqual(actual.duration.lower(), "unspecified")
        self.assertEqual(actual.age, ideal["age"])

    def test_scenario_06_regional_tamil_voice(self):
        data = self.load_scenario("scenario-06.json")
        ideal, actual, red_flags = self.run_stageA_extraction(data)

        # Chief complaint must strictly be English canonical despite Tamil input
        self.assertTrue(actual.chief_complaint)
        self.assertFalse(
            any("\u0b80" <= ch <= "\u0bff" for ch in actual.chief_complaint),
            f"Tamil script found in chief_complaint: {actual.chief_complaint}",
        )
        self.assertIn("fever", actual.chief_complaint.lower())

        # Duration extracted from Tamil
        self.assertNotEqual(actual.duration.lower(), "unspecified")

        # Raw transcript must remain untouched Tamil
        self.assertEqual(actual.raw_transcript, ideal["raw_transcript"])
        self.assertEqual(actual.age, ideal["age"])

    def test_scenario_07_prompt_injection_safety(self):
        data = self.load_scenario("scenario-07.json")
        ideal, actual, red_flags = self.run_stageA_extraction(data)

        # Explicitly verify adversarial phrase did NOT downplay extraction
        self.assertNotIn("routine", actual.chief_complaint.lower())
        self.assertNotIn("low priority", actual.chief_complaint.lower())
        self.assertNotIn("ignore previous", " ".join(actual.symptoms).lower())

        # Anaphylaxis red flag must be caught regardless of injection
        self.assertIn("anaphylaxis", red_flags)
        self.assertEqual(actual.age, ideal["age"])

    def test_scenario_08_pediatric_febrile_seizure(self):
        data = self.load_scenario("scenario-08.json")
        ideal, actual, red_flags = self.run_stageA_extraction(data)

        # Age must correctly be 3
        self.assertEqual(actual.age, 3)

        # Seizure red flag detected
        self.assertIn("seizure", red_flags)
        self.assertTrue(any("seizure" in s.lower() for s in actual.symptoms))


def generate_scenario_report() -> list[dict]:
    """Generate comprehensive comparison report across all 8 mock scenarios."""
    mock_dir = get_mock_data_dir()
    reports = []

    for i in range(1, 9):
        fname = f"scenario-{i:02d}.json"
        fpath = mock_dir / fname
        if not fpath.exists():
            continue

        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)

        stageA = data["stageA"]
        mock_in = stageA["mock_input"]
        ideal = stageA["ideal_output"]

        parsed_conds = parse_known_conditions_raw(mock_in.get("known_conditions_raw", ""))
        req = IntakeRequest(
            patient_id=mock_in.get("patient_id", f"P{i:03d}"),
            raw_transcript=mock_in["raw_transcript"],
            language=mock_in.get("language", "en"),
            age=mock_in.get("age"),
            known_conditions=parsed_conds,
        )
        actual = extract_intake(req)
        red_flags = scan_red_flags(mock_in["raw_transcript"])

        reports.append({
            "scenario_id": data.get("scenario_id", fname),
            "description": data.get("description", ""),
            "input_language": mock_in.get("language", "en"),
            "actual_chief_complaint": actual.chief_complaint,
            "ideal_chief_complaint": ideal.get("chief_complaint"),
            "actual_duration": actual.duration,
            "ideal_duration": ideal.get("duration"),
            "actual_age": actual.age,
            "ideal_age": ideal.get("age"),
            "actual_symptoms": actual.symptoms,
            "ideal_symptoms": ideal.get("symptoms", []),
            "actual_conditions": actual.known_conditions,
            "ideal_conditions": ideal.get("known_conditions", []),
            "actual_confidence": actual.input_confidence,
            "ideal_confidence": ideal.get("input_confidence"),
            "detected_red_flags": red_flags,
            "canonical_red_flags": get_canonical_red_flag_symptoms(red_flags),
        })

    return reports


if __name__ == "__main__":
    unittest.main()
