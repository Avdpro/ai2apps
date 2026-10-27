"""Default-model image generation exposed through the Tool Gateway."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import uuid
from collections.abc import Callable
from typing import Any

from ai2apps.cloud_gateway import request_cloud_image
from ai2apps.model_manager import ModelManagerStore
from ai2apps.services import (
    ServiceInstanceStatus,
    ServiceRegistry,
    ServiceRepository,
    ServiceRuntimeMode,
    ToolCallContext,
    ToolProviderError,
)
from ai2apps.workspace import WorkspaceRepository
from ai2apps.images.parameters import base_schema

_DATA_URL = re.compile(r"^data:(image/(?:png|jpeg|webp));base64,(.+)$", re.DOTALL)


def _default_image_model(store: ModelManagerStore) -> str:
    configured = store.resolve_default_model("image_generation")
    if configured:
        return configured
    for model in store.enabled_cloud_models():
        text = f"{model.get('id', '')} {model.get('name', '')}".lower()
        if any(token in text for token in ("gpt-image", "dall-e", "imagen", "flux")):
            return str(model["gateway_id"])
    # The managed route still validates account/session/catalog server-side.
    return "cloud/ai2apps/openai/gpt-image-2"


def install_image_service(
    *,
    base_path,
    cloud_client,
    workspace: WorkspaceRepository,
    repository: ServiceRepository,
    registry: ServiceRegistry,
    runtime_provider: Callable[[], Any | None] | None = None,
) -> None:
    service = repository.ensure_service(
        service_key="ai2apps.images",
        package_id="ai2apps.images",
        package_version="1.0.0",
        display_name="AI2Apps Images",
        runtime_mode=ServiceRuntimeMode.IN_PROCESS,
        capabilities=("image.generate", "artifact.create"),
    )
    instance = repository.ensure_instance(
        service_id=service.id,
        provider_key="builtin:images",
        status=ServiceInstanceStatus.RUNNING,
        endpoint="/v1/images/generations",
        health={"status": "ok"},
    )
    repository.ensure_tool(
        service_id=service.id,
        qualified_name="image.generate",
        display_name="Generate image",
        description=(
            "Generate one image from a text prompt using the user's default image "
            "generation model, and return a durable Session artifact. Use capability.describe to inspect Provider/model constraints; app.collect_parameters can collect missing inputs."
        ),
        input_schema={**base_schema(),
            'properties':{**base_schema()['properties'],
                'provider':{'type':'string'},'parameters':{'type':'object'}}},
        output_schema={"type": "object"},
        effects=("network", "billing", "workspace.write", "artifact.create"),
        required_capabilities=("image.generate", "workspace.write", "artifact.create"),
        timeout_ms=300_000,
    )

    from ai2apps.services.capability_routing import CapabilityRouter, CapabilityProvider, ProviderUnavailable
    from ai2apps.images.agent_providers import mini_app_handler, principal_for
    runtime = runtime_provider() if runtime_provider else None
    router = CapabilityRouter(repository.database)
    if runtime is not None:
        runtime.app_capability_router = router

    # The public Tool is the capability facade, not a fixed implementation.
    original = repository.get_tool("image.generate")
    edit_schema = {**original.input_schema, "properties": {
        **original.input_schema["properties"],
        "artifact_id": {"type": "string", "minLength": 1, "maxLength": 256},
    }, "required": ["prompt", "artifact_id"]}
    repository.ensure_tool(service_id=service.id, qualified_name="image.edit", display_name="Edit image",
        description="Edit an existing image artifact from this Session using Imagine Studio's image-edit Mini-App. Requires the original artifact_id. Never use image.generate as a substitute for editing.",
        input_schema=edit_schema, output_schema={"type":"object"},
        effects=("network","billing","workspace.write","artifact.create"),
        required_capabilities=("image.edit","workspace.write","artifact.create"), timeout_ms=300_000)

    async def generate(arguments: dict[str, Any], context: ToolCallContext):
        if context.session_id is None:
            raise ToolProviderError("Image generation requires a Session")
        runtime = runtime_provider() if runtime_provider is not None else None
        if runtime_provider is not None:
            # The compatibility Provider shares the same Studio execution owner.
            return await mini_app_handler(runtime_provider, workspace, _default_image_model)(arguments, context)
        model_manager = (
            getattr(runtime, "model_manager", None)
            if runtime is not None
            else None
        ) or ModelManagerStore(base_path)
        model = arguments.get('model') or _default_image_model(model_manager)
        request_fingerprint = hashlib.sha256(
            json.dumps(arguments, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:16]
        await context.report_progress("Generating image", progress=0.15)
        request_payload = {
                "model": model,
                "prompt": arguments["prompt"],
                "size": arguments.get("size", "1024x1024"),
                "quality": arguments.get("quality", "auto"),
                "outputFormat": arguments.get("format", "png"),
                "n": 1,
                "idempotencyKey": (
                    f"agent-image-{context.invocation_id or context.trace_id or uuid.uuid4()}-"
                    f"{request_fingerprint}"
                ),
            }
        invocations = (
            None if runtime is None else getattr(runtime, "model_invocations", None)
        )
        package_model = None if invocations is None else invocations.model(model)
        if package_model is not None:
            if not package_model.checkpoint_ready or "image_generation" not in package_model.capabilities:
                raise ProviderUnavailable("Default local image generation model is not ready")
            scheduling_context = (
                invocations.context_for_actor(
                    context.actor_user_id,
                    session_id=context.session_id,
                    consumer_app_id=context.caller_id,
                )
                if context.actor_user_id is not None
                and hasattr(invocations, "context_for_actor")
                else None
            )
            response = await invocations.invoke_foreground_json(
                package_model.id,
                "image_generation",
                request_payload,
                **(
                    {"context": scheduling_context}
                    if scheduling_context is not None
                    else {}
                ),
            )
            if response.status_code >= 400:
                raise ToolProviderError(
                    f"Image provider failed with HTTP {response.status_code}"
                )
            try:
                result = json.loads(bytes(response.body))
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ToolProviderError("Image provider returned invalid JSON") from exc
            if not isinstance(result, dict):
                raise ToolProviderError("Image provider response must be an object")
            data = result.get("data")
            first = data[0] if isinstance(data, list) and data and isinstance(data[0], dict) else {}
            if not result.get("image") and first.get("b64_json"):
                output_format = arguments.get("format", "png")
                mime = "image/jpeg" if output_format == "jpeg" else f"image/{output_format}"
                result["image"] = {
                    "dataUrl": f"data:{mime};base64,{first['b64_json']}",
                    "size": arguments.get("size", "1024x1024"),
                    "quality": arguments.get("quality", "auto"),
                    "format": output_format,
                }
        else:
            result = await request_cloud_image(
                request_payload,
                edit=False,
                base_path=base_path,
                cloud_client=cloud_client,
                cloud_headers=runtime.cloud_ai_authorization_headers(principal_for(runtime, context)) if runtime is not None else None,
                model_manager=model_manager,
            )
        image = result.get("image") if isinstance(result, dict) else None
        match = _DATA_URL.fullmatch(str((image or {}).get("dataUrl") or ""))
        if match is None:
            raise ToolProviderError("Image provider did not return a storable image")
        try:
            data = base64.b64decode(match.group(2), validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ToolProviderError("Image provider returned invalid image data") from exc
        extension = "jpg" if match.group(1) == "image/jpeg" else match.group(1).split("/", 1)[1]
        filename = f"generated-{uuid.uuid4().hex[:12]}.{extension}"
        path = f"generated-images/{filename}"
        workspace.write(
            context.session_id,
            path,
            base64.b64encode(data).decode("ascii"),
            encoding="base64",
        )
        artifact = workspace.create_artifact(
            context.session_id,
            path,
            filename,
            run_id=(
                context.trace_id
                if context.trace_id and context.trace_id.startswith("run_")
                else None
            ),
            media_type=match.group(1),
            metadata={
                "generator": "ai2apps.images",
                "model": model,
                "size": (image or {}).get("size"),
                "quality": (image or {}).get("quality"),
            },
        )
        await context.report_progress("Image artifact ready", progress=1.0)
        cloud_settlement = {
            key: result.get(key)
            for key in (
                "requestId",
                "model",
                "status",
                "usage",
                "points",
                "pointsReleased",
                "balance",
                "pricingVersion",
                "usageEstimated",
            )
            if result.get(key) is not None
        }
        cloud_settlement["phase"] = "completed"
        return {
            "model": model,
            "ai2apps_cloud": [cloud_settlement],
            "artifact": {
                "id": artifact.id,
                "uri": artifact.uri,
                "name": artifact.name,
                "media_type": artifact.media_type,
                "size_bytes": artifact.size_bytes,
                "download_url": (
                    f"/v1/platform/sessions/{context.session_id}/artifacts/"
                    f"{artifact.id}/download"
                ),
            },
        }

    from ai2apps.images.parameters import describe, prepare
    def parameter_callbacks(edit):
        async def descriptor(principal, model=None):
            return await describe(runtime_provider(), principal, edit, model)
        async def preflight(arguments, context):
            active = runtime_provider()
            return await prepare(active, principal_for(active,context), arguments, edit)
        return descriptor, preflight
    descriptor, preflight = parameter_callbacks(False)
    from .mini_parameters import agent_context
    router.register(CapabilityProvider("ai2apps.images.generate", "image.generate", "ai2apps.imagine-studio" if runtime_provider else "ai2apps.images", generate, mini_app_id="ai2apps.imagine.text-to-image" if runtime_provider else None, priority=50 if runtime_provider else 100, describe=descriptor if runtime_provider else None, prepare=preflight if runtime_provider else None,
        agent_context=agent_context(),
        display_name={'zh': '内置图像服务', 'en': 'Built-in image service'},
        summary={'zh': '通过 Imagine Studio 任务生成图片，并返回当前会话。', 'en': 'Generate through an Imagine Studio job and return the image to this session.'}))
    if runtime_provider is not None:
        from ai2apps.images.capabilities import MINI_APP_CAPABILITIES
        from ai2apps.images import mini_parameters
        def workflow_callbacks(mini):
            async def descriptor(principal,model=None):
                return await mini_parameters.describe(runtime_provider(),principal,mini,model)
            async def preflight(arguments,context):
                active=runtime_provider()
                return await mini_parameters.prepare(active,principal_for(active,context),mini,arguments)
            return descriptor,preflight
        for mini_id, capability in MINI_APP_CAPABILITIES.items():
            workflow=mini_id in mini_parameters.WORKFLOWS
            descriptor,preflight=workflow_callbacks(mini_id) if workflow else parameter_callbacks(capability=='image.edit')
            from .app_continuation import KEY as continuation_key, switch_values
            router.register(CapabilityProvider(
                mini_id, capability, "ai2apps.imagine-studio",
                mini_app_handler(runtime_provider, workspace, _default_image_model,
                                 edit=capability == "image.edit",mini_id=mini_id),
                mini_app_id=mini_id, priority=100, version="1.0.0",
                describe=descriptor,prepare=preflight,
                related_capabilities=('image.reference_creation',) if capability=='image.group_photo' else ('image.group_photo',) if capability=='image.reference_creation' else (),
                switch_values=switch_values,continuation=continuation_key,display_name=mini_parameters.FORM_NAMES.get(mini_id),summary=mini_parameters.FORM_SUMMARIES.get(mini_id),agent_context=mini_parameters.agent_context(mini_id)))
            if workflow:
                input_schema=mini_parameters.schema(mini_id)
                input_schema['properties']['provider']={'type':'string'}
                repository.ensure_tool(service_id=service.id,qualified_name=capability,display_name=mini_id.rsplit('.',1)[-1],
                    description=mini_parameters.WORKFLOW_DESCRIPTIONS[mini_id]+' Run the Imagine Studio '+mini_id+' Mini-App. Reference IDs must be real image artifacts in this Session; never invent IDs. Returns a durable image artifact.',
                    input_schema=input_schema,output_schema={'type':'object'},effects=('network','billing','workspace.write','artifact.create'),
                    required_capabilities=('image.edit','workspace.write','artifact.create'),timeout_ms=300000)
                async def route(arguments,context,cap=capability):return await router.invoke(cap,arguments,context)
                registry.bind_tool(capability,provider_key=instance.provider_key,handler=route)
    repository.ensure_tool(service_id=service.id, qualified_name='capability.describe',
        display_name='Describe Provider parameters',
        description='Inspect Provider-owned parameters and model-specific constraints before image.generate/image.edit. Optional model selects the effective schema. Use app.collect_parameters with the functional capability and optional provider ID to ask the user for model and parameters. Never silently reduce explicit size or switch an explicitly selected model.',
        input_schema={'type':'object','properties':{'provider':{'type':'string'},'model':{'type':'string'}},'required':['provider'],'additionalProperties':False},
        output_schema={'type':'object'}, effects=(), timeout_ms=30000)
    async def describe_provider(arguments,context):
        provider=router.providers.get(arguments['provider'])
        if provider is None or provider.describe is None: raise ToolProviderError('Provider has no parameter descriptor')
        return await provider.describe(principal_for(runtime_provider(),context),arguments.get('model'))
    registry.bind_tool('capability.describe',provider_key=instance.provider_key,handler=describe_provider)
    async def route_generate(arguments, context):
        return await router.invoke("image.generate", arguments, context)
    async def route_edit(arguments, context):
        return await router.invoke("image.edit", arguments, context)
    registry.bind_tool("image.generate", provider_key=instance.provider_key, handler=route_generate)
    registry.bind_tool("image.edit", provider_key=instance.provider_key, handler=route_edit)
