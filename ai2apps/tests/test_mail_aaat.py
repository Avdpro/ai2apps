import asyncio
import json
from email import policy
from email.parser import BytesParser

import httpx
import pytest
from fastapi import FastAPI

from ai2apps.api.router import create_ai2apps_router
from ai2apps.chat import ChatRepository
from ai2apps.config import PlatformConfig
from ai2apps.identity import IdentityRepository, OrganizationType
from ai2apps.mail import imap, service
from ai2apps.platform_runtime import PlatformRuntime
from ai2apps.secrets.backends import MemorySecretBackend


@pytest.mark.asyncio
async def test_general_agent_search_read_draft_and_mail_review(tmp_path, monkeypatch):
    monkeypatch.setattr(imap, "verify", lambda *args: None)
    monkeypatch.setattr(service, "probe_smtp", lambda *args: "authenticated")
    monkeypatch.setattr(service, "deliver_smtp", lambda *args: pytest.fail("AaAT must not send"))
    monkeypatch.setattr(imap, "snapshot", lambda *args: (
        35, [(10, "Meeting plans", "sender@example.test", "2026-11-13T10:00:00+00:00", 0, 0)], False,
    ))
    monkeypatch.setattr(imap, "read_preview", lambda *args: {"text": "Can you meet Tuesday?", "preview_status": "complete"})
    original = BytesParser(policy=policy.default).parsebytes(
        b"From: sender@example.test\r\nReply-To: organizer@example.test\r\nSubject: Meeting plans\r\n\r\n"
    )
    monkeypatch.setattr(imap, "reply_headers", lambda *args: original)
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    runtime.mail.secrets.backend = MemorySecretBackend()
    identities = IdentityRepository(runtime.database)
    identities.bind_installation(installation_id="mail-fixture", cloud_device_id="test-device",
                                organization_id="test-org", organization_type=OrganizationType.HOUSEHOLD,
                                core_user_id="alice", billing_account_id="billing", access_epoch=1)
    principal = identities.principal_for("alice")
    app = FastAPI()
    app.include_router(create_ai2apps_router(runtime_provider=lambda: runtime, principal_provider=lambda: principal))
    try:
        account = runtime.mail.connect(principal, {
            "provider": "imap", "address": "mail@example.test", "password": "fixture",
            "username": "", "display_name": "", "host": "imap.example.test", "port": 993,
            "smtp_host": "", "smtp_port": 587, "smtp_username": "", "smtp_tls": "starttls",
        })
        runtime.mail.sync(principal, account["id"])
        thread, _ = ChatRepository(runtime.database, runtime.events, principal=principal).create_thread(title="Mail review")
        results = {}
        def model(request):
            tools = [item["function"]["name"] for item in request["tools"]]
            assert not any(name.startswith("mail__send") for name in tools)
            for message in request["messages"]:
                if message["role"] != "tool":
                    continue
                value = json.loads(message["content"])
                if isinstance(value, dict) and "items" in value:
                    results["search"] = value
                elif isinstance(value, dict) and "text" in value and "message_ref" in value:
                    results["read"] = value
                elif isinstance(value, dict) and value.get("status") == "draft":
                    results["draft"] = value
                elif isinstance(value, dict) and value.get("status") == "completed" and "draft_id" in value.get("result", {}):
                    assert value["result"]["sent"] is False
                    return {"choices": [{"message": {"role": "assistant", "content": "Draft confirmed."}, "finish_reason": "stop"}]}
            if "draft" in results:
                name, args = "app.interact", {"request_id": "review-1", "capability": "mail.review_draft",
                                               "parameters": {"draft_id": results["draft"]["draft_id"]}}
            elif "read" in results:
                name, args = "mail.draft_reply", {"message_ref": results["read"]["message_ref"], "body": "Tuesday works."}
            elif "search" in results:
                name, args = "mail.read_message", {"message_ref": results["search"]["items"][0]["message_ref"]}
            else:
                name, args = "mail.search", {"query": "Meeting"}
            alias = next((tool for tool in tools if tool.startswith(name.replace(".", "__") + "_")), None)
            if alias is None:
                args = {"capability": name}
                alias = next(tool for tool in tools if tool.startswith("app__describe_"))
            return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [{
                "id": f"fixture-{len(request['messages'])}", "type": "function",
                "function": {"name": alias, "arguments": json.dumps(args)},
            }]}, "finish_reason": "tool_calls"}]}

        runtime.agent_runtime.bind_model_provider(model)
        run, _ = runtime.agents.create_run(
            session_id=thread.session.id, agent_key="ai2apps.general-agent",
            input={"model": "test", "prompt": "Find my meeting email, draft a reply accepting Tuesday and let me review it in Mail."},
        )
        await runtime.agent_runtime.start()

        async def wait(expected):
            for _ in range(500):
                state = runtime.agents.get_run(run.id)
                if state.status.value == expected:
                    return state
                if state.status.value in {"completed", "failed", "cancelled"}:
                    pytest.fail(f"{state.status}: {state.error}; {[(s.tool_name, s.output, s.error) for s in runtime.agents.list_steps(run.id)]}")
                await asyncio.sleep(.02)
            pytest.fail(f"Run did not reach {expected}: {state.status}; "
                        f"{[(s.tool_name, s.status, s.error) for s in runtime.agents.list_steps(run.id)]}; "
                        f"{[(i.kind, i.request) for i in runtime.agents.list_interactions(run.id)]}")

        await wait("waiting_input")
        interaction, = runtime.agents.list_interactions(run.id)
        assert interaction.request["capability"] == "mail.review_draft"
        base = f"/v1/platform/mail/reviews/{run.id}/{interaction.id}"
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            handoff = await client.get(f"/v1/platform/agent-runs/{run.id}/interactions/{interaction.id}/handoff")
            assert handoff.json()["target"]["app_id"] == "ai2apps.mail"
            draft = (await client.get(base)).json()
            assert draft["recipients"] == ["organizer@example.test"] and draft["body"] == "Tuesday works."
            edited = {key: draft[key] for key in ("account_id", "recipients", "subject", "reply", "attachments", "revision")}
            saved = await client.put(f"/v1/platform/mail/drafts/{draft['id']}", json={**edited, "body": "Tuesday at 10 works."})
            assert saved.json()["revision"] == 2
            assert (await client.post(base, json={"decision": "confirmed", "revision": 1})).status_code == 409
            for _ in range(2):
                receipt = await client.post(base, json={"decision": "confirmed", "revision": 2})
                assert receipt.json() == {"status": "completed", "result": {"draft_id": draft["id"], "revision": 2, "sent": False}}
        await wait("completed")
        stored = runtime.mail.drafts.get(principal, draft["id"])
        assert stored["status"] == "draft" and stored["body"] == "Tuesday at 10 works."
        assert not runtime.mail.messages(principal, None, 10, 0)["items"][0]["seen"]
    finally:
        await runtime.agent_runtime.stop()
        runtime.stop()
