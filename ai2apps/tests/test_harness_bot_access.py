"""Harness App admission with a deterministic model and a real local process."""
import json
import shutil

import pytest

from ai2apps.messager.bots import REGISTRATION
from ai2apps.processes import TestSandboxAdapter as ProcessTestSandboxAdapter
from ai2apps.processes.harness_app import APP_ID, TOOLS
from test_app_chat_durable import P, bind_identity, response
from test_app_interactions import runtime, wait
from test_bot_dialogue import job_wait


@pytest.mark.asyncio
async def test_harness_disk_query_requires_app_access_and_command_confirmation(runtime):
    if not shutil.which("df"):
        pytest.skip("requires df")
    runtime.processes.sandbox = ProcessTestSandboxAdapter()
    bot = runtime.messager_bots.create("local", "Harness acceptance", "Check actual disk space")
    bot_id = bot["id"]
    access = runtime.messager_bot_app_access
    catalog = access.catalog("local", bot_id)
    entry = next(row for row in catalog["items"] if row["app_id"] == APP_ID)
    assert (entry["name"], entry["available"], entry["selected"]) == ("Harness", True, False)
    assert {p.capability for p in access.providers() if p.app_id == APP_ID} == set(TOOLS)

    async def model(request):
        if "Decide quickly" in request["messages"][0]["content"]:
            return response(text=json.dumps({"kind": "task", "title": "Disk space", "text": "Queued"}))
        results = [json.loads(m["content"]) for m in request["messages"] if m["role"] == "tool"]
        if logs := next((x for x in results if x.get("capability") == "process.logs"), None):
            return response(text="".join(row["content"] for row in logs["items"] if row["stream"] == "stdout"))
        if finished := next((x for x in results if x.get("capability") == "process.wait"), None):
            assert finished["exit_code"] == 0
            return response("process.logs", {"process_id": finished["id"]})
        if started := next((x for x in results if x.get("capability") == "process.start"), None):
            assert started["network_enabled"] is False
            return response("process.wait", {"process_id": started["id"], "timeout_ms": 3000})
        return response("process.start", {"argv": ["df", "-h", "."]})

    runtime.agent_runtime.bind_model_provider(model)
    sid = runtime.app_chat.open(P(), REGISTRATION, {"bot_id": bot_id}, {})
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        parent = runtime.messager_dialogue.submit(
            P(), bot_id, sid, "harness-df", "我当前还剩多少磁盘空间？", "fixture", [],
        )
        await wait(runtime, parent, "completed")
        job = await job_wait(runtime, parent, "running")
        worker = job["worker_run"]
        await wait(runtime, worker, "waiting_capability")
        approval = next(item for item in runtime.agents.list_interactions(worker)
                        if item.status.value == "pending")
        review = access.request("local", bot_id, worker, approval.id)
        assert review["app"]["app_id"] == APP_ID
        assert review["task_tree"] and review["special"] and not review["access_granted"]
        assert access.allow("local", bot_id, worker, approval.id, review["request_hash"]) == {
            "continued": False, "requires_confirmation": True,
        }
        runtime.agents.respond_interaction(worker, approval.id, response_id="accept-df",
                                           response={"decision": "approve", "scope": "once"})
        runtime.agent_runtime.wake()
        await job_wait(runtime, parent, "completed")
        assert "Filesystem" in runtime.agents.get_run(worker).output["content"]
        assert not next(row for row in access.catalog("local", bot_id)["items"]
                        if row["app_id"] == APP_ID)["selected"]
    finally:
        await runtime.stop_background_tasks()
