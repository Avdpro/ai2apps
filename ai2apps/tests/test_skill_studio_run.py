import json
from types import SimpleNamespace

import httpx
from fastapi import FastAPI

from ai2apps.api.imagine_studio import create_imagine_studio_router
from ai2apps.config import PlatformConfig
from ai2apps.core import AppInstanceMode, SingletonScope
from ai2apps.events import EventStore
from ai2apps.identity import RequestPrincipal, user_singleton_key
from ai2apps.skills.library import SkillLibrary, principal_owner
from ai2apps.skills.mini_apps import IMAGINE, MiniAppConfig, SkillMiniApps
from ai2apps.storage import PlatformDatabase
from ai2apps.storage.repositories import AppRepository
from ai2apps.studio.background import StudioBackgroundJobs
from ai2apps.workspace import WorkspaceRepository


async def test_skill_studio_submission_replays_once_and_publishes_shared_output(tmp_path, monkeypatch):
    config = PlatformConfig.from_base_path(tmp_path)
    database = PlatformDatabase(config.paths.database_path)
    database.initialize()
    actor = RequestPrincipal.legacy_local()
    apps = AppRepository(database)
    definition = apps.create_definition(package_id=IMAGINE, package_version="1", display_name="Imagine",
        instance_mode=AppInstanceMode.SINGLETON, singleton_scope=SingletonScope.USER)
    instance = apps.create_instance(app_definition_id=definition.id, owner_user_id=actor.actor_user_id,
        singleton_key=user_singleton_key(IMAGINE, actor.actor_user_id)).id
    library = SkillLibrary(tmp_path / "platform" / "skills")
    owner = principal_owner(actor)
    preview = library.preview(owner, "postcard", {
        "SKILL.md": b"---\nname: postcard\ndescription: Draw a postcard\n---\nUse the chosen plant.",
        "references/style.md": b"Use gouache",
        "references/unrelated.md": b"Unrelated secret fixture",
    }, {"kind": "local"}, "local:postcard")
    skill = library.install(owner, preview["id"])
    mini = SkillMiniApps(library).create(owner, skill["id"], MiniAppConfig(
        title="Postcard", studio=IMAGINE, revision=skill["revision"],
        parameters=[{"key": "plant", "label": "Plant", "type": "text", "required": True}],
    ))
    model_id = "cloud/fixture/image"
    calls = []

    async def catalog(*_):
        return {"items": [{"id": model_id, "label": "Fixture", "ready": True, "source": "cloud",
            "referenceLimit": 0, "formats": ["png"], "qualities": ["auto"],
            "size": {"mode": "fixed", "presets": ["1024x1024"]}}]}

    async def chat(request, *, context):
        assert "tools" not in request
        assert context.app_instance_id == instance
        data = json.loads(request["messages"][1]["content"])
        calls.append(data)
        value = ({"paths": ["references/style.md"]} if "available_paths" in data
                 else {"prompt": "Draw ginkgo in gouache"})
        return {"choices": [{"message": {"content": json.dumps(value)}}]}

    async def draw(runtime, principal, job, payload, request_id):
        assert payload["prompt"] == "Draw ginkgo in gouache"
        assert payload["model"] == model_id
        return b"fixture", {"media_type": "image/png", "model": model_id, "size": "1024x1024"}

    monkeypatch.setattr("ai2apps.studio.image_workflow.model_catalog", catalog)
    monkeypatch.setattr("ai2apps.studio.skill_workflow.generate_image", draw)
    events = EventStore(database)
    runtime = SimpleNamespace(config=config, database=database, events=events,
        workspace=WorkspaceRepository(database, events, config.paths),
        extension_manager=SimpleNamespace(require_instance_access=lambda *_: None,
                                          instance_entry=lambda *_, **__: {"app_key": IMAGINE}),
        model_manager=SimpleNamespace(resolve_default_model=lambda *_, **__: "cloud/fixture/text"),
        model_invocations=SimpleNamespace(model=lambda _: None, invoke_chat_json=chat))
    runtime.studio_jobs = StudioBackgroundJobs(runtime)
    app = FastAPI()
    app.include_router(create_imagine_studio_router(lambda: runtime, lambda: actor))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test",
                                 headers={"X-AI2Apps-App-Instance": instance}) as client:
        route = f"/imagine-studio/skill-mini-apps/{mini['id']}/runs"
        body = {"key": "90bd034f-2d55-4c9f-a457-57581199e2b7", "model": model_id,
                "size": "1024x1024", "values": {"plant": "Ginkgo"}}
        assert (await client.post(route, json={**body, "values": {}})).status_code == 422
        response = await client.post(route, json=body)
        assert response.status_code == 202, response.text
        queued = response.json()
        assert (await client.post(route, json=body)).json()["id"] == queued["id"]
        assert (await client.post(route, json={**body, "values": {"plant": "Oak"}})).status_code == 422
    with database.transaction() as db:
        assert db.execute("SELECT count(*) FROM studio_runs").fetchone()[0] == 1
        job = dict(db.execute("SELECT * FROM studio_background_jobs WHERE id=?", (queued["id"],)).fetchone())
    await runtime.studio_jobs._run(job)
    from ai2apps.studio.repository import StudioRepository
    result = StudioRepository(database).get_run(queued["run_id"], **runtime.studio_jobs.scope(job))
    assert result["status"] == "succeeded"
    assert len(result["artifacts"]) == 1 and result["artifacts"][0]["mediaType"] == "image/png"
    assert calls[0]["parameters"] == [{"key": "plant", "label": "Plant", "value": "Ginkgo"}]
    assert calls[1]["references"] == {"references/style.md": "Use gouache"}
