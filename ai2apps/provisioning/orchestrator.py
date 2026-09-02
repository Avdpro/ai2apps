"""ACPF resolution, planning, and durable provisioning orchestration."""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from contextlib import suppress
from typing import Any

from packaging.specifiers import SpecifierSet
from packaging.version import Version

from ai2apps.checkpoint_acquisition import CheckpointAcquisitionService
from ai2apps.checkpoint_distribution import (
    CheckpointCache,
    CheckpointConsentRequiredError,
)
from ai2apps.checkpoint_registry import CheckpointRegistryClient
from ai2apps.core import utc_now_text
from ai2apps.model_installer import AI2AppsInstaller
from ai2apps.model_providers import (
    installed_model_preparation_recipes,
    resolve_package_model,
)
from ai2apps.packages.registry import RegistryError

from .profiles import (
    CapabilityProfileRegistry,
    device_profile,
    profile_device_compatibility,
)
from .repository import ProvisioningSessionRepository


class CapabilityProvisioner:
    """One platform-owned provisioning engine shared by every App."""

    def __init__(
        self,
        *,
        runtime: Any,
        repository: ProvisioningSessionRepository,
        profiles: CapabilityProfileRegistry | None = None,
    ) -> None:
        self.runtime = runtime
        self.repository = repository
        self.profiles = profiles or CapabilityProfileRegistry()
        self.hf_downloader: Any | None = None
        self.ms_downloader: Any | None = None
        self.model_installer: AI2AppsInstaller | None = None
        self.checkpoint_acquisition: CheckpointAcquisitionService | None = None
        self._runners: dict[str, asyncio.Task[None]] = {}
        self._runtime_epoch = uuid.uuid4().hex

    def bind_hf_downloader(self, downloader: Any) -> AI2AppsInstaller:
        """Compatibility wrapper for callers that only provide Hugging Face."""

        return self.bind_checkpoint_downloaders(downloader, self.ms_downloader)

    def bind_checkpoint_downloaders(
        self, hf_downloader: Any, ms_downloader: Any | None = None
    ) -> AI2AppsInstaller:
        """Bind the platform-owned checkpoint transports to one installer."""

        self.hf_downloader = hf_downloader
        self.ms_downloader = ms_downloader
        recipes = installed_model_preparation_recipes(self.runtime)
        registry_packages = getattr(self.runtime, "registry_packages", None)
        if registry_packages is not None and self.checkpoint_acquisition is None:
            registry_root = registry_packages.root.parent
            self.checkpoint_acquisition = CheckpointAcquisitionService(
                registry=CheckpointRegistryClient(
                    cloud=registry_packages.cloud,
                    root=registry_root,
                    repository_fingerprint=registry_packages.repository_fingerprint,
                ),
                cache=CheckpointCache(registry_root / "checkpoint-cache-v1"),
            )

        async def activate(recipe: dict[str, Any]) -> None:
            service_key = recipe.get("service_key")
            if service_key and self.runtime.package_manager is not None:
                await self.runtime.package_manager.restart(service_key)
                resources = getattr(self.runtime, "worker_resources", None)
                if resources is not None:
                    resources.mark_started(service_key)

        if self.model_installer is None:
            self.model_installer = AI2AppsInstaller(
                hf_downloader,
                recipes,
                on_ready=activate,
                ms_downloader=ms_downloader,
                checkpoint_acquisition=self.checkpoint_acquisition,
            )
        else:
            self.model_installer.hf_downloader = hf_downloader
            self.model_installer.ms_downloader = ms_downloader
            self.model_installer.checkpoint_acquisition = self.checkpoint_acquisition
            self.model_installer.package_recipes = recipes
            self.model_installer.on_ready = activate
        return self.model_installer

    async def _start_verification_services(self, session: dict[str, Any]) -> None:
        """Start declared Services; readiness remains a health check, not inference."""

        manager = getattr(self.runtime, "package_manager", None)
        if manager is None:
            return
        stack = session["plan"]["stack"]
        if isinstance(stack.get("components"), list):
            service_keys = [
                component.get("service_key")
                for component in stack["components"]
                if component.get("kind") == "verify"
            ]
        else:
            service_keys = [stack.get("provider", {}).get("service_key")]
        resources = getattr(self.runtime, "worker_resources", None)
        for service_key in dict.fromkeys(service_keys):
            if not isinstance(service_key, str):
                continue
            await manager.start(service_key)
            if resources is not None:
                resources.mark_started(service_key)

    def refresh_model_installer(self) -> AI2AppsInstaller:
        if self.hf_downloader is None:
            raise RuntimeError("Checkpoint downloader is not initialized")
        return self.bind_checkpoint_downloaders(
            self.hf_downloader, self.ms_downloader
        )

    async def startup(self) -> None:
        """Resume owner-approved provisioning work after a Local restart."""

        for session in self.repository.list_active():
            await self.resume_if_possible(session["id"])

    async def shutdown(self) -> None:
        runners = tuple(self._runners.values())
        for runner in runners:
            runner.cancel()
        if runners:
            await asyncio.gather(*runners, return_exceptions=True)
        self._runners.clear()

    @staticmethod
    def _model_satisfies(model: Any, requirements: dict[str, Any]) -> bool:
        operations = set(requirements.get("operations", ()))
        capabilities = set(model.capabilities)
        combinations = {
            item.get("id")
            for item in (model.video_capabilities or {}).get("content_combinations", ())
            if isinstance(item, dict)
        }
        return operations.issubset(capabilities | combinations)

    def resolve_ready(
        self,
        app_id: str,
        capability: str,
        requirements: dict[str, Any],
        *,
        profile_id: str | None = None,
    ) -> dict[str, Any] | None:
        device = device_profile()
        preferred_model_id = requirements.get("modelId")
        preferred_profile_id = requirements.get("profileId")
        profiles = self.profiles.candidates(
            app_id,
            capability,
            device,
            recommended=(
                profile_id is None
                and not isinstance(preferred_model_id, str)
                and not isinstance(preferred_profile_id, str)
            ),
        )
        for profile in profiles:
            if profile_id is not None and profile.get("id") != profile_id:
                continue
            if (
                isinstance(preferred_profile_id, str)
                and profile.get("id") != preferred_profile_id
            ):
                continue
            components = profile.get("stack", {}).get("components")
            if isinstance(components, list):
                ready = self._resolve_component_stack(profile, capability)
                if ready is not None:
                    return ready
                continue
            model_id = profile.get("stack", {}).get("checkpoint", {}).get("model_id")
            if not isinstance(model_id, str):
                continue
            if isinstance(preferred_model_id, str) and model_id != preferred_model_id:
                continue
            model = resolve_package_model(self.runtime, model_id)
            if (
                model is not None
                and model.checkpoint_ready
                and self._model_satisfies(model, requirements)
            ):
                return {
                    "modelId": model.id,
                    "serviceKey": model.service_key,
                    "profileId": profile["id"],
                    "reused": True,
                }
        return None

    def _service_component_ready(self, component: dict[str, Any]) -> bool:
        services = getattr(self.runtime, "services", None)
        service_key = component.get("service_key")
        if services is None or not isinstance(service_key, str):
            return False
        try:
            service = services.get_service(service_key)
            instance = services.get_instance_for_service(service.id)
        except Exception:
            return False
        service_status = getattr(service.status, "value", service.status)
        instance_status = getattr(instance.status, "value", instance.status)
        if service_status != "enabled" or instance_status != "running":
            return False
        health_status = instance.health.get("status")
        if health_status not in {"ok", "ready"}:
            return False
        required = set(component.get("capabilities", ()))
        available = set(service.capabilities) | set(
            instance.health.get("capabilities", ())
        )
        return required.issubset(available)

    def _resolve_component_stack(
        self, profile: dict[str, Any], capability: str
    ) -> dict[str, Any] | None:
        components = profile.get("stack", {}).get("components", ())
        service_key = None
        for component in components:
            if not isinstance(component, dict):
                return None
            kind = component.get("kind")
            if kind == "package":
                if not self._package_fact(component)["ready"]:
                    return None
                service_key = component.get("service_key") or service_key
            elif kind == "checkpoint":
                model_id = component.get("model_id")
                model = (
                    resolve_package_model(self.runtime, model_id)
                    if isinstance(model_id, str)
                    else None
                )
                if model is None or not model.checkpoint_ready:
                    return None
            elif kind == "verify":
                if not self._service_component_ready(component):
                    return None
                service_key = component.get("service_key") or service_key
            else:
                return None
        return {
            "serviceKey": service_key,
            "profileId": profile["id"],
            "capability": capability,
            "reused": True,
        }

    def _package_fact(self, descriptor: dict[str, Any]) -> dict[str, Any]:
        service_key = descriptor["service_key"]
        active = (
            None
            if self.runtime.package_repository is None
            else self.runtime.package_repository.active(service_key)
        )
        version = None if active is None else active.package_version
        compatible = bool(
            version is not None and version in SpecifierSet(descriptor["version"])
        )
        return {
            "packageId": descriptor["package_id"],
            "serviceKey": service_key,
            "requiredVersion": descriptor["version"],
            "installedVersion": version,
            "ready": compatible,
        }

    def _component_plan(
        self,
        *,
        app_id: str,
        capability: str,
        requirements: dict[str, Any],
        profile: dict[str, Any],
        presentation: dict[str, Any],
        device: dict[str, Any],
        profile_options: list[dict[str, Any]],
    ) -> dict[str, Any]:
        step_labels = presentation.get("steps", {})
        steps = []
        for component in profile["stack"]["components"]:
            component_id = str(component["id"])
            kind = component["kind"]
            phase = str(component.get("phase", kind))
            if kind == "package":
                fact = self._package_fact(component)
                ready = fact["ready"]
                details = fact
            elif kind == "checkpoint":
                model_id = component["model_id"]
                model = resolve_package_model(self.runtime, model_id)
                ready = bool(model is not None and model.checkpoint_ready)
                details = {"modelId": model_id}
            elif kind == "verify":
                ready = self._service_component_ready(component)
                details = {
                    "serviceKey": component["service_key"],
                    "capabilities": list(component.get("capabilities", ())),
                }
            else:
                raise ValueError(f"Unsupported ACPF component kind: {kind}")
            default_title = {
                "runtime": "配置能力 Runtime",
                "provider": "安装能力 Package",
                "checkpoint": "下载模型 Checkpoint",
                "verify": "启动并验证能力",
            }.get(phase, f"配置 {component_id}")
            steps.append(
                {
                    "id": component_id,
                    "kind": kind,
                    "phase": phase,
                    "title": step_labels.get(phase, default_title),
                    "status": "complete" if ready else "pending",
                    **details,
                }
            )
        return {
            "schema": "ai2apps.provisioning-plan/v1",
            "appId": app_id,
            "capability": capability,
            "profileId": profile["id"],
            "requirements": requirements,
            "presentation": presentation,
            "device": device,
            "stack": profile["stack"],
            "profileOptions": profile_options,
            "steps": steps,
            "reasons": [
                f"匹配 {device['accelerator']['vendor']} {device['accelerator']['api']} 设备",
                f"App 推荐方案：{profile['id']}",
            ],
        }

    def _multi_profile_plan(
        self,
        *,
        app_id: str,
        capability: str,
        requirements: dict[str, Any],
        profiles: tuple[dict[str, Any], ...],
        presentation: dict[str, Any],
        device: dict[str, Any],
        profile_options: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Merge multiple model profiles into one durable, deduplicated plan."""

        components: list[dict[str, Any]] = []
        package_keys: set[tuple[str, str, str, str]] = set()
        operations = list(requirements.get("operations", ()))
        for profile in profiles:
            stack = profile.get("stack", {})
            if isinstance(stack.get("components"), list):
                for component in stack["components"]:
                    candidate = {
                        **component,
                        "id": f"{profile['id']}:{component['id']}",
                    }
                    if candidate["kind"] == "package":
                        key = (
                            str(candidate["package_id"]),
                            str(candidate["service_key"]),
                            str(candidate["version"]),
                            str(candidate.get("phase", "provider")),
                        )
                        if key in package_keys:
                            continue
                        package_keys.add(key)
                    components.append(candidate)
                continue
            profile_id = str(profile["id"])
            for phase in ("runtime", "provider"):
                descriptor = stack[phase]
                key = (
                    str(descriptor["package_id"]),
                    str(descriptor["service_key"]),
                    str(descriptor["version"]),
                    phase,
                )
                if key in package_keys:
                    continue
                package_keys.add(key)
                components.append(
                    {
                        "id": f"{phase}:{descriptor['service_key']}",
                        "kind": "package",
                        "phase": phase,
                        **descriptor,
                    }
                )
            components.extend(
                (
                    {
                        "id": f"checkpoint:{profile_id}",
                        "kind": "checkpoint",
                        "phase": "checkpoint",
                        "model_id": stack["checkpoint"]["model_id"],
                    },
                    {
                        "id": f"verify:{profile_id}",
                        "kind": "verify",
                        "phase": "verify",
                        "service_key": stack["provider"]["service_key"],
                        "capabilities": operations,
                    },
                )
            )
        profile_ids = [str(profile["id"]) for profile in profiles]
        aggregate = self._component_plan(
            app_id=app_id,
            capability=capability,
            requirements=requirements,
            profile={"id": profile_ids[0], "stack": {"components": components}},
            presentation=presentation,
            device=device,
            profile_options=profile_options,
        )
        aggregate.update(
            {
                "profileIds": profile_ids,
                "selectionMode": "multiple",
                "reasons": [
                    f"匹配 {device['accelerator']['vendor']} {device['accelerator']['api']} 设备",
                    f"用户选择安装 {len(profile_ids)} 个模型",
                ],
            }
        )
        return aggregate

    def resolve_plan_ready(self, plan: dict[str, Any]) -> dict[str, Any] | None:
        """Resolve every provider selected by a single- or multi-profile plan."""

        profile_ids = plan.get("profileIds")
        if not isinstance(profile_ids, list):
            return self.resolve_ready(
                plan["appId"],
                plan["capability"],
                plan.get("requirements", {}),
                profile_id=plan["profileId"],
            )
        providers = []
        for profile_id in profile_ids:
            requirements = dict(plan.get("requirements", {}))
            requirements.pop("profileIds", None)
            requirements["profileId"] = profile_id
            provider = self.resolve_ready(
                plan["appId"],
                plan["capability"],
                requirements,
                profile_id=profile_id,
            )
            if provider is None:
                return None
            providers.append(provider)
        return {
            "profileIds": list(profile_ids),
            "providers": providers,
            "reused": all(item.get("reused", False) for item in providers),
        }

    def plan(
        self,
        app_id: str,
        capability: str,
        requirements: dict[str, Any],
    ) -> dict[str, Any] | None:
        device = device_profile()
        preferred_profile_id = requirements.get("profileId")
        preferred_profile_ids = requirements.get("profileIds")
        if preferred_profile_ids is not None and (
            not isinstance(preferred_profile_ids, list)
            or not 1 <= len(preferred_profile_ids) <= 8
            or not all(isinstance(item, str) and item for item in preferred_profile_ids)
            or len(set(preferred_profile_ids)) != len(preferred_profile_ids)
        ):
            return None
        candidates = self.profiles.candidates(
            app_id,
            capability,
            device,
            recommended=(
                not isinstance(requirements.get("modelId"), str)
                and not isinstance(preferred_profile_id, str)
                and not isinstance(preferred_profile_ids, list)
            ),
        )
        preferred_model_id = requirements.get("modelId")
        if isinstance(preferred_model_id, str):
            candidates = tuple(
                profile
                for profile in candidates
                if profile.get("stack", {}).get("checkpoint", {}).get("model_id")
                == preferred_model_id
            )
        if isinstance(preferred_profile_id, str):
            candidates = tuple(
                profile
                for profile in candidates
                if profile.get("id") == preferred_profile_id
            )
        if isinstance(preferred_profile_ids, list):
            candidates_by_id = {str(profile.get("id")): profile for profile in candidates}
            if any(profile_id not in candidates_by_id for profile_id in preferred_profile_ids):
                return None
            candidates = tuple(candidates_by_id[profile_id] for profile_id in preferred_profile_ids)
        if not candidates:
            return None
        profile = candidates[0]
        capability_entry = self.profiles.capability(app_id, capability) or {}
        presentation = capability_entry.get("presentation", {})
        step_labels = presentation.get("steps", {})
        stack = profile["stack"]
        recommended_ids = {
            item.get("id")
            for item in self.profiles.candidates(
                app_id, capability, device, recommended=True
            )
        }
        profile_options = []
        for option in sorted(
            capability_entry.get("profiles", ()),
            key=lambda item: int(item.get("priority", 0)),
            reverse=True,
        ):
            compatible, disabled_reasons = profile_device_compatibility(option, device)
            option_stack = option.get("stack", {})
            option_model_id = option_stack.get("checkpoint", {}).get("model_id")
            if option_model_id is None and isinstance(
                option_stack.get("components"), list
            ):
                option_model_id = next(
                    (
                        component.get("model_id")
                        for component in option_stack["components"]
                        if component.get("kind") == "checkpoint"
                    ),
                    None,
                )
            option_id = str(option.get("id") or "")
            label = option.get("label")
            description = option.get("description")
            profile_options.append(
                {
                    "profileId": option_id,
                    "label": (
                        str(label).strip()[:160]
                        if isinstance(label, str) and label.strip()
                        else option_id
                    ),
                    "description": (
                        str(description).strip()[:240]
                        if isinstance(description, str) and description.strip()
                        else ""
                    ),
                    "modelId": option_model_id,
                    "compatible": compatible,
                    "recommended": compatible and option_id in recommended_ids,
                    "selected": (
                        option_id in preferred_profile_ids
                        if isinstance(preferred_profile_ids, list)
                        else option_id == profile["id"]
                    ),
                    "disabledReasons": list(disabled_reasons),
                    "minimumMemoryGiB": option.get("device", {})
                    .get("accelerator", {})
                    .get("unified_memory_gib", {})
                    .get("minimum"),
                }
            )
        selection_mode = str(capability_entry.get("selection_mode", "single"))
        if isinstance(preferred_profile_ids, list):
            return self._multi_profile_plan(
                app_id=app_id,
                capability=capability,
                requirements=requirements,
                profiles=candidates,
                presentation=presentation,
                device=device,
                profile_options=profile_options,
            )
        if isinstance(stack.get("components"), list):
            result = self._component_plan(
                app_id=app_id,
                capability=capability,
                requirements=requirements,
                profile=profile,
                presentation=presentation,
                device=device,
                profile_options=profile_options,
            )
            result["selectionMode"] = selection_mode
            return result
        runtime_fact = self._package_fact(stack["runtime"])
        provider_fact = self._package_fact(stack["provider"])
        model_id = stack["checkpoint"]["model_id"]
        model = resolve_package_model(self.runtime, model_id)
        checkpoint_ready = bool(model is not None and model.checkpoint_ready)
        steps = [
            {
                "id": "runtime",
                "title": step_labels.get("runtime", "配置推理 Runtime"),
                "status": "complete" if runtime_fact["ready"] else "pending",
                **runtime_fact,
            },
            {
                "id": "provider",
                "title": step_labels.get("provider", "安装模型 Service Package"),
                "status": "complete" if provider_fact["ready"] else "pending",
                **provider_fact,
            },
            {
                "id": "checkpoint",
                "title": step_labels.get("checkpoint", "下载模型 Checkpoint"),
                "status": "complete" if checkpoint_ready else "pending",
                "modelId": model_id,
            },
            {
                "id": "verify",
                "title": step_labels.get("verify", "启动并验证模型服务"),
                "status": "complete" if checkpoint_ready else "pending",
            },
        ]
        return {
            "schema": "ai2apps.provisioning-plan/v1",
            "appId": app_id,
            "capability": capability,
            "profileId": profile["id"],
            "requirements": requirements,
            "presentation": presentation,
            "device": device,
            "stack": stack,
            "profileOptions": profile_options,
            "selectionMode": selection_mode,
            "steps": steps,
            "reasons": [
                f"匹配 {device['accelerator']['vendor']} {device['accelerator']['api']} 设备",
                f"统一内存约 {round(device['system_memory_gib'])} GiB",
                f"App 推荐方案：{profile['id']}",
            ],
        }

    def ensure(
        self,
        *,
        actor_id: str,
        installation_id: str,
        app_instance_id: str,
        app_id: str,
        capability: str,
        action_id: str,
        requirements: dict[str, Any],
        intent: dict[str, Any],
    ) -> dict[str, Any]:
        plan = self.plan(app_id, capability, requirements)
        if plan is None:
            return {
                "status": "unsupported",
                "reasons": ["当前设备没有经过此 App 验证的本地配置方案"],
            }
        ready = self.resolve_plan_ready(plan)
        if ready is not None:
            return {"status": "ready", "provider": ready}
        request_fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "requirements": requirements,
                    "profileId": plan["profileId"],
                    "stack": plan["stack"],
                },
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        session = self.repository.create(
            actor_id=actor_id,
            installation_id=installation_id,
            app_instance_id=app_instance_id,
            app_id=app_id,
            capability=capability,
            action_id=action_id,
            status="awaiting_confirmation",
            profile_id=plan["profileId"],
            request_fingerprint=request_fingerprint,
            plan=plan,
            intent=intent,
        )
        return {
            "status": "setup_required",
            "sessionId": session["id"],
            "session": session,
        }

    def select_profile(
        self, session_id: str, profile_id: str
    ) -> dict[str, Any]:
        """Replace an unconfirmed Session with the user's compatible tier choice."""

        session = self.repository.get(session_id)
        if session is None:
            raise KeyError(session_id)
        if session["status"] != "awaiting_confirmation":
            raise ValueError("Profile can only change before confirmation")
        if session.get("profileId") == profile_id:
            return {
                "status": "setup_required",
                "sessionId": session["id"],
                "session": session,
            }
        capability = self.profiles.capability(
            session["appId"], session["capability"]
        )
        option = next(
            (
                item
                for item in (capability or {}).get("profiles", ())
                if item.get("id") == profile_id
            ),
            None,
        )
        if option is None:
            raise ValueError("Unknown capability profile")
        compatible, reasons = profile_device_compatibility(option, device_profile())
        if not compatible:
            raise ValueError("；".join(reasons) or "Profile is not compatible")
        requirements = dict(session["plan"].get("requirements", {}))
        requirements["profileId"] = profile_id
        result = self.ensure(
            actor_id=session["actorId"],
            installation_id=session["installationId"],
            app_instance_id=session["appInstanceId"],
            app_id=session["appId"],
            capability=session["capability"],
            action_id=session["actionId"],
            requirements=requirements,
            intent=session["intent"],
        )
        replacement_id = result.get("sessionId")
        if result.get("status") == "ready" or replacement_id != session_id:
            self.repository.update(
                session_id,
                status="cancelled",
                progress={"phase": "cancelled", "percent": 0},
            )
        return result

    def _start_runner(self, session_id: str) -> None:
        running = self._runners.get(session_id)
        if running is not None and not running.done():
            return
        task = asyncio.create_task(
            self._run(session_id), name=f"acpf-provision-{session_id}"
        )
        self._runners[session_id] = task
        task.add_done_callback(lambda _task: self._runners.pop(session_id, None))

    async def confirm(
        self,
        session_id: str,
        license_consents: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        session = self.repository.get(session_id)
        if session is None:
            raise KeyError(session_id)
        if session["status"] in {"ready", "cancelled", "unsupported"}:
            return session
        if license_consents:
            operations = [
                item
                for item in session["operations"]
                if item.get("kind") != "checkpointLicenseConsent"
            ]
            accepted_at = utc_now_text()
            for consent in license_consents:
                if not isinstance(consent, dict):
                    continue
                operations.append(
                    {
                        "kind": "checkpointLicenseConsent",
                        "actorId": session["actorId"],
                        "installationId": session["installationId"],
                        "acceptedAt": accepted_at,
                        "consent": dict(consent),
                    }
                )
            session = self.repository.update(
                session_id, operations=operations, clear_error=True
            )
        else:
            session = self.repository.update(session_id, clear_error=True)
        self._start_runner(session_id)
        record = self.repository.get(session_id)
        assert record is not None
        return record

    @staticmethod
    def _license_consents(
        session: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        if session is None:
            return []
        return [
            dict(item["consent"])
            for item in session.get("operations", ())
            if item.get("kind") == "checkpointLicenseConsent"
            and isinstance(item.get("consent"), dict)
        ]

    async def resume_if_possible(self, session_id: str) -> dict[str, Any] | None:
        session = self.repository.get(session_id)
        if session is None:
            return None
        if session["status"] == "awaiting_restart":
            if session["progress"].get("runtimeEpoch") != self._runtime_epoch:
                self._start_runner(session_id)
        elif session["status"] in {
            "installing_runtime",
            "installing_provider",
            "downloading_checkpoint",
            "activating",
            "verifying",
        }:
            self._start_runner(session_id)
        return session

    async def _install_package(
        self,
        session_id: str,
        descriptor: dict[str, Any],
        phase: str,
        *,
        progress_start: float | None = None,
        progress_end: float | None = None,
    ) -> bool:
        fact = self._package_fact(descriptor)
        if fact["ready"]:
            return True
        if self.runtime.registry_packages is None:
            raise RuntimeError("Discover Package Registry is not ready")
        namespace, name = descriptor["package_id"].split("/", 1)
        snapshot = await self.runtime.registry_packages.trusted_snapshot()
        specifier = SpecifierSet(descriptor["version"])
        releases = [
            item
            for item in snapshot.get("releases", ())
            if isinstance(item, dict)
            and item.get("packageId") == descriptor["package_id"]
            and item.get("status") == "published"
            and Version(str(item.get("version"))) in specifier
        ]
        if not releases:
            raise RegistryError(
                "dependency_unresolved",
                f"No published release satisfies {descriptor['package_id']} {descriptor['version']}",
            )
        selected_version = str(
            max(releases, key=lambda item: Version(str(item["version"])))["version"]
        )
        current_session = self.repository.get(session_id)
        operations = current_session["operations"]
        current_progress = current_session.get("progress", {})
        progress_start = float(
            current_progress.get("percent", 0)
            if progress_start is None
            else progress_start
        )
        progress_end = float(
            min(95, progress_start + 15)
            if progress_end is None
            else progress_end
        )
        mapped_percent = progress_start

        def progress(value: dict[str, Any]) -> None:
            nonlocal mapped_percent
            operation = {
                "kind": "package",
                "packageId": descriptor["package_id"],
                **value,
            }
            completed = value.get("bytesCompleted")
            total = value.get("bytesTotal")
            if (
                isinstance(completed, (int, float))
                and not isinstance(completed, bool)
                and isinstance(total, (int, float))
                and not isinstance(total, bool)
                and total > 0
            ):
                ratio = max(0.0, min(1.0, float(completed) / float(total)))
                mapped_percent = max(
                    mapped_percent,
                    progress_start + (progress_end - progress_start) * ratio,
                )
            self.repository.update(
                session_id,
                operations=[*operations, operation],
                progress={
                    "phase": phase,
                    "detail": value,
                    "percent": mapped_percent,
                },
            )

        await self.runtime.registry_packages.install(
            namespace,
            name,
            selected_version,
            # The Installation owner explicitly approved this signed,
            # device-recommended stack through the ACPF confirmation sheet.
            # Keep the approval scoped to this exact Registry install call;
            # Package signature, compatibility, and audit verification still
            # run normally.
            approve_review=True,
            progress=progress,
        )
        return self._package_fact(descriptor)["ready"]

    async def _install_component_checkpoint(
        self, session_id: str, component: dict[str, Any]
    ) -> None:
        model_id = component["model_id"]
        model = resolve_package_model(self.runtime, model_id)
        if model is not None and model.checkpoint_ready:
            return
        installer = self.refresh_model_installer()
        self.repository.update(
            session_id,
            status="downloading_checkpoint",
            progress={"phase": "downloading_checkpoint", "percent": 55},
        )
        task = await installer.start(
            model_id,
            "huggingface",
            "auto",
            "",
            "keep_source",
            self._license_consents(self.repository.get(session_id)),
        )
        operations = self.repository.get(session_id)["operations"]
        self.repository.update(
            session_id,
            operations=[
                *operations,
                {"kind": "checkpoint", "taskId": task.task_id, "modelId": model_id},
            ],
        )
        while task.status.value in {
            "pending",
            "downloading",
            "indexing",
            "converting",
            "configuring",
            "validating",
        }:
            current = self.repository.get(session_id)
            if current is None or current["status"] == "cancelled":
                await installer.cancel(task.task_id)
                return
            self.repository.update(
                session_id,
                progress={
                    "phase": "downloading_checkpoint",
                    "percent": 55 + task.progress * 0.35,
                    "detail": task.to_dict(),
                },
            )
            await asyncio.sleep(0.5)
        if task.status.value != "completed":
            raise RuntimeError(task.error or f"Checkpoint {task.status.value}")

    async def _run_component_stack(
        self, session_id: str, session: dict[str, Any]
    ) -> None:
        plan = session["plan"]
        components = plan["stack"]["components"]
        packages = [item for item in components if item["kind"] == "package"]
        for index, component in enumerate(packages):
            phase = component.get("phase", "provider")
            status = (
                "installing_runtime" if phase == "runtime" else "installing_provider"
            )
            percent = 5 + int(index / max(1, len(packages)) * 40)
            self.repository.update(
                session_id,
                status=status,
                progress={"phase": status, "percent": percent},
            )
            next_percent = 5 + int(
                (index + 1) / max(1, len(packages)) * 40
            )
            if not await self._install_package(
                session_id,
                component,
                status,
                progress_start=percent,
                progress_end=next_percent,
            ):
                self.repository.update(
                    session_id,
                    status="awaiting_restart",
                    progress={
                        "phase": "awaiting_restart",
                        "percent": percent,
                        "runtimeEpoch": self._runtime_epoch,
                    },
                )
                return
        for component in components:
            if component["kind"] == "checkpoint":
                await self._install_component_checkpoint(session_id, component)
        self.repository.update(
            session_id,
            status="verifying",
            progress={"phase": "verifying", "percent": 95},
        )
        await self._start_verification_services(session)
        for _ in range(60):
            ready = self.resolve_plan_ready(plan)
            if ready is not None:
                completed_plan = dict(plan)
                completed_plan["provider"] = ready
                self.repository.update(
                    session_id,
                    status="ready",
                    plan=completed_plan,
                    progress={"phase": "ready", "percent": 100},
                    clear_error=True,
                )
                return
            await asyncio.sleep(1)
        raise RuntimeError("Capability Service did not become ready after activation")

    async def _run(self, session_id: str) -> None:
        try:
            session = self.repository.get(session_id)
            if session is None or session["status"] in {"cancelled", "ready"}:
                return
            plan = session["plan"]
            stack = plan["stack"]
            if isinstance(stack.get("components"), list):
                await self._run_component_stack(session_id, session)
                return

            self.repository.update(
                session_id,
                status="installing_runtime",
                progress={"phase": "installing_runtime", "percent": 5},
            )
            runtime_ready = await self._install_package(
                session_id,
                stack["runtime"],
                "installing_runtime",
                progress_start=5,
                progress_end=20,
            )
            if not runtime_ready:
                self.repository.update(
                    session_id,
                    status="awaiting_restart",
                    progress={
                        "phase": "awaiting_restart",
                        "percent": 20,
                        "runtimeEpoch": self._runtime_epoch,
                    },
                )
                return

            self.repository.update(
                session_id,
                status="installing_provider",
                progress={"phase": "installing_provider", "percent": 25},
            )
            provider_ready = await self._install_package(
                session_id,
                stack["provider"],
                "installing_provider",
                progress_start=25,
                progress_end=40,
            )
            if not provider_ready:
                self.repository.update(
                    session_id,
                    status="awaiting_restart",
                    progress={
                        "phase": "awaiting_restart",
                        "percent": 40,
                        "runtimeEpoch": self._runtime_epoch,
                    },
                )
                return

            requirements = plan.get("requirements", {})
            ready = self.resolve_ready(
                plan["appId"],
                plan["capability"],
                requirements,
                profile_id=plan["profileId"],
            )
            if ready is None:
                installer = self.refresh_model_installer()
                model_id = stack["checkpoint"]["model_id"]
                self.repository.update(
                    session_id,
                    status="downloading_checkpoint",
                    progress={"phase": "downloading_checkpoint", "percent": 45},
                )
                task = await installer.start(
                    model_id,
                    "huggingface",
                    "auto",
                    "",
                    "keep_source",
                    self._license_consents(self.repository.get(session_id)),
                )
                operations = self.repository.get(session_id)["operations"]
                self.repository.update(
                    session_id,
                    operations=[
                        *operations,
                        {
                            "kind": "checkpoint",
                            "taskId": task.task_id,
                            "modelId": model_id,
                        },
                    ],
                )
                while task.status.value in {
                    "pending",
                    "downloading",
                    "indexing",
                    "converting",
                    "configuring",
                    "validating",
                }:
                    current = self.repository.get(session_id)
                    if current is None or current["status"] == "cancelled":
                        await installer.cancel(task.task_id)
                        return
                    self.repository.update(
                        session_id,
                        progress={
                            "phase": "downloading_checkpoint",
                            "percent": 45 + task.progress * 0.45,
                            "detail": task.to_dict(),
                        },
                    )
                    await asyncio.sleep(0.5)
                if task.status.value != "completed":
                    raise RuntimeError(task.error or f"Checkpoint {task.status.value}")

            self.repository.update(
                session_id,
                status="verifying",
                progress={"phase": "verifying", "percent": 95},
            )
            await self._start_verification_services(session)
            for _ in range(60):
                ready = self.resolve_ready(
                    plan["appId"],
                    plan["capability"],
                    requirements,
                    profile_id=plan["profileId"],
                )
                if ready is not None:
                    completed_plan = dict(plan)
                    completed_plan["provider"] = ready
                    self.repository.update(
                        session_id,
                        status="ready",
                        plan=completed_plan,
                        progress={"phase": "ready", "percent": 100},
                        clear_error=True,
                    )
                    return
                await asyncio.sleep(1)
            raise RuntimeError("Provider did not become ready after activation")
        except asyncio.CancelledError:
            raise
        except CheckpointConsentRequiredError as exc:
            self.repository.update(
                session_id,
                status="awaiting_confirmation",
                error={
                    "code": "checkpoint_license_consent_required",
                    "message": str(exc),
                    "retryable": True,
                    "challenges": list(exc.challenges),
                },
            )
        except RegistryError as exc:
            awaiting_restart = exc.code == "dependency_restart_required"
            self.repository.update(
                session_id,
                status="awaiting_restart" if awaiting_restart else "failed",
                progress=(
                    {
                        "phase": "awaiting_restart",
                        "percent": 20,
                        "runtimeEpoch": self._runtime_epoch,
                    }
                    if awaiting_restart
                    else None
                ),
                error={
                    "code": exc.code,
                    "message": str(exc),
                    "retryable": exc.code != "platform_incompatible",
                    "details": exc.details,
                },
            )
        except Exception as exc:
            self.repository.update(
                session_id,
                status="failed",
                error={
                    "code": "provisioning_failed",
                    "message": str(exc),
                    "retryable": True,
                },
            )

    async def cancel(self, session_id: str) -> dict[str, Any]:
        session = self.repository.get(session_id)
        if session is None:
            raise KeyError(session_id)
        for operation in session["operations"]:
            if (
                operation.get("kind") == "checkpoint"
                and self.model_installer is not None
            ):
                with suppress(Exception):
                    await self.model_installer.cancel(operation["taskId"])
        runner = self._runners.get(session_id)
        if runner is not None:
            runner.cancel()
        return self.repository.update(
            session_id,
            status="cancelled",
            progress={
                "phase": "cancelled",
                "percent": session["progress"].get("percent", 0),
            },
        )
