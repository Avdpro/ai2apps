from __future__ import annotations

import html
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import quote
from xml.etree.ElementTree import Element, ElementTree, SubElement

from .state import atomic_write_json, now_text


def conclusion(state: dict[str, Any], finalize_pending: bool = False) -> str:
    finalize_pending = finalize_pending or state.get("status") in {"completed", "cancelled"}
    lease_status = state.get("testAccountLease", {}).get("status")
    if lease_status == "release_failed":
        return "BLOCKED" if finalize_pending else "RUNNING"
    if state.get("status") == "cancelled":
        return "CANCELLED"
    results = state["results"]
    cases = state["plan"]["cases"]
    statuses = [
        results.get(case["id"], {}).get("status", "pending") for case in cases
        if not (state.get("pipelineStop") and
                results.get(case["id"], {}).get("skipReason") == "pipeline-stop")
    ]
    if "failed" in statuses:
        return "FAIL"
    if lease_status == "leased":
        return "BLOCKED" if finalize_pending else "RUNNING"
    if "blocked" in statuses or "skipped" in statuses or "pending" in statuses:
        return "BLOCKED" if finalize_pending else "RUNNING"
    required_selected = {case["id"] for case in cases if case.get("required", True)}
    required_catalog = set(state["plan"].get("requiredCaseIds", []))
    return "PASS" if required_catalog <= required_selected else "SCOPED_PASS"


def write_reports(
    run_dir: Path, state: dict[str, Any], finalize_pending: bool = False
) -> dict[str, Any]:
    result = {
        "schemaVersion": "ai2apps.test-result.v1",
        "runId": state["runId"],
        "generatedAt": now_text(),
        "conclusion": conclusion(state, finalize_pending=finalize_pending),
        "plan": state["plan"],
        "results": state["results"],
        "testAccount": state.get("testAccountLease"),
        "pipelineStop": state.get("pipelineStop"),
    }
    atomic_write_json(run_dir / "result.json", result)
    counts = Counter(
        value.get("status", "pending") for value in state["results"].values()
    )
    account_status = state.get("testAccountLease", {}).get("status", "not-required")
    total = len(state["plan"]["cases"])
    diagnostics = state["plan"].get("catalogDiagnostics", {})
    lines = [
        f"# AI2Apps Test Report — {state['runId']}",
        "",
        f"- Conclusion: **{result['conclusion']}**",
        f"- Priority: **{state['plan']['priority']}**",
        f"- Selected cases: **{total}**",
        f"- Passed: {counts['passed']}; Failed: {counts['failed']}; Blocked: {counts['blocked']}; Skipped: {counts['skipped']}; Pending: {total - sum(counts.values())}",
        f"- Test account: **{account_status}**",
        f"- Catalog changes: newly discovered {len(diagnostics.get('newlyDiscovered', []))}; changed contracts {len(diagnostics.get('changedContracts', []))}; stale references {len(diagnostics.get('staleReferences', []))}",
        "",
        "## Cases",
        "",
        "| Status | Expected | Observed | Scope | Group | Source | Case | Summary |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    rows = []
    for case in state["plan"]["cases"]:
        case_result = state["results"].get(case["id"], {})
        status = case_result.get("status", "pending")
        summary = (
            str(case_result.get("summary", "")).replace("|", "\\|").replace("\n", " ")
        )
        duration = case_result.get("durationSeconds")
        timing = f"{duration:.1f} 秒" if isinstance(duration, (int, float)) else "—（未记录）"
        summary = f"耗时：{timing}。 {summary}"
        scope = case.get("priority") or "on-demand"
        source = case.get("sourceType", case.get("source_type", "built-in"))
        expected = case_result.get("expectedStatus", case.get("expectedStatus", ""))
        observed = case_result.get("observedStatus", "")
        rows.append(
            (
                status,
                expected,
                observed,
                scope,
                case["group"],
                source,
                case["id"],
                summary,
            )
        )
        lines.append(
            f"| {status} | {expected} | {observed} | {scope} | {case['group']} | "
            f"{source} | `{case['id']}` | {summary} |"
        )
    evidence_sections = []
    lines.extend(["", "## Evidence", ""])
    for case in state["plan"]["cases"]:
        links = []
        lines.extend([f"### {case['id']}", ""])
        for evidence in state["results"].get(case["id"], {}).get("evidence", []):
            path = (run_dir / evidence).resolve()
            if run_dir.resolve() not in path.parents or not path.is_file():
                continue
            relative = path.relative_to(run_dir.resolve()).as_posix()
            href = "./" + quote(relative, safe="/")
            links.append(f'<li><a href="{html.escape(href, quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(relative)}</a></li>')
            lines.append(f"- [{relative}]({href})")
        title = html.escape(f"{case['name']} · {case['id']}")
        evidence_sections.append(f"<section><h3>{title}</h3><ul>{''.join(links) if links else '<li>暂无证据文件</li>'}</ul></section>")
    (run_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    table_rows = "".join(
        "<tr>"
        + "".join(f"<td>{html.escape(str(value))}</td>" for value in row)
        + "</tr>"
        for row in rows
    )
    document = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>AI2Apps Test Report {html.escape(state["runId"])}</title>
<style>body{{font:14px system-ui;margin:32px;color:#202124}}.summary{{display:flex;gap:16px;flex-wrap:wrap}}.card{{padding:12px 16px;border:1px solid #ddd;border-radius:10px}}table{{border-collapse:collapse;width:100%;margin-top:24px}}th,td{{border-bottom:1px solid #ddd;padding:9px;text-align:left}}th{{position:sticky;top:0;background:#fff}}</style></head>
<body><h1>AI2Apps Test Report</h1><div class="summary"><div class="card">Conclusion<br><strong>{result["conclusion"]}</strong></div><div class="card">Priority<br><strong>{state["plan"]["priority"]}</strong></div><div class="card">Selected<br><strong>{total}</strong></div><div class="card">Test account<br><strong>{html.escape(account_status)}</strong></div><div class="card">Catalog changes<br><strong>{len(diagnostics.get("newlyDiscovered", []))} new / {len(diagnostics.get("changedContracts", []))} changed</strong></div></div>
<table><thead><tr><th>Status</th><th>Expected</th><th>Observed</th><th>Scope</th><th>Group</th><th>Source</th><th>Case</th><th>Summary</th></tr></thead><tbody>{table_rows}</tbody></table></body></html>"""
    document = document.replace("</body>", "<h2>证据文件</h2>" + "".join(evidence_sections) + "</body>")
    (run_dir / "report.html").write_text(document, encoding="utf-8")
    suite = Element("testsuite", name="ai2apps-test", tests=str(total))
    for case in state["plan"]["cases"]:
        case_result = state["results"].get(case["id"], {})
        item = SubElement(
            suite,
            "testcase",
            classname=case["group"],
            name=case["id"],
            time=str(case_result.get("durationSeconds", 0)),
        )
        status = case_result.get("status", "pending")
        summary = str(case_result.get("summary", ""))
        if status == "failed":
            SubElement(item, "failure", message=summary).text = summary
        elif status in {"blocked", "pending", "skipped"}:
            SubElement(item, "skipped", message=summary or status)
    ElementTree(suite).write(
        run_dir / "junit.xml", encoding="utf-8", xml_declaration=True
    )
    return result
