import base64
import json
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from PIL import Image

from ai2apps.api.imagine_studio import create_imagine_studio_router
from ai2apps.config import PlatformConfig
from ai2apps.core import AppInstanceMode, SingletonScope
from ai2apps.events import EventStore
from ai2apps.identity import RequestPrincipal, user_singleton_key
from ai2apps.storage import PlatformDatabase
from ai2apps.storage.repositories import AppRepository
from ai2apps.experiments import comfyui_studio as comfyui
from ai2apps.studio.background import StudioBackgroundJobs
from ai2apps.workspace import WorkspaceRepository


def workflow():
    def node(kind, **inputs):
        return {"class_type": kind, "inputs": inputs}

    return {
        "1": node("CheckpointLoaderSimple", ckpt_name="example.safetensors"),
        "2": node("CLIPTextEncode", clip=["1", 1], text="A forest"),
        "3": node("CLIPTextEncode", clip=["1", 1], text="Watermarks"),
        "4": node("EmptyLatentImage", width=1024, height=1024, batch_size=1),
        "5": node("KSampler", model=["1", 0], positive=["2", 0], negative=["3", 0],
                  latent_image=["4", 0], seed=2**64 - 1, sampler_name="euler", steps=20),
        "6": node("VAEDecode", samples=["5", 0], vae=["1", 2]),
        "7": node("SaveImage", images=["6", 0], filename_prefix="ComfyUI"),
    }


