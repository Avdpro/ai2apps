import asyncio
import json

import pytest
from test_app_interactions import runtime  # noqa: F401
from test_comapps import WeixinFixture

from ai2apps.comapps.bot_channel import BotChannel
from ai2apps.identity import IdentityRepository, OrganizationType
from ai2apps.messager.conversation_profile import settings
from ai2apps.secrets.backends import MemorySecretBackend
from ai2apps.storage.repositories import MessageRepository


async def test_wechat_bot_menu_pages_and_switches_only_owned_conversation_bots(
    runtime,  # noqa: F811
    monkeypatch,
):
    from ai2apps.comapps.command_menu import BOT_COMMAND
    from ai2apps.identity import RequestPrincipal
    from ai2apps.messager import bot_types
    from ai2apps.messager.dialogue import CHAT

    principal = RequestPrincipal.legacy_local()
    directory = runtime.messager_bots
    actor = principal.actor_user_id
    default = directory.ensure_default(actor)
    asc = directory.create(actor, "ASC 快捷入口", "Fixture")["id"]
    with runtime.database.transaction(write=True) as db:
        db.execute("DELETE FROM messager_bot_definitions WHERE bot_id=?", (asc,))
        bot_types.save(
            db, actor, asc, {"execution_mode": "app_shortcut", "config": {"state": {}}}
        )
    bots = [
        directory.create(actor, f"我的助手 {index:02d}", "Fixture")["id"]
        for index in range(21)
    ]
    directory.create("other", "其他账号的助手", "Fixture")
    monkeypatch.setattr(BotChannel, "_principal", lambda *args: principal)

    submitted = []

    def submit(owner, bot, sid, key, text, model, attachments, *, poke):
        assert owner == principal
        submitted.append((bot, sid, text, model, attachments, poke))
        return "fixture-run"

    monkeypatch.setattr(runtime.messager_dialogue, "submit", submit)
    provider = WeixinFixture()
    service = runtime.comapps
    service.ilink = provider
    service.vault = MemorySecretBackend()
    channel = BotChannel(runtime, service)
    service.bot_channel = channel
    login = service.invoke(principal, "ilink-start")
    service.invoke(principal, "ilink-poll", login_id=login["login_id"])
    service.invoke(principal, "ilink-auto-enable", instance_id="fixture-app")
    with runtime.database.transaction() as db:
        row = dict(db.execute("SELECT * FROM comapps_bot_channels").fetchone())

    async def ask(text, mid):
        config = channel._config(row)
        config["pending"].append({"mid": mid, "text": text, "token": "menu-context"})
        config["access_menu_number"] = 2
        config["staged_media"] = {
            "ids": ["fixture-attachment"],
            "until": 10**12,
            "session": "other-session",
        }
        channel._save(row, config)
        await channel._turn(row)
        reply = provider.sent[-1]
        assert reply["context_token"] == "menu-context"
        assert reply["to_user_id"] == "bound-user"
        return reply["item_list"][0]["text_item"]["text"]

    first = await ask("b", "1")
    assert first.startswith("[🤖AI2Apps]: 我的 Bot")
    assert "1｜AI2Apps（当前对话，默认）" in first
    assert "bp2" in first
    assert "其他账号的助手" not in first and "ASC 快捷入口" not in first
    assert "尚未显示" in await ask("b21", "2")
    second = await ask("bp2", "3")
    assert "21｜我的助手 19" in second
    assert "22｜我的助手 20" in second
    assert "其他账号的助手" not in second
    assert await ask("bp2", "3") == second
    assert len(provider.sent) == 3
    assert "当前对话 Bot：我的助手 10" in await ask("b12", "4")
    assert "12｜我的助手 10（当前对话）" in await ask("b", "5")
    directory.set_order(actor, [bots[10], default])
    assert "列表已变化" in await ask("b1", "6")
    assert channel._config(row)["staged_media"]["ids"] == ["fixture-attachment"]
    assert BOT_COMMAND.fullmatch("B2") is None
    assert not submitted

    settings(runtime, actor, bots[10], model_id="fixture-model", expected_revision=0)
    channel = BotChannel(runtime, service)
    config = channel._config(row)
    config["pending"].append({"mid": "7", "text": "继续聊天", "token": "menu-context"})
    channel._save(row, config)
    await channel._turn(row)
    session = runtime.app_chat.open(principal, CHAT, {"bot_id": bots[10]}, {})
    assert submitted == [(bots[10], session, "继续聊天", "fixture-model", [], False)]
    config = channel._config(row)
    config["staged_media"]["session"] = session
    config["pending"] = [{"mid": "8", "text": "p", "token": "poke-context"}]
    channel._save(row, config)
    await channel._turn(row)
    assert submitted[-1] == (bots[10], session, "👋 Poke", "fixture-model", [], True)
    assert channel._config(row)["staged_media"]["ids"] == ["fixture-attachment"]


