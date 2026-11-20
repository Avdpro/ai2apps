"""Discover Skill lifecycle API."""


import asyncio
import json
import logging
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, ValidationError
from starlette.concurrency import run_in_threadpool

from ai2apps.api.identity import require_app_capability
from ai2apps.apps.access import APP_SYSTEM_MANAGE
from ai2apps.http_security import enforce_same_origin_cookie_request
from ai2apps.model_invocation import ModelInvocationContext
from ai2apps.skills.github import GitHubSkills, github_client
from ai2apps.skills.library import MAX_BYTES, MAX_FILES, SkillLibrary, folder_upload, principal_owner
from ai2apps.skills.mini_apps import IMAGINE, OPTIONS, MiniAppConfig, SkillMiniApps
from ai2apps.skills.security_review import SYSTEM_PROMPT, parse_report, review_plan
from ai2apps.task_llm import resolve_task_model, task_payload


logger = logging.getLogger(__name__)


class UploadedFile(BaseModel):
    path: str = Field(max_length=512)
    content: str


class LocalImport(BaseModel):
    files: list[UploadedFile] = Field(max_length=MAX_FILES)
    target: str | None = None
    expected_revision: str | None = None


class GithubLocation(BaseModel):
    url: str = Field(max_length=512)


class GithubImport(GithubLocation):
    folder: str = Field(max_length=512)
    ref: str = Field(max_length=512)
    commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    target: str | None = None
    expected_revision: str | None = None


class ReviewRequest(BaseModel):
    plan_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    language: Literal["en", "zh"] = "en"


