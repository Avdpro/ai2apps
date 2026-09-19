from ai2apps_test.report import write_reports


def test_completed_report_keeps_terminal_conclusion_and_links_safe_evidence(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    (run / "sample image.txt").write_text("evidence")
    (tmp_path / "outside.txt").write_text("outside")
    state = {
        "runId": "sample", "status": "completed",
        "plan": {"priority": None, "cases": [
            {"id": "case-1", "name": "Case <one>", "group": "Group"}
        ]},
        "results": {"case-1": {"status": "blocked", "evidence": [
            "sample image.txt", "../outside.txt", "https://example.com/file"
        ]}},
    }
    result = write_reports(run, state)
    assert result["conclusion"] == "BLOCKED"
    report = (run / "report.html").read_text()
    assert 'href="./sample%20image.txt" target="_blank"' in report
    assert "Case &lt;one&gt;" in report
    assert "outside.txt" not in report
    assert 'href="https:' not in report