@pytest.mark.parametrize(("source", "case"), [
    ("local", None), ("cloud", None), ("byok", None),
    ("local", "F01.canvas"), ("local", "F02.canvas"), ("local", "F10.canvas"),
    ("local", "F01.api"), ("local", "F02.api"),
])
async def test_comfyui_preset_runs_through_existing_image_jobs(tmp_path, monkeypatch, source, case):
    config = PlatformConfig.from_base_path(tmp_path)
    database = PlatformDatabase(config.paths.database_path)
    database.initialize()
    actor = RequestPrincipal.legacy_local()
    studio_id = "ai2apps.imagine-studio"
    apps = AppRepository(database)
    definition = apps.create_definition(
        package_id=studio_id, package_version="1", display_name="Imagine",
        instance_mode=AppInstanceMode.SINGLETON, singleton_scope=SingletonScope.USER,
    )
    instance = apps.create_instance(
        app_definition_id=definition.id, owner_user_id=actor.actor_user_id,
        singleton_key=user_singleton_key(studio_id, actor.actor_user_id),
    ).id
    png = BytesIO()
    Image.new("RGB", (3, 4)).save(png, format="PNG")
    image = {"image": {"dataUrl": "data:image/png;base64," + base64.b64encode(png.getvalue()).decode()}}
    calls = []
    model_id = {"local": "fixture-mlx/4b", "cloud": "cloud/fixture/image", "byok": "byok/fixture/image"}[source]
    model = SimpleNamespace(
        id=model_id, checkpoint_ready=True, model_type="image_generation",
        image_capabilities={"operations": ["image_generation"]},
    )

    async def local_generate(identifier, operation, payload, **options):
        assert identifier == model_id and operation == "image_generation"
        calls.append(("local", payload))
        return JSONResponse(image)

    async def cloud_generate(payload, **options):
        assert options["edit"] is False
        calls.append(("api", payload))
        return image

    monkeypatch.setattr("ai2apps.images.cloud_gateway.request_cloud_image", cloud_generate)
    events = EventStore(database)
    runtime = SimpleNamespace(
        config=config, database=database, events=events,
        workspace=WorkspaceRepository(database, events, config.paths),
        cloud=object(), cloud_ai_authorization_headers=lambda _: {},
        extension_manager=SimpleNamespace(
            require_instance_access=lambda *_: None,
            instance_entry=lambda *_, **__: {"app_key": studio_id},
        ),
        model_invocations=SimpleNamespace(
            model=lambda identifier: model if identifier == model_id else None,
            invoke_background_json=local_generate, context_for_actor=lambda *a, **k: None,
        ),
    )
    runtime.studio_jobs = StudioBackgroundJobs(runtime)
    app = FastAPI()
    monkeypatch.setattr("ai2apps.api.imagine_studio.comfyui_prototype_enabled", lambda: True)
    app.include_router(create_imagine_studio_router(lambda: runtime, lambda: actor))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", headers={"X-AI2Apps-App-Instance": instance},
    ) as client:
        url = "/imagine-studio/comfyui"
        spec = {
            "id": "1" * 32, "name": "Landscape", "workflow_json": json.dumps(workflow()),
            "output": "7", "prompt": "A quiet lake", "size": "1024x1024",
            "model": model_id, "source": source,
        }
        if case:
            corpus = Path(comfyui.__file__).parent / "benchmark" / "workflows"
            spec["workflow_json"] = (corpus / f"{case}.json").read_text()
        inspected = await client.post(f"{url}/inspect", json={"workflow_json": spec["workflow_json"]})
        assert inspected.status_code == 200
        mapping = inspected.json()
        assert mapping["runnable"] and mapping["size"] == "1024x1024"
        spec["output"] = mapping["output"]
        if case:
            assert mapping["prompt"].strip()
            spec["prompt"] = mapping["prompt"]
            if case == "F10.canvas":
                assert [item["id"] for item in mapping["outputs"]] == ["9"]
                assert any(item["id"] == "78" for item in mapping["inactiveNodes"])
                assert any(link["from"] == "76" and link["port"] == "text" for link in mapping["links"])
        else:
            assert mapping["prompt"] == "A forest"
            omitted = {item["parameter"]: item["value"] for item in mapping["omitted"]}
            assert omitted["seed"] == str(2**64 - 1)
            assert {"ckpt_name", "text", "steps", "sampler_name", "batch_size"} <= omitted.keys()
        rejected = await client.post(f"{url}/runs", json={"preset": spec, "test": True})
        assert rejected.status_code == 422
        assert "accept" in rejected.json()["detail"]
        spec["accepted_mapping"] = True
        save_url = f"{url}/presets/{spec['id']}"

        async def finish(run):
            assert run.status_code == 202, run.text
            run_id = run.json()["id"]
            job = runtime.studio_jobs.for_run(run_id, actor)
            with database.transaction() as connection:
                row = connection.execute("SELECT * FROM studio_background_jobs WHERE id=?", (job["id"],)).fetchone()
            await runtime.studio_jobs._run(dict(row))
            completed = (await client.get(f"{url}/runs/{run_id}")).json()
            assert completed["status"] == "succeeded", completed.get("error")
            assert completed["miniAppId"] == comfyui.MINI_APP_ID
            assert completed["artifacts"][0]["mediaType"] == "image/png"
            return run_id

        trial = await client.post(f"{url}/runs", json={"preset": spec, "test": True})
        body = {"preset": spec, "base_version": 0, "test_run_id": trial.json()["id"]}
        assert (await client.put(save_url, json=body)).status_code == 409
        await finish(trial)
        assert calls[-1][1]["prompt"] == spec["prompt"].strip()
        changed = {**spec, "prompt": "Untested modification"}
        assert (await client.put(save_url, json={**body, "preset": changed})).status_code == 409
        result = await client.put(save_url, json=body)
        assert result.status_code == 200, result.text
        assert result.json()["version"] == 1
        assert (await client.put(save_url, json=body)).status_code == 409
        saved = (await client.get(f"{url}/presets")).json()["items"][0]
        assert saved["model"] == model_id and saved["prompt"] == spec["prompt"]
        actor = replace(actor, actor_user_id="other")
        assert (await client.get(f"{url}/presets")).json()["items"] == []
        assert (await client.get(f"{save_url}/versions")).status_code == 404
        actor = RequestPrincipal.legacy_local()

        changed.update(layout={"size_first": True, "size_choices": [{"label": "Square", "size": "1024x1024"}]})
        second_trial = await client.post(f"{url}/runs", json={"preset": changed, "test": True})
        second_id = await finish(second_trial)
        second_body = {"preset": changed, "base_version": 1, "test_run_id": second_id}
        assert (await client.put(save_url, json=second_body)).json()["version"] == 2
        versions = (await client.get(f"{save_url}/versions")).json()["items"]
        assert [version["version"] for version in versions] == [2, 1]
        assert versions[1]["prompt"] == spec["prompt"]
        assert versions[1]["workflow_json"] == spec["workflow_json"]
        restored = await client.post(f"{url}/runs", json={"preset": versions[1], "test": True})
        restored_id = await finish(restored)
        assert (await client.put(save_url, json={
            "preset": versions[1], "base_version": 2, "test_run_id": restored_id,
        })).json()["version"] == 3

        run = await client.post(f"{url}/runs", json={"preset": {**saved, "prompt": "A new prompt"}})
        await finish(run)
        assert calls[-1][0] == ("local" if source == "local" else "api")
        assert calls[-1][1]["prompt"] == "A new prompt"
        assert calls[-1][1]["size"] == "1024x1024"
        assert set(calls[-1][1]).isdisjoint({"workflow_json", "seed", "steps", "ckpt_name", "layout"})


def test_unsupported_operation_is_reported_instead_of_dropped():
    graph = workflow()
    graph["1"]["class_type"] = "LoraLoader"
    with pytest.raises(comfyui.ComfyError, match=r"1 \(LoraLoader\)"):
        comfyui.Workflow(workflow_json=json.dumps(graph)).inspect()