async def test_wechat_selects_flash_bot_and_returns_its_workflow_result(
    runtime,  # noqa: F811
    monkeypatch,
):
    from test_flash_bots import prepare

    from ai2apps.identity import RequestPrincipal

    principal = RequestPrincipal.legacy_local()
    bot, session = prepare(runtime)
    monkeypatch.setattr(BotChannel, "_principal", lambda *args: principal)
    provider = WeixinFixture()
    service = runtime.comapps
    service.ilink = provider
    service.vault = MemorySecretBackend()
    channel = BotChannel(runtime, service)
    service.bot_channel = channel
    login = service.invoke(principal, "ilink-start")
    service.invoke(principal, "ilink-poll", login_id=login["login_id"])
    service.invoke(principal, "ilink-auto-enable", instance_id="fixture-app")
    with runtime.database.transaction() as db:
        row = dict(db.execute("SELECT * FROM comapps_bot_channels").fetchone())

    async def send(message, mid):
        config = channel._config(row)
        config["pending"].append(
            {"mid": mid, "text": message, "token": f"context-{mid}"}
        )
        channel._save(row, config)
        await channel._turn(row)
        return provider.sent[-1]["item_list"][0]["text_item"]["text"]

    await runtime.agent_runtime.start()
    try:
        menu = await send("b", "1")
        number = next(
            line.split("｜")[0]
            for line in menu.splitlines()
            if f"｜{bot['name']}" in line
        )
        assert bot["name"] in await send(f"b{number}", "2")
        assert "工作流输入" in await send("p", "3")
        assert "不符合当前工作流要求" in await send("怎么用", "5")
        assert not channel._config(row).get("flash_jobs")
        assert "处理完成后会回复" in await send("3+3", "4")
        assert len(channel._config(row)["flash_jobs"]) == 1
        ref = next(iter(channel._config(row)["flash_jobs"]))
        assert runtime.messager_flash.row(ref)["session_id"] == session
        default = runtime.messager_bots.ensure_default("local")
        default_number = next(
            key
            for key, bot_id in channel._config(row)["bot_menu_choices"].items()
            if bot_id == default
        )
        await send(f"b{default_number}", "6")
        assert channel._config(row)["conversation_bot"] == default
        for _ in range(200):
            if await channel._notice(row):
                break
            await asyncio.sleep(0.02)
        assert provider.sent[-1]["context_token"] == "context-4"
        assert (
            provider.sent[-1]["item_list"][0]["text_item"]["text"]
            == "[🤖AI2Apps]: 3+3 = 6"
        )
        assert not channel._config(row)["flash_jobs"]
        await send("3+3", "4")
        assert len(runtime.todo.store.snapshot("local")["runs"]) == 1
    finally:
        await runtime.todo.shutdown()
        await runtime.system_tasks.shutdown()
        await runtime.agent_runtime.stop()


