"""End-to-end Bot and worker execution with deterministic model responses."""

import json

import pytest

from ai2apps.skills.library import principal_owner
from test_app_chat_durable import bind_identity, response
from test_app_interactions import runtime, wait
from test_bot_capability_discovery import P, setup
from test_bot_dialogue import job_wait


def install_skill(library, owner, text, update=None, files=None):
    entry = f"---\nname: format-check\ndescription: Format a test receipt\n---\n{text}\n"
    pending = library.preview(owner, "format-check", {"SKILL.md": entry.encode(), **(files or {})},
                              {"kind": "local"}, "local:format-check",
                              update and update["id"], update and update["revision"])
    return library.install(owner, pending["id"])


@pytest.mark.asyncio
@pytest.mark.parametrize("with_references", [False, True])
async def test_enabled_skill_is_loaded_on_demand_by_dialogue_and_task(runtime, bind_identity, with_references):
    bot, sid, _, _ = setup(runtime)
    principal = P()
    library = runtime.messager_skills.library
    owner = principal_owner(principal)
    item = install_skill(library, owner, "Use receipt format RECEIPT-729.", files={
        "references/receipt.md": b"LOADED-391",
        "references/unrelated.md": b"UNRELATED-248",
        "scripts/shell.sh": b"SCRIPT-533",
    } if with_references else None)
    library.set_bot_skill(owner, bot["id"], item["id"], True)
    observed = []

    async def model(request):
        messages = request["messages"]
        serialized = json.dumps(messages)
        assert "UNRELATED-248" not in serialized
        assert "SCRIPT-533" not in serialized
        if messages[0]["content"].startswith("Select one Skill"):
            assert 'RECEIPT-729' not in serialized
            assert 'LOADED-391' not in serialized
            assert 'reference_paths' not in serialized
            observed.append("select")
            return response(text=item["id"])
        if messages[0]["content"].startswith("Choose which Skill reference"):
            assert 'RECEIPT-729' in serialized
            assert 'LOADED-391' not in serialized
            assert 'scripts/shell.sh' not in serialized
            observed.append("references")
            return response(text=json.dumps({"paths": [
                "references/receipt.md", "../private.txt", "scripts/shell.sh",
            ]}))
        assert 'RECEIPT-729' in serialized
        assert ('LOADED-391' in serialized) == with_references
        assert not any(m.get("role") == "assistant" and '"paths"' in m.get("content", "") for m in messages)
        if "Decide quickly" in messages[0]["content"]:
            worker = "start a task" in messages[-1]["content"]
            observed.append("route" if worker else "reply")
            return response(text=json.dumps({"kind": "task" if worker else "reply",
                                            "title": "Skill fixture",
                                            "text": "Queued" if worker else "RECEIPT-729"}))
        observed.append("work")
        assert not any(m.get("role") == "assistant" and m.get("content") == item["id"] for m in messages)
        return response(text="Task receipt RECEIPT-729")

    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        dialogue = runtime.messager_dialogue
        first = dialogue.submit(principal, bot["id"], sid, "skill-reply", "/skill format-check say the label", "fixture", [])
        await wait(runtime, first, "completed")
        second = dialogue.submit(principal, bot["id"], sid, "skill-task", "start a task to format a test receipt", "fixture", [])
        await wait(runtime, second, "completed")
        await job_wait(runtime, second, "completed")
        messages = runtime.app_chat.message_page(principal, sid)["items"]
        assert any(m["content"] == "Task receipt RECEIPT-729" for m in messages)
        expected = ["references"] if with_references else []
        assert observed == [*expected, "reply", "select", *expected, "route", "select", *expected, "work"]
    finally:
        await runtime.stop_background_tasks()


def test_old_revision_remains_pinned_until_revocation(tmp_path):
    from ai2apps.skills.library import SkillLibrary

    library = SkillLibrary(tmp_path)
    item = install_skill(library, "owner", "Version one", files={"references/code.txt": b"one"})
    library.set_bot_skill("owner", "bot", item["id"], True)
    old, = library.bot_snapshot("owner", "bot")
    assert library.bot_snapshot("owner", "different-bot") == []
    new_item = install_skill(library, "owner", "Version two", update=item, files={"references/code.txt": b"two"})
    new, = library.bot_snapshot("owner", "bot")
    assert new["revision"] == new_item["revision"]
    assert library.bot_entry("owner", "bot", old).endswith("Version one\n")
    assert library.bot_entry("owner", "bot", new).endswith("Version two\n")
    def reference(pin):
        return library.bot_content("owner", "bot", pin, paths=["references/code.txt"])[1]
    assert reference(old) == [{"path": "references/code.txt", "text": "one"}]
    assert reference(new) == [{"path": "references/code.txt", "text": "two"}]
    library.set_bot_skill("owner", "bot", item["id"], False)
    library.set_bot_skill("owner", "bot", item["id"], True)
    with pytest.raises(PermissionError):
        reference(old)
    current, = library.bot_snapshot("owner", "bot")
    library.remove("owner", item["id"])
    with pytest.raises(PermissionError):
        library.bot_entry("owner", "bot", current)


