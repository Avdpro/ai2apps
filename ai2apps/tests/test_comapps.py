import hashlib
import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_app_interactions import runtime  # noqa: F401

from ai2apps.api.comapps import create_comapps_router
from ai2apps.comapps.media import inbound_ref
from ai2apps.comapps.service import ComApps
from ai2apps.comapps.weixin import ConnectorError, trusted_base
from ai2apps.extensions.sandbox_document import inline_sandbox_assets
from ai2apps.secrets.backends import MemorySecretBackend

OWNER = SimpleNamespace(
    installation_id="local-a",
    actor_user_id="owner",
    authentication_type="cloud_session",
    client_scope="desktop",
    is_core=True,
)
OTHER = SimpleNamespace(**{**vars(OWNER), "actor_user_id": "other"})


def test_comapps_opens_and_lists_workers_while_connector_owns_claim():
    service = ComApps(MemorySecretBackend())
    scope = service.owner_scope(OWNER)
    config = {"path": "/fixture/wechat-agent", "profile": "default", "namespace": "fuel"}
    workspace = service.proxy_account_key(config)
    service._store(scope, "cli", config)
    service._store(scope, "proxy-workers-" + workspace, {"revision": 3, "entries": []})

    with service.claim(scope):
        assert service.invoke(OWNER, "state")["cli_workspace"] == workspace
        assert service.invoke(OWNER, "cli-workers") == {
            "workspace": workspace, "revision": 3, "entries": [],
        }
        with pytest.raises(ConnectorError, match="comapps_busy"):
            service.invoke(OWNER, "cli-disconnect")


@pytest.mark.parametrize(
    "url",
    [
        "https://example.org/c2c/download",
        "https://novac2c.cdn.weixin.qq.com@127.0.0.1/c2c/download",
        "https://novac2c.cdn.weixin.qq.com/c2c/upload",
    ],
)
def test_ilink_rejects_untrusted_media_download_url(url):
    with pytest.raises(ConnectorError, match="ilink_media_invalid_url"):
        inbound_ref({"type": 2, "image_item": {"media": {"full_url": url}}})


class WeixinFixture:
    def __init__(self):
        self.sent = []
        self.timeout = False
        self.observed_cursors = []

    def request(self, operation, **params):
        if operation == "get_bot_qrcode":
            return {
                "qrcode": "scan-ticket",
                "qrcode_img_content": "https://weixin.qq.com/scan",
            }
        if operation == "get_qrcode_status":
            assert params["query"]["qrcode"] == "scan-ticket"
            return {
                "status": "confirmed",
                "bot_token": "private-bot-token",
                "ilink_bot_id": "bound-bot",
                "ilink_user_id": "bound-user",
            }
        if operation == "getupdates":
            self.observed_cursors.append(params["data"]["get_updates_buf"])
            base = {
                "from_user_id": "bound-user",
                "to_user_id": "bound-bot",
                "message_type": 1,
                "message_id": "9223372036854775809",
                "context_token": "private-context-token",
                "item_list": [{"type": 1, "text_item": {"text": "Hello from WeChat"}}],
            }
            return {
                "get_updates_buf": "next-page",
                "msgs": [
                    base,
                    {**base, "from_user_id": "other", "message_id": 2},
                    {**base, "group_id": "group", "message_id": 3},
                ],
            }
        assert operation == "sendmessage"
        self.sent.append(params["data"]["msg"])
        if self.timeout:
            raise ConnectorError("ilink_request_failed")
        return {"ret": 0}