@pytest.mark.parametrize("provider", ["system", "codex"])
async def test_arrangement_is_an_owned_validated_draft(tmp_path, monkeypatch, provider):
    from ai2apps.codex.transport import CodexDesktop
    from ai2apps.studio.capability_broker import StudioCapabilityBroker
    from ai2apps.experiments.comfyui_studio import codex as comfyui_codex

    config = PlatformConfig.from_base_path(tmp_path)
    database = PlatformDatabase(config.paths.database_path)
    database.initialize()
    actor = RequestPrincipal.legacy_local()
    runtime = SimpleNamespace(config=config, database=database, extension_manager=SimpleNamespace(
        require_instance_access=lambda *_: None,
        instance_entry=lambda *_, **__: {"app_key": "ai2apps.imagine-studio"},
    ))
    proposal = {"name": "Landscape", "prompt": "A forest", "size": "1024x1024",
                "prompt_label": "Scene", "layout": {"size_first": True},
                "unmapped_requests": ["Seed is unavailable"]}
    calls = []

    async def codex(system, prompt):
        calls.append("codex")
        assert "workflow_json" not in prompt
        return json.dumps(proposal)

    async def system(self, mount, **kwargs):
        calls.append("system")
        assert mount.declaration["id"] == comfyui.MINI_APP_ID
        assert kwargs["complexity"] == "standard"
        return {"text": json.dumps(proposal)}

    async def available():
        return True

    monkeypatch.setattr(CodexDesktop, "executable", staticmethod(lambda: "/fixture/codex"))
    monkeypatch.setattr(comfyui_codex, "available", available)
    monkeypatch.setattr(comfyui_codex, "propose", codex)
    monkeypatch.setattr(StudioCapabilityBroker, "complete_for_mini_app", system)
    app = FastAPI()
    monkeypatch.setattr("ai2apps.api.imagine_studio.comfyui_prototype_enabled", lambda: True)
    app.include_router(create_imagine_studio_router(lambda: runtime, lambda: actor))
    transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 50000))
    async with httpx.AsyncClient(transport=transport, base_url="http://test", headers={
        "X-AI2Apps-App-Instance": "fixture",
    }) as client:
        endpoint = "/imagine-studio/comfyui/arrangement"
        assert (await client.get(endpoint + "/providers")).json()["codex"] is True
        body = {
            "provider": provider, "instruction": "Move size above the prompt",
            "draft": {"name": "Landscape", "prompt": "A forest", "size": "1024x1024"},
            "workflow": {"workflow_json": json.dumps(workflow())},
        }
        result = await client.post(endpoint, json=body)
        assert result.status_code == 200, result.text
        assert result.json()["layout"]["size_first"] is True
        assert result.json()["unmapped_requests"] == ["Seed is unavailable"]
        assert calls == [provider]
        assert (await client.get("/imagine-studio/comfyui/presets")).json()["items"] == []
        proposal["model"] = "the-assistant-must-not-change-the-image-model"
        assert (await client.post(endpoint, json=body)).status_code == 422


def test_release_router_does_not_register_prototype(monkeypatch):
    from ai2apps.studio.development import comfyui_prototype_enabled

    monkeypatch.setenv("AI2APPS_INSTANCE_ID", "default")
    monkeypatch.setenv("AI2APPS_ALLOW_DEVELOPMENT_RUNTIME", "1")
    assert not comfyui_prototype_enabled()
    app = FastAPI()
    app.include_router(create_imagine_studio_router(lambda: None))
    assert not any("/comfyui/" in path for path in app.openapi()["paths"])


def test_canvas_diagnosis_follows_media_edges_and_selected_output():
    corpus = Path(comfyui.__file__).parent / "benchmark" / "workflows"

    def inspect(case, output=None):
        return comfyui.Workflow(
            workflow_json=(corpus / f"{case}.canvas.json").read_text(), output=output,
        ).diagnose()

    reference = inspect("H02")
    assert not reference["runnable"]
    assert [source["ports"] for source in reference["mediaInputs"]] == [
        ["ref_images.ref_image_0"], ["ref_images.ref_image_1"],
    ]
    first_frame = inspect("H03")
    assert first_frame["mediaInputs"] == [{"id": "114", "kind": "image", "ports": ["first_frame"]}]
    control = inspect("H04")
    assert control["output"] == "707"
    assert control["outputs"] == [
        {"id": "704", "label": "PreviewImage · 704", "type": "PreviewImage"},
        {"id": "707", "label": "SaveVideo · 707", "type": "SaveVideo"},
    ]
    assert control["mediaInputs"][0]["kind"] == "video"
    assert inspect("H04", "704")["output"] == "704"
    with pytest.raises(comfyui.ComfyError, match="active workflow output"):
        inspect("F10", "78")


def test_unwired_canvas_output_is_diagnostic_only():
    canvas = {"nodes": [{"id": 1, "type": "SaveImage", "inputs": []}], "links": []}
    workflow = comfyui.Workflow(workflow_json=json.dumps(canvas))
    assert not workflow.diagnose()["runnable"]
    with pytest.raises(comfyui.ComfyError):
        workflow.inspect()
