from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_python_context_manifest_is_diverse_and_excludes_eval_topic():
    all_ids = set()
    for version in (1, 2):
        manifest = json.loads(
            (
                ROOT
                / "configs"
                / f"code-python-mixed-contexts.v{version}.json"
            ).read_text()
        )
        prompts = manifest["prompts"]
        ids = {item["id"] for item in prompts}
        assert len(prompts) >= 16
        assert len(ids) == len(prompts)
        assert not (all_ids & ids)
        all_ids.update(ids)
        assert {item["language"] for item in prompts} == {"en", "zh"}
        assert len({item["category"] for item in prompts}) >= 8
        joined = " ".join(item["content"].lower() for item in prompts)
        assert "asynchronous job queue" not in joined
