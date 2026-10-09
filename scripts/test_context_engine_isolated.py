#!/usr/bin/env python3
"""Accept the standalone core in a fresh stdlib-only venv before host integration."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    source = repo / "ai2apps/context_engine"
    tests = repo / "tests/context_engine_isolated/test_engine.py"
    hashes = {
        str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [
            source / "pruning.py",
            source / "images.py",
            source / "core.py",
            source / "__init__.py",
            source / "DEEPSEEK-LICENSE.txt",
            tests,
        ]
    }
    with tempfile.TemporaryDirectory(prefix="ai2apps-context-acceptance-") as directory:
        root = Path(directory)
        (root / "context_engine").mkdir()
        (root / "tests").mkdir()
        for name in (
            "core.py",
            "images.py",
            "pruning.py",
            "__init__.py",
            "DEEPSEEK-LICENSE.txt",
        ):
            shutil.copy2(source / name, root / "context_engine" / name)
        shutil.copy2(tests, root / "tests/test_engine.py")
        subprocess.run([sys.executable, "-m", "venv", str(root / "venv")], check=True)
        program = (
            "import sys,unittest,json; from pathlib import Path; sys.path.insert(0,sys.argv[1]); "
            "suite=unittest.defaultTestLoader.discover(sys.argv[1]+'/tests'); "
            "result=unittest.TextTestRunner().run(suite); "
            "assert not any(n=='ai2apps' or n.startswith('ai2apps.') for n in sys.modules); "
            "Path(sys.argv[1]+'/result.json').write_text(json.dumps({'tests':result.testsRun,'success':result.wasSuccessful()})); "
            "sys.exit(not result.wasSuccessful())"
        )
        result = subprocess.run(
            [str(root / "venv/bin/python"), "-I", "-c", program, str(root)], cwd=root
        )
        if result.returncode:
            return result.returncode
        result_data = json.loads((root / "result.json").read_text())
    if args.receipt:
        args.receipt.write_text(
            json.dumps(
                {
                    "upstream_commit": "5badb15009ae1756c3afe0ae0cef1faafc290ccc",
                    "engine": "deepseek-context-python/1",
                    "environment": "fresh venv, Python -I, stdlib only",
                    "ai2apps_imported": False,
                    "result": "passed",
                    "tests": result_data["tests"],
                    "source_sha256": hashes,
                    "scope": "Translated behavioral cases; not the complete upstream Vitest suite or real-model validation",
                },
                indent=2,
            )
            + "\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
