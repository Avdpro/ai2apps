"""Runs with unittest in a clean stdlib-only environment."""

import importlib.util
import tempfile
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "draft_core",
    Path(__file__).resolve().parents[1] / "ai2apps/app_development/core.py",
)
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)
Draft, DraftError = _core.Draft, _core.DraftError


class DraftTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "project"
        self.source.mkdir()
        (self.source / "main.js").write_text("const value = 1;\n")
        self.draft = Draft(
            self.source, self.root / "workspace", self.root / "state/draft.json"
        )
        self.draft.create()

    def test_read_observe_edit_and_original_is_unchanged(self):
        read = self.draft.read("main.js")
        self.draft.edit("main.js", "value = 1", "value = 2", read["sha256"])
        self.assertIn("value = 1", (self.source / "main.js").read_text())
        review = self.draft.review()
        self.assertIn("+const value = 2", review["changes"][0]["diff"])
        self.draft.apply(review["revision"])
        self.assertIn("value = 2", (self.source / "main.js").read_text())
        self.assertIn("value = 1", (self.root / "state/backup/main.js").read_text())

    def test_unread_overwrite_is_rejected(self):
        with self.assertRaises(DraftError):
            self.draft.write("main.js", "overwrite")

    def test_stale_observation_does_not_overwrite(self):
        read = self.draft.read("main.js")
        (self.draft.workspace / "main.js").write_text("changed by command")
        with self.assertRaises(DraftError):
            self.draft.write("main.js", "overwrite", read["sha256"])
        self.assertEqual(
            (self.draft.workspace / "main.js").read_text(), "changed by command"
        )

    def test_ambiguous_edit_is_rejected(self):
        self.draft.write("duplicates.js", "x x")
        read = self.draft.read("duplicates.js")
        with self.assertRaises(DraftError):
            self.draft.edit("duplicates.js", "x", "y", read["sha256"])
        self.draft.edit("duplicates.js", "x", "y", read["sha256"], True)
        self.assertEqual((self.draft.workspace / "duplicates.js").read_text(), "y y")

    def test_source_conflict_blocks_entire_apply(self):
        read = self.draft.read("main.js")
        self.draft.write("main.js", "draft", read["sha256"])
        self.draft.write("new.js", "new")
        (self.source / "main.js").write_text("external edit")
        review = self.draft.review()
        with self.assertRaises(DraftError):
            self.draft.apply(review["revision"])
        self.assertFalse((self.source / "new.js").exists())
        self.assertEqual((self.source / "main.js").read_text(), "external edit")

    def test_review_revision_rejects_changed_draft(self):
        self.draft.write("new.js", "a")
        review = self.draft.review()
        read = self.draft.read("new.js")
        self.draft.write("new.js", "b", read["sha256"])
        with self.assertRaises(DraftError):
            self.draft.apply(review["revision"])
        self.assertFalse((self.source / "new.js").exists())

    def test_paths_and_symlinks_do_not_escape(self):
        for path in ("../secret", "/tmp/secret", "a\\b", ".env", ".git/config"):
            with self.subTest(path=path), self.assertRaises(DraftError):
                self.draft.write(path, "x")
        (self.draft.workspace / "link").symlink_to(
            self.source, target_is_directory=True
        )
        with self.assertRaises(DraftError):
            self.draft.write("link/main.js", "x")

    def test_durable_observation_survives_new_adapter(self):
        read = self.draft.read("main.js")
        fresh = Draft(self.source, self.draft.workspace, self.draft.state)
        fresh.edit("main.js", "1", "2", read["sha256"])
        self.assertEqual(len(fresh.review()["changes"]), 1)

    def test_secret_and_dependencies_are_excluded(self):
        source = self.root / "second"
        source.mkdir()
        (source / ".env.local").write_text("secret")
        (source / "node_modules").mkdir()
        (source / "node_modules/a.js").write_text("dependency")
        (source / "app.html").write_text("hello")
        draft = Draft(
            source, self.root / "second-work", self.root / "second-state/meta.json"
        )
        info = draft.create()
        self.assertEqual(info["files"], 1)
        self.assertIn(".env.local", info["excluded"])

    def test_bounded_line_reads_and_continuation(self):
        self.draft.write("large.js", "\n".join(str(i) for i in range(600)))
        result = self.draft.read("large.js", 1, 200)
        self.assertEqual(result["next_offset"], 201)
        self.assertTrue(result["content"].startswith("1: 0"))
        self.assertTrue(
            self.draft.read("large.js", 201, 200)["content"].startswith("201: 200")
        )

    def test_deletion_is_not_applied(self):
        (self.draft.workspace / "main.js").unlink()
        review = self.draft.review()
        with self.assertRaises(DraftError):
            self.draft.apply(review["revision"])
        self.assertTrue((self.source / "main.js").exists())

    def test_nested_creation_and_no_double_apply(self):
        self.draft.write("web/components/new.js", "new")
        review = self.draft.review()
        self.draft.apply(review["revision"])
        self.assertEqual((self.source / "web/components/new.js").read_text(), "new")
        with self.assertRaises(DraftError):
            self.draft.apply(review["revision"])


if __name__ == "__main__":
    unittest.main()
