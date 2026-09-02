import json
import subprocess
import sys
from pathlib import Path


def test_release_a_gate_emits_reproducible_model_free_report(tmp_path):
    root = Path(__file__).parents[1]
    output = tmp_path / "knowledge-release-a.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/acceptance_knowledge_release_a.py",
            "--skip-tests",
            "--output",
            str(output),
        ],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(output.read_text())
    assert report["format"] == "ai2apps-knowledge-release-a-gate"
    assert report["version"] == 1
    assert len(report["fixture_digests"]["eval_cases.json"]) == 64
    assert report["passed"] is True
    assert report["release_ready"] is False
    assert report["pending_checks"] == ["focused_tests", "live_answer_quality"]
    quality = next(
        value for value in report["checks"] if value["id"] == "model_free_quality"
    )
    assert quality["status"] == "pass"
    assert all(value == 1.0 for value in quality["metrics"].values() if isinstance(value, float))


def test_release_a_gate_can_require_live_model_evidence(tmp_path):
    root = Path(__file__).parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "scripts/acceptance_knowledge_release_a.py",
            "--skip-tests",
            "--require-live",
        ],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["failed_checks"] == ["live_answer_quality"]
    assert report["release_ready"] is False