def test_bot_skill_assignment_survives_disable_without_retaining_runtime_access(tmp_path):
    from ai2apps.skills.library import SkillLibrary

    library = SkillLibrary(tmp_path)
    item = install_skill(library, "owner", "Test assignment.")
    skill = item["id"]

    def state(bot="bot"):
        row, = SkillLibrary(tmp_path).bot_items("owner", bot)
        return row["added"], row["enabled"]

    assert state() == (False, False)
    library.set_bot_skill("owner", "bot", skill, True)
    old, = library.bot_snapshot("owner", "bot")
    assert state() == (True, True)
    assert state("other") == (False, False)

    library.set_bot_skill("owner", "bot", skill, False)
    assert state() == (True, False)
    assert library.bot_snapshot("owner", "bot") == []
    with pytest.raises(PermissionError):
        library.bot_entry("owner", "bot", old)

    library.set_bot_skill("owner", "bot", skill, True)
    assert state() == (True, True)
    current, = library.bot_snapshot("owner", "bot")
    library.remove_bot_skill("owner", "bot", skill)
    assert state() == (False, False)
    with pytest.raises(PermissionError):
        library.bot_entry("owner", "bot", current)

    library.set_bot_skill("owner", "bot", skill, True)
    library.set_bot_skill("owner", "bot", skill, False)
    library.remove_bot_skill("owner", "bot", skill)
    assert state() == (False, False)


@pytest.mark.asyncio
async def test_skill_management_routes_keep_disabled_entries_until_removed(runtime):
    import httpx
    from fastapi import FastAPI
    from ai2apps.api.router import create_ai2apps_router

    bot, _, _, _ = setup(runtime)
    library = runtime.messager_skills.library
    item = install_skill(library, principal_owner(P()), "Test assignment.")
    app = FastAPI()
    app.include_router(create_ai2apps_router(runtime_provider=lambda: runtime, principal_provider=P))
    url = f"/v1/platform/messager/bots/{bot['id']}/skills"
    entry = f"{url}/{item['id']}"
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
        headers={"Origin": "http://test"},
    ) as client:
        for request, expected in (
            (lambda: client.get(url), (False, False)),
            (lambda: client.put(entry, json={"enabled": True}), (True, True)),
            (lambda: client.put(entry, json={"enabled": False}), (True, False)),
            (lambda: client.delete(entry), (False, False)),
        ):
            result = await request()
            assert result.status_code == 200, result.text
            row, = result.json()["items"]
            assert (row["added"], row["enabled"]) == expected


def test_reference_loader_opens_only_requested_text(tmp_path, monkeypatch):
    import zipfile
    from ai2apps.skills.library import MAX_REFERENCE_BYTES, SkillLibrary

    library = SkillLibrary(tmp_path)
    item = install_skill(library, "owner", "Reference check", files={
        "references/a.txt": b"A-318",
        "references/b.txt": b"B-451",
        "references/big.txt": b"x" * (MAX_REFERENCE_BYTES + 1),
        "references/binary.txt": b"\0\0",
        "references/codec.bin": b"BIN",
        "scripts/tool.py": b"print('not run')",
    })
    library.set_bot_skill("owner", "bot", item["id"], True)
    pin, = library.bot_snapshot("owner", "bot")
    assert pin["references"] == ["references/a.txt", "references/b.txt", "references/big.txt", "references/binary.txt"]
    original = zipfile.ZipFile.open
    opened = []

    def trace(archive, name, *args, **kwargs):
        opened.append(name.filename if isinstance(name, zipfile.ZipInfo) else name)
        return original(archive, name, *args, **kwargs)

    monkeypatch.setattr(zipfile.ZipFile, "open", trace)
    assert library.bot_content("owner", "bot", pin, read=False) is None
    assert not opened
    for invalid in ("../README.md", "/references/a.txt", "references/../SKILL.md",
                    "references/missing.md", "references/codec.bin", "scripts/tool.py"):
        with pytest.raises(ValueError):
            library.bot_content("owner", "bot", pin, paths=[invalid])
    assert not opened
    _, refs = library.bot_content("owner", "bot", pin, paths=[
        "references/a.txt", "references/big.txt", "references/binary.txt",
    ])
    assert refs[0] == {"path": "references/a.txt", "text": "A-318"}
    assert all("unavailable" in ref for ref in refs[1:])
    assert opened == ["format-check/SKILL.md", "format-check/references/a.txt",
                      "format-check/references/binary.txt"]