@pytest.mark.parametrize(
    ("timeout", "poke"), [(False, False), (True, False), (False, True)]
)
async def test_bound_wechat_text_runs_real_default_bot_once(
    runtime,  # noqa: F811
    monkeypatch,
    timeout,
    poke,
):
    identities = IdentityRepository(runtime.database)
    identities.bind_installation(
        installation_id="local",
        cloud_device_id="fixture-device",
        organization_id="local",
        organization_type=OrganizationType.HOUSEHOLD,
        core_user_id="local",
        billing_account_id="local",
        access_epoch=1,
    )
    principal = identities.principal_for("local")
    provider = WeixinFixture()
    provider.timeout = timeout
    if poke:
        original_request = provider.request

        def request(operation, **params):
            result = original_request(operation, **params)
            if operation == "getupdates":
                result["msgs"][0]["item_list"] = [
                    {"type": 1, "text_item": {"text": "p"}}
                ]
            return result

        provider.request = request
    service = runtime.comapps
    service.ilink = provider
    service.vault = MemorySecretBackend()
    bot = runtime.messager_bots.ensure_default("local")
    settings(runtime, "local", bot, model_id="fixture-model", expected_revision=0)
    # Fixture substitutes only package access, WeChat, and model output.
    monkeypatch.setattr(BotChannel, "_principal", lambda *args: principal)
    calls = []

    async def model(request):
        calls.append(request["messages"][-1]["content"])
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(
                            {"kind": "reply", "text": "Bot fixture reply"}
                        ),
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"total_tokens": 10},
        }

    runtime.agent_runtime.bind_model_provider(model)
    login = service.invoke(principal, "ilink-start")
    service.invoke(principal, "ilink-poll", login_id=login["login_id"])
    await runtime.start_background_tasks()
    try:
        channel = BotChannel(runtime, service)
        service.bot_channel = channel
        service.invoke(principal, "ilink-auto-enable", instance_id="fixture-app")
        with runtime.database.transaction() as db:
            row = dict(db.execute("SELECT * FROM comapps_bot_channels").fetchone())
        # Drive the worker through its real phases with deterministic external I/O.
        await channel._poll(row, channel._config(row))
        await channel._turn(row)
        for _ in range(300):
            rid = channel._config(row)["pending"][0]["run_id"]
            run = runtime.agents.get_run(rid)
            assert run.status.value != "failed", run.error
            if run.status.value == "completed":
                break
            await asyncio.sleep(0.01)
        assert run.status.value == "completed"
        await channel._turn(row)
        assert len(provider.sent) == 1
        assert provider.sent[0]["to_user_id"] == "bound-user"
        assert provider.sent[0]["context_token"] == "private-context-token"
        assert (
            provider.sent[0]["item_list"][0]["text_item"]["text"]
            == "[🤖AI2Apps]: Bot fixture reply"
        )
        assert run.input["owner_context"].get("activation") == (
            "poke" if poke else None
        )
        assert len(calls) == 1
        if not poke:
            assert calls == ["Hello from WeChat"]
        assert MessageRepository(runtime.database).get_by_idempotency_key(
            run.session_id, f"agent-run:{rid}:assistant"
        )
        assert service.invoke(principal, "state")["ilink_delivery"] == (
            "unknown" if timeout else "submitted"
        )
        # An old item replayed after the bounded seen window still cannot resend.
        config = channel._config(row)
        config["seen"] = []
        channel._save(row, config)
        await channel._poll(row, config)
        await channel._turn(row)
        assert len(provider.sent) == 1
        service.invoke(principal, "ilink-auto-disable")
        assert channel._config(row) is None
    finally:
        await runtime.stop_background_tasks()


