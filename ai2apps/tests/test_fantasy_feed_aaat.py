from datetime import datetime
from pathlib import Path

import pytest

from ai2apps.services import ToolProviderError
from ai2apps.studio.fantasy_feed_aaat import RENDERER_SHA256, build_scene, match_profile, profile_rows


def test_resolves_self_and_family_alias_to_saved_avatars():
    avatar = "data:image/png;base64,AAAA"
    profiles = profile_rows({"draft": {"participantProfiles": [
        {"name": "小林", "isSelf": True, "avatar": avatar},
        {"name": "林女士", "aliases": ["妈妈"]},
    ]}})
    scene, matched = build_scene({
        "title": "回家吃饭",
        "participants": [
            {"key": "mom", "name": "妈妈", "profile": "妈妈"},
            {"key": "me", "name": "我", "profile": "我", "self": True},
        ],
        "messages": [{"speaker": "mom", "text": "今晚有你最爱的菜！"},
                     {"speaker": "me", "text": "到家之前帮我留一口！", "offset_seconds": 600}],
    }, profiles, datetime(2026, 11, 9, 18, 15))
    assert matched == {"me": "小林", "mom": "林女士"}
    assert scene["people"][0]["avatar"] == avatar
    assert [item["own"] for item in scene["messages"]] == [False, True]
    assert scene["messages"][1]["time"] - scene["messages"][0]["time"] == 600_000


def test_ambiguous_alias_and_missing_profile_fail_closed():
    profiles = profile_rows({"draft": {"participantProfiles": [
        {"name": "一号", "aliases": ["妈妈"]}, {"name": "二号", "aliases": ["妈妈"]},
    ]}})
    with pytest.raises(ToolProviderError, match="ambiguous"):
        match_profile("妈妈", profiles)
    with pytest.raises(ToolProviderError, match="not found"):
        match_profile("姐姐", profiles)


def test_source_declaration_and_reviewed_renderer_match():
    import hashlib
    import json
    import yaml
    from ai2apps.packages.mini_app_exports import declarations

    root = Path(__file__).resolve().parents[2] / "packages" / "ai2apps-fantasy-feed"
    mini = yaml.safe_load((root / "app.yaml").read_text())["mini_apps"][0]
    catalog = json.loads((root / "ai2apps.json").read_text())["capabilityCatalog"]
    specs = declarations(mini, catalog)
    assert specs[0]["sdk"] == "studio.fictional-conversation/v1"
    assert hashlib.sha256((root / "web/render.js").read_bytes()).hexdigest() == RENDERER_SHA256


@pytest.mark.asyncio
async def test_source_provider_publishes_output_and_reuses_receipt(tmp_path, monkeypatch):
    import base64
    import io
    from dataclasses import replace

    from PIL import Image
    from ai2apps.chat.repository import ChatRepository
    from ai2apps.config import PlatformConfig
    from ai2apps.identity import RequestPrincipal
    from ai2apps.platform_runtime import PlatformRuntime
    from ai2apps.services import ToolCallContext
    from ai2apps.studio import fantasy_feed_aaat as feed
    from ai2apps.studio.repository import StudioRepository

    root = Path(__file__).resolve().parents[2]
    monkeypatch.setenv("AI2APPS_ALLOW_DEVELOPMENT_RUNTIME", "1")
    monkeypatch.setenv("AI2APPS_DEVELOPMENT_SOURCE_ROOT", str(root))
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path / "source-data"))
    runtime.start()
    try:
        principal = RequestPrincipal.legacy_local()
        host, _, _ = runtime.extension_manager.launch_app(feed.STUDIO, principal=principal)
        scope = dict(actor_id=principal.actor_user_id, installation_id=principal.installation_id,
                     app_instance_id=host.id, studio_id=feed.STUDIO)
        repo = StudioRepository(runtime.database)
        repo.save_draft(**scope, mini_app_id=feed.MINI, draft={"participantProfiles": [
            {"name": "小林", "isSelf": True}, {"name": "林女士", "aliases": ["妈妈"]},
        ]})
        render_calls = []

        async def render(_runtime, actor, script, scene, mode, locale):
            assert actor.actor_user_id == principal.actor_user_id
            assert [person["name"] for person in scene["people"]] == ["小林", "林女士"]
            assert mode == "png"
            render_calls.append(scene)
            target = io.BytesIO()
            Image.new("RGB", (720, 1280), "green").save(target, format="PNG")
            return [base64.b64encode(target.getvalue()).decode()]

        monkeypatch.setattr(feed, "render_frames", render)
        thread, _ = ChatRepository(runtime.database, runtime.events).create_thread(title="Fixture chat")
        context = replace(ToolCallContext.from_principal(principal, caller_id="fixture",
                          session_id=thread.session.id), invocation_id="fantasy-feed-once")
        provider = next(p for p in runtime.app_capability_router.providers.values()
                        if p.capability == "media.fictional_conversation")
        args = {"title": "回家吃饭",
                "participants": [{"key": "me", "name": "我", "profile": "我", "self": True},
                                 {"key": "mom", "name": "妈妈", "profile": "妈妈"}],
                "messages": [{"speaker": "mom", "text": "饭好了！"}]}
        result = await provider.handler(args, context)
        again = await provider.handler(args, context)
        assert result == again and len(render_calls) == 1
        run = repo.get_run(result["studio_run_id"], **scope)
        assert run["status"] == "succeeded"
        assert result["artifact"]["download_url"] == run["artifacts"][0]["downloadUrl"]
        assert result["profiles"] == {"me": "小林", "mom": "林女士"}
    finally:
        for key in list(runtime.package_mini_exports.owned):
            runtime.app_capability_router.unregister(key)
        runtime.stop()