def test_ilink_binding_reply_and_cursor_survive_service_restart():
    vault, weixin = MemorySecretBackend(), WeixinFixture()
    svc = ComApps(vault, weixin)
    login = svc.invoke(OWNER, "ilink-start")
    assert login["qr"].startswith("data:image/png;base64,")
    with pytest.raises(ConnectorError, match="ilink_qr_expired"):
        svc.invoke(OTHER, "ilink-poll", login_id=login["login_id"])
    assert svc.invoke(OWNER, "ilink-poll", login_id=login["login_id"]) == {
        "status": "confirmed"
    }
    assert svc.invoke(OTHER, "state")["ilink_bound"] is False
    inbox = svc.invoke(OWNER, "ilink-inbox")
    assert inbox["message"] == "Hello from WeChat"
    assert "private-context-token" not in str(inbox)
    svc = ComApps(vault, weixin)
    assert svc.invoke(OWNER, "ilink-inbox") == inbox
    assert weixin.observed_cursors == ["", "next-page"]
    assert svc.invoke(
        OWNER, "ilink-reply", reply_id=inbox["reply_id"], text="Reply"
    ) == {"status": "submitted"}
    assert weixin.sent[0]["to_user_id"] == "bound-user"
    assert weixin.sent[0]["context_token"] == "private-context-token"
    activity = svc.invoke(OWNER, "state")["ilink_activity"]
    assert [(item["direction"], item["text"]) for item in activity] == [
        ("in", "Hello from WeChat"),
        ("out", "Reply"),
    ]
    assert activity[-1]["delivery"] == "submitted"
    assert svc.invoke(OTHER, "state")["ilink_activity"] == []
    assert svc.invoke(OWNER, "ilink-inbox")["reply_id"] is None
    with pytest.raises(ConnectorError, match="ilink_reply_unavailable"):
        svc.invoke(OWNER, "ilink-reply", reply_id=inbox["reply_id"], text="Duplicate")
    assert len(weixin.sent) == 1
    svc.invoke(OWNER, "ilink-logoff")
    state = ComApps(vault, weixin).invoke(OWNER, "state")
    assert state["ilink_signed_out"] and not state["ilink_bound"]
    assert not state["ilink_auto"] and state["ilink_activity"] == []
    svc.invoke(OWNER, "ilink-disconnect")
    assert not vault.values


def test_ilink_unknown_send_does_not_retry():
    weixin = WeixinFixture()
    svc = ComApps(MemorySecretBackend(), weixin)
    login = svc.invoke(OWNER, "ilink-start")
    svc.invoke(OWNER, "ilink-poll", login_id=login["login_id"])
    reply_id = svc.invoke(OWNER, "ilink-inbox")["reply_id"]
    weixin.timeout = True
    with pytest.raises(ConnectorError, match="ilink_send_unknown"):
        svc.invoke(OWNER, "ilink-reply", reply_id=reply_id, text="Reply")
    assert svc.invoke(OWNER, "ilink-inbox")["reply_id"] is None
    assert len(weixin.sent) == 1


@pytest.mark.parametrize(
    "url",
    [
        "http://ilinkai.weixin.qq.com",
        "https://evil.weixin.qq.com@example.org",
        "https://weixin.qq.com.evil.test",
        "https://ilinkai.weixin.qq.com:8000",
    ],
)
def test_ilink_refuses_untrusted_credential_destination(url):
    with pytest.raises(ConnectorError, match="ilink_untrusted_server"):
        trusted_base(url)