@pytest.mark.parametrize(
    "decision", ["allow", "deny", "changed", "special", "png", "jpeg", "pdf"]
)
async def test_wechat_menu_returns_to_real_bot_access(
    runtime,  # noqa: F811
    monkeypatch,
    decision,
    tmp_path,
):
    import base64
    import hashlib
    import io
    from dataclasses import replace
    from types import SimpleNamespace

    from PIL import Image
    from pypdf import PdfWriter
    from pypdf.generic import (
        DecodedStreamObject,
        DictionaryObject,
        NameObject,
    )
    from test_app_chat_durable import response
    from test_bot_capability_discovery import setup

    from ai2apps.comapps import media

    identities = IdentityRepository(runtime.database)
    identities.bind_installation(
        installation_id="local",
        cloud_device_id="fixture-device",
        organization_id="local",
        organization_type=OrganizationType.HOUSEHOLD,
        core_user_id="local",
        billing_account_id="local",
        access_epoch=1,
    )
    principal = identities.principal_for("local")
    bot, _, calls, tool = setup(runtime)
    monkeypatch.setattr(
        runtime.messager_bots, "ensure_default", lambda actor: bot["id"]
    )
    if decision == "special":
        runtime.app_capability_router.providers[tool.id] = replace(
            tool, access_policy="confirm"
        )
    if decision in {"png", "jpeg", "pdf"}:
        suffix = decision
        decision = "allow"
        data = io.BytesIO()
        mime = "application/pdf" if suffix == "pdf" else "image/" + suffix
        file = tmp_path / ("fixture." + suffix)
        if suffix == "pdf":
            writer = PdfWriter()
            page = writer.add_blank_page(width=200, height=200)
            page[NameObject("/Resources")] = DictionaryObject(
                {
                    NameObject("/Font"): DictionaryObject(
                        {
                            NameObject("/F1"): DictionaryObject(
                                {
                                    NameObject("/Type"): NameObject("/Font"),
                                    NameObject("/Subtype"): NameObject("/Type1"),
                                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                                }
                            )
                        }
                    )
                }
            )
            contents = DecodedStreamObject()
            contents.set_data(b"BT /F1 12 Tf 20 100 Td (WeChat PDF fixture) Tj ET")
            page.replace_contents(contents)
            writer.write(data)
        elif suffix == "png":
            Image.effect_noise((256, 256), 32).convert("RGB").save(data, format="PNG")
        else:
            Image.new("RGB", (8, 8), "green").save(data, format=suffix.upper())
        file.write_bytes(data.getvalue())
        item_type = 4 if suffix == "pdf" else 2
        key = bytes(range(16))
        cdn = {"incoming": media.crypt(file.read_bytes(), key, encrypt=True)}
        ticket = {}

        class CDNResponse(io.BytesIO):
            status = 200
            headers = {"x-encrypted-param": "outgoing"}

        def cdn_open(request, *, timeout):
            assert request.host == "novac2c.cdn.weixin.qq.com"
            assert "Authorization" not in request.headers
            if request.get_method() == "POST":
                assert timeout == 60
                assert len(request.data) == ticket["filesize"]
                original = media.crypt(
                    request.data, bytes.fromhex(ticket["aeskey"]), encrypt=False
                )
                assert ticket["rawsize"] == len(original)
                assert ticket["rawfilemd5"] == hashlib.md5(
                    original, usedforsecurity=False
                ).hexdigest()
                if suffix == "png" and not cdn.get("attempted"):
                    cdn["attempted"] = True
                    raise TimeoutError
                cdn["outgoing"] = request.data
                return CDNResponse()
            ref = request.full_url.rsplit("=", 1)[-1]
            return CDNResponse(cdn[ref])

        monkeypatch.setattr(
            media, "build_opener", lambda _: SimpleNamespace(open=cdn_open)
        )

        async def handler(args, ctx):
            calls.append((args, ctx.session_id))
            asset = runtime.workspace.import_artifact(
                ctx.session_id, file, media_type=mime
            )
            return {
                "created": "fixture-output",
                "artifact": {
                    "download_url": f"/v1/platform/sessions/{ctx.session_id}/artifacts/{asset.id}/download",
                },
            }

        runtime.app_capability_router.providers[tool.id] = replace(
            tool, handler=handler
        )
    else:
        file = None
    settings(runtime, "local", bot["id"], model_id="fixture-model", expected_revision=0)
    monkeypatch.setattr(BotChannel, "_principal", lambda *args: principal)
    provider = WeixinFixture()
    if file:
        original = provider.request

        def request(operation, **params):
            if operation == "getuploadurl":
                assert params["token"] == "private-bot-token"
                ticket.update(params["data"])
                assert ticket["to_user_id"] == "bound-user"
                assert ticket["media_type"] == (3 if suffix == "pdf" else 1)
                if suffix == "png":
                    return {
                        "upload_full_url": "https://untrusted.example/c2c/upload",
                        "upload_param": "ticket",
                    }
                return {"upload_param": "ticket"}
            result = original(operation, **params)
            if operation == "getupdates":
                body = {
                    "file_name": file.name,
                    "media": {
                        "encrypt_query_param": "incoming",
                        "aes_key": base64.b64encode(key).decode(),
                    },
                }
                result["msgs"].insert(
                    0,
                    {
                        **result["msgs"][0],
                        "message_id": "987",
                        "context_token": "attachment-context",
                        "item_list": [
                            {
                                "type": item_type,
                                "file_item" if suffix == "pdf" else "image_item": body,
                            }
                        ],
                    },
                )
            return result

        provider.request = request
    service = runtime.comapps
    service.ilink = provider
    service.vault = MemorySecretBackend()
    prompts = []
    model_inputs = []

    async def model(request):
        prompts.append(request["messages"][-1]["content"])
        model_inputs.extend(
            message["content"]
            for message in request["messages"]
            if message.get("role") == "user"
        )
        if "Decide quickly without Tools" in request["messages"][0]["content"]:
            return response(
                text=json.dumps(
                    {"kind": "task", "text": "Queued", "title": "Fixture task"}
                )
            )
        results = [
            json.loads(m["content"])
            for m in request["messages"]
            if m.get("role") == "tool"
        ]
        if any(x.get("created") for x in results):
            return response(text="Fixture task completed")
        if not any(x.get("providers") for x in results):
            return response("app.describe", {"capability": tool.capability})
        return response(tool.capability, {"prompt": "fixture"})

    def sent():
        return [
            item["text_item"]["text"]
            for x in provider.sent
            for item in x["item_list"]
            if item["type"] == 1
        ]

    runtime.agent_runtime.bind_model_provider(model)
    login = service.invoke(principal, "ilink-start")
    service.invoke(principal, "ilink-poll", login_id=login["login_id"])
    await runtime.start_background_tasks()
    try:
        channel = BotChannel(runtime, service)
        service.bot_channel = channel
        service.invoke(principal, "ilink-auto-enable", instance_id="fixture-app")
        with runtime.database.transaction() as db:
            row = dict(db.execute("SELECT * FROM comapps_bot_channels").fetchone())

        async def until(check):
            for _ in range(300):
                if check():
                    return
                await asyncio.sleep(0.02)
            pytest.fail("Bot did not reach expected state")

        await channel._poll(row, channel._config(row))
        if file:
            await channel._turn(row)
            assert "已收到 1 个附件" in sent()[-1]
            assert len(channel._config(row)["staged_media"]["ids"]) == 1
        await channel._turn(row)
        source = channel._config(row)["pending"][0]["run_id"]
        await until(lambda: runtime.agents.get_run(source).status.value == "completed")
        await channel._turn(row)
        jobs = channel._config(row)["access_jobs"]
        assert len(jobs) == 1
        ref = next(iter(jobs))

        def worker():
            return runtime.messager_dialogue.row(ref)["worker_run"]

        await until(
            lambda: (
                worker()
                and runtime.agents.get_run(worker()).status.value
                == "waiting_capability"
            )
        )
        assert await channel._notice(row)
        assert not calls
        if decision == "special":
            assert "请在 AI2Apps" in sent()[-1] and "1｜" not in sent()[-1]
            assert not channel._config(row)["access_jobs"][ref]["menu"]
            return
        assert "1｜允许此 Bot 持续访问" in sent()[-1] and "2｜拒绝" in sent()[-1]
        menu = channel._config(row)["access_jobs"][ref]["menu"]
        assert menu["offered_at"]

        async def choose(text, mid, stamp):
            config = channel._config(row)
            config["pending"].append(
                {
                    "mid": mid,
                    "text": text,
                    "token": "choice-context",
                    "created_ms": stamp,
                }
            )
            channel._save(row, config)
            await channel._turn(row)

        await choose("1", "40", menu["offered_at"] - 1)
        assert "失效" in sent()[-1] and not calls
        await choose("3", "41", menu["offered_at"] + 1)
        assert "权限详情" in sent()[-1] and not calls
        if decision == "allow":
            other = runtime.messager_bots.create("local", "另一个 Bot", "Fixture")
            number = next(
                index
                for index, entry in enumerate(runtime.messager_bots.list("local"), 1)
                if entry["id"] == other["id"]
            )
            await choose("b", "47", menu["offered_at"] + 1)
            await choose(f"b{number}", "48", menu["offered_at"] + 1)
            assert channel._config(row)["conversation_bot"] == other["id"]
        if decision == "changed":
            access = runtime.messager_bot_app_access
            with runtime.database.transaction(write=True) as db:
                access.grant_targets("local", bot["id"], {"ai2apps.knowledge"}, db)
            await choose("A1", "43", menu["offered_at"] + 2)
            assert "失效" in sent()[-1] and not calls
            assert await channel._notice(row)
            assert "B1｜" in sent()[-1]
            menu = channel._config(row)["access_jobs"][ref]["menu"]
            await choose("1", "44", menu["offered_at"] + 1)
            assert "失效" in sent()[-1] and not calls
        await choose(
            {"changed": "B1", "allow": "A1", "deny": "2"}[decision],
            "42",
            menu["offered_at"] + 2,
        )
        assert ("已批准" if decision != "deny" else "已拒绝") in sent()[-1]
        await until(
            lambda: (
                runtime.messager_dialogue.row(ref)["status"] in {"completed", "failed"}
            )
        )
        assert await channel._notice(row)
        if decision != "deny":
            assert "Fixture task completed" in sent()[-1] and len(calls) == 1
            if file:
                item = provider.sent[-1]["item_list"][0]
                assert item["type"] == item_type
                if suffix == "pdf":
                    assert item["file_item"]["file_name"] == file.name
                content, _, media_type = media.MediaTransport(provider).download(
                    media.inbound_ref(item)
                )
                if suffix == "png":
                    assert media_type == "image/jpeg"
                    assert len(content) < file.stat().st_size
                    with Image.open(io.BytesIO(content)) as compact:
                        assert compact.size == (256, 256)
                else:
                    assert (content, media_type) == (file.read_bytes(), mime)
                assert provider.sent[-1]["to_user_id"] == "bound-user"
                assert provider.sent[-1]["context_token"] == "private-context-token"
                if suffix == "pdf":
                    assert any(
                        "WeChat PDF fixture" in str(prompt) for prompt in model_inputs
                    )
                else:
                    assert any(
                        "data:image/jpeg;base64," in str(prompt)
                        for prompt in model_inputs
                    )
        else:
            assert "没有完成" in sent()[-1] and not calls
        assert not {"1", "2", "3", "A1", "B1"}.intersection(prompts)
        count = len(sent())
        await choose("A1", "42", menu["offered_at"] + 2)
        assert len(sent()) == count
    finally:
        await runtime.stop_background_tasks()
