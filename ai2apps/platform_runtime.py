"""Lifecycle boundary for the durable AI2Apps platform backend."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import uuid
from contextlib import suppress
from dataclasses import dataclass
from typing import Literal

from ai2apps.agents import (
    AgentRepository,
    AgentRuntime,
    install_delegation_service,
    install_diagnostic_agent,
    install_general_agent,
)
from ai2apps.apps import ensure_system_apps
from ai2apps.browser import (
    BrowserManager,
    BrowserRuntimeConfig,
    ChromeBrowserBackend,
    install_browser_service,
)
from ai2apps.browser.acefox import AceFoxBrowserBackend
from ai2apps.capabilities import (
    CapabilityPolicyEngine,
    CapabilityRepository,
    PolicyEffect,
)
from ai2apps.chat import ChatRepository
from ai2apps.cloud_client import (
    DEFAULT_AI2APPS_CLOUD_BASE_URL,
    AI2AppsCloudClient,
    CloudSessionStore,
    cloud_browser_cookie_name,
)
from ai2apps.coder import CoderManager
from ai2apps.config import (
    DEFAULT_SESSION_RETENTION_INTERVAL_SECONDS,
    PlatformConfig,
)
from ai2apps.documents import (
    DocumentManager,
    DocumentRepository,
    install_document_service,
)
from ai2apps.events import EventNotificationBus, EventStore
from ai2apps.extensions import ExtensionRepository, InteractivePackageManager
from ai2apps.identity import (
    LOCAL_SESSION_COOKIE,
    IdentityBindingError,
    IdentityRepository,
    RequestPrincipal,
    local_session_cookie_name,
)
from ai2apps.images import install_image_service
from ai2apps.installation_security import (
    LocalInstanceLease,
    LocalSecurityIdentity,
    LocalSecurityIdentityRepository,
    claim_local_security_identity,
)
from ai2apps.model_manager import ModelManagerStore
from ai2apps.packages import PackageRepository, ServicePackageManager
from ai2apps.packages.registry import RegistryPackageManager
from ai2apps.processes import ProcessManager, install_process_service
from ai2apps.remote import (
    RemoteAccessError,
    RemoteAccessManager,
    RemoteDeviceRepository,
    RemoteFrpcConfig,
    RemoteFrpcSupervisor,
)
from ai2apps.research import install_research_agent, install_web_research_service
from ai2apps.secrets import SecretRepository, create_secret_backend
from ai2apps.services import (
    MCPServiceAdapter,
    OmlxModelServiceAdapter,
    ServiceRegistry,
    ServiceRepository,
    ToolGateway,
    install_echo_service,
)
from ai2apps.sharing import SharingManager, stable_gateway_id
from ai2apps.storage import PlatformDatabase
from ai2apps.storage.repositories import SessionRepository
from ai2apps.terminal import TerminalManager, install_terminal_service
from ai2apps.upstream import UpstreamGatewayManager
from ai2apps.workspace import WorkspaceRepository, install_workspace_service

logger = logging.getLogger(__name__)

DatabaseRuntimeState = Literal["unconfigured", "not_initialized", "ready"]


@dataclass(frozen=True, slots=True)
class PlatformDatabaseStatus:
    """Database state exposed to platform health contracts."""

    configured: bool
    status: DatabaseRuntimeState
    schema_version: int
    target_schema_version: int
    filename: str
    journal_mode: str | None = None


class PlatformRuntime:
    """Own platform startup state without depending on oMLX internals."""

    def __init__(self, config: PlatformConfig) -> None:
        self.config = config
        self._database_status = self.status_before_start(config)
        self.database: PlatformDatabase | None = None
        self.security_identity: LocalSecurityIdentity | None = None
        self._instance_lease: LocalInstanceLease | None = None
        self.notifications: EventNotificationBus | None = None
        self.events: EventStore | None = None
        self.services: ServiceRepository | None = None
        self.service_registry: ServiceRegistry | None = None
        self.tools: ToolGateway | None = None
        self.sharing: SharingManager | None = None
        self.upstreams: UpstreamGatewayManager | None = None
        self.capabilities: CapabilityRepository | None = None
        self.secrets: SecretRepository | None = None
        self.cloud: AI2AppsCloudClient | None = None
        self._browser_cloud_clients: dict[str, AI2AppsCloudClient] = {}
        self._core_bootstrap_lock = asyncio.Lock()
        self.capability_policy: CapabilityPolicyEngine | None = None
        self.agents: AgentRepository | None = None
        self.agent_runtime: AgentRuntime | None = None
        self.workspace: WorkspaceRepository | None = None
        self.processes: ProcessManager | None = None
        self.web_provider = None
        self.browser: BrowserManager | None = None
        self.terminal: TerminalManager | None = None
        self.coder: CoderManager | None = None
        self.documents: DocumentRepository | None = None
        self.document_manager: DocumentManager | None = None
        self.package_repository: PackageRepository | None = None
        self.package_manager: ServicePackageManager | None = None
        self.registry_packages: RegistryPackageManager | None = None
        self.remote: RemoteAccessManager | None = None
        self.extension_repository: ExtensionRepository | None = None
        self.extension_manager: InteractivePackageManager | None = None
        self._retention_stop: asyncio.Event | None = None
        self._retention_task: asyncio.Task[None] | None = None

    @staticmethod
    def status_before_start(config: PlatformConfig) -> PlatformDatabaseStatus:
        configured = config.paths is not None
        return PlatformDatabaseStatus(
            configured=configured,
            status="not_initialized" if configured else "unconfigured",
            schema_version=0,
            target_schema_version=config.database_schema_version,
            filename=config.database_filename,
        )

    @property
    def database_status(self) -> PlatformDatabaseStatus:
        return self._database_status

    async def start_background_tasks(
        self,
        *,
        retention_interval_seconds: float = DEFAULT_SESSION_RETENTION_INTERVAL_SECONDS,
    ) -> None:
        """Start bounded platform maintenance loops after database startup."""

        if self.database is None or self.events is None or self._retention_task:
            return
        if retention_interval_seconds <= 0:
            raise ValueError("retention_interval_seconds must be positive")
        self._retention_stop = asyncio.Event()
        self._retention_task = asyncio.create_task(
            self._run_session_retention(retention_interval_seconds),
            name="ai2apps-session-retention",
        )
        if self.package_manager is not None:
            await self.package_manager.startup()
        if self.processes is not None:
            await self.processes.startup()
        if self.terminal is not None:
            await self.terminal.startup()
        if self.agent_runtime is not None:
            await self.agent_runtime.start()
        if self.upstreams is not None:
            await self.upstreams.start()
        if self.document_manager is not None:
            await self.document_manager.startup()
        if self.remote is not None:
            await self.remote.startup()

    async def _run_session_retention(self, interval_seconds: float) -> None:
        assert self.database is not None
        assert self.events is not None
        assert self._retention_stop is not None
        repository = SessionRepository(self.database, self.events)
        while not self._retention_stop.is_set():
            try:
                await asyncio.to_thread(repository.expire_temporary)
            except Exception:
                logger.exception("AI2Apps temporary Session retention pass failed")
            with suppress(TimeoutError):
                await asyncio.wait_for(
                    self._retention_stop.wait(), timeout=interval_seconds
                )

    async def stop_background_tasks(self) -> None:
        """Stop maintenance loops and wait until their current batch completes."""

        if self.agent_runtime is not None:
            await self.agent_runtime.stop()
        if self.upstreams is not None:
            await self.upstreams.stop()
        if self.document_manager is not None:
            await self.document_manager.shutdown()
        if self.remote is not None:
            await self.remote.shutdown()
        if self._browser_cloud_clients:
            await asyncio.gather(
                *(client.close() for client in self._browser_cloud_clients.values()),
                return_exceptions=True,
            )
            self._browser_cloud_clients.clear()
        if self.cloud is not None:
            await self.cloud.close()
        if self.browser is not None:
            await self.browser.close()
        if self.package_manager is not None:
            await self.package_manager.shutdown()
        if self.processes is not None:
            await self.processes.shutdown()
        if self.terminal is not None:
            await self.terminal.shutdown()
        if self._retention_stop is not None:
            self._retention_stop.set()
        if self._retention_task is not None:
            await self._retention_task
        self._retention_task = None
        self._retention_stop = None

    async def set_safe_mode(self, active: bool, reason: str = "user-request") -> dict:
        """Apply the unpatchable recovery boundary across platform subsystems."""
        if self.extension_manager is None:
            raise RuntimeError("Interactive package runtime is unavailable")
        revoked = ()
        stopped = 0
        if active and self.capabilities is not None:
            revoked = self.capabilities.revoke_all(reason=f"safe-mode:{reason}")
        if active and self.processes is not None:
            records = await asyncio.to_thread(self.processes.repository.active)
            results = await asyncio.gather(
                *(
                    self.processes.cancel(
                        record.id,
                        session_id=record.session_id,
                        run_id=record.run_id,
                    )
                    for record in records
                ),
                return_exceptions=True,
            )
            stopped = sum(not isinstance(result, BaseException) for result in results)
        closed_terminals = 0
        if active and self.terminal is not None:
            terminal_ids = tuple(item["id"] for item in self.terminal.list())
            results = await asyncio.gather(
                *(self.terminal.close(session_id) for session_id in terminal_ids),
                return_exceptions=True,
            )
            closed_terminals = sum(
                not isinstance(result, BaseException) for result in results
            )
        state = self.extension_manager.safe_mode(active, reason)
        return {
            **state,
            "revoked_grants": len(revoked),
            "stopped_processes": stopped,
            "closed_terminals": closed_terminals,
        }

    def start(self) -> PlatformDatabaseStatus:
        """Initialize the platform and release its root claim on any failure."""

        if self.config.paths is None:
            return self._database_status
        if self._instance_lease is not None:
            raise RuntimeError("Platform runtime is already started")
        self._instance_lease = LocalInstanceLease.acquire(
            self.config.paths.database_path.parent
        )
        try:
            return self._start_claimed()
        except Exception:
            self._instance_lease.release()
            self._instance_lease = None
            raise

    def _start_claimed(self) -> PlatformDatabaseStatus:
        """Initialize components while ``start`` owns the canonical root."""

        assert self.config.paths is not None
        database = PlatformDatabase(self.config.paths.database_path)
        state = database.initialize()
        security_identity = LocalSecurityIdentityRepository(database).get_or_create()
        claim_local_security_identity(
            security_identity.security_instance_id,
            self.config.paths.database_path.parent,
        )
        notifications = EventNotificationBus()
        self.database = database
        self.security_identity = security_identity
        self.notifications = notifications
        self.events = EventStore(database, notifications)
        ChatRepository(database, self.events).ensure_builtin()
        ensure_system_apps(database, self.events)
        self.services = ServiceRepository(database, self.events)
        interrupted_invocations = self.services.recover_interrupted_invocations()
        for invocation in interrupted_invocations:
            with database.transaction(write=True) as connection:
                self.events.append_in_transaction(
                    connection,
                    event_type="tool.invocation.interrupted",
                    subject_id=invocation.tool_id,
                    session_id=invocation.session_id,
                    trace_id=invocation.trace_id,
                    payload={
                        "invocation_id": invocation.id,
                        "caller_id": invocation.caller_id,
                        "status": "interrupted",
                        "code": "runtime_restarted",
                    },
                )
        self.service_registry = ServiceRegistry(self.services)
        self.tools = ToolGateway(
            database,
            self.events,
            self.services,
            self.service_registry,
        )
        secret_backend = create_secret_backend(
            self.config.paths.secrets_path,
            configured=self.config.secret_backend,
            namespace=security_identity.security_instance_id,
        )
        self.secret_backend = secret_backend
        self.model_manager = ModelManagerStore(
            self.config.paths.base_path,
            secret_backend=secret_backend,
        )
        self.model_manager.migrate_legacy_credentials()
        self.sharing = SharingManager(
            database,
            self.tools,
            model_source_resolver=self.model_manager.model_source,
        )
        self.upstreams = UpstreamGatewayManager(
            database, secret_backend, self.services, self.service_registry,
            local_node_id=stable_gateway_id(self.config.paths.database_path),
        )
        self.secrets = SecretRepository(database, self.events, secret_backend)
        cloud_base_url = os.environ.get(
            "AI2APPS_CLOUD_BASE_URL", DEFAULT_AI2APPS_CLOUD_BASE_URL
        )
        self.cloud = AI2AppsCloudClient(
            base_url=cloud_base_url,
            session_store=CloudSessionStore(
                secret_backend,
                cloud_base_url,
                namespace=f"installation:{security_identity.security_instance_id}",
            ),
        )
        remote_runtime_directory = self.config.paths.base_path / "platform" / "remote"
        remote_config_error = None
        try:
            remote_frpc_config = RemoteFrpcConfig.from_environment(
                remote_runtime_directory
            )
        except ValueError as error:
            remote_frpc_config = None
            remote_config_error = str(error)
        if remote_frpc_config is None and remote_config_error is None:
            remote_config_error = RemoteFrpcConfig.unavailable_reason(
                remote_runtime_directory
            )
        self.remote = RemoteAccessManager(
            cloud=self.cloud,
            repository=RemoteDeviceRepository(database),
            secret_backend=secret_backend,
            client_version=os.environ.get("AI2APPS_CLIENT_VERSION", "0.2.0"),
            identity_repository=IdentityRepository(database),
            frpc=RemoteFrpcSupervisor(
                remote_frpc_config,
                secret_backend,
                unavailable_reason=remote_config_error,
            ),
        )
        self.tools.bind_secret_resolver(self.secrets.inject_arguments)
        install_echo_service(self.services, self.service_registry)
        self.capabilities = CapabilityRepository(database, self.events)
        self.capabilities.ensure_builtin_defaults()
        self.capabilities.upsert_policy(
            policy_key="builtin.general-agent-workspace-write",
            effect=PolicyEffect.ALLOW,
            capability_pattern="workspace.write",
            agent_pattern="ai2apps.general-agent",
            tool_pattern="workspace.*",
            priority=100,
            source="builtin",
        )
        self.capabilities.upsert_policy(
            policy_key="builtin.general-agent-document-create-pdf",
            effect=PolicyEffect.ALLOW,
            capability_pattern="artifact.create",
            agent_pattern="ai2apps.general-agent",
            tool_pattern="document.create_pdf",
            priority=100,
            source="builtin",
        )
        self.capabilities.upsert_policy(
            policy_key="builtin.general-agent-document-create-pdf-workspace",
            effect=PolicyEffect.ALLOW,
            capability_pattern="workspace.write",
            agent_pattern="ai2apps.general-agent",
            tool_pattern="document.create_pdf",
            priority=100,
            source="builtin",
        )
        self.capabilities.upsert_policy(
            policy_key="builtin.general-agent-artifact-create",
            effect=PolicyEffect.ALLOW,
            capability_pattern="artifact.create",
            agent_pattern="ai2apps.general-agent",
            tool_pattern="artifact.create",
            priority=100,
            source="builtin",
        )
        self.capability_policy = CapabilityPolicyEngine(self.capabilities)
        self.workspace = WorkspaceRepository(database, self.events, self.config.paths)
        install_workspace_service(self.workspace, self.services, self.service_registry)
        self.documents = DocumentRepository(database, self.config.paths)
        self.document_manager = DocumentManager(self.documents)
        install_document_service(
            self.documents, self.workspace, self.services, self.service_registry
        )
        install_image_service(
            base_path=self.config.paths.base_path,
            cloud_client=self.cloud,
            workspace=self.workspace,
            repository=self.services,
            registry=self.service_registry,
            runtime_provider=lambda: self,
        )
        self.capabilities.upsert_policy(
            policy_key="builtin.general-agent-image-artifact",
            effect=PolicyEffect.ALLOW,
            capability_pattern="artifact.create",
            agent_pattern="ai2apps.general-agent",
            tool_pattern="image.generate",
            priority=100,
            source="builtin",
        )
        self.capabilities.upsert_policy(
            policy_key="builtin.general-agent-image-workspace",
            effect=PolicyEffect.ALLOW,
            capability_pattern="workspace.write",
            agent_pattern="ai2apps.general-agent",
            tool_pattern="image.generate",
            priority=100,
            source="builtin",
        )
        self.web_provider = install_web_research_service(
            self.services, self.service_registry
        )
        browser_config = BrowserRuntimeConfig(
            profile_path=str(self.config.paths.browsers_path / "managed-default")
        )
        browser_backend = (
            AceFoxBrowserBackend(browser_config)
            if os.environ.get("AI2APPS_BROWSER_BACKEND") == "acefox"
            else ChromeBrowserBackend(browser_config)
        )
        self.browser = BrowserManager(browser_backend, workspace=self.workspace)
        install_browser_service(self.browser, self.services, self.service_registry)
        self.processes = ProcessManager(database, self.events, self.workspace)
        install_process_service(self.processes, self.services, self.service_registry)
        self.terminal = TerminalManager()
        install_terminal_service(self.terminal, self.services, self.service_registry)
        self.coder = CoderManager(
            database,
            self.terminal,
            project_root=self.config.paths.projects_path,
            testflight_root=self.config.paths.packages_path / "testflight",
        )
        self.package_repository = PackageRepository(database, self.events)
        self.package_manager = ServicePackageManager(
            self.config.paths,
            self.package_repository,
            self.services,
            self.service_registry,
        )
        self.package_manager.restore_registry()
        self.agents = AgentRepository(database, self.events, self.capabilities)
        self.agent_runtime = AgentRuntime(
            self.agents, self.tools, self.capability_policy, self.capabilities
        )
        self.agent_runtime.bind_run_terminal_handler(
            self.processes.schedule_cancel_by_run
        )
        install_diagnostic_agent(self.agents, self.agent_runtime)
        install_general_agent(
            self.agents,
            self.agent_runtime,
            database,
            self.events,
            self.tools,
        )
        install_research_agent(self.agents)
        self.sharing.bind_agents(self.agents, self.agent_runtime)
        install_delegation_service(
            self.agents,
            self.agent_runtime,
            self.services,
            self.service_registry,
        )
        self.extension_manager = InteractivePackageManager(
            database,
            self.events,
            self.config.paths.packages_path,
            self.package_repository,
            self.agents,
        )
        self.extension_repository = self.extension_manager.repository
        self.registry_packages = RegistryPackageManager(
            cloud=self.cloud,
            root=self.config.paths.packages_path,
            secrets=self.secrets,
            extension_manager=self.extension_manager,
            service_manager=self.package_manager,
        )
        self._database_status = PlatformDatabaseStatus(
            configured=True,
            status="ready",
            schema_version=state.schema_version,
            target_schema_version=self.config.database_schema_version,
            filename=state.path.name,
            journal_mode=state.journal_mode,
        )
        return self._database_status

    def bind_builtin_runtime_services(
        self,
        *,
        engine_pool_provider,
        mcp_manager_provider,
    ) -> None:
        """Bind existing oMLX providers after their own startup has completed."""

        if self.services is None or self.service_registry is None:
            return
        OmlxModelServiceAdapter(engine_pool_provider).bind(
            self.services,
            self.service_registry,
        )
        MCPServiceAdapter(mcp_manager_provider).bind(
            self.services,
            self.service_registry,
        )

    def bind_ai_capability_auditor(self, auditor) -> None:
        """Bind an optional independent AI reviewer for ask-policy decisions."""

        if self.capability_policy is None:
            raise RuntimeError("Capability policy runtime is not ready")
        self.capability_policy.bind_ai_auditor(auditor)

    def bind_service_package_auditor(self, auditor) -> None:
        """Bind an optional independent local AI source auditor for Service packages."""

        if self.package_manager is None:
            raise RuntimeError("Service package runtime is not ready")
        self.package_manager.trust.bind_local_ai_auditor(auditor)

    def cloud_ai_authorization_headers(
        self, principal: RequestPrincipal
    ) -> dict[str, str]:
        """Resolve the bound installation to its private Cloud Device credential."""

        if self.database is None or self.remote is None:
            raise IdentityBindingError("Platform identity runtime is not ready")
        installation = IdentityRepository(self.database).get_installation()
        if installation is None:
            raise IdentityBindingError("Installation is not bound to AI2Apps Cloud")
        if installation.id != principal.installation_id:
            raise IdentityBindingError(
                "Request principal does not belong to the bound installation"
            )
        if installation.status != "active":
            raise IdentityBindingError("Installation is not active")
        return self.remote.cloud_ai_headers(
            device_id=installation.cloud_device_id,
            principal=principal,
        )

    def cloud_for_browser(self, browser_session_id: str) -> AI2AppsCloudClient:
        """Return one persistent Cloud client isolated to a browser profile."""

        if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", browser_session_id):
            raise ValueError("Cloud browser session identifier is invalid")
        existing = self._browser_cloud_clients.get(browser_session_id)
        if existing is not None:
            return existing
        if self.cloud is None:
            raise RuntimeError("Cloud client is not ready")
        if len(self._browser_cloud_clients) >= 64:
            raise RuntimeError("Too many active Cloud browser sessions")
        client = AI2AppsCloudClient(
            base_url=self.cloud.base_url,
            session_store=CloudSessionStore(
                self.cloud.session_store.backend,
                self.cloud.base_url,
                namespace=f"browser:{browser_session_id}",
            ),
            transport=self.cloud.transport,
            timeout=self.cloud.timeout,
        )
        self._browser_cloud_clients[browser_session_id] = client
        return client

    async def clear_cloud_for_browser(self, browser_session_id: str) -> None:
        """Forget and close one browser's Cloud session without affecting peers."""

        if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", browser_session_id):
            return
        client = self._browser_cloud_clients.pop(browser_session_id, None)
        if client is None and self.cloud is not None:
            client = AI2AppsCloudClient(
                base_url=self.cloud.base_url,
                session_store=CloudSessionStore(
                    self.cloud.session_store.backend,
                    self.cloud.base_url,
                    namespace=f"browser:{browser_session_id}",
                ),
                transport=self.cloud.transport,
                timeout=self.cloud.timeout,
            )
        if client is not None:
            await client.clear_session()
            await client.close()

    def legacy_api_key_principal(self) -> RequestPrincipal:
        """Map the installation API key to its bound core account when available."""

        if self.database is None:
            return RequestPrincipal.legacy_local()
        identities = IdentityRepository(self.database)
        installation = identities.get_installation()
        if installation is None or installation.status != "active":
            return RequestPrincipal.legacy_local()
        return identities.principal_for(installation.core_user_id)

    def authorize_local_session(self, token: str | None) -> RequestPrincipal | None:
        """Resolve a host-only browser session against the current member projection."""

        if self.database is None:
            return None
        return IdentityRepository(self.database).authorize_local_session(token)

    def local_session_cookie_name(self) -> str:
        """Return this Installation's browser-session cookie name.

        An unbound installation cannot issue a member session, so the legacy
        name is returned only to keep pre-enrollment request handling simple.
        """

        if self.security_identity is None:
            return LOCAL_SESSION_COOKIE
        return local_session_cookie_name(self.security_identity.security_instance_id)

    def legacy_admin_session_cookie_name(self) -> str:
        """Return the legacy Admin cookie name scoped to this Local instance."""

        if self.security_identity is None:
            return "omlx_admin_session"
        suffix = hashlib.sha256(
            self.security_identity.security_instance_id.encode("ascii")
        ).hexdigest()[:16]
        return f"omlx_admin_session_{suffix}"

    def local_session_token_from_cookies(self, cookies) -> str | None:
        """Read this Installation's cookie, with bounded legacy migration."""

        cookie_name = self.local_session_cookie_name()
        token = cookies.get(cookie_name)
        if token is None and cookie_name != LOCAL_SESSION_COOKIE:
            token = cookies.get(LOCAL_SESSION_COOKIE)
        return token

    def cloud_browser_cookie_name(self) -> str:
        """Return this Local instance's Cloud browser-profile cookie name."""

        if self.security_identity is None:
            from ai2apps.cloud_client import AI2APPS_CLOUD_BROWSER_COOKIE

            return AI2APPS_CLOUD_BROWSER_COOKIE
        return cloud_browser_cookie_name(
            self.security_identity.security_instance_id
        )

    def cloud_browser_session_from_cookies(self, cookies) -> str | None:
        """Read the scoped Cloud browser ID with one-release compatibility."""

        from ai2apps.cloud_client import AI2APPS_CLOUD_BROWSER_COOKIE

        cookie_name = self.cloud_browser_cookie_name()
        value = cookies.get(cookie_name)
        if value is None and cookie_name != AI2APPS_CLOUD_BROWSER_COOKIE:
            value = cookies.get(AI2APPS_CLOUD_BROWSER_COOKIE)
        return value

    def revoke_local_session(self, token: str | None) -> None:
        """Revoke one host-only browser session without affecting other members."""

        if self.database is not None:
            IdentityRepository(self.database).revoke_local_session(token)

    async def exchange_member_handoff(
        self, handoff: str
    ) -> tuple[str, RequestPrincipal]:
        """Consume a Cloud handoff without retaining its assertion in browser state."""

        if self.remote is None:
            raise IdentityBindingError("Remote installation runtime is not ready")
        return await self.remote.exchange_member_handoff(handoff=handoff)

    async def activate_current_cloud_member(
        self,
        *,
        cloud: AI2AppsCloudClient | None = None,
    ) -> tuple[str, RequestPrincipal]:
        """Turn the signed-in registered Cloud member into the Local actor."""

        if self.remote is None:
            raise IdentityBindingError("Remote installation runtime is not ready")
        return await self.remote.activate_current_cloud_member(cloud=cloud)

    async def bootstrap_core_account(
        self,
        *,
        display_name: str,
        owner_password: str,
        cloud: AI2AppsCloudClient,
    ) -> tuple[str, RequestPrincipal]:
        """Claim an unbound Local instance for the signed-in Cloud account."""

        if self.database is None or self.remote is None:
            raise IdentityBindingError("Installation identity runtime is not ready")
        async with self._core_bootstrap_lock:
            identities = IdentityRepository(self.database)
            if identities.get_installation() is not None:
                raise IdentityBindingError(
                    "This Local instance already has a Core account"
                )
            account = await self.remote._request(
                "GET", "/v1/auth/me", cloud=cloud
            )
            user = account.get("user")
            if not isinstance(user, dict):
                raise RemoteAccessError(
                    502,
                    "CLOUD_ACCOUNT_INVALID",
                    "Cloud returned an invalid account projection",
                )
            account_name = str(user.get("displayName") or "AI2Apps").strip()
            organization = await self.remote._request(
                "POST",
                "/v1/organizations",
                json={
                    "type": "household",
                    "displayName": f"{account_name}'s household",
                },
                cloud=cloud,
            )
            organization_id = str(organization.get("organizationId") or "")
            if not re.fullmatch(
                r"[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-"
                r"[89ab][0-9a-f]{3}-[0-9a-f]{12}",
                organization_id,
            ):
                raise RemoteAccessError(
                    502,
                    "CLOUD_ORGANIZATION_INVALID",
                    "Cloud returned an invalid organization identity",
                )
            reauth = await self.remote._request(
                "POST",
                "/v1/owner-reauth/grants",
                json={
                    "purpose": "installation.bind",
                    "resourceType": "organization",
                    "resourceId": organization_id,
                    "password": owner_password,
                },
                cloud=cloud,
            )
            grant = str(reauth.get("grant") or "")
            if not grant:
                raise RemoteAccessError(
                    502,
                    "CLOUD_REAUTH_INVALID",
                    "Cloud omitted the installation binding grant",
                )
            await self.remote.register(
                display_name=display_name,
                cloud=cloud,
                organization_id=organization_id,
                owner_reauth_grant=grant,
                idempotency_key=str(uuid.uuid4()),
            )
            token, principal = await self.remote.activate_current_cloud_member(
                cloud=cloud
            )
            if not principal.is_core:
                identities.revoke_local_session(token)
                raise IdentityBindingError(
                    "Cloud registration did not bind the signed-in account as Core"
                )
            return token, principal

    def stop(self) -> None:
        """Release runtime resources.

        Connections are deliberately transaction-scoped in this milestone, so
        shutdown currently has no persistent handle to close.
        """
        if self._instance_lease is not None:
            self._instance_lease.release()
            self._instance_lease = None
