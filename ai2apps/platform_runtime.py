"""Lifecycle boundary for the durable AI2Apps platform backend."""

from __future__ import annotations

import asyncio
import logging
import os
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
from ai2apps.images import install_image_service
from ai2apps.packages import PackageRepository, ServicePackageManager
from ai2apps.packages.registry import RegistryPackageManager
from ai2apps.remote import (
    RemoteAccessManager,
    RemoteDeviceRepository,
    RemoteFrpcConfig,
    RemoteFrpcSupervisor,
)
from ai2apps.processes import ProcessManager, install_process_service
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
from ai2apps.storage import PlatformDatabase
from ai2apps.storage.repositories import SessionRepository
from ai2apps.terminal import TerminalManager, install_terminal_service
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
        self.notifications: EventNotificationBus | None = None
        self.events: EventStore | None = None
        self.services: ServiceRepository | None = None
        self.service_registry: ServiceRegistry | None = None
        self.tools: ToolGateway | None = None
        self.capabilities: CapabilityRepository | None = None
        self.secrets: SecretRepository | None = None
        self.cloud: AI2AppsCloudClient | None = None
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
        if self.document_manager is not None:
            await self.document_manager.shutdown()
        if self.remote is not None:
            await self.remote.shutdown()
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
        """Initialize the single platform database when a data root exists."""

        if self.config.paths is None:
            return self._database_status

        database = PlatformDatabase(self.config.paths.database_path)
        state = database.initialize()
        notifications = EventNotificationBus()
        self.database = database
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
        )
        self.secrets = SecretRepository(database, self.events, secret_backend)
        cloud_base_url = os.environ.get(
            "AI2APPS_CLOUD_BASE_URL", DEFAULT_AI2APPS_CLOUD_BASE_URL
        )
        self.cloud = AI2AppsCloudClient(
            base_url=cloud_base_url,
            session_store=CloudSessionStore(secret_backend, cloud_base_url),
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
        self.browser = BrowserManager(
            ChromeBrowserBackend(
                BrowserRuntimeConfig(
                    profile_path=str(self.config.paths.browsers_path / "chrome-default")
                )
            ),
            workspace=self.workspace,
        )
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

    def stop(self) -> None:
        """Release runtime resources.

        Connections are deliberately transaction-scoped in this milestone, so
        shutdown currently has no persistent handle to close.
        """