def test_local_cli_subprocess_pins_profile_pid_and_account(tmp_path):
    binary = tmp_path / "wechat-agent"
    account = tmp_path / "account"
    account.write_text("account-a")
    binary.write_text(r"""#!/bin/sh
set -eu
if [ "$*" = 'profile list' ]; then
  printf '%s\n' '{"ok":true,"result":{"profiles":[{"name":"default","display_name":"Fixture"}]}}'
elif [ "$*" = 'profile create group-helper' ]; then
  printf '%s\n' '{"ok":true,"result":{"name":"group-helper","created":true}}'
elif [ "$*" = '--profile group-helper --timeout 12 launch' ]; then
  printf '%s\n' '{"ok":true,"result":{"target_profile":{"name":"group-helper"},"started":true}}'
elif [ "$*" = '--profile default --timeout 12 queue identity' ]; then
  printf '{"ok":true,"result":{"profile":"default","pid":42,"namespace":"%s"}}\n' "$(cat account)"
elif [ "$*" = '--profile default --timeout 12 --pid 42 conversations' ]; then
  printf '%s\n' '{"ok":true,"result":{"target_profile":{"name":"default"},"conversations":[{"user_name":"alice","unread_count":1}],"truncated":true}}'
else
  exit 2
fi
""")
    binary.chmod(0o700)
    svc = ComApps(MemorySecretBackend())
    assert (
        svc.invoke(OWNER, "cli-configure", path=str(binary))["profiles"][0]["name"]
        == "default"
    )
    svc.invoke(OWNER, "cli-bind", profile="default")
    assert svc.invoke(OWNER, "cli-profile-create", profile="group-helper") == {
        "profile": "group-helper",
        "created": True,
    }
    assert svc.invoke(OWNER, "cli-profile-launch", profile="group-helper") == {
        "profile": "group-helper",
    }
    with pytest.raises(ConnectorError, match="wechat_cli_invalid_profile"):
        svc.invoke(OWNER, "cli-profile-create", profile="default")
    assert svc.invoke(OWNER, "state")["cli_profile"] == "default"
    assert svc.invoke(OWNER, "cli-conversations") == {
        "items": [{"user_name": "alice", "unread_count": 1}],
        "partial": True,
    }
    assert svc.invoke(OTHER, "state")["cli_path"] is None
    account.write_text("account-b")
    with pytest.raises(ConnectorError, match="wechat_cli_account_changed"):
        svc.invoke(OWNER, "cli-conversations")
    binary.write_text(binary.read_text() + "\n")
    with pytest.raises(ConnectorError, match="wechat_cli_changed_reconfigure"):
        svc.invoke(OWNER, "cli-profiles")


def test_shell_route_requires_local_owner_and_builtin_instance(tmp_path):
    service = ComApps(MemorySecretBackend())
    entry = {
        "app_key": "ai2apps.comapps",
        "renderer": "sandbox",
        "source": "builtin",
    }
    local = SimpleNamespace(
        comapps=service,
        extension_manager=SimpleNamespace(
            instance_entry=lambda *args, **kwargs: entry,
        ),
    )
    actor = OWNER
    local.local_session_token_from_cookies = lambda cookies: cookies.get(
        "ai2apps_local_session"
    )
    local.authorize_local_session = lambda token: actor if token == "fixture" else None
    app = FastAPI()
    app.include_router(create_comapps_router(lambda: local, lambda: actor))
    client = TestClient(
        app, base_url="http://127.0.0.1:8000", client=("127.0.0.1", 50000)
    )
    url = "/comapps/instances/comapps-instance/"
    headers = {
        "origin": "http://127.0.0.1:8000",
        "cookie": "ai2apps_local_session=fixture",
    }
    assert client.post(url + "state", json={}, headers=headers).status_code == 200
    assert (
        client.post(
            url + "state",
            json={},
            headers={**headers, "origin": "http://127.0.0.1:8001"},
        ).status_code
        == 403
    )
    assert client.post(url + "state", json={}).status_code == 403
    assert (
        client.post(
            url + "state", json={"text": "unexpected"}, headers=headers
        ).status_code
        == 422
    )
    assert client.post(url + "cli-exec", json={}, headers=headers).status_code == 422
    scope = hashlib.sha256(json.dumps(["local-a", "owner"]).encode()).hexdigest()
    cli_binding = {
        "path": "/fixture/wechat-agent",
        "profile": "default",
        "namespace": "account-a",
    }
    service._store(scope, "cli", cli_binding)
    worker_url = url + "cli-worker-save"
    workspace = client.post(url + "cli-workers", json={}, headers=headers).json()
    save = {
        "workspace": workspace["workspace"],
        "revision": 0,
        "worker": {
            "id": "a" * 32,
            "kind": "broadcast",
            "name": "Saved draft",
            "targets": [{"id": "example@chatroom", "label": "Example group"}],
            "content": [{"kind": "text", "value": "Hello"}],
            "interval": 15,
        },
    }
    assert client.post(worker_url, json=save, headers=headers).status_code == 200
    assert client.post(worker_url, json=save, headers=headers).status_code == 409
    service._store(scope, "cli", {**cli_binding, "namespace": "account-b"})
    assert (
        client.post(url + "cli-workers", json={}, headers=headers).json()["entries"]
        == []
    )
    assert client.post(worker_url, json=save, headers=headers).status_code == 409
    service._store(scope, "cli", cli_binding)
    restored = client.post(url + "cli-workers", json={}, headers=headers).json()
    assert restored["entries"][0]["targets"] == save["worker"]["targets"]
    actor = SimpleNamespace(**{**vars(OWNER), "is_core": False})
    assert client.post(url + "cli-workers", json={}, headers=headers).status_code == 403
    assert (
        client.post(
            url + "cli-configure", json={"path": str(tmp_path)}, headers=headers
        ).status_code
        == 403
    )
    actor = OWNER
    entry["app_key"] = "other.app"
    assert client.post(url + "state", json={}, headers=headers).status_code == 404
    entry.update(app_key="ai2apps.comapps", source="local")
    assert client.post(url + "state", json={}, headers=headers).status_code == 403


