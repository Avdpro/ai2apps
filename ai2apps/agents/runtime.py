"""Recoverable asynchronous Agent scheduler and action interpreter."""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress
from datetime import UTC, datetime

from ai2apps.capabilities import (
    CapabilityPolicyEngine,
    CapabilityRepository,
    PolicyEffect,
    action_preview,
)
from ai2apps.services import ToolCallContext, ToolGateway, ToolGatewayError

from .models import (
    AgentAction,
    AgentExecutionContext,
    AgentRunStatus,
    CompleteAction,
    ContinueAction,
    FailAction,
    InteractionAction,
    InteractionKind,
    InteractionStatus,
    ModelCallAction,
    RunStepStatus,
    StatusAction,
    ToolCallAction,
)
from .repository import AgentRepository

logger = logging.getLogger(__name__)

AgentExecutor = Callable[
    [AgentExecutionContext],
    AgentAction | Awaitable[AgentAction],
]
ModelProgressReporter = Callable[[dict], None | Awaitable[None]]
ModelProvider = Callable[..., dict | Awaitable[dict]]


async def _await_action(value):
    if inspect.isawaitable(value):
        return await value
    return value


class AgentRuntime:
    def __init__(
        self,
        repository: AgentRepository,
        tools: ToolGateway,
        capability_policy: CapabilityPolicyEngine | None = None,
        capabilities: CapabilityRepository | None = None,
        *,
        global_concurrency: int = 32,
    ) -> None:
        if global_concurrency <= 0:
            raise ValueError("global_concurrency must be positive")
        self.repository = repository
        self.tools = tools
        self.capability_policy = capability_policy
        self.capabilities = capabilities
        self.global_concurrency = global_concurrency
        self._executors: dict[str, AgentExecutor] = {}
        self._model_provider: ModelProvider | None = None
        self._model_provider_accepts_progress = False
        self._wake = asyncio.Event()
        self._stopping = False
        self._dispatcher: asyncio.Task[None] | None = None
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._run_terminal_handlers: list[Callable[[str], None]] = []
        self._terminal_events: dict[str, asyncio.Event] = {}

    def bind_executor(self, executor_key: str, executor: AgentExecutor) -> None:
        if not executor_key:
            raise ValueError("executor_key must not be empty")
        self._executors[executor_key] = executor

    def bind_model_provider(self, provider: ModelProvider) -> None:
        self._model_provider = provider
        try:
            parameters = inspect.signature(provider).parameters.values()
            self._model_provider_accepts_progress = any(
                item.kind is inspect.Parameter.VAR_POSITIONAL for item in parameters
            ) or sum(
                item.kind
                in {
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                }
                for item in parameters
            ) >= 2
        except (TypeError, ValueError):
            self._model_provider_accepts_progress = False

    async def _call_model_provider(
        self,
        request: dict,
        progress_reporter: ModelProgressReporter,
    ) -> dict:
        assert self._model_provider is not None
        if self._model_provider_accepts_progress:
            value = self._model_provider(request, progress_reporter)
        else:
            value = self._model_provider(request)
        return await _await_action(value)

    async def _run_model_call(
        self,
        run_id: str,
        request: dict,
        *,
        model_name: str,
        step_sequence: int,
    ) -> dict:
        """Invoke a model while durably surfacing stream and wait progress."""

        latest_update: dict = {}
        started = asyncio.get_running_loop().time()

        async def publish(update: dict) -> None:
            nonlocal latest_update
            latest_update = dict(update)
            content = dict(update.get("content") or {})
            content.setdefault("tone", "info")
            content.setdefault("icon", "sparkles")
            content.setdefault("model", model_name)
            content.setdefault("step", step_sequence)
            await asyncio.to_thread(
                self.repository.update_status_line,
                run_id,
                phase=str(update.get("phase") or "model"),
                text=str(update.get("text") or f"Waiting for {model_name}"),
                presentation=str(update.get("presentation") or "indeterminate"),
                progress=update.get("progress"),
                content=content,
            )

        await publish(
            {
                "phase": "model_starting",
                "text": f"Starting {model_name}",
                "presentation": "indeterminate",
                "content": {
                    "effect": "indeterminate",
                    "detail": f"Preparing model context · step {step_sequence}",
                },
            }
        )
        task = asyncio.create_task(
            self._call_model_provider(request, publish),
            name=f"ai2apps-agent-model-{run_id}-{step_sequence}",
        )
        try:
            while True:
                done, _ = await asyncio.wait({task}, timeout=5.0)
                if task in done:
                    return await task
                elapsed = max(1, int(asyncio.get_running_loop().time() - started))
                content = dict(latest_update.get("content") or {})
                detail = content.get("detail")
                if latest_update.get("phase") == "model_streaming":
                    text = str(latest_update.get("text") or "Receiving model response")
                    if detail:
                        detail = f"{detail} · {elapsed}s elapsed"
                else:
                    text = f"Waiting for {model_name} · {elapsed}s"
                    detail = "The model is generating the next Agent action"
                await publish(
                    {
                        "phase": str(latest_update.get("phase") or "model_waiting"),
                        "text": text,
                        "presentation": "indeterminate",
                        "content": {
                            **content,
                            "effect": "indeterminate",
                            "detail": detail,
                            "elapsed_seconds": elapsed,
                        },
                    }
                )
        finally:
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    def bind_run_terminal_handler(self, handler: Callable[[str], None]) -> None:
        """Register fail-safe cleanup invoked when a Run reaches a terminal state."""

        self._run_terminal_handlers.append(handler)

    def _notify_run_terminal(self, run_id: str) -> None:
        event = self._terminal_events.pop(run_id, None)
        if event is not None:
            event.set()
        for handler in tuple(self._run_terminal_handlers):
            try:
                handler(run_id)
            except Exception:
                logger.exception("Agent Run terminal cleanup failed for %s", run_id)

    async def start(self) -> None:
        if self._dispatcher is not None:
            return
        self._stopping = False
        await asyncio.to_thread(self.repository.recover_interrupted)
        self._dispatcher = asyncio.create_task(
            self._dispatch_loop(),
            name="ai2apps-agent-dispatcher",
        )
        self.wake()

    async def stop(self) -> None:
        self._stopping = True
        if self._dispatcher is not None:
            self._dispatcher.cancel()
            with suppress(asyncio.CancelledError):
                await self._dispatcher
        self._dispatcher = None
        await asyncio.to_thread(self.repository.suspend_queued_for_shutdown)
        tasks = tuple(self._tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()

    def wake(self) -> None:
        self._wake.set()

    def cancel(self, run_id: str):
        descendants = self.repository.list_descendants(run_id)
        for child in reversed(descendants):
            if child.status not in {
                AgentRunStatus.COMPLETED,
                AgentRunStatus.FAILED,
                AgentRunStatus.CANCELLED,
            }:
                self.repository.request_cancel(child.id)
                self._notify_run_terminal(child.id)
                task = self._tasks.get(child.id)
                if task is not None:
                    task.cancel()
        run = self.repository.request_cancel(run_id)
        self._notify_run_terminal(run_id)
        task = self._tasks.get(run_id)
        if task is not None:
            task.cancel()
        self.wake()
        return run

    def pause(self, run_id: str):
        descendants = self.repository.list_descendants(run_id)
        for child in reversed(descendants):
            if child.status in {
                AgentRunStatus.QUEUED,
                AgentRunStatus.PLANNING,
                AgentRunStatus.RUNNING,
            }:
                self.repository.request_pause(child.id)
                task = self._tasks.get(child.id)
                if task is not None:
                    task.cancel()
        run = self.repository.request_pause(run_id)
        task = self._tasks.get(run_id)
        if task is not None:
            task.cancel()
        self.wake()
        return run

    def resume(self, run_id: str, *, uncertain_resolution: str | None = None):
        """Resume a parent plus safely paused descendants, deepest first."""

        for child in reversed(self.repository.list_descendants(run_id)):
            if child.status is not AgentRunStatus.INTERRUPTED:
                continue
            has_uncertain = any(
                step.status is RunStepStatus.UNCERTAIN
                for step in self.repository.list_steps(child.id)
            )
            if not has_uncertain:
                self.repository.resume_interrupted(child.id)
        run = self.repository.resume_interrupted(
            run_id, uncertain_resolution=uncertain_resolution
        )
        self.wake()
        return run

    async def wait_for_terminal(
        self, run_id: str, *, timeout: float | None = None
    ):
        """Wait for a child Run without losing its durable terminal result."""

        terminal = {
            AgentRunStatus.COMPLETED,
            AgentRunStatus.FAILED,
            AgentRunStatus.CANCELLED,
        }
        run = await asyncio.to_thread(self.repository.get_run, run_id)
        if run.status in terminal:
            return run
        event = self._terminal_events.setdefault(run_id, asyncio.Event())
        # Close the registration race with a second durable read.
        run = await asyncio.to_thread(self.repository.get_run, run_id)
        if run.status not in terminal:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        return await asyncio.to_thread(self.repository.get_run, run_id)

    @staticmethod
    def _step_budget(run, definition) -> int:
        configured = run.input.get("run_budget", {}).get("max_steps")
        limit = (
            min(definition.max_steps, configured)
            if isinstance(configured, int) and configured > 0
            else definition.max_steps
        )
        delegated = run.delegation.get("budget", {}).get("max_steps")
        if isinstance(delegated, int) and delegated > 0:
            return min(limit, delegated)
        return limit

    async def wait_for_idle(self, timeout: float = 5.0) -> None:
        async def idle() -> None:
            while True:
                if not self._tasks and self.repository.dispatching_count() == 0:
                    return
                await asyncio.sleep(0.01)

        await asyncio.wait_for(idle(), timeout=timeout)

    async def _dispatch_loop(self) -> None:
        while not self._stopping:
            try:
                await asyncio.to_thread(self.repository.expire_interactions)
                if self.capabilities is not None:
                    await asyncio.to_thread(self.capabilities.expire_leases)
                while len(self._tasks) < self.global_concurrency:
                    run = await asyncio.to_thread(self.repository.claim_next)
                    if run is None:
                        break
                    task = asyncio.create_task(
                        self._run_claimed(run.id),
                        name=f"ai2apps-agent-{run.id}",
                    )
                    self._tasks[run.id] = task
                    task.add_done_callback(
                        lambda _task, run_id=run.id: self._task_done(run_id)
                    )
                self._wake.clear()
                with suppress(TimeoutError):
                    await asyncio.wait_for(self._wake.wait(), timeout=0.25)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("AI2Apps Agent dispatcher pass failed")
                await asyncio.sleep(0.1)

    def _task_done(self, run_id: str) -> None:
        task = self._tasks.pop(run_id, None)
        if task is not None and not task.cancelled():
            error = task.exception()
            if error is not None:
                logger.error(
                    "Agent task %s escaped runtime handling",
                    run_id,
                    exc_info=(type(error), error, error.__traceback__),
                )
        try:
            run = self.repository.get_run(run_id)
            if run.status in {
                AgentRunStatus.COMPLETED,
                AgentRunStatus.FAILED,
                AgentRunStatus.CANCELLED,
            }:
                self._notify_run_terminal(run_id)
        except Exception:
            logger.exception("Could not inspect Agent Run %s for cleanup", run_id)
        self.wake()

    async def _run_claimed(self, run_id: str) -> None:
        active_tool_step = None
        active_tool_effects: tuple[str, ...] = ()
        active_model_step = None
        try:
            run = await asyncio.to_thread(
                self.repository.transition,
                run_id,
                expected={AgentRunStatus.PLANNING},
                status=AgentRunStatus.RUNNING,
            )
            definition, run, _, steps, interactions = await asyncio.to_thread(
                self.repository.snapshot, run_id
            )
            executor = self._executors.get(definition.executor_key)
            if executor is None:
                await self._fail(
                    run_id,
                    "executor_unavailable",
                    f"Agent executor is not bound: {definition.executor_key}",
                )
                return
            remaining = (run.deadline_at - datetime.now(UTC)).total_seconds()
            if remaining <= 0:
                await self._fail(
                    run_id, "run_deadline_exceeded", "Agent deadline expired"
                )
                return
            context = AgentExecutionContext(definition, run, steps, interactions)
            await asyncio.to_thread(
                self.repository.update_status_line,
                run_id,
                phase="planning",
                text="Examining the conversation",
                presentation="pulse",
                content={
                    "tone": "info",
                    "effect": "shimmer",
                    "icon": "sparkles",
                    "detail": f"Choosing the next action · step {run.current_step + 1}",
                },
            )
            async with asyncio.timeout(remaining):
                action = await _await_action(executor(context))
            if isinstance(action, CompleteAction):
                await asyncio.to_thread(
                    self.repository.transition,
                    run_id,
                    expected={AgentRunStatus.RUNNING},
                    status=AgentRunStatus.COMPLETED,
                    output=action.output,
                )
            elif isinstance(action, FailAction):
                await self._fail(
                    run_id,
                    action.code,
                    action.message,
                    retryable=action.retryable,
                )
            elif isinstance(action, StatusAction):
                await asyncio.to_thread(
                    self.repository.update_status_line,
                    run_id,
                    phase=action.phase,
                    text=action.text,
                    presentation=action.presentation,
                    progress=action.progress,
                    content=action.content,
                )
                await self._requeue(run_id, action.text)
            elif isinstance(action, ContinueAction):
                await self._requeue(run_id, action.status_text)
            elif isinstance(action, InteractionAction):
                await asyncio.to_thread(
                    self.repository.create_interaction,
                    run_id,
                    request_key=action.request_key,
                    kind=action.kind,
                    prompt=action.prompt,
                    response_schema=action.response_schema,
                    ui_hints=action.ui_hints,
                    request=action.request,
                    timeout_seconds=action.timeout_seconds,
                )
            elif isinstance(action, ToolCallAction):
                if run.current_step >= self._step_budget(run, definition):
                    await self._fail(
                        run_id,
                        "max_steps_exceeded",
                        "Agent step budget exhausted",
                    )
                    return
                await asyncio.to_thread(
                    self.repository.update_status_line,
                    run_id,
                    phase="tool_preparing",
                    text=f"Preparing {action.tool_name}",
                    presentation="pulse",
                    content={
                        "tone": "info",
                        "effect": "shimmer",
                        "icon": "activity",
                        "detail": "Checking permissions and Tool availability",
                        "tool_name": action.tool_name,
                    },
                )
                tool = await asyncio.to_thread(
                    self.tools.repository.get_tool, action.tool_name
                )
                # GrantLease/policy is authoritative once M4 is configured.
                # The Run JSON field remains a response compatibility cache only.
                effective_capabilities = (
                    set() if self.capability_policy is not None
                    else set(run.granted_capabilities)
                )
                required_capabilities = self.tools.required_capabilities(
                    tool, action.arguments
                )
                missing = tuple(sorted(required_capabilities - effective_capabilities))
                decision = None
                if missing and self.capability_policy is not None:
                    decision = await self.capability_policy.evaluate(
                        run_id=run.id,
                        agent_key=definition.agent_key,
                        tool_name=action.tool_name,
                        capabilities=missing,
                        effects=tool.effects,
                        arguments=action.arguments,
                    )
                    effective_capabilities.update(decision.allowed_capabilities)
                    if self.capabilities is not None:
                        await asyncio.to_thread(
                            self.capabilities.record_decision,
                            run_id=run.id,
                            interaction_id=None,
                            decision=decision.effect,
                            source=decision.source,
                            capabilities=missing,
                            tool_name=action.tool_name,
                            effects=tool.effects,
                            matched_policy_ids=decision.matched_policy_ids,
                            evidence={
                                **(decision.evidence or {}),
                                "matched_lease_ids": decision.matched_lease_ids,
                            },
                        )
                    missing = tuple(
                        sorted(required_capabilities - effective_capabilities)
                    )
                if decision is not None and decision.effect is PolicyEffect.DENY:
                    await self._fail(
                        run_id,
                        "capability_policy_denied",
                        f"Capability policy denied {action.tool_name}",
                    )
                    return
                if missing:
                    preview = action_preview(
                        action.tool_name, tool.effects, action.arguments
                    )
                    await asyncio.to_thread(
                        self.repository.create_interaction,
                        run_id,
                        request_key=f"capability:{action.call_id}",
                        kind=InteractionKind.APPROVAL,
                        prompt=f"Allow {preview['summary']}?",
                        response_schema={
                            "type": "object",
                            "properties": {
                                "decision": {
                                    "type": "string",
                                    "enum": ["approve", "deny"],
                                },
                                "scope": {
                                    "type": "string",
                                    "enum": [
                                        "once", "run", "session", "agent", "app"
                                    ],
                                },
                            },
                            "required": ["decision"],
                            "additionalProperties": False,
                        },
                        ui_hints={
                            "control": "approval",
                            "default_scope": "once",
                            "scopes": ["once", "run", "session", "agent", "app"],
                            "operation_class": preview["operation_class"],
                            "risk_level": preview["risk_level"],
                        },
                        request={
                            "tool_name": action.tool_name,
                            "arguments": preview["arguments"],
                            "capabilities": missing,
                            "effects": list(tool.effects),
                            "action_preview": preview,
                            "resource_selector": preview["resource_selector"],
                        },
                        timeout_seconds=86_400,
                    )
                    return
                if decision is not None and self.capabilities is not None:
                    # A once grant is consumed before dispatch. A crash can therefore
                    # never replay authority without asking the user again.
                    await asyncio.to_thread(
                        self.capabilities.consume_single_use_leases,
                        decision.matched_lease_ids,
                    )
                step, created = await asyncio.to_thread(
                    self.repository.create_step,
                    run_id,
                    action_key=action.call_id,
                    kind="tool",
                    input=action.arguments,
                    tool_name=action.tool_name,
                )
                active_tool_step = step
                active_tool_effects = tool.effects
                if not created:
                    if step.status is RunStepStatus.COMPLETED:
                        await self._requeue(run_id, f"Completed {action.tool_name}")
                    elif step.status is RunStepStatus.UNCERTAIN:
                        await asyncio.to_thread(
                            self.repository.transition,
                            run_id,
                            expected={AgentRunStatus.RUNNING},
                            status=AgentRunStatus.INTERRUPTED,
                            error={"code": "uncertain_tool_side_effect"},
                        )
                    else:
                        await self._fail(
                            run_id,
                            "tool_step_not_retriable",
                            f"Tool step is {step.status.value}",
                        )
                    return
                try:
                    await asyncio.to_thread(
                        self.repository.update_status_line,
                        run_id,
                        phase="tool",
                        text=f"Running {action.tool_name}",
                        presentation="indeterminate",
                    )

                    async def report_tool_progress(update: dict) -> None:
                        await asyncio.to_thread(
                            self.repository.update_status_line,
                            run_id,
                            phase=str(update.get("phase") or "tool"),
                            text=str(
                                update.get("text")
                                or f"Running {action.tool_name}"
                            ),
                            presentation=(
                                "progress"
                                if update.get("progress") is not None
                                else "pulse"
                            ),
                            progress=update.get("progress"),
                            content=update.get("content") or {},
                        )

                    result = await self.tools.execute(
                        action.tool_name,
                        action.arguments,
                        context=ToolCallContext(
                            caller_id=f"agent:{definition.agent_key}",
                            session_id=run.session_id,
                            granted_capabilities=frozenset(effective_capabilities),
                            trace_id=run.id,
                            progress_reporter=report_tool_progress,
                        ),
                        timeout_ms=action.timeout_ms,
                    )
                except ToolGatewayError as error:
                    await asyncio.to_thread(
                        self.repository.settle_step,
                        step.id,
                        status=RunStepStatus.FAILED,
                        error={"code": error.code, "message": str(error)},
                    )
                    await self._fail(
                        run_id, error.code, str(error), retryable=error.retryable
                    )
                    return
                await asyncio.to_thread(
                    self.repository.settle_step,
                    step.id,
                    status=RunStepStatus.COMPLETED,
                    output=result.output,
                )
                active_tool_step = None
                await self._requeue(run_id, f"Completed {action.tool_name}")
            elif isinstance(action, ModelCallAction):
                if run.current_step >= self._step_budget(run, definition):
                    await self._fail(
                        run_id,
                        "max_steps_exceeded",
                        "Agent step budget exhausted",
                    )
                    return
                step, created = await asyncio.to_thread(
                    self.repository.create_step,
                    run_id,
                    action_key=action.call_id,
                    kind="model",
                    input=action.request,
                )
                active_model_step = step
                if not created:
                    if step.status is RunStepStatus.COMPLETED:
                        await self._requeue(run_id, "Model response received")
                    else:
                        await self._fail(
                            run_id,
                            "model_step_not_retriable",
                            f"Model step is {step.status.value}",
                        )
                    return
                if self._model_provider is None:
                    await asyncio.to_thread(
                        self.repository.settle_step,
                        step.id,
                        status=RunStepStatus.FAILED,
                        error={"code": "model_provider_unavailable"},
                    )
                    await self._fail(
                        run_id,
                        "model_provider_unavailable",
                        "Model Runtime provider is not bound",
                    )
                    return
                try:
                    model_name = str(action.request.get("model") or "the model")
                    model_output = await _await_action(
                        self._run_model_call(
                            run_id,
                            action.request,
                            model_name=model_name,
                            step_sequence=step.sequence,
                        )
                    )
                except Exception as error:
                    await asyncio.to_thread(
                        self.repository.settle_step,
                        step.id,
                        status=RunStepStatus.FAILED,
                        error={"code": "model_provider_error", "message": str(error)},
                    )
                    await self._fail(
                        run_id,
                        "model_provider_error",
                        str(error),
                        retryable=True,
                    )
                    return
                await asyncio.to_thread(
                    self.repository.update_status_line,
                    run_id,
                    phase="model_interpreting",
                    text="Interpreting the model response",
                    presentation="pulse",
                    content={
                        "tone": "info",
                        "effect": "shimmer",
                        "icon": "sparkles",
                        "detail": "Selecting a Tool call or final response",
                        "model": model_name,
                        "step": step.sequence,
                    },
                )
                await asyncio.to_thread(
                    self.repository.settle_step,
                    step.id,
                    status=RunStepStatus.COMPLETED,
                    output=model_output,
                )
                active_model_step = None
                await self._requeue(run_id, "Model response received")
            else:
                await self._fail(
                    run_id,
                    "invalid_agent_action",
                    f"Executor returned unsupported action: {type(action).__name__}",
                )
        except TimeoutError:
            await self._fail(run_id, "run_deadline_exceeded", "Agent deadline expired")
        except asyncio.CancelledError:
            current = await asyncio.to_thread(self.repository.get_run, run_id)
            if active_model_step is not None:
                await asyncio.to_thread(
                    self.repository.abandon_step_for_retry,
                    active_model_step.id,
                    error={"code": "runtime_stopped_during_model"},
                )
            if (
                active_tool_step is not None
                and current.status is AgentRunStatus.CANCELLED
            ):
                await asyncio.to_thread(
                    self.repository.settle_step,
                    active_tool_step.id,
                    status=(
                        RunStepStatus.CANCELLED
                        if not active_tool_effects
                        else RunStepStatus.UNCERTAIN
                    ),
                    error={"code": "user_cancelled_during_tool"},
                )
            if current.status is AgentRunStatus.CANCELLED:
                raise
            if (
                current.status is AgentRunStatus.INTERRUPTED
                and (current.error or {}).get("code") == "user_paused"
            ):
                if active_tool_step is not None:
                    if active_tool_effects:
                        await asyncio.to_thread(
                            self.repository.settle_step,
                            active_tool_step.id,
                            status=RunStepStatus.UNCERTAIN,
                            error={"code": "user_paused_during_tool"},
                        )
                    else:
                        await asyncio.to_thread(
                            self.repository.abandon_step_for_retry,
                            active_tool_step.id,
                            error={"code": "user_paused_during_tool"},
                        )
                raise
            if active_tool_step is not None:
                if active_tool_effects:
                    await asyncio.to_thread(
                        self.repository.settle_step,
                        active_tool_step.id,
                        status=RunStepStatus.UNCERTAIN,
                        error={"code": "runtime_stopped_during_tool"},
                    )
                    target = AgentRunStatus.INTERRUPTED
                else:
                    # Change the abandoned step's action key so the durable
                    # executor can safely create a fresh attempt after restart.
                    await asyncio.to_thread(
                        self.repository.abandon_step_for_retry,
                        active_tool_step.id,
                        error={"code": "runtime_stopped_during_tool"},
                    )
                    target = AgentRunStatus.QUEUED
            else:
                target = AgentRunStatus.QUEUED
            await asyncio.to_thread(
                self.repository.transition,
                run_id,
                expected={AgentRunStatus.RUNNING, AgentRunStatus.PLANNING},
                status=target,
                error=(
                    {"code": "runtime_stopped"}
                    if target is AgentRunStatus.QUEUED
                    else {"code": "uncertain_tool_side_effect"}
                ),
            )
            raise
        except Exception as exc:
            logger.exception("AgentRun %s failed", run_id)
            try:
                await self._fail(run_id, "agent_runtime_error", str(exc))
            except Exception:
                logger.exception("Failed to persist AgentRun %s failure", run_id)

    async def _requeue(self, run_id: str, text: str) -> None:
        await asyncio.to_thread(
            self.repository.transition,
            run_id,
            expected={AgentRunStatus.RUNNING},
            status=AgentRunStatus.QUEUED,
            status_text=text,
        )
        self.wake()

    async def _fail(
        self,
        run_id: str,
        code: str,
        message: str,
        *,
        retryable: bool = False,
    ) -> None:
        current = await asyncio.to_thread(self.repository.get_run, run_id)
        if current.status in {
            AgentRunStatus.COMPLETED,
            AgentRunStatus.FAILED,
            AgentRunStatus.CANCELLED,
        }:
            return
        await asyncio.to_thread(
            self.repository.transition,
            run_id,
            expected={current.status},
            status=AgentRunStatus.FAILED,
            error={"code": code, "message": message, "retryable": retryable},
            status_text=message or "Failed",
            presentation="error",
        )


def diagnostic_executor(context: AgentExecutionContext) -> AgentAction:
    """Deterministic built-in Agent used to qualify scheduling and UI protocols."""

    mode = context.run.input.get("mode", "echo")
    if mode in {"menu", "text", "file", "approval"}:
        key = f"diagnostic:{mode}"
        interaction = context.interaction(key)
        if interaction is None or interaction.status is InteractionStatus.PENDING:
            if mode == "menu":
                schema = {
                    "type": "object",
                    "properties": {
                        "choice": {"type": "string", "enum": ["alpha", "beta"]}
                    },
                    "required": ["choice"],
                    "additionalProperties": False,
                }
                hints = {"control": "menu", "options": ["alpha", "beta"]}
                kind = InteractionKind.MENU
            elif mode == "file":
                schema = {
                    "type": "object",
                    "properties": {
                        "resource_handle": {"type": "string", "minLength": 1}
                    },
                    "required": ["resource_handle"],
                    "additionalProperties": False,
                }
                hints = {"control": "file", "returns": "resource_handle"}
                kind = InteractionKind.FILE
            elif mode == "approval":
                schema = {
                    "type": "object",
                    "properties": {
                        "decision": {
                            "type": "string",
                            "enum": ["approve", "deny"],
                        }
                    },
                    "required": ["decision"],
                    "additionalProperties": False,
                }
                hints = {"control": "approval"}
                kind = InteractionKind.APPROVAL
            else:
                schema = {
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                    "additionalProperties": False,
                }
                hints = {"control": "text"}
                kind = InteractionKind.TEXT
            return InteractionAction(
                request_key=key,
                kind=kind,
                prompt=f"Diagnostic {mode} input",
                response_schema=schema,
                ui_hints=hints,
            )
        return CompleteAction(
            {
                "mode": mode,
                "response": interaction.response,
                "status": interaction.status,
            }
        )
    if mode == "tool":
        step = context.step("diagnostic-tool")
        if step is None:
            return ToolCallAction(
                call_id="diagnostic-tool",
                tool_name=context.run.input.get("tool_name", "system.echo"),
                arguments=context.run.input.get("arguments", {"value": "agent"}),
            )
        if step.status is RunStepStatus.COMPLETED:
            return CompleteAction({"tool_output": step.output})
        return FailAction("diagnostic_tool_failed", f"Tool step is {step.status.value}")
    if mode == "model":
        step = context.step("diagnostic-model")
        if step is None:
            return ModelCallAction(
                call_id="diagnostic-model",
                request=context.run.input.get(
                    "request",
                    {
                        "model": context.run.input.get("model", ""),
                        "messages": [{"role": "user", "content": "Say hello"}],
                    },
                ),
            )
        if step.status is RunStepStatus.COMPLETED:
            return CompleteAction({"model_output": step.output})
        return FailAction(
            "diagnostic_model_failed", f"Model step is {step.status.value}"
        )
    return CompleteAction(
        {
            "echo": {
                key: value
                for key, value in context.run.input.items()
                if key not in {"invocation", "parameters"}
            }
        }
    )


def install_diagnostic_agent(
    repository: AgentRepository, runtime: AgentRuntime
) -> None:
    repository.ensure_definition(
        agent_key="ai2apps.diagnostic-agent",
        package_version="1.0.0",
        display_name="Diagnostic Agent",
        description="Qualifies asynchronous Agent scheduling and interaction contracts.",
        executor_key="builtin:diagnostic-agent",
        manifest={
            "builtin": True,
            "discoverable": False,
            "invocation_schema": {"type": "object", "properties": {}},
        },
    )
    runtime.bind_executor("builtin:diagnostic-agent", diagnostic_executor)
