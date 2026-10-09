"""Standard-library-only policy/snapshot acceptance; no platform imports."""

import sys
import tempfile
import types
import unittest
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "ai2apps/app_development"
# Load this module family under a private name so importing cannot initialize AI2Apps.
for name, path in [
    ("isolated_coding", root),
    ("isolated_coding.subagents", root / "subagents"),
]:
    module = types.ModuleType(name)
    module.__path__ = [str(path)]
    sys.modules[name] = module
from isolated_coding.core import Draft  # noqa: E402
from isolated_coding.subagents.contracts import Request, SubagentError  # noqa: E402
from isolated_coding.subagents.policy import tools_for, validate_request  # noqa: E402
from isolated_coding.subagents.snapshots import (  # noqa: E402
    capture,
    merge_patch,
    source_id,
)


class CooperationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.source.joinpath("main.js").write_text("old")
        self.draft = Draft(
            self.source, self.root / "draft", self.root / "state/draft.json"
        )
        self.draft.create()

    def test_role_admission_and_recursion(self):
        validate_request(Request("analyst", "inspect", "a"))
        for request, kwargs in [
            (Request("arbitrary", "task", "a"), {}),
            (Request("worker", "task", "a"), {"depth": 1}),
            (Request("tester", "task", "a"), {"child_count": 4}),
        ]:
            with self.assertRaises(SubagentError):
                validate_request(request, **kwargs)

    def test_reader_permissions(self):
        for role in ["analyst", "reviewer"]:
            self.assertNotIn("appdev.child.write", tools_for(role))
            self.assertNotIn("appdev.child.command", tools_for(role))

    def test_snapshot_is_materialized_and_excludes_secrets(self):
        self.draft.workspace.joinpath(".env").write_text("secret")
        report = capture(self.draft.workspace, self.root / "snapshot")
        self.draft.workspace.joinpath("main.js").write_text("later")
        self.assertEqual(self.root.joinpath("snapshot/main.js").read_text(), "old")
        self.assertFalse(self.root.joinpath("snapshot/.env").exists())
        self.assertNotEqual(report["snapshot_id"], source_id(self.draft.workspace))

    def worker(self):
        capture(self.draft.workspace, self.root / "baseline")
        capture(self.root / "baseline", self.root / "worker")
        return self.root / "worker"

    def test_merge_only_parent_draft(self):
        worker = self.worker()
        worker.joinpath("main.js").write_text("fixed")
        result = merge_patch(
            self.draft, self.root / "baseline", worker, self.draft.review()["revision"]
        )
        self.assertEqual(result["merged"], ["main.js"])
        self.assertEqual(self.source.joinpath("main.js").read_text(), "old")

    def test_conflict_prevents_all_writes(self):
        worker = self.worker()
        worker.joinpath("main.js").write_text("worker")
        worker.joinpath("new.js").write_text("new")
        self.draft.workspace.joinpath("main.js").write_text("parent")
        with self.assertRaises(SubagentError):
            merge_patch(
                self.draft,
                self.root / "baseline",
                worker,
                self.draft.review()["revision"],
            )
        self.assertFalse(self.draft.workspace.joinpath("new.js").exists())

    def test_stale_revision_rejects_merge(self):
        worker = self.worker()
        revision = self.draft.review()["revision"]
        worker.joinpath("main.js").write_text("worker")
        self.draft.workspace.joinpath("extra.js").write_text("parent")
        with self.assertRaises(SubagentError):
            merge_patch(self.draft, self.root / "baseline", worker, revision)

    def test_deletion_rejected(self):
        worker = self.worker()
        worker.joinpath("main.js").unlink()
        with self.assertRaises(SubagentError):
            merge_patch(
                self.draft,
                self.root / "baseline",
                worker,
                self.draft.review()["revision"],
            )

    def test_budget_bounds(self):
        for request in [
            Request("tester", "task", "x", max_model_tokens=20001),
            Request("tester", "task", "x", max_steps=25),
            Request("tester", "task", "x", timeout_seconds=901),
        ]:
            with self.assertRaises(SubagentError):
                validate_request(request)


class PreviewTests(unittest.TestCase):
    def setUp(self):
        from isolated_coding.core import DraftError, safe_path
        from isolated_coding.preview import document

        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.entry = self.root / "index.html"
        self.rejection = (ValueError, DraftError)
        self.render = lambda: document(
            self.entry, "index.html", lambda resource: safe_path(self.root, resource)
        )

    def test_owned_js_css_are_embedded_and_defer_keeps_dom_order(self):
        self.entry.write_text(
            '<head><script defer src="main.js"></script><link rel="stylesheet" href="style.css"></head><body><button>Go</button></body>'
        )
        (self.root / "main.js").write_text(
            'document.querySelector("button").textContent="ready";'
        )
        (self.root / "style.css").write_text("button {color:green;}")
        value = self.render()
        self.assertNotIn('src="main.js"', value)
        self.assertNotIn('href="style.css"', value)
        self.assertIn("<style>button {color:green;}</style>", value)
        self.assertLess(value.index("<button>"), value.index("document.querySelector"))

    def test_external_and_escaping_assets_are_rejected(self):
        for src in ["https://example.com/a.js", "../foreign.js", "/absolute.js"]:
            self.entry.write_text('<script src="' + src + '"></script>')
            with self.assertRaises(self.rejection):
                self.render()

    def test_module_and_oversized_assets_are_not_silently_accepted(self):
        self.entry.write_text('<script type="module" src="main.js"></script>')
        with self.assertRaises(self.rejection):
            self.render()
        self.entry.write_text('<script src="main.js"></script>')
        (self.root / "main.js").write_bytes(b"x" * (1024 * 1024 + 1))
        with self.assertRaises(self.rejection):
            self.render()

    def test_case_insensitive_closing_tags_cannot_break_embedding(self):
        self.entry.write_text('<script src="main.js"></script>')
        (self.root / "main.js").write_text('const sample="</sCrIpT>";')
        self.assertIn("<\\/script>", self.render())


if __name__ == "__main__":
    unittest.main()
