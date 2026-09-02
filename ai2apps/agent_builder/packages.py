"""P2 Site Agent Package validation, local provisioning, and export."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from packaging.version import InvalidVersion, Version

from ai2apps.core import (
    EntityIdKind,
    ResourceConflictError,
    new_entity_id,
    parse_utc,
    utc_now_text,
)
from ai2apps.extensions import UnitKind
from ai2apps.packages.contract_v1 import build_package

from .compiler import COMPILER_VERSION, compile_source
from .models import SiteAgentPackageBindingRecord
from .repository import AgentBuilderRepository, _json
from .sites import canonical_site_key, normalize_site_agent_source

WEB_AGENT_PACKAGE_SCHEMA = "ai2apps.web-agent-package/v1"
FORBIDDEN_SCRIPT_PATTERNS = (
    r"\bdocument\.cookie\b", r"\blocalStorage\b", r"\bsessionStorage\b",
    r"\bindexedDB\b", r"\bfetch\s*\(", r"\bXMLHttpRequest\b",
    r"\bWebSocket\b", r"\beval\s*\(", r"\bFunction\s*\(",
    r"\.value\b.*(?:password|otp)|(?:password|otp).*\.value\b",
)
ALLOWED_BROWSER_PERMISSIONS = frozenset({
    "browser.read", "browser.interact", "browser.automation",
    "knowledge.write", "download.read", "upload.user-selected", "model.lightweight",
    "model.advanced",
})


def _digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


def validate_web_agent_package(manifest: dict[str, Any]) -> dict[str, Any]:
    package = manifest.get("web_agent")
    if package is None:
        return {}
    if not isinstance(package, dict) or package.get("schema") != WEB_AGENT_PACKAGE_SCHEMA:
        raise ValueError(f"web_agent must use {WEB_AGENT_PACKAGE_SCHEMA}")
    source = package.get("source")
    if not isinstance(source, dict):
        raise ValueError("Web Agent Package requires an inline authoritative source")
    site_key = canonical_site_key(str(package.get("site_key") or ""))
    normalized = normalize_site_agent_source(source, site_key=site_key)
    if not site_key:
        site_key = canonical_site_key(str(normalized.get("site_key") or ""))
    if not site_key:
        raise ValueError("Web Agent Package requires one normalized website")
    if canonical_site_key(str(normalized.get("site_key") or "")) != site_key:
        raise ValueError("Package site_key and Agent Source disagree")
    permissions = package.get("permissions", [])
    if not isinstance(permissions, list) or not all(isinstance(item, str) for item in permissions):
        raise ValueError("Web Agent Package permissions must be strings")
    unknown = set(permissions) - ALLOWED_BROWSER_PERMISSIONS
    if unknown:
        raise ValueError(f"Unsupported Web Agent Package permissions: {sorted(unknown)}")
    tests = package.get("tests", [])
    if not isinstance(tests, list) or not tests:
        raise ValueError("Web Agent Package requires at least one fixture/contract test")
    result = compile_source(normalized)
    if not result.valid:
        raise ValueError("Web Agent Package source does not compile")
    serialized = json.dumps(normalized, ensure_ascii=False)
    for pattern in FORBIDDEN_SCRIPT_PATTERNS:
        if re.search(pattern, serialized, re.IGNORECASE):
            raise ValueError(f"Web Agent Package contains forbidden script access: {pattern}")
    hint = package.get("publisher_hint")
    if hint is not None and not isinstance(hint, dict):
        raise ValueError("publisher_hint must be an object")
    return {
        **package,
        "site_key": site_key,
        "source": normalized,
        "permissions": sorted(set(permissions)),
        "source_digest": result.source_digest,
        "hint_digest": None if hint is None else _digest(hint),
        "compile_report": result.report,
    }


class SiteAgentPackageService:
    def __init__(self, store: AgentBuilderRepository, extension_manager) -> None:
        self.store = store
        self.database = store.database
        self.extension_manager = extension_manager
        self.extensions = extension_manager.repository

    @staticmethod
    def _binding(row) -> SiteAgentPackageBindingRecord:
        return SiteAgentPackageBindingRecord(
            id=row["id"], owner_user_id=row["owner_user_id"], package_key=row["package_key"],
            package_version=row["package_version"], package_digest=row["package_digest"],
            publisher_id=row["publisher_id"], site_key=row["site_key"], draft_id=row["draft_id"],
            granted_permissions=tuple(json.loads(row["granted_permissions_json"])),
            source_digest=row["source_digest"], hint_digest=row["hint_digest"], status=row["status"],
            installed_at=parse_utc(row["installed_at"]), updated_at=parse_utc(row["updated_at"]),
            source=json.loads(row["source_json"]), update_policy=row["update_policy"],
            pinned_version=row["pinned_version"],
            activated_at=None if row["activated_at"] is None else parse_utc(row["activated_at"]),
        )

    def _event(
        self, connection, *, owner_user_id: str, package_key: str, action: str,
        from_digest: str | None = None, to_digest: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        connection.execute(
            """INSERT INTO agent_site_package_events(id,owner_user_id,package_key,action,
               from_digest,to_digest,details_json,created_at) VALUES(?,?,?,?,?,?,?,?)""",
            (new_entity_id(EntityIdKind.AGENT_PACKAGE_EVENT), owner_user_id, package_key,
             action, from_digest, to_digest, _json(details or {}), utc_now_text()),
        )

    def bindings_for(
        self, owner_user_id: str, package_key: str,
    ) -> tuple[SiteAgentPackageBindingRecord, ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                """SELECT * FROM agent_site_package_bindings WHERE owner_user_id=?
                   AND package_key=? AND status!='uninstalled'
                   ORDER BY installed_at DESC,id DESC""",
                (owner_user_id, package_key),
            ).fetchall()
        return tuple(self._binding(row) for row in rows)

    def active_binding(
        self, owner_user_id: str, package_key: str,
    ) -> SiteAgentPackageBindingRecord | None:
        with self.database.transaction() as connection:
            row = connection.execute(
                """SELECT * FROM agent_site_package_bindings WHERE owner_user_id=?
                   AND package_key=? AND status='active' ORDER BY updated_at DESC,id DESC LIMIT 1""",
                (owner_user_id, package_key),
            ).fetchone()
        return None if row is None else self._binding(row)

    def installed_candidates(
        self, *, owner_user_id: str, site_key: str = "", capability: str = "",
    ) -> tuple[dict[str, Any], ...]:
        normalized_site = canonical_site_key(site_key)
        result = []
        for record in self.extensions.installed(UnitKind.AGENT):
            if record.status.value == "uninstalled":
                continue
            try:
                package = validate_web_agent_package(record.manifest)
            except ValueError:
                continue
            exports = [
                str(item.get("name") or item.get("id") or "")
                for item in package["source"].get("capabilities", []) if isinstance(item, dict)
            ]
            if normalized_site and package["site_key"] != normalized_site:
                continue
            if capability and capability not in exports:
                continue
            binding = self.binding_for_digest(owner_user_id, record.unit_key, record.digest)
            result.append({
                "package_key": record.unit_key, "version": record.version, "digest": record.digest,
                "publisher_id": record.manifest.get("publisher", {}).get("id", record.publisher_key),
                "site_key": package["site_key"], "capabilities": exports,
                "permissions": package["permissions"], "tests": package.get("tests", []),
                "source_digest": package["source_digest"], "hint_digest": package["hint_digest"],
                "publisher_hint_trusted": False, "binding": None if binding is None else binding,
            })
        return tuple(result)

    def binding_for(self, owner_user_id: str, package_key: str) -> SiteAgentPackageBindingRecord | None:
        with self.database.transaction() as connection:
            row = connection.execute(
                """SELECT * FROM agent_site_package_bindings WHERE owner_user_id=? AND package_key=?
                   AND status!='uninstalled' ORDER BY updated_at DESC,id DESC LIMIT 1""",
                (owner_user_id, package_key),
            ).fetchone()
        return None if row is None else self._binding(row)

    def binding_for_digest(
        self, owner_user_id: str, package_key: str, package_digest: str,
    ) -> SiteAgentPackageBindingRecord | None:
        with self.database.transaction() as connection:
            row = connection.execute(
                """SELECT * FROM agent_site_package_bindings WHERE owner_user_id=?
                   AND package_key=? AND package_digest=? AND status!='uninstalled'""",
                (owner_user_id, package_key, package_digest),
            ).fetchone()
        return None if row is None else self._binding(row)

    @staticmethod
    def _version_key(value: str) -> tuple[int, Any]:
        try:
            return (1, Version(value))
        except InvalidVersion:
            return (0, value)

    def lifecycle(self, *, owner_user_id: str, package_key: str) -> dict[str, Any]:
        bindings = self.bindings_for(owner_user_id, package_key)
        installed = []
        binding_by_digest = {item.package_digest: item for item in bindings}
        for package in self.extensions.installed(UnitKind.AGENT, package_key):
            binding = binding_by_digest.get(package.digest)
            installed.append({
                "package_key": package.unit_key, "version": package.version,
                "digest": package.digest, "package_status": package.status.value,
                "binding": None if binding is None else binding,
            })
        installed.sort(key=lambda item: self._version_key(item["version"]), reverse=True)
        active = next((item for item in bindings if item.status == "active"), None)
        with self.database.transaction() as connection:
            event_rows = connection.execute(
                """SELECT * FROM agent_site_package_events WHERE owner_user_id=?
                   AND package_key=? ORDER BY created_at DESC,id DESC LIMIT 50""",
                (owner_user_id, package_key),
            ).fetchall()
        events = [
            {
                "id": row["id"], "action": row["action"],
                "from_digest": row["from_digest"], "to_digest": row["to_digest"],
                "details": json.loads(row["details_json"]), "created_at": row["created_at"],
            }
            for row in event_rows
        ]
        return {
            "package_key": package_key,
            "active_binding": active,
            "update_policy": "manual" if active is None else active.update_policy,
            "pinned_version": None if active is None else active.pinned_version,
            "versions": installed,
            "events": events,
        }

    def set_policy(
        self, *, owner_user_id: str, package_key: str, update_policy: str,
        pinned_version: str | None,
    ) -> SiteAgentPackageBindingRecord:
        if update_policy not in {"manual", "pinned"}:
            raise ValueError("Unsupported Site Agent update policy")
        active = self.active_binding(owner_user_id, package_key)
        if active is None:
            raise ResourceConflictError("Site Agent Package has no active binding")
        normalized_pin = (pinned_version or "").strip() or None
        if update_policy == "pinned":
            normalized_pin = normalized_pin or active.package_version
            if not any(item.package_version == normalized_pin for item in self.bindings_for(owner_user_id, package_key)):
                raise ResourceConflictError("Pinned Site Agent version is not installed")
        else:
            normalized_pin = None
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """UPDATE agent_site_package_bindings SET update_policy=?,pinned_version=?,
                   updated_at=? WHERE owner_user_id=? AND package_key=?""",
                (update_policy, normalized_pin, now, owner_user_id, package_key),
            )
            self._event(
                connection, owner_user_id=owner_user_id, package_key=package_key,
                action="policy_changed", to_digest=active.package_digest,
                details={"update_policy": update_policy, "pinned_version": normalized_pin},
            )
            row = connection.execute(
                "SELECT * FROM agent_site_package_bindings WHERE id=?", (active.id,)
            ).fetchone()
        return self._binding(row)

    def provision(
        self, *, owner_user_id: str, package_key: str, granted_permissions: list[str],
        expected_digest: str | None = None, activate: bool = False,
    ) -> tuple[SiteAgentPackageBindingRecord, Any, Any]:
        record = self.extensions.active_package(UnitKind.AGENT, package_key)
        if record is None:
            raise ResourceConflictError("Site Agent Package is not installed and active")
        if expected_digest and expected_digest != record.digest:
            raise ResourceConflictError("Installed Site Agent Package digest changed")
        package = validate_web_agent_package(record.manifest)
        if not package:
            raise ResourceConflictError("Installed Agent is not a Site Agent Package")
        granted = set(granted_permissions)
        required = set(package["permissions"])
        if not required.issubset(granted):
            raise ResourceConflictError(
                f"Package permissions require explicit grant: {sorted(required - granted)}"
            )
        source = deepcopy(package["source"])
        source["provenance"] = {
            **(source.get("provenance") if isinstance(source.get("provenance"), dict) else {}),
            "package_key": record.unit_key, "package_version": record.version,
            "package_digest": record.digest, "publisher_id": record.manifest.get("publisher", {}).get("id", record.publisher_key),
            "publisher_hint_trusted": False,
        }
        prior_active = self.active_binding(owner_user_id, record.unit_key)
        binding = self.binding_for(owner_user_id, record.unit_key)
        draft = None if binding is None else self.store.get_draft(binding.draft_id, owner_user_id)
        if draft is None:
            existing = self.store.find_site_agent(owner_user_id, package["site_key"])
            if existing is not None:
                raise ResourceConflictError(
                    "A local Site Agent already owns this website; merge or archive it explicitly"
                )
            draft = self.store.create_draft(
                owner_user_id=owner_user_id,
                name=str(source.get("name") or f"{package['site_key']} Agent"),
                description=str(source.get("description") or record.manifest.get("description") or ""),
                site_scope=list(source.get("site_scope") or []), source=source,
            )
        else:
            draft = self.store.update_draft(
                draft.id, owner_user_id, expected_revision=draft.revision,
                name=str(source.get("name") or draft.name),
                description=str(source.get("description") or draft.description),
                site_scope=list(source.get("site_scope") or []), source=source,
            )
        compiled = compile_source(source)
        generation = self.store.create_generation(
            draft, source_digest=compiled.source_digest, compiler_version=COMPILER_VERSION,
            policy_version=str(compiled.report.get("policy_version") or "agent-builder-policy-p0/1"),
            ir=compiled.ir,
            report={**compiled.report, "package_digest": record.digest, "publisher_hint_executed": False,
                    "calibration_required": True}, valid=compiled.valid,
        )
        if not compiled.valid:
            raise ResourceConflictError("Locally compiled Package source failed validation")
        replacing_digest = binding is not None and binding.package_digest != record.digest
        if binding is None or replacing_digest:
            binding_id = new_entity_id(EntityIdKind.AGENT_PACKAGE_BINDING)
            installed_at = utc_now_text()
        else:
            binding_id = binding.id
            installed_at = binding.installed_at.isoformat(timespec="microseconds").replace("+00:00", "Z")
        now = utc_now_text()
        status = (
            "active"
            if activate or binding is None or (
                prior_active is not None and prior_active.package_digest == record.digest
            )
            else "installed"
        )
        update_policy = "manual" if prior_active is None else prior_active.update_policy
        pinned_version = None if prior_active is None else prior_active.pinned_version
        activated_at = now if status == "active" else None
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """INSERT INTO agent_site_package_bindings(id,owner_user_id,package_key,package_version,
                   package_digest,publisher_id,site_key,draft_id,granted_permissions_json,source_digest,
                   hint_digest,status,installed_at,updated_at,source_json,update_policy,
                   pinned_version,activated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(owner_user_id,package_key,package_digest) DO UPDATE SET
                   draft_id=excluded.draft_id,granted_permissions_json=excluded.granted_permissions_json,
                   source_digest=excluded.source_digest,hint_digest=excluded.hint_digest,
                   status=excluded.status,updated_at=excluded.updated_at,
                   source_json=excluded.source_json,update_policy=excluded.update_policy,
                   pinned_version=excluded.pinned_version,activated_at=excluded.activated_at""",
                (binding_id, owner_user_id, record.unit_key, record.version, record.digest,
                 record.manifest.get("publisher", {}).get("id", record.publisher_key), package["site_key"],
                 draft.id, _json(sorted(granted)), compiled.source_digest, package["hint_digest"],
                 status, installed_at, now, _json(source), update_policy, pinned_version,
                 activated_at),
            )
            if status == "active":
                connection.execute(
                    """UPDATE agent_site_package_bindings SET status='retained',updated_at=?
                       WHERE owner_user_id=? AND package_key=? AND package_digest!=?
                       AND status='active'""",
                    (now, owner_user_id, record.unit_key, record.digest),
                )
            self._event(
                connection, owner_user_id=owner_user_id, package_key=record.unit_key,
                action="installed" if binding is None else "candidate_created",
                from_digest=None if prior_active is None else prior_active.package_digest,
                to_digest=record.digest,
                details={"version": record.version, "activated": status == "active"},
            )
            row = connection.execute(
                """SELECT * FROM agent_site_package_bindings WHERE owner_user_id=?
                   AND package_key=? AND package_digest=?""",
                (owner_user_id, record.unit_key, record.digest),
            ).fetchone()
        if activate or binding is None:
            self.extension_manager.activate_version(UnitKind.AGENT, record.unit_key, record.digest)
            draft = self.store.activate_generation(draft.id, generation.id, owner_user_id)
        elif prior_active is not None and prior_active.package_digest != record.digest:
            self.extension_manager.activate_version(
                UnitKind.AGENT, record.unit_key, prior_active.package_digest
            )
        return self._binding(row), draft, generation

    def activate_binding(
        self, *, owner_user_id: str, package_key: str, package_digest: str,
        rollback: bool = False,
    ) -> tuple[SiteAgentPackageBindingRecord, Any, Any]:
        bindings = self.bindings_for(owner_user_id, package_key)
        target = next((item for item in bindings if item.package_digest == package_digest), None)
        if target is None:
            raise ResourceConflictError("Site Agent Package version is not provisioned")
        active = next((item for item in bindings if item.status == "active"), None)
        policy = target.update_policy if active is None else active.update_policy
        pinned = target.pinned_version if active is None else active.pinned_version
        if policy == "pinned" and pinned and target.package_version != pinned:
            raise ResourceConflictError(
                f"Site Agent Package is pinned to version {pinned}"
            )
        generations = self.store.list_generations(target.draft_id, owner_user_id)
        generation = next(
            (item for item in generations if item.report.get("package_digest") == package_digest),
            None,
        )
        if generation is None:
            raise ResourceConflictError("Package generation is unavailable for activation")
        package = self.extensions.package(package_digest)
        validated = validate_web_agent_package(package.manifest)
        source = target.source or validated["source"]
        draft = self.store.get_draft(target.draft_id, owner_user_id)
        if draft.source != source:
            draft = self.store.update_draft(
                draft.id, owner_user_id, expected_revision=draft.revision,
                name=str(source.get("name") or draft.name),
                description=str(source.get("description") or draft.description),
                site_scope=list(source.get("site_scope") or []), source=source,
            )
        self.extension_manager.activate_version(UnitKind.AGENT, package_key, package_digest)
        draft = self.store.activate_generation(draft.id, generation.id, owner_user_id)
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """UPDATE agent_site_package_bindings SET status=CASE WHEN package_digest=?
                   THEN 'active' ELSE 'retained' END,update_policy=?,pinned_version=?,
                   activated_at=CASE WHEN package_digest=? THEN ? ELSE activated_at END,
                   updated_at=? WHERE owner_user_id=? AND package_key=?""",
                (package_digest, policy, pinned, package_digest, now, now,
                 owner_user_id, package_key),
            )
            self._event(
                connection, owner_user_id=owner_user_id, package_key=package_key,
                action="rolled_back" if rollback else "activated",
                from_digest=None if active is None else active.package_digest,
                to_digest=package_digest,
                details={"version": target.package_version},
            )
            row = connection.execute(
                "SELECT * FROM agent_site_package_bindings WHERE id=?", (target.id,)
            ).fetchone()
        return self._binding(row), draft, generation

    def rollback(
        self, *, owner_user_id: str, package_key: str, package_digest: str | None = None,
    ) -> tuple[SiteAgentPackageBindingRecord, Any, Any]:
        bindings = self.bindings_for(owner_user_id, package_key)
        active = next((item for item in bindings if item.status == "active"), None)
        candidates = [item for item in bindings if item.status == "retained"]
        if package_digest:
            candidates = [item for item in candidates if item.package_digest == package_digest]
        if not candidates:
            raise ResourceConflictError("No retained Site Agent Package version is available")
        target = max(candidates, key=lambda item: item.updated_at)
        if active is not None and active.update_policy == "pinned":
            # Rollback is explicit; retain pin semantics but move the pin to the chosen version.
            self.set_policy(
                owner_user_id=owner_user_id, package_key=package_key,
                update_policy="pinned", pinned_version=target.package_version,
            )
        return self.activate_binding(
            owner_user_id=owner_user_id, package_key=package_key,
            package_digest=target.package_digest, rollback=True,
        )

    def export_source(
        self, *, owner_user_id: str, draft_id: str, root: Path, package_id: str,
        version: str, publisher_id: str,
    ) -> dict[str, str]:
        draft = self.store.get_draft(draft_id, owner_user_id)
        generation = None if not draft.active_generation_id else self.store.get_generation(
            draft.active_generation_id, owner_user_id
        )
        package_root = root / f"{package_id.replace('/', '-')}-{version}"
        package_root.mkdir(parents=True, exist_ok=True)
        agent_definition = {
            "schema": "ai2apps.agent/v1", "id": package_id.replace("/", "."),
            "name": draft.name, "description": draft.description, "version": version,
            "publisher": {"id": publisher_id}, "executor": {"key": "builtin:browser-builder-runtime"},
            "discoverable": True,
            "runtime": {"max_steps": 100, "timeout_seconds": 86400, "resume_policy": "restart"},
            "invocation_schema": {"type": "object", "properties": {}},
            "web_agent": {
                "schema": WEB_AGENT_PACKAGE_SCHEMA, "site_key": draft.site_key,
                "source": draft.source,
                "permissions": sorted({
                    "browser.read",
                    *("browser.interact" for capability in draft.source.get("capabilities", [])
                      if any(str(step.get("operation") or "") in {"click", "input", "hover", "scroll", "drag"}
                             for step in capability.get("steps", []) if isinstance(step, dict))),
                }),
                "tests": draft.source.get("fixtures") or [{"name": "compile-contract", "kind": "compile"}],
                "publisher_hint": None if generation is None else generation.ir,
            },
        }
        (package_root / "agent.yaml").write_text(json.dumps(agent_definition, ensure_ascii=False, indent=2) + "\n")
        (package_root / "LICENSE.txt").write_text("All rights reserved by the Publisher.\n")
        sbom = {
            "spdxVersion": "SPDX-2.3", "SPDXID": "SPDXRef-DOCUMENT",
            "name": f"{package_id}-{version}", "dataLicense": "CC0-1.0",
            "documentNamespace": f"https://ai2apps.local/spdx/{package_id}/{version}",
            "creationInfo": {"created": "2026-08-29T00:00:00Z", "creators": ["Tool: AI2Apps Agent Studio"]},
            "packages": [],
        }
        meta = package_root / "META"
        meta.mkdir(exist_ok=True)
        (meta / "sbom.spdx.json").write_text(json.dumps(sbom, indent=2) + "\n")
        manifest = {
            "schemaVersion": "ai2apps.package-manifest.v1",
            "package": {
                "id": package_id, "type": "agent", "version": version,
                "displayName": draft.name, "description": draft.description,
                "license": {"name": "Proprietary", "spdx": "LicenseRef-Proprietary",
                            "path": "LICENSE.txt", "url": "https://ai2apps.com/terms"},
            },
            "compatibility": {"ai2apps": ">=0.1.0"},
            "entrypoints": [{"name": "main", "kind": "agent", "path": "agent.yaml"}],
            "permissions": [
                {"capability": item, "reason": "Required by the signed Site Agent Source", "required": True}
                for item in agent_definition["web_agent"]["permissions"]
            ],
            "dependencies": [], "files": [],
            "sbom": {"format": "spdx-json-2.3", "path": "META/sbom.spdx.json"},
        }
        (package_root / "ai2apps.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        artifact = root / f"{package_id.replace('/', '-')}-{version}.ai2agent"
        inspected = build_package(package_root, artifact)
        return {"source": str(package_root), "artifact": str(artifact), "sha256": inspected.sha256}