def test_cli_search_matches_beyond_the_browse_limit_and_combines_names(monkeypatch):
    from ai2apps.comapps import cli

    service = ComApps(MemorySecretBackend())
    config = {"profile": "default", "namespace": "fixture"}
    scope = hashlib.sha256(json.dumps(["local-a", "owner"]).encode()).hexdigest()
    service._store(scope, "cli", config)
    directories = {
        "conversations": [
            *({"user_name": f"recent_{i}"} for i in range(110)),
            {"user_name": "old_friend", "summary": "needle"},
        ],
        "friends": [
            {"user_name": "old_friend", "remark": "张三", "alias": "Needle"},
            {"user_name": "other", "nickname": "Needlework"},
        ],
        "groups": [{"user_name": "group@chatroom", "nickname": "Needle 群"}],
    }

    def run(_config, operation, profile, *, pid=None, full_directory=False):
        assert profile == "default"
        if operation == "identity":
            return {**config, "pid": 42}
        assert pid == 42 and full_directory
        return {operation: directories[operation], "truncated": operation == "groups"}

    monkeypatch.setattr(cli, "run", run)
    workspace = service.proxy_account_key(config)
    result = service.invoke(
        OWNER,
        "cli-search",
        query=" ＮＥＥＤＬＥ ",
        directory="all",
        workspace=workspace,
    )
    assert result == {
        "items": [
            {"id": "old_friend", "label": "张三"},
            {"id": "other", "label": "Needlework"},
            {"id": "group@chatroom", "label": "Needle 群"},
        ],
        "more": False,
        "incomplete": True,
    }
    result = service.invoke(
        OWNER,
        "cli-search",
        query="old_friend",
        directory="conversations",
        workspace=workspace,
    )
    assert result["items"] == [{"id": "old_friend", "label": "old_friend"}]


