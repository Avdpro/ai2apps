"""Transactional Agent/App package, Effective definition, Patch, and App runtime manager."""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import os
import shutil
import tempfile
import zipfile
from contextlib import suppress
from pathlib import Path, PurePosixPath

import yaml

from ai2apps.agents import AgentRepository
from ai2apps.core import (
    AppInstanceMode,
    AppInstanceStatus,
    EntityIdKind,
    ResourceConflictError,
    ResourceNotFoundError,
    SessionKind,
    SingletonScope,
    new_entity_id,
    utc_now_text,
)
from ai2apps.events import EventStore
from ai2apps.packages import PackageFile, PackageRepository, package_digest
from ai2apps.storage import PlatformDatabase
from ai2apps.storage.repositories import AppRepository, SessionRepository

from .archive import InteractiveArchive
from .models import (
    ExtensionError,
    InteractivePackageStatus,
    PatchStatus,
    UnitKind,
)
from .patching import canonical_digest, compose
from .repository import ExtensionRepository, _json
from .signing import DeviceSigner, InteractiveTrustVerifier


class InteractivePackageManager:
    def __init__(
        self,
        database: PlatformDatabase,
        events: EventStore,
        root: Path,
        publishers: PackageRepository,
        agents: AgentRepository,
    ) -> None:
        self.database = database
        self.events = events
        self.root = root / "interactive"
        self.repository = ExtensionRepository(database, events)
        self.agents = agents
        self.apps = AppRepository(database, events)
        self.sessions = SessionRepository(database, events)
        self.device = DeviceSigner(root)
        self.trust = InteractiveTrustVerifier(publishers, self.device)
        self._lock = asyncio.Lock()
        self._auditor = None

    def bind_local_ai_auditor(self, auditor) -> None:
        self._auditor = auditor

    async def _audit(self, bundle) -> dict:
        source: dict[str, str] = {}
        remaining = 2 * 1024 * 1024
        with zipfile.ZipFile(bundle.archive_path) as archive:
            for item in bundle.files:
                if remaining <= 0:
                    break
                if not item.path.lower().endswith(
                    (".py", ".js", ".mjs", ".ts", ".tsx", ".html", ".css", ".json")
                ):
                    continue
                content = archive.read(item.path)[:remaining]
                remaining -= len(content)
                source[item.path] = content.decode("utf-8", "replace")
        if self._auditor is None:
            return {
                "decision": "review",
                "risk": "medium",
                "issuer": "ai2apps:interactive-static-gate",
                "evidence": {
                    "reason": "local_ai_auditor_not_configured",
                    "source_files_reviewed": sorted(source),
                },
            }
        request = {
            "schema": "ai2apps.interactive-audit/v1",
            "kind": str(bundle.kind),
            "key": bundle.key,
            "version": bundle.version,
            "digest": bundle.digest,
            "manifest": bundle.manifest,
            "files": [item.path for item in bundle.files],
            "sbom": bundle.sbom,
            "source": source,
        }
        try:
            result = self._auditor(request)
            if inspect.isawaitable(result):
                result = await result
        except Exception as error:
            raise ExtensionError(
                "audit_failed_closed", "Local AI audit failed"
            ) from error
        if not isinstance(result, dict) or result.get("decision") not in {
            "approve",
            "review",
            "reject",
        }:
            raise ExtensionError(
                "invalid_audit", "Local AI audit returned invalid output"
            )
        if result["decision"] == "reject" or result.get("risk") == "critical":
            raise ExtensionError(
                "audit_rejected", "Local AI audit rejected the package"
            )
        return result

    def inspect(self, path):
        bundle = InteractiveArchive.inspect(path)
        verification = self.trust.verify(bundle)
        return bundle, verification

    @staticmethod
    def _readonly(root: Path):
        for path in sorted(root.rglob("*"), reverse=True):
            path.chmod(0o555 if path.is_dir() else 0o444)
        root.chmod(0o555)

    def _store(self, bundle):
        final = (
            self.root
            / str(bundle.kind)
            / bundle.key
            / bundle.version
            / bundle.digest.removeprefix("sha256:")
        )
        if final.exists():
            return final, False
        self.root.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix="interactive-", dir=self.root.parent))
        payload = staging / "payload"
        payload.mkdir()
        try:
            with zipfile.ZipFile(bundle.archive_path) as archive:
                archive.extractall(payload)
            shutil.copy2(
                bundle.archive_path, payload / f"package{bundle.archive_path.suffix}"
            )
            final.parent.mkdir(parents=True, exist_ok=True)
            os.replace(payload, final)
            self._readonly(final)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        return final, True

    async def install(self, path, *, approve_review=False):
        async with self._lock:
            bundle, verification = self.inspect(path)
            return await self._install_verified_bundle(
                bundle, verification, approve_review=approve_review
            )

    async def install_verified_bundle(
        self, bundle, verification: dict, *, approve_review=False
    ):
        """Install a bundle authenticated by an external trust contract.

        AI2Apps Cloud v1 uses detached signatures and signed repository
        metadata.  The registry verifier calls this boundary only after those
        checks and after adapting ``ai2apps.json`` to an effective App/Agent
        definition.  Local audit and transactional activation still run here.
        """

        async with self._lock:
            return await self._install_verified_bundle(
                bundle, verification, approve_review=approve_review
            )

    async def _install_verified_bundle(
        self, bundle, verification: dict, *, approve_review=False
    ):
            audit = await self._audit(bundle)
            if bundle.kind == "patch":
                return await self.install_patch_bundle(
                    bundle, verification, audit, approve_review
                )
            if audit.get("decision") == "review" and not approve_review:
                raise ExtensionError(
                    "audit_review_required",
                    "Interactive package requires explicit local review",
                )
            for old in self.repository.installed(bundle.kind, bundle.key):
                if old.version == bundle.version and old.digest != bundle.digest:
                    raise ExtensionError(
                        "version_digest_conflict",
                        "Same version already has another digest",
                    )
            operation_id = self.repository.begin_operation(
                bundle.kind,
                bundle.key,
                "upgrade"
                if self.repository.active_package(bundle.kind, bundle.key)
                else "install",
                {"digest": bundle.digest, "version": bundle.version},
            )
            try:
                store, created = self._store(bundle)
                record = self.repository.record_package(
                    bundle,
                    str(store),
                    {
                        "signature": verification,
                        "audit": {**audit, "approved": approve_review},
                    },
                )
            except BaseException as error:
                self.repository.settle_operation(
                    operation_id,
                    "failed",
                    {"code": getattr(error, "code", "storage_failed")},
                )
                raise
            prior = self.repository.active_package(bundle.kind, bundle.key)
            prior_effective = self.repository.effective(bundle.kind, bundle.key)
            try:
                effective = self._assemble(record)
                if bundle.kind is UnitKind.AGENT:
                    self._activate_agent(record, effective)
                else:
                    self._activate_app(record, effective)
                self.repository.activate_package(record)
                self.repository.settle_operation(operation_id, "completed")
                return self.repository.active_package(bundle.kind, bundle.key)
            except BaseException as error:
                if prior_effective is not None:
                    with suppress(Exception):
                        self._restore_effective(prior_effective)
                if (
                    isinstance(error, ExtensionError)
                    and error.code == "patch_rebase_conflict"
                ):
                    self.repository.set_package_status(
                        record.digest, InteractivePackageStatus.CONFLICTED
                    )
                    self.repository.settle_operation(
                        operation_id,
                        "rolled_back",
                        {"code": error.code, "details": error.details},
                    )
                    raise
                if created:
                    self._remove(store)
                    with self.database.transaction(write=True) as connection:
                        connection.execute(
                            "UPDATE interactive_packages SET status='uninstalled' WHERE package_digest=?",
                            (record.digest,),
                        )
                if prior is not None:
                    with suppress(Exception):
                        self.repository.activate_package(prior)
                self.repository.settle_operation(
                    operation_id,
                    "rolled_back",
                    {"code": getattr(error, "code", "activation_failed")},
                )
                raise

    def activate_candidate(self, digest: str):
        record = self.repository.package(digest)
        if record.status not in {
            InteractivePackageStatus.INSTALLED,
            InteractivePackageStatus.CONFLICTED,
            InteractivePackageStatus.RETAINED,
        }:
            raise ExtensionError("candidate_unavailable", "Package is not activatable")
        prior_effective = self.repository.effective(record.kind, record.unit_key)
        try:
            effective = self._assemble(record)
            if record.kind is UnitKind.AGENT:
                self._activate_agent(record, effective)
            else:
                self._activate_app(record, effective)
            return self.repository.activate_package(record)
        except BaseException:
            if prior_effective is not None:
                with suppress(Exception):
                    self._restore_effective(prior_effective)
            raise

    def _restore_effective(self, effective):
        return self.repository.activate_effective(
            kind=effective.kind,
            key=effective.unit_key,
            upstream=effective.upstream_digest,
            patch_set=effective.patch_set_digest,
            digest=effective.effective_digest,
            version=effective.effective_version,
            manifest=effective.manifest,
            resources=effective.resources,
            audit=effective.audit,
        )

    def _assemble(self, record):
        patches = self.repository.patches(
            record.kind, record.unit_key, enabled_only=True
        )
        manifest, resources, conflicts = compose(
            record.manifest, patches, record.digest
        )
        if conflicts:
            for conflict in conflicts:
                self.repository.set_patch(
                    conflict["patch_id"], PatchStatus.CONFLICTED, conflict=conflict
                )
            raise ExtensionError(
                "patch_rebase_conflict",
                "Local Patch cannot be safely rebased",
                details={"conflicts": conflicts},
            )
        patch_set = canonical_digest([patch.digest for patch in patches])
        effective_digest = canonical_digest(
            {
                "upstream": record.digest,
                "patches": patch_set,
                "manifest": manifest,
                "resources": resources,
            }
        )
        version = record.version + (f"+local.{len(patches)}" if patches else "")
        from .patching import target_value

        for patch in patches:
            for test in patch.tests:
                if test.get("kind", "semantic-equals") != "semantic-equals":
                    raise ExtensionError(
                        "unsupported_patch_test", "Unsupported Patch test"
                    )
                if target_value(manifest, str(test.get("target", ""))) != test.get(
                    "equals"
                ):
                    self.repository.set_patch(patch.id, PatchStatus.FAILED_TESTS)
                    raise ExtensionError(
                        "patch_tests_failed",
                        "Effective definition failed Patch tests",
                    )
        return self.repository.activate_effective(
            kind=record.kind,
            key=record.unit_key,
            upstream=record.digest,
            patch_set=patch_set,
            digest=effective_digest,
            version=version,
            manifest=manifest,
            resources=resources,
            audit={"composition": "approved"},
        )

    def _activate_agent(self, record, effective):
        m = effective.manifest
        executor = m["executor"]["key"]
        now = utc_now_text()
        concurrency = m.get("runtime", {}).get("concurrency", {})
        group = concurrency.get("group")
        limit = concurrency.get("limit")
        with self.database.transaction(write=True) as c:
            if group:
                existing = c.execute(
                    "SELECT concurrency_limit FROM agent_concurrency_groups WHERE group_key=?",
                    (group,),
                ).fetchone()
                if existing is None:
                    c.execute(
                        "INSERT INTO agent_concurrency_groups VALUES(?,?,?,?)",
                        (group, int(limit or 1), now, now),
                    )
                elif existing[0] != int(limit or 1):
                    raise ResourceConflictError(
                        "Agent concurrency group limit conflict"
                    )
            row = c.execute(
                "SELECT id,executor_key FROM agent_definitions WHERE agent_key=?",
                (record.unit_key,),
            ).fetchone()
            values = (
                record.version,
                str(m.get("name", record.unit_key)),
                str(m.get("description", "")),
                executor,
                group,
                str(m.get("runtime", {}).get("resume_policy", "restart")),
                int(m.get("runtime", {}).get("max_steps", 20)),
                int(m.get("runtime", {}).get("timeout_seconds", 300)),
                _json(m),
                record.digest,
                effective.effective_digest,
                now,
            )
            if row is None:
                c.execute(
                    """INSERT INTO agent_definitions(id,agent_key,package_version,display_name,description,
                    source,status,executor_key,concurrency_group,resume_policy,max_steps,timeout_seconds,
                    manifest_json,upstream_digest,effective_digest,created_at,updated_at)
                    VALUES(?,?,?,?,?,'installed','enabled',?,?,?,?,?,?,?,?,?,?)""",
                    (
                        new_entity_id(EntityIdKind.AGENT_DEFINITION),
                        record.unit_key,
                        *values[:-1],
                        now,
                        now,
                    ),
                )
            else:
                if row["executor_key"] != executor:
                    raise ExtensionError(
                        "executor_change_denied", "Upgrade cannot change bound executor"
                    )
                c.execute(
                    """UPDATE agent_definitions SET package_version=?,display_name=?,description=?,
                    executor_key=?,concurrency_group=?,resume_policy=?,max_steps=?,timeout_seconds=?,manifest_json=?,
                    upstream_digest=?,effective_digest=?,status='enabled',revision=revision+1,updated_at=? WHERE agent_key=?""",
                    (*values, record.unit_key),
                )

    def _activate_app(self, record, effective):
        m = effective.manifest
        instances = m.get("instances", {})
        mode = AppInstanceMode(instances.get("mode", "multiple"))
        scope = (
            None
            if mode is AppInstanceMode.MULTIPLE
            else SingletonScope(instances.get("scope", "system"))
        )
        active = self._active_app_definition(record.unit_key)
        existing_instances = [] if active is None else self._instances(active["id"])
        if (
            active
            and (
                active["instance_mode"] != mode.value
                or active["singleton_scope"] != (None if scope is None else scope.value)
            )
            and existing_instances
        ):
            raise ExtensionError(
                "instance_policy_conflict",
                "Cannot change App instance policy while instances exist",
            )
        migrated = self._migrate_states(existing_instances, active, effective)
        now = utc_now_text()
        with self.database.transaction(write=True) as c:
            target_definition = c.execute(
                "SELECT id FROM app_definitions WHERE package_id=? AND effective_digest=?",
                (record.unit_key, effective.effective_digest),
            ).fetchone()
            definition_id = (
                new_entity_id(EntityIdKind.APP_DEFINITION)
                if target_definition is None
                else target_definition["id"]
            )
            c.execute(
                "UPDATE app_definitions SET status='disabled',revision=revision+1,updated_at=? WHERE package_id=? AND status='enabled'",
                (now, record.unit_key),
            )
            if target_definition is None:
                c.execute(
                    """INSERT INTO app_definitions(id,package_id,package_version,display_name,instance_mode,
                    singleton_scope,source,status,manifest_schema_version,manifest_json,upstream_digest,effective_digest,
                    created_at,updated_at) VALUES(?,?,?,?,?,?,'installed','enabled',1,?,?,?,?,?)""",
                    (
                        definition_id,
                        record.unit_key,
                        effective.effective_version,
                        str(m.get("name", record.unit_key)),
                        mode.value,
                        None if scope is None else scope.value,
                        _json(m),
                        record.digest,
                        effective.effective_digest,
                        now,
                        now,
                    ),
                )
            else:
                c.execute(
                    "UPDATE app_definitions SET status='enabled',revision=revision+1,"
                    "manifest_json=?,upstream_digest=?,updated_at=? WHERE id=?",
                    (_json(m), record.digest, now, definition_id),
                )
            for instance, state, version in migrated:
                c.execute(
                    "INSERT INTO app_state_snapshots VALUES(?,?,?,?,?,?,?)",
                    (
                        new_entity_id(EntityIdKind.APP_STATE_SNAPSHOT),
                        instance["id"],
                        active["effective_digest"],
                        instance["state_schema_version"],
                        instance["state_json"],
                        "pre-upgrade",
                        now,
                    ),
                )
                c.execute(
                    "UPDATE app_instances SET app_definition_id=?,state_schema_version=?,state_json=?,revision=revision+1,updated_at=? WHERE id=?",
                    (definition_id, version, _json(state), now, instance["id"]),
                )

    def _active_app_definition(self, key):
        with self.database.transaction() as c:
            return c.execute(
                "SELECT * FROM app_definitions WHERE package_id=? AND status='enabled' ORDER BY created_at DESC LIMIT 1",
                (key,),
            ).fetchone()

    def _instances(self, definition_id):
        with self.database.transaction() as c:
            return c.execute(
                "SELECT * FROM app_instances WHERE app_definition_id=? AND status!='closed'",
                (definition_id,),
            ).fetchall()

    def _migrate_states(self, instances, active, effective):
        target = int(effective.manifest.get("state", {}).get("version", 1))
        result = []
        for row in instances:
            state = json.loads(row["state_json"])
            current = row["state_schema_version"]
            if current != target:
                migration = next(
                    (
                        x
                        for x in effective.manifest.get("migrations", [])
                        if x.get("from") == current and x.get("to") == target
                    ),
                    None,
                )
                if migration is None:
                    raise ExtensionError(
                        "state_migration_missing",
                        f"No state migration {current}->{target}",
                    )
                for operation in migration.get("operations", []):
                    from .patching import apply_operation

                    apply_operation(state, operation)
            result.append((row, state, target))
        return result

    async def install_patch_bundle(self, bundle, verification, audit, approve_review):
        if audit.get("decision") == "review" and not approve_review:
            raise ExtensionError(
                "audit_review_required", "Local Patch requires explicit review"
            )
        active = self.repository.active_package(
            UnitKind(bundle.manifest["target"]["kind"]), bundle.key
        )
        if active is None:
            raise ExtensionError(
                "patch_target_not_installed", "Patch target is not installed"
            )
        operation_id = self.repository.begin_operation(
            active.kind,
            active.unit_key,
            "patch",
            {
                "patch_digest": bundle.digest,
                "base_digest": bundle.manifest["base_digest"],
            },
        )
        store, created = self._store(bundle)
        patch = self.repository.record_patch(
            bundle,
            str(store),
            {"signature": verification, "audit": audit},
        )
        prior_effective = self.repository.effective(active.kind, active.unit_key)
        try:
            effective = self._assemble(active)
            if active.kind is UnitKind.AGENT:
                self._activate_agent(active, effective)
            else:
                self._activate_app(active, effective)
            self.repository.settle_operation(operation_id, "completed")
            return patch
        except BaseException as error:
            if prior_effective is not None:
                with suppress(Exception):
                    self._restore_effective(prior_effective)
            if created:
                self.repository.set_patch(
                    patch.id,
                    PatchStatus.CONFLICTED,
                    conflict={"code": "activation_failed"},
                )
            self.repository.settle_operation(
                operation_id,
                "rolled_back",
                {"code": getattr(error, "code", "patch_activation_failed")},
            )
            raise

    def resolve_patch(self, patch_id, resolution, *, candidate_digest=None):
        with self.database.transaction() as c:
            row = c.execute(
                "SELECT * FROM local_patches WHERE id=?", (patch_id,)
            ).fetchone()
        if row is None:
            raise ResourceNotFoundError("local_patch", patch_id)
        kind = UnitKind(row["target_kind"])
        active = self.repository.active_package(kind, row["target_key"])
        if active is None:
            raise ExtensionError(
                "patch_target_not_installed", "Patch target is not active"
            )
        if resolution in {"disable", "accept-upstream"}:
            status = (
                PatchStatus.DISABLED
                if resolution == "disable"
                else PatchStatus.SUPERSEDED
            )
            return self.repository.set_patch(patch_id, status, conflict=None)
        if resolution == "preserve-local":
            base_digest = candidate_digest or active.digest
            candidate = self.repository.package(base_digest)
            if candidate.kind is not kind or candidate.unit_key != row["target_key"]:
                raise ExtensionError(
                    "invalid_rebase_candidate", "Candidate does not match Patch target"
                )
            return self.repository.set_patch(
                patch_id, PatchStatus.REBASED, conflict=None, base_digest=base_digest
            )
        raise ExtensionError("invalid_patch_resolution", "Unknown Patch resolution")

    def resolve_patch_and_activate(
        self, patch_id, resolution, *, candidate_digest=None
    ) -> dict:
        """Resolve one Patch conflict and apply the resulting effective definition.

        Upgrade conflicts intentionally leave the new package installed with a
        ``conflicted`` status.  System Control uses this operation so that the
        user's decision is not merely bookkeeping: once every conflicting Patch
        has a decision, the retained candidate is assembled and activated.  If
        other Patch conflicts remain, their conflict records are preserved and
        the candidate remains recoverable for the next decision.
        """
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT target_kind,target_key FROM local_patches WHERE id=?",
                (patch_id,),
            ).fetchone()
        if row is None:
            raise ResourceNotFoundError("local_patch", patch_id)
        kind = UnitKind(row["target_kind"])
        key = row["target_key"]
        candidate = None
        if candidate_digest:
            candidate = self.repository.package(candidate_digest)
            if candidate.kind is not kind or candidate.unit_key != key:
                raise ExtensionError(
                    "invalid_rebase_candidate",
                    "Candidate does not match Patch target",
                )
        else:
            candidate = next(
                (
                    package
                    for package in self.repository.installed(kind, key)
                    if package.status is InteractivePackageStatus.CONFLICTED
                ),
                None,
            )
        resolved = self.resolve_patch(
            patch_id,
            resolution,
            candidate_digest=None if candidate is None else candidate.digest,
        )
        target = candidate or self.repository.active_package(kind, key)
        if target is None:
            raise ExtensionError(
                "patch_target_not_installed", "Patch target is not installed"
            )
        try:
            if target.status is InteractivePackageStatus.ACTIVE:
                effective = self._assemble(target)
                if kind is UnitKind.AGENT:
                    self._activate_agent(target, effective)
                else:
                    self._activate_app(target, effective)
                activated = target
            else:
                activated = self.activate_candidate(target.digest)
        except ExtensionError as error:
            if error.code != "patch_rebase_conflict":
                raise
            return {
                "patch": resolved,
                "package": target,
                "activated": False,
                "pending_conflicts": error.details.get("conflicts", []),
            }
        return {
            "patch": resolved,
            "package": activated,
            "activated": True,
            "pending_conflicts": [],
        }

    def launch_app(self, key, *, singleton_identity="local", state=None):
        definition = self._active_app_definition(key)
        if definition is None:
            raise ResourceNotFoundError("app_definition", key)
        mode = AppInstanceMode(definition["instance_mode"])
        scope = definition["singleton_scope"]
        singleton_key = (
            None
            if mode is AppInstanceMode.MULTIPLE
            else f"{key}:{scope}:{singleton_identity}"
        )
        if singleton_key:
            with self.database.transaction() as c:
                existing = c.execute(
                    "SELECT * FROM app_instances WHERE singleton_key=?",
                    (singleton_key,),
                ).fetchone()
            if existing:
                instance = self.apps.get_instance(existing["id"])
                if instance.status is not AppInstanceStatus.ACTIVE:
                    instance = self.apps.update_instance(
                        instance.id,
                        expected_revision=instance.revision,
                        status=AppInstanceStatus.ACTIVE,
                    )
                return (
                    instance,
                    self._home(existing["id"]),
                    False,
                )
        manifest = json.loads(definition["manifest_json"])
        version = int(manifest.get("state", {}).get("version", 1))
        initial = {**manifest.get("state", {}).get("defaults", {}), **(state or {})}
        instance = self.apps.create_instance(
            app_definition_id=definition["id"],
            singleton_key=singleton_key,
            status=AppInstanceStatus.ACTIVE,
            state_schema_version=version,
            state=initial,
        )
        home = self.sessions.create(
            app_instance_id=instance.id,
            title=str(manifest.get("name", key)),
            is_home=True,
            session_kind=SessionKind.APP,
        )
        return instance, home, True

    def list_apps(self) -> tuple[dict, ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM app_definitions WHERE status='enabled' "
                "ORDER BY display_name,package_id"
            ).fetchall()
            instance_rows = connection.execute(
                """
                SELECT i.*,s.id AS home_session_id
                FROM app_instances i
                LEFT JOIN sessions s
                  ON s.app_instance_id=i.id AND s.is_home=1 AND s.status='active'
                WHERE i.status!='closed'
                ORDER BY i.updated_at DESC,i.created_at DESC
                """
            ).fetchall()
        instances_by_definition: dict[str, list[dict]] = {}
        for item in instance_rows:
            instances_by_definition.setdefault(item["app_definition_id"], []).append(
                {
                    "id": item["id"],
                    "status": item["status"],
                    "home_session_id": item["home_session_id"],
                    "created_at": item["created_at"],
                    "updated_at": item["updated_at"],
                }
            )
        result = []
        for row in rows:
            manifest = json.loads(row["manifest_json"])
            navigation = manifest.get("navigation", {})
            testflight = manifest.get("testflight")
            is_testflight = (
                row["source"] == "local"
                and isinstance(testflight, dict)
                and testflight.get("signed") is False
            )
            category = str(navigation.get("category", "Third-party"))
            if is_testflight:
                category = "TestFlight"
            elif category == "TestFlight":
                category = "Third-party"
            entry = manifest.get("entry")
            if not isinstance(entry, dict):
                entry = {"kind": "host", "resource": str(entry or "")}
            instances = instances_by_definition.get(row["id"], [])
            result.append(
                {
                    "id": row["id"],
                    "app_key": row["package_id"],
                    "version": row["package_version"],
                    "display_name": row["display_name"],
                    "description": str(manifest.get("description", "")),
                    "source": row["source"],
                    "instance_mode": row["instance_mode"],
                    "singleton_scope": row["singleton_scope"],
                    "effective_digest": row["effective_digest"],
                    "entry": entry,
                    "mini_entry": manifest.get("mini_entry"),
                    "mobile": manifest.get("mobile", {"ready": False}),
                    "mobile_entry": manifest.get("mobile_entry"),
                    "activation": manifest.get("activation", {}),
                    "navigation": {
                        "category": category,
                        "icon": str(navigation.get("icon", "app-window")),
                        "order": int(navigation.get("order", 1000)),
                        "pinned_default": bool(
                            navigation.get("pinned_default", False)
                        ),
                    },
                    "instances": instances,
                    "running_count": len(instances),
                    "entry_url": f"/apps/{row['package_id']}",
                    "distribution": "testflight" if is_testflight else "installed",
                }
            )
        return tuple(
            sorted(
                result,
                key=lambda item: (
                    item["navigation"]["order"],
                    item["display_name"].casefold(),
                ),
            )
        )

    @staticmethod
    def resolve_mobile_entry(manifest: dict) -> tuple[str, dict] | None:
        """Resolve the deterministic Mobile-Entry fallback for one App."""

        mobile = manifest.get("mobile")
        if not isinstance(mobile, dict) or mobile.get("ready") is not True:
            return None
        for source in ("mobile_entry", "mini_entry", "entry"):
            view = manifest.get(source)
            if isinstance(view, dict):
                return source, view
        raise ExtensionError(
            "mobile_entry_missing", "Mobile Ready App has no usable Entry"
        )

    def list_mobile_apps(self) -> tuple[dict, ...]:
        """Return only explicit, launchable Mobile Ready Apps."""

        result = []
        for app in self.list_apps():
            manifest = {
                "mobile": app.get("mobile"),
                "mobile_entry": app.get("mobile_entry"),
                "mini_entry": app.get("mini_entry"),
                "entry": app.get("entry"),
            }
            resolved = self.resolve_mobile_entry(manifest)
            if resolved is None:
                continue
            entry_source, view = resolved
            if view.get("kind") == "host" and app["source"] != "builtin":
                continue
            result.append(
                {
                    "id": app["id"],
                    "app_key": app["app_key"],
                    "display_name": app["display_name"],
                    "description": app["description"],
                    "navigation": app["navigation"],
                    "instance_mode": app["instance_mode"],
                    "instances": app["instances"],
                    "running_count": app["running_count"],
                    "entry_source": entry_source,
                    "mobile_renderer": view.get("kind", "host"),
                }
            )
        return tuple(result)

    def suggest_apps(self, text: str) -> tuple[dict, ...]:
        """Return conservative manifest-declared natural-language App matches."""
        normalized = " ".join(text.casefold().split())
        if not normalized:
            return ()
        words = {word for word in normalized.replace("，", " ").replace("。", " ").split() if len(word) > 1}
        matches = []
        for app in self.list_apps():
            activation = app.get("activation") or {}
            if not isinstance(activation, dict):
                continue
            behavior = str(activation.get("behavior", "suggest"))
            if behavior == "explicit":
                continue
            examples = activation.get("examples", [])
            examples = examples if isinstance(examples, list) else []
            description = str(activation.get("description", ""))
            score = 0.0
            matched = ""
            for example in examples:
                candidate = " ".join(str(example).casefold().split())
                if candidate and (candidate in normalized or normalized in candidate):
                    score = 1.0
                    matched = str(example)
                    break
            if score == 0 and words:
                haystack = description.casefold()
                overlap = sum(1 for word in words if word in haystack)
                if overlap >= min(2, len(words)):
                    score = min(0.85, 0.55 + overlap * 0.1)
                    matched = description
            if score >= 0.65:
                matches.append(
                    {
                        "app_key": app["app_key"],
                        "display_name": app["display_name"],
                        "description": app["description"],
                        "navigation": app["navigation"],
                        "behavior": "suggest",
                        "score": score,
                        "matched": matched,
                    }
                )
        return tuple(sorted(matches, key=lambda item: (-item["score"], item["display_name"]))[:3])

    def instance_entry(self, instance_id: str) -> dict:
        """Return the validated current Entry contract for one live instance."""

        with self.database.transaction() as connection:
            row = connection.execute(
                """
                SELECT i.id AS instance_id,i.status AS instance_status,
                       d.id AS definition_id,d.package_id,d.display_name,
                       d.source,d.status AS definition_status,d.manifest_json,
                       d.upstream_digest,d.effective_digest
                FROM app_instances i
                JOIN app_definitions d ON d.id=i.app_definition_id
                WHERE i.id=?
                """,
                (instance_id,),
            ).fetchone()
        if row is None:
            raise ResourceNotFoundError("app_instance", instance_id)
        if row["definition_status"] != "enabled" or row["instance_status"] == "closed":
            raise ExtensionError(
                "app_instance_unavailable", "App instance is not active"
            )
        manifest = json.loads(row["manifest_json"])
        entry = manifest.get("entry")
        if not isinstance(entry, dict):
            entry = {"kind": "host", "resource": str(entry or "")}
        return {
            "instance_id": row["instance_id"],
            "app_key": row["package_id"],
            "display_name": row["display_name"],
            "source": row["source"],
            "renderer": entry.get("kind", "host"),
            "resource": entry.get("resource", ""),
            "effective_digest": row["effective_digest"],
        }

    def mobile_instance_entry(self, instance_id: str) -> dict:
        """Return the selected Mobile Entry for one live AppInstance."""

        with self.database.transaction() as connection:
            row = connection.execute(
                """
                SELECT i.id AS instance_id,i.status AS instance_status,
                       d.package_id,d.display_name,d.source,
                       d.status AS definition_status,d.manifest_json,
                       d.effective_digest
                FROM app_instances i
                JOIN app_definitions d ON d.id=i.app_definition_id
                WHERE i.id=?
                """,
                (instance_id,),
            ).fetchone()
        if row is None:
            raise ResourceNotFoundError("app_instance", instance_id)
        if row["definition_status"] != "enabled" or row["instance_status"] == "closed":
            raise ExtensionError(
                "app_instance_unavailable", "App instance is not active"
            )
        resolved = self.resolve_mobile_entry(json.loads(row["manifest_json"]))
        if resolved is None:
            raise ExtensionError(
                "mobile_not_ready", "App is not declared Mobile Ready"
            )
        entry_source, entry = resolved
        if entry.get("kind") == "host" and row["source"] != "builtin":
            raise ExtensionError(
                "mobile_host_renderer_denied",
                "Third-party Mobile Apps cannot use a host renderer",
            )
        return {
            "instance_id": row["instance_id"],
            "app_key": row["package_id"],
            "display_name": row["display_name"],
            "source": row["source"],
            "entry_source": entry_source,
            "renderer": entry.get("kind", "host"),
            "resource": entry.get("resource", ""),
            "effective_digest": row["effective_digest"],
        }

    def focus_instance(self, instance_id: str):
        """Resume an existing instance without creating another one."""

        instance = self.apps.get_instance(instance_id)
        if instance.status is AppInstanceStatus.ACTIVE:
            return instance
        return self.apps.update_instance(
            instance.id,
            expected_revision=instance.revision,
            status=AppInstanceStatus.ACTIVE,
        )

    def suspend_instance(self, instance_id: str):
        instance = self.apps.get_instance(instance_id)
        if instance.status is AppInstanceStatus.SUSPENDED:
            return instance
        return self.apps.update_instance(
            instance.id,
            expected_revision=instance.revision,
            status=AppInstanceStatus.SUSPENDED,
        )

    def close_instance(self, instance_id: str):
        instance = self.apps.get_instance(instance_id)
        if instance.status is AppInstanceStatus.CLOSED:
            return instance
        updated = self.apps.update_instance(
            instance.id,
            expected_revision=instance.revision,
            status=AppInstanceStatus.CLOSED,
        )
        with self.database.transaction(write=True) as connection:
            connection.execute(
                "UPDATE app_mounts SET status='unmounted',updated_at=? "
                "WHERE app_instance_id=? AND status='mounted'",
                (utc_now_text(), instance_id),
            )
        return updated

    def resolve_app_resource(self, instance_id: str, resource: str) -> Path:
        """Resolve and re-hash one installed App resource before serving it."""

        safe = PurePosixPath(resource)
        if (
            not resource
            or resource.startswith("/")
            or "\\" in resource
            or ".." in safe.parts
        ):
            raise ExtensionError("unsafe_app_resource", "Unsafe App resource path")
        entry = self.instance_entry(instance_id)
        if entry["source"] == "local":
            with self.database.transaction() as connection:
                definition = connection.execute(
                    "SELECT manifest_json FROM app_definitions WHERE package_id=? "
                    "AND status='enabled' ORDER BY updated_at DESC LIMIT 1",
                    (entry["app_key"],),
                ).fetchone()
            manifest = {} if definition is None else json.loads(definition["manifest_json"])
            testflight = manifest.get("testflight")
            if not isinstance(testflight, dict) or testflight.get("signed") is not False:
                raise ExtensionError(
                    "app_resource_unavailable",
                    "Local App is not an isolated TestFlight submission",
                )
            return self._verified_stored_resource(
                Path(str(testflight.get("store_path", ""))), resource, None
            )
        if entry["source"] != "installed":
            raise ExtensionError(
                "app_resource_unavailable",
                "Built-in host Apps have no package resource",
            )
        definition_digest = entry["effective_digest"]
        effective = self.repository.effective(UnitKind.APP, entry["app_key"])
        if effective is None or effective.effective_digest != definition_digest:
            raise ExtensionError(
                "app_definition_stale",
                "App instance is not bound to the active definition",
            )

        mapped = effective.resources.get(resource)
        if mapped is not None:
            for patch in reversed(
                self.repository.patches(
                    UnitKind.APP, entry["app_key"], enabled_only=True
                )
            ):
                if patch.resources.get(resource) != mapped:
                    continue
                return self._verified_stored_resource(
                    Path(patch.store_path), str(mapped), None
                )

        package = self.repository.package(effective.upstream_digest)
        indexed = next(
            (item for item in package.file_index if item.get("path") == resource),
            None,
        )
        if indexed is None:
            raise ResourceNotFoundError("app_resource", resource)
        return self._verified_stored_resource(
            Path(package.store_path), resource, indexed
        )

    @staticmethod
    def _verified_stored_resource(
        root: Path, resource: str, indexed: dict | None
    ) -> Path:
        root = root.resolve(strict=True)
        path = (root / resource).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():
            raise ExtensionError(
                "unsafe_app_resource", "App resource escaped its package"
            )
        if indexed is None:
            index_path = root / "META" / "files.json"
            values = json.loads(index_path.read_text(encoding="utf-8"))["files"]
            indexed = next(
                (item for item in values if item.get("path") == resource), None
            )
        if indexed is None:
            raise ResourceNotFoundError("app_resource", resource)
        content = path.read_bytes()
        digest = f"sha256:{hashlib.sha256(content).hexdigest()}"
        expected_digest = indexed.get("sha256", indexed.get("content_hash"))
        expected_size = indexed.get("size", indexed.get("size_bytes"))
        if expected_digest != digest or expected_size != len(content):
            raise ExtensionError(
                "app_resource_integrity_failed",
                "App resource no longer matches its package",
            )
        return path

    def _home(self, instance_id):
        rows = self.sessions.list_for_instance(instance_id)
        return next((item for item in rows if item.is_home), None)

    def mount(
        self,
        instance_id,
        *,
        mini=False,
        placement="entry",
        interaction_session_id=None,
        context=None,
    ):
        instance = self.apps.get_instance(instance_id)
        definition = self.apps.get_definition(instance.app_definition_id)
        if interaction_session_id is not None:
            self.sessions.get(interaction_session_id)
        entry_source = "mini_entry" if mini else "entry"
        if placement == "mobile":
            resolved = self.resolve_mobile_entry(definition.manifest)
            if resolved is None:
                raise ExtensionError(
                    "mobile_not_ready", "App is not declared Mobile Ready"
                )
            entry_source, view = resolved
            if view.get("kind") == "host" and definition.source != "builtin":
                raise ExtensionError(
                    "mobile_host_renderer_denied",
                    "Third-party Mobile Apps cannot use a host renderer",
                )
        else:
            view = (
                definition.manifest.get("mini_entry")
                if mini
                else definition.manifest.get("entry")
            )
        if view is None:
            view = {"kind": "host", "resource": "ai2apps:generic-launcher"}
        if mini and placement not in view.get("placements", ["inline", "sidebar"]):
            raise ExtensionError(
                "placement_denied", "Mini-Entry placement is not declared"
            )
        mount_id = new_entity_id(EntityIdKind.APP_MOUNT)
        now = utc_now_text()
        mount_context = dict(context or {})
        with self.database.transaction(write=True) as c:
            c.execute(
                """
                INSERT INTO app_mounts(
                    id,app_instance_id,interaction_session_id,placement,
                    renderer,resource,status,created_at,updated_at,context_json,
                    entry_source
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    mount_id,
                    instance_id,
                    interaction_session_id,
                    placement,
                    view["kind"],
                    view.get("resource", ""),
                    "mounted",
                    now,
                    now,
                    _json(mount_context),
                    entry_source,
                ),
            )
            event_app_instance_id = instance_id
            if interaction_session_id is not None:
                event_scope = c.execute(
                    "SELECT app_instance_id FROM sessions WHERE id=?",
                    (interaction_session_id,),
                ).fetchone()
                event_app_instance_id = event_scope["app_instance_id"]
            self.events.append_in_transaction(
                c,
                event_type=(
                    "app.mobile_entry.mount"
                    if placement == "mobile"
                    else "app.mini_entry.mount" if mini else "app.entry.mount"
                ),
                subject_id=mount_id,
                app_instance_id=event_app_instance_id,
                session_id=interaction_session_id,
                payload={
                    "placement": placement,
                    "renderer": view["kind"],
                    "entry_source": entry_source,
                    "mounted_app_instance_id": instance_id,
                },
            )
        return {
            "id": mount_id,
            "app_instance_id": instance_id,
            "app_key": definition.package_id,
            "display_name": definition.display_name,
            "source": definition.source,
            "interaction_session_id": interaction_session_id,
            "placement": placement,
            "renderer": view["kind"],
            "resource": view.get("resource", ""),
            "entry_source": entry_source,
            "context": mount_context,
        }

    def mount_mobile(self, instance_id: str, *, context=None) -> dict:
        """Create or focus the durable Mobile mount for an AppInstance."""

        selected = self.mobile_instance_entry(instance_id)
        with self.database.transaction() as connection:
            rows = connection.execute(
                "SELECT id FROM app_mounts WHERE app_instance_id=? "
                "AND placement='mobile' AND status='mounted' "
                "ORDER BY updated_at DESC,id DESC",
                (instance_id,),
            ).fetchall()
        for row in rows:
            existing = self.mount_entry(row["id"])
            if (
                existing["renderer"] == selected["renderer"]
                and existing["resource"] == selected["resource"]
                and existing["entry_source"] == selected["entry_source"]
            ):
                now = utc_now_text()
                with self.database.transaction(write=True) as connection:
                    connection.execute(
                        "UPDATE app_mounts SET updated_at=? WHERE id=?",
                        (now, existing["id"]),
                    )
                return {**existing, "updated_at": now, "reused": True}
            with self.database.transaction(write=True) as connection:
                connection.execute(
                    "UPDATE app_mounts SET status='unmounted',updated_at=? WHERE id=?",
                    (utc_now_text(), existing["id"]),
                )
        return {
            **self.mount(instance_id, placement="mobile", context=context),
            "reused": False,
        }

    def list_mobile_mounts(self) -> tuple[dict, ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                "SELECT id FROM app_mounts WHERE placement='mobile' "
                "AND status='mounted' ORDER BY updated_at DESC,id DESC"
            ).fetchall()
        return tuple(self.mount_entry(row["id"]) for row in rows)

    def mount_entry(self, mount_id: str) -> dict:
        with self.database.transaction() as connection:
            row = connection.execute(
                """
                SELECT m.*,d.package_id,d.display_name,d.source,d.effective_digest
                FROM app_mounts m
                JOIN app_instances i ON i.id=m.app_instance_id
                JOIN app_definitions d ON d.id=i.app_definition_id
                WHERE m.id=?
                """,
                (mount_id,),
            ).fetchone()
        if row is None:
            raise ResourceNotFoundError("app_mount", mount_id)
        if row["status"] != "mounted":
            raise ExtensionError("app_mount_unavailable", "App mount is not active")
        return {
            "id": row["id"],
            "app_instance_id": row["app_instance_id"],
            "app_key": row["package_id"],
            "display_name": row["display_name"],
            "source": row["source"],
            "effective_digest": row["effective_digest"],
            "interaction_session_id": row["interaction_session_id"],
            "placement": row["placement"],
            "renderer": row["renderer"],
            "resource": row["resource"],
            "entry_source": row["entry_source"],
            "context": json.loads(row["context_json"]),
        }

    def list_mounts(self, interaction_session_id: str) -> tuple[dict, ...]:
        self.sessions.get(interaction_session_id)
        with self.database.transaction() as connection:
            rows = connection.execute(
                "SELECT id FROM app_mounts WHERE interaction_session_id=? "
                "AND status='mounted' ORDER BY created_at,id",
                (interaction_session_id,),
            ).fetchall()
        return tuple(self.mount_entry(row["id"]) for row in rows)

    def instance_can_use_session(self, instance_id: str, session_id: str) -> bool:
        self.apps.get_instance(instance_id)
        self.sessions.get(session_id)
        with self.database.transaction() as connection:
            owned = connection.execute(
                "SELECT 1 FROM sessions WHERE id=? AND app_instance_id=?",
                (session_id, instance_id),
            ).fetchone()
            mounted = connection.execute(
                "SELECT 1 FROM app_mounts WHERE app_instance_id=? "
                "AND interaction_session_id=? AND status='mounted'",
                (instance_id, session_id),
            ).fetchone()
        return owned is not None or mounted is not None

    def unmount(self, mount_id: str) -> dict:
        entry = self.mount_entry(mount_id)
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                "UPDATE app_mounts SET status='unmounted',updated_at=? WHERE id=?",
                (now, mount_id),
            )
            event_app_instance_id = entry["app_instance_id"]
            if entry["interaction_session_id"] is not None:
                event_scope = connection.execute(
                    "SELECT app_instance_id FROM sessions WHERE id=?",
                    (entry["interaction_session_id"],),
                ).fetchone()
                event_app_instance_id = event_scope["app_instance_id"]
            self.events.append_in_transaction(
                connection,
                event_type=(
                    "app.mobile_entry.unmount"
                    if entry["placement"] == "mobile"
                    else "app.view.unmount"
                ),
                subject_id=mount_id,
                app_instance_id=event_app_instance_id,
                session_id=entry["interaction_session_id"],
                payload={
                    "placement": entry["placement"],
                    "mounted_app_instance_id": entry["app_instance_id"],
                },
            )
        return {**entry, "status": "unmounted", "updated_at": now}

    def safe_mode_status(self) -> dict:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT active,reason,updated_at FROM safe_mode_state WHERE id=1"
            ).fetchone()
        if row is None:
            return {"active": False, "reason": "", "updated_at": None}
        return {
            "active": bool(row["active"]),
            "reason": row["reason"],
            "updated_at": row["updated_at"],
        }

    def control_snapshot(self) -> dict:
        packages = self.repository.installed()
        targets = {(package.kind, package.unit_key) for package in packages}
        patches = [
            patch
            for kind, key in sorted(
                targets, key=lambda item: (item[0].value, item[1])
            )
            for patch in self.repository.patches(kind, key)
        ]
        return {
            "safe_mode": self.safe_mode_status(),
            "packages": [
                {
                    "kind": package.kind.value,
                    "key": package.unit_key,
                    "version": package.version,
                    "digest": package.digest,
                    "publisher": package.publisher_key,
                    "status": package.status.value,
                    "verification": package.verification,
                    "manifest": package.manifest,
                }
                for package in packages
            ],
            "patches": [
                {
                    "id": patch.id,
                    "kind": patch.target_kind.value,
                    "key": patch.target_key,
                    "intent": patch.intent,
                    "status": patch.status.value,
                    "base_digest": patch.base_digest,
                    "digest": patch.digest,
                    "conflict": patch.conflict,
                    "audit": patch.audit,
                    "stack_order": patch.stack_order,
                }
                for patch in patches
            ],
        }

    def safe_mode(self, active: bool, reason="user-request"):
        current = self.safe_mode_status()
        if current["active"] is active:
            return current
        now = utc_now_text()
        with self.database.transaction(write=True) as c:
            if active:
                c.execute("DELETE FROM safe_mode_patch_states")
                c.execute(
                    "INSERT INTO safe_mode_patch_states SELECT id,status FROM local_patches WHERE status NOT IN ('disabled','superseded')"
                )
                c.execute(
                    "UPDATE local_patches SET status='disabled',updated_at=? WHERE status NOT IN ('disabled','superseded')",
                    (now,),
                )
            else:
                c.execute(
                    "UPDATE local_patches SET status=(SELECT prior_status FROM safe_mode_patch_states s WHERE s.patch_id=local_patches.id),updated_at=? WHERE id IN (SELECT patch_id FROM safe_mode_patch_states)",
                    (now,),
                )
                c.execute("DELETE FROM safe_mode_patch_states")
            c.execute(
                "INSERT INTO safe_mode_state(id,active,reason,updated_at) VALUES(1,?,?,?) ON CONFLICT(id) DO UPDATE SET active=excluded.active,reason=excluded.reason,updated_at=excluded.updated_at",
                (int(active), reason, now),
            )
        for package in self.repository.installed():
            if package.status is not InteractivePackageStatus.ACTIVE:
                continue
            effective = self._assemble(package)
            if package.kind is UnitKind.AGENT:
                self._activate_agent(package, effective)
            else:
                self._activate_app(package, effective)
        return {"active": active, "reason": reason, "updated_at": now}

    def set_enabled(self, kind: UnitKind, key: str, enabled: bool) -> None:
        now = utc_now_text()
        table = "agent_definitions" if kind is UnitKind.AGENT else "app_definitions"
        key_column = "agent_key" if kind is UnitKind.AGENT else "package_id"
        with self.database.transaction(write=True) as connection:
            cursor = connection.execute(
                f"UPDATE {table} SET status=?,revision=revision+1,updated_at=? "
                f"WHERE {key_column}=? AND effective_digest=(SELECT effective_digest "
                "FROM effective_definitions WHERE unit_kind=? AND unit_key=? AND status='active')",
                ("enabled" if enabled else "disabled", now, key, kind.value, key),
            )
            if cursor.rowcount == 0:
                raise ResourceNotFoundError(f"{kind.value}_definition", key)

    def rollback(self, kind: UnitKind, key: str):
        active = self.repository.active_package(kind, key)
        if active is None:
            raise ResourceNotFoundError("interactive_package", key)
        retained = [
            item
            for item in self.repository.installed(kind, key)
            if item.status is InteractivePackageStatus.RETAINED
        ]
        if not retained:
            raise ExtensionError("rollback_unavailable", "No retained upstream version")
        target = retained[0]
        effective = self._assemble(target)
        if kind is UnitKind.AGENT:
            self._activate_agent(target, effective)
        else:
            self._rollback_app(target, effective)
        return self.repository.activate_package(target)

    def _rollback_app(self, target, effective) -> None:
        target_definition = None
        with self.database.transaction() as connection:
            target_definition = connection.execute(
                "SELECT * FROM app_definitions WHERE package_id=? AND effective_digest=?",
                (target.unit_key, effective.effective_digest),
            ).fetchone()
            current = self._active_app_definition(target.unit_key)
        if target_definition is None or current is None:
            self._activate_app(target, effective)
            return
        instances = self._instances(current["id"])
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                "UPDATE app_definitions SET status='disabled',updated_at=? WHERE id=?",
                (now, current["id"]),
            )
            connection.execute(
                "UPDATE app_definitions SET status='enabled',updated_at=? WHERE id=?",
                (now, target_definition["id"]),
            )
            for instance in instances:
                snapshot = connection.execute(
                    "SELECT * FROM app_state_snapshots WHERE app_instance_id=? "
                    "AND effective_digest=? ORDER BY created_at DESC LIMIT 1",
                    (instance["id"], effective.effective_digest),
                ).fetchone()
                if snapshot is None:
                    raise ExtensionError(
                        "rollback_snapshot_missing",
                        "App rollback state snapshot is missing",
                    )
                connection.execute(
                    "UPDATE app_instances SET app_definition_id=?,state_schema_version=?,"
                    "state_json=?,revision=revision+1,updated_at=? WHERE id=?",
                    (
                        target_definition["id"],
                        snapshot["state_schema_version"],
                        snapshot["state_json"],
                        now,
                        instance["id"],
                    ),
                )

    def uninstall(self, kind: UnitKind, key: str, *, force=False) -> None:
        active = self.repository.active_package(kind, key)
        if active is None:
            raise ResourceNotFoundError("interactive_package", key)
        if kind is UnitKind.APP:
            definition = self._active_app_definition(key)
            instances = [] if definition is None else self._instances(definition["id"])
            if instances and not force:
                raise ExtensionError(
                    "app_has_instances",
                    "Close App instances before uninstalling",
                    details={"instances": [item["id"] for item in instances]},
                )
        self.set_enabled(kind, key, False)
        for package in self.repository.installed(kind, key):
            self.repository.set_package_status(
                package.digest, InteractivePackageStatus.UNINSTALLED
            )
        for patch in self.repository.patches(kind, key):
            self.repository.set_patch(patch.id, PatchStatus.DISABLED)

    def create_patch(
        self,
        output_path: str | Path,
        *,
        target_kind: UnitKind,
        target_key: str,
        intent: str,
        operations: list[dict],
        rebase_policy: str = "strict",
        tests: list[dict] | None = None,
        resources: dict[str, str] | None = None,
        version: str = "1.0.0",
    ) -> Path:
        active = self.repository.active_package(target_kind, target_key)
        if active is None:
            raise ExtensionError(
                "patch_target_not_installed", "Patch target is not active"
            )
        manifest = {
            "schema": "ai2apps.patch/v1",
            "version": version,
            "target": {"kind": target_kind.value, "id": target_key},
            "base_digest": active.digest,
            "intent": intent,
            "rebase_policy": rebase_policy,
            "operations": operations,
            "tests": tests or [],
            "resources": {key: key for key in (resources or {})},
        }
        sbom = {
            "spdxVersion": "SPDX-2.3",
            "SPDXID": "SPDXRef-DOCUMENT",
            "name": f"local-patch-{target_key}",
            "dataLicense": "CC0-1.0",
        }
        immutable = {
            "patch.yaml": yaml.safe_dump(manifest, sort_keys=True).encode(),
            "META/sbom.spdx.json": json.dumps(sbom, sort_keys=True).encode(),
            **{key: value.encode() for key, value in (resources or {}).items()},
        }
        files = tuple(
            PackageFile(
                path,
                f"sha256:{hashlib.sha256(content).hexdigest()}",
                len(content),
            )
            for path, content in immutable.items()
        )
        digest = package_digest(manifest, files)
        index = {
            "files": [
                {
                    "path": item.path,
                    "sha256": item.content_hash,
                    "size": item.size_bytes,
                }
                for item in files
            ]
        }
        destination = Path(output_path).resolve()
        if destination.suffix != ".ai2patch":
            raise ExtensionError(
                "invalid_patch_path", "Patch output must end in .ai2patch"
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, content in immutable.items():
                archive.writestr(name, content)
            archive.writestr("META/files.json", json.dumps(index, sort_keys=True))
            archive.writestr(
                "attestations/device.json",
                json.dumps({"package_digest": digest, "device": True}, sort_keys=True),
            )
            archive.writestr(
                "signatures/device.sig",
                json.dumps(
                    {
                        "algorithm": "ed25519",
                        "public_key": self.device.public_key,
                        "signature": self.device.sign(digest),
                    },
                    sort_keys=True,
                ),
            )
        return destination

    @staticmethod
    def _remove(path):
        for item in path.rglob("*"):
            with suppress(OSError):
                item.chmod(0o755 if item.is_dir() else 0o644)
        with suppress(OSError):
            path.chmod(0o755)
        shutil.rmtree(path, ignore_errors=True)