def create_skill_router(runtime_provider, principal_provider):
    router = APIRouter(
        prefix="/skills",
        dependencies=[Depends(require_app_capability(principal_provider, APP_SYSTEM_MANAGE))],
    )
    principal_dep = Depends(principal_provider)

    def library():
        runtime = runtime_provider()
        if runtime is None:
            raise HTTPException(503, "Local runtime is unavailable")
        return SkillLibrary(runtime.config.paths.base_path / "platform" / "skills")

    def invoke(operation, *args):
        try:
            return operation(*args)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(502, "GitHub request failed. Check the link or try again later") from exc

    @router.get("")
    def installed(principal=principal_dep):
        return {"items": library().list(principal_owner(principal))}

    @router.get("/mini-app-studios")
    def studio_options():
        return {"items": [
            {"id": studio, "name": name, "name_zh": zh, "compatible": studio == IMAGINE}
            for studio, name, zh in OPTIONS
        ]}

    @router.post("/{skill_id}/mini-apps", status_code=201)
    def create_mini_app(request: Request, skill_id: str, config: MiniAppConfig, principal=principal_dep):
        enforce_same_origin_cookie_request(request)
        return invoke(SkillMiniApps(library()).create, principal_owner(principal), skill_id, config)

    @router.post("/preview/local")
    async def preview_local(request: Request, principal=principal_dep):
        enforce_same_origin_cookie_request(request)
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > 12 * 1024 * 1024:
                raise HTTPException(413, "Skill upload exceeds the size limit")
            body.extend(chunk)
        try:
            payload = LocalImport.model_validate_json(body)
        except ValidationError as exc:
            raise HTTPException(400, "Invalid Skill folder upload") from exc

        def preview():
            folder, files = folder_upload([item.model_dump() for item in payload.files])
            return library().preview(principal_owner(principal), folder, files, {"kind": "local", "folder": folder},
                                     f"local:{folder}", payload.target, payload.expected_revision)

        return await run_in_threadpool(invoke, preview)

    @router.post("/github/folders")
    def github_folders(request: Request, payload: GithubLocation):
        enforce_same_origin_cookie_request(request)
        with github_client() as client:
            return invoke(GitHubSkills(client).discover, payload.url)

    @router.post("/preview/github")
    def preview_github(request: Request, payload: GithubImport, principal=principal_dep):
        enforce_same_origin_cookie_request(request)
        with github_client() as client:
            folder, files, source, key = invoke(
                GitHubSkills(client).snapshot, payload.url, payload.folder, payload.ref, payload.commit,
            )
        return invoke(library().preview, principal_owner(principal), folder, files, source, key,
                      payload.target, payload.expected_revision)

    @router.post("/install/{preview_id}")
    def install(request: Request, preview_id: str, principal=principal_dep):
        enforce_same_origin_cookie_request(request)
        return invoke(library().install, principal_owner(principal), preview_id)

    def prepare_review(preview_id, principal):
        snapshot = invoke(library().review_snapshot, principal_owner(principal), preview_id)
        runtime = runtime_provider()
        invocations = getattr(runtime, "model_invocations", None)
        model = resolve_task_model(runtime, "standard", "privacy") if invocations else None
        destination = None
        if model:
            if model.startswith("cloud/"):
                destination = "cloud"
            else:
                destination = "local" if invocations.model(model) is not None else "external"
        plan, files = review_plan(preview_id, snapshot, model, destination)
        return plan, files, invocations

    @router.get("/preview/{preview_id}/security-review")
    def plan_review(preview_id: str, principal=principal_dep):
        return prepare_review(preview_id, principal)[0]

    @router.post("/preview/{preview_id}/security-review")
    async def assess(request: Request, preview_id: str, payload: ReviewRequest, principal=principal_dep):
        enforce_same_origin_cookie_request(request)
        plan, files, invocations = await run_in_threadpool(prepare_review, preview_id, principal)
        if payload.plan_id != plan["id"]:
            raise HTTPException(409, "Review settings changed. Reopen Safety review to check the model and files")
        if not plan["model"] or not files:
            raise HTTPException(409, "Safety review needs a configured Privacy task model and reviewable text files")
        context = ModelInvocationContext.from_principal(
            principal, session_id=f"skill-review-{preview_id}", consumer_app_id="ai2apps.discover",
        )
        model_request = task_payload(plan["model"], [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(
                {"language": payload.language, "files": files}, ensure_ascii=False,
            )},
        ], "standard", max_tokens=3000)
        try:
            if plan["destination"] == "local":
                model_request["chat_template_kwargs"] = {"enable_thinking": False}
                result = await asyncio.wait_for(invocations.invoke_background_json(
                    plan["model"], "chat_completions", {**model_request, "stream": False}, context=context,
                ), timeout=165)
                if result.status_code >= 400:
                    raise RuntimeError("Local model request failed")
                response = json.loads(result.body)
            else:
                response = await asyncio.wait_for(
                    invocations.invoke_chat_json(model_request, context=context), timeout=90,
                )
            report = parse_report(response, files)
        except Exception as exc:
            logger.warning("Skill safety review failed: %s", type(exc).__name__)
            raise HTTPException(502, "Safety review could not produce a verifiable report") from None
        return {**plan, **report}

    @router.delete("/{skill_id}", status_code=204)
    def remove(request: Request, skill_id: str, principal=principal_dep):
        enforce_same_origin_cookie_request(request)
        library().remove(principal_owner(principal), skill_id)
        return Response(status_code=204)

    @router.get("/{skill_id}/export")
    def export(skill_id: str, principal=principal_dep):
        metadata, archive = invoke(library().export, principal_owner(principal), skill_id)
        return Response(archive, media_type="application/zip", headers={
            "Content-Disposition": f'attachment; filename="{metadata["name"]}.zip"',
            "Cache-Control": "no-store",
        })

    @router.get("/{skill_id}")
    def detail(skill_id: str, principal=principal_dep):
        import io
        import zipfile

        metadata, archive = invoke(library().export, principal_owner(principal), skill_id)
        with zipfile.ZipFile(io.BytesIO(archive)) as snapshot:
            markdown = snapshot.read(f'{metadata["name"]}/SKILL.md').decode("utf-8-sig")
        return {**metadata, "markdown": markdown}

    return router