@pytest.mark.parametrize("legacy_source", [None, "local", "installed"])
def test_builtin_launch_and_legacy_instance_migration(runtime, legacy_source):  # noqa: F811
    from ai2apps.apps import ensure_system_apps
    from ai2apps.comapps import APP_ID
    from ai2apps.comapps.bot_channel import BotChannel
    from ai2apps.extensions import ExtensionError
    from ai2apps.identity import RequestPrincipal

    principal = RequestPrincipal.legacy_local()
    manager = runtime.extension_manager
    service = runtime.comapps
    service.ilink = WeixinFixture()
    service.vault = MemorySecretBackend()
    service.bot_channel = BotChannel(runtime, service)
    app, home, created = manager.launch_app(APP_ID, principal=principal)
    assert created
    if legacy_source:
        login = service.invoke(principal, "ilink-start")
        service.invoke(principal, "ilink-poll", login_id=login["login_id"])
        service.invoke(principal, "ilink-auto-enable", instance_id=app.id)
        with runtime.database.transaction(write=True) as db:
            db.execute(
                "UPDATE app_definitions SET source=?,manifest_json=? WHERE id=?",
                (
                    legacy_source,
                    '{"entry":{"kind":"sandbox","resource":"web/index.html"}}',
                    app.app_definition_id,
                ),
            )
        ensure_system_apps(runtime.database, runtime.events)
        ensure_system_apps(runtime.database, runtime.events)
        with runtime.database.transaction() as db:
            assert (
                db.execute("SELECT instance_id FROM comapps_bot_channels").fetchone()[0]
                == app.id
            )
        state = service.invoke(principal, "state")
        assert state["ilink_bound"] and state["ilink_auto"]

    launched, restored_home, created = manager.launch_app(APP_ID, principal=principal)
    assert not created
    assert (launched.id, restored_home.id) == (app.id, home.id)
    entry = manager.instance_entry(app.id, principal=principal)
    assert entry["source"] == "builtin"
    assert entry["renderer"] == "sandbox"
    assert entry["resource"] == "comapps/index.html"
    listed = [
        item
        for item in manager.list_apps(principal=principal, locale="zh")
        if item["app_key"] == APP_ID
    ]
    assert len(listed) == 1
    assert listed[0]["display_name"] == "传信"
    assert listed[0]["navigation"]["icon"] == "comapps"
    path = manager.resolve_app_resource(app.id, entry["resource"], principal=principal)
    html = inline_sandbox_assets(
        path.read_text(), entry["resource"], lambda _: pytest.fail("Unexpected asset")
    )
    assert "ai2apps.comapps.request" in html
    assert path.with_name("icon.svg").is_file()
    with pytest.raises(ExtensionError, match="System Apps cannot be replaced"):
        manager._require_package_app_key(APP_ID)


@pytest.mark.parametrize(
    ("variant", "format"), [("thumbnail", "jpeg"), ("large", "png")]
)
def test_cli_image_work_logs_exact_variant_without_sending(
    monkeypatch, variant, format
):
    from io import BytesIO

    from PIL import Image

    from ai2apps.comapps import cli

    service = ComApps(MemorySecretBackend())
    config = {"profile": "default", "namespace": "fixture"}
    scope = hashlib.sha256(json.dumps(["local-a", "owner"]).encode()).hexdigest()
    service._store(scope, "cli", config)
    workspace = service.proxy_account_key(config)
    work_id = "b" * 32
    worker_id = "a" * 32
    service.invoke(
        OWNER,
        "cli-worker-save",
        workspace=workspace,
        revision=0,
        worker={
            "kind": "monitor",
            "source": "session",
            "id": worker_id,
            "name": "Fixture",
            "target": {"id": "wxid_fixture", "label": "Fixture"},
            "works": [{"id": work_id, "trigger": "image"}],
        },
    )
    image = BytesIO()
    Image.new("RGB", (32, 40), "blue").save(image, format.upper())
    content = image.getvalue()
    identity = {
        "database": "message_0.db",
        "local_id": 82,
        "server_id": "9007199254740993",
    }
    paths = []
    calls = []

    def run(_config, operation, profile, **kwargs):
        calls.append(operation)
        assert profile == "default"
        if operation == "identity":
            return {"profile": profile, "namespace": "fixture", "pid": 42}
        assert operation == "image-read"
        assert kwargs["image_variant"] == variant
        assert kwargs["chat"] == "wxid_fixture" and kwargs["pid"] == 42
        actual = kwargs["image_identity"]
        if actual != identity:
            raise ConnectorError("wechat_cli_message_mismatch")
        path = kwargs["destination"]
        paths.append(path)
        path.write_bytes(content)
        return {
            **actual,
            "chat": kwargs["chat"],
            "namespace": "fixture",
            "file": str(path),
            "variant": variant,
            "format": format,
            "width": 32,
            "height": 40,
            "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }

    monkeypatch.setattr(cli, "run", run)
    args = {"workspace": workspace, "worker_id": worker_id, "work_id": work_id}
    if variant == "large":
        args["variant"] = variant
    entry = service.invoke(OWNER, "cli-worker-image-test", **args, **identity)["entry"]
    assert (entry["state"], entry["variant"], entry["format"]) == (
        f"{variant}_read",
        variant,
        format,
    )
    assert entry["server_id"] == identity["server_id"]
    assert not paths[0].exists()
    bad = service.invoke(
        OWNER, "cli-worker-image-test", **args, **{**identity, "server_id": "9"}
    )["entry"]
    assert bad["state"] == "unread" and bad["error"] == "wechat_cli_message_mismatch"
    stored = service.invoke(OWNER, "cli-workers")
    assert stored["image_test_logs"][worker_id + ":" + work_id] == [bad, entry]
    assert stored["revision"] == 1
    assert calls == ["identity", "image-read", "identity", "identity", "image-read"]


def test_proxy_one_image_watch_ignores_history_and_outbound(monkeypatch):
    from ai2apps.comapps import cli, proxy_workers

    target = "wxid_fixture"
    database = "message_0.db"
    config = {"profile": "default", "namespace": "fixture"}
    history = [
        {
            "local_id": 82,
            "server_id": "9007199254740993",
            "type": 3,
            "from_user": target,
            "database_name": database,
        },
    ]

    def run(config, operation, profile, **kwargs):
        if operation == "identity":
            return {"profile": profile, "namespace": config["namespace"], "pid": 42}
        assert operation == "messages" and kwargs["chat"] == target
        assert kwargs["pid"] == 42
        shard, cursor = kwargs["message_window"]
        assert shard == database
        rows = list(history)
        if cursor == 82:
            rows.extend(
                [
                    {
                        **history[0],
                        "local_id": 83,
                        "server_id": "9007199254740994",
                        "from_user": "self",
                    },
                    {**history[0], "local_id": 84, "server_id": "9007199254740995"},
                ]
            )
        return {"user_name": target, "table_found": True, "messages": rows}

    monkeypatch.setattr(cli, "run", run)
    assert proxy_workers.wait_for_image(config, target, database) == {
        "database": database,
        "local_id": 84,
        "server_id": "9007199254740995",
    }


def test_proxy_monitor_reads_multiple_shards_without_replaying_history(monkeypatch):
    from ai2apps.comapps import proxy_monitor

    target = "wxid_fixture"
    first, second = "message_0.db", "message_1.db"
    config = {"profile": "default", "namespace": "fixture"}
    shards = {first: [1, 11], second: [1, 12]}

    def row(shard, local_id, server_id, created_at, sender=target):
        return {
            "local_id": local_id,
            "server_id": server_id,
            "database_name": shard,
            "created_at": created_at,
            "from_user": sender,
            "type": 3,
        }

    rows = {first: [row(first, 9, "101", 50)], second: []}
    monkeypatch.setattr(
        proxy_monitor.cli,
        "run",
        lambda *_a, **_kw: {
            "namespace": "fixture",
            "pid": 42,
        },
    )
    monkeypatch.setattr(proxy_monitor, "discover_shards", lambda *_: shards)
    monkeypatch.setattr(
        proxy_monitor,
        "read_window",
        lambda _c, _o, _t, shard, cursor: [
            entry for entry in rows[shard] if entry["local_id"] >= cursor
        ],
    )
    checkpoint, images = proxy_monitor.snapshot(config, target, None, 100)
    assert not images
    rows[first] += [row(first, 10, "102", 101, "self"), row(first, 11, "103", 102)]
    rows[second] = [row(second, 1, "104", 90), row(second, 2, "105", 103)]
    checkpoint, images = proxy_monitor.snapshot(config, target, checkpoint, 100)
    assert [(entry["database"], entry["server_id"]) for entry in images] == [
        (first, "103"),
        (second, "105"),
    ]
    assert proxy_monitor.snapshot(config, target, checkpoint, 100)[1] == []
    shards[second] = [1, 99]
    with pytest.raises(ConnectorError, match="comapps_image_shard_changed"):
        proxy_monitor.snapshot(config, target, checkpoint, 100)


@pytest.mark.parametrize("group", [False, True])
def test_recall_replays_text_and_preserves_image_preview(tmp_path, monkeypatch, group):
    """An already-recalled image must use its preview from the new-message event."""
    from ai2apps.comapps import recall_monitor

    monitor = object.__new__(recall_monitor.RecallMonitor)
    monitor.root = tmp_path / "private"
    monitor.stopping = False
    monkeypatch.setattr(monitor, "_update", lambda *_: None)
    shard = "message_0.db"
    target = "test@chatroom" if group else "wxid_darthfalcon_fixture"
    image_id = "90071992547409931"
    text_id = "90071992547409932"
    config = {"profile": "default", "namespace": "fuel-fixture"}
    now = 1_700_000_000
    scope = {"profile": "default", "namespace": "fuel-fixture", "chat": target, "database": shard}

    def event(event_id, kind, local_id, server_id, **payload):
        return {**scope, "event_id": event_id, "event": kind, "local_id": local_id,
                "server_id": server_id, **payload}

    calls = []
    original_text = {"type": 1, "local_id": 83, "server_id": text_id,
                     "database_name": shard, "raw_content": "撤回测试",
                     "from_user": "wxid_sender"}
    original_image = {"type": 3, "local_id": 82, "server_id": image_id,
                      "database_name": shard}

    def run(config, op, profile, **kwargs):
        calls.append(op)
        if op == "identity":
            return {"profile": profile, "namespace": config["namespace"], "pid": 42}
        assert kwargs["pid"] == 42
        if op == "friends":
            return {"friends": [
                {"user_name": "wxid_admin", "remark": "管理员备注", "nickname": "管理员"},
                {"user_name": "wxid_sender", "nickname": "原作者"},
            ]}
        assert kwargs["chat"] == target
        if op == "messages":
            return {"user_name": target, "table_found": True, "messages": []}
        if op == "message-original":
            identity = kwargs["image_identity"]
            return {"original": original_text if identity["server_id"] == text_id else original_image}
        assert op == "message-events"
        kwargs["event_state"].touch(mode=0o600, exist_ok=True)
        return {"events": {
            0: [],
            1: [
                event(2, "message_recalled", 82, image_id, revoke_time=now, original_available=True),
                event(3, "message_recalled", 83, text_id, revoke_time=now + 1,
                      original_available=True, **({"revoker_id": "wxid_admin"} if group else {})),
            ],
        }.get(kwargs["after_event"], [])}

    monkeypatch.setattr(recall_monitor.cli, "run", run)
    monkeypatch.setattr(recall_monitor, "discover_shards", lambda *_: {shard: [1, 2]})
    image = "data:image/jpeg;base64,fixture"
    monkeypatch.setattr(recall_monitor, "preview", lambda *_: image)
    row = {"target": target, "checkpoints": "{}", "generation": "fixture", "previews": "{}",
           "entries": json.dumps([{"at": now - i - 1} for i in range(20)])}
    monitor._poll(row, config)
    assert json.loads(row["checkpoints"])[shard]["cursor"] == 0
    baseline = run

    def new_image(config, op, profile, **kwargs):
        if op == "message-events" and kwargs["after_event"] == 0:
            return {"events": [event(1, "message_new", 82, image_id, message=original_image)]}
        return baseline(config, op, profile, **kwargs)

    monkeypatch.setattr(recall_monitor.cli, "run", new_image)
    monitor._poll(row, config)
    monitor._poll(row, config)
    monitor._poll(row, config)
    entries = json.loads(row["entries"])
    assert len(entries) == 20
    assert entries[0]["text"] == "撤回测试"
    assert entries[0]["revoke_time"] == now + 1
    assert entries[1]["image"] == image
    assert entries[1]["server_id"] == image_id
    assert entries[1]["revoker_id"] is None
    if group:
        assert entries[0]["revoker_id"] == "wxid_admin"
        assert entries[0]["revoker_name"] == "管理员备注"
        assert entries[0]["sender_id"] == "wxid_sender"
        assert entries[0]["sender_name"] == "原作者"
        assert calls.count("friends") == 1
    assert json.loads(row["previews"]) == {}
    assert calls.count("message-original") == 2
