"""App Providers for the Harness's existing Session tools."""

import logging

from ai2apps.api.ownership import authorize_session
from ai2apps.services import ToolProviderError
from ai2apps.services.aaat import principal_for
from ai2apps.services.capability_routing import CapabilityProvider, ProviderIncompatible

from .local_files import TOOLS as FILE_TOOLS
from .harness_materials import TOOLS as MATERIAL_TOOLS
from .continuity import TOOLS as CONTINUITY_TOOLS

APP_ID = "ai2apps.harness"
TOOLS = (
    "process.start", "process.status", "process.wait", "process.logs", "process.cancel", "process.write_stdin",
    "workspace.list", "workspace.stat", "workspace.read", "workspace.search",
    "workspace.glob", "workspace.write", "workspace.apply_patch",
    "resource.read", "artifact.create", "artifact.list", "artifact.preview", "artifact.export",
    "attachment.list", "attachment.status", "document.info", "document.read", "document.search", "document.preview", "document.create_pdf",
    "host.directory.list", "host.directory.import",
) + FILE_TOOLS + MATERIAL_TOOLS + CONTINUITY_TOOLS

_PROCESS_START = (
    "Run a command as an argv array inside the current Session workspace, with networking off. "
    "This App waits up to 10 seconds and returns stdout, stderr and exit_code for a settled process. "
    "If still running, use process.wait with its returned process ID; waiting also returns output. "
    "Always inspect exit_code and stderr. A nonzero exit is a command failure: investigate and correct "
    "the command's arguments before moving to unrelated tools. A started process is not success. "
    "Paths are restricted to this Session workspace; an empty workspace cannot establish host-wide disk usage. "
    "For available disk space, run df -h . and identify the reported volume. "
    "On macOS, du -a and -d cannot be combined: use du -h -d 2 . for directory totals."
    " Set wait_ms=0 to return a background job immediately; process.jobs recovers its ID. "
    "Set pty=true for an interactive terminal, then use write_stdin, resize or interrupt. "
    "Checkpoint long multi-step work with task.checkpoint; task.resume recovers actual receipts after interruption."
)



def install_harness_app(runtime):
    from .local_directories import install as install_directories
    directories = install_directories(runtime)
    runtime.harness_local_directories = directories
    from .local_files import install as install_files
    from .harness_materials import install as install_materials
    files = install_files(runtime, directories)
    install_materials(runtime)
    from .continuity import install as install_continuity
    runtime.harness_continuity = install_continuity(runtime)
    router = runtime.app_capability_router
    registry = runtime.service_registry

    async def offline_process(arguments, context):
        if arguments.get("network") is True or arguments.get("environment"):
            raise ProviderIncompatible(
                "Harness App commands run offline with the standard sandbox environment."
            )
        return arguments

    for name in TOOLS:
        tool = runtime.services.get_tool(name)
        bound = registry.bound_tool(name)
        if bound is None:
            raise RuntimeError(f"Harness service tool is not bound: {name}")

        async def execute(arguments, context, handler=bound.handler, capability=name):
            if not context.session_id:
                raise ToolProviderError("Harness App requires an owned Session")
            authorize_session(runtime, principal_for(runtime, context), context.session_id)
            result = await handler(arguments, context)
            if capability in ('process.start', 'process.wait', 'process.status'):
                from ai2apps.processes.service import _record
                if capability == 'process.start':
                    from ai2apps.processes.models import ProcessServiceError
                    try:
                        wait_ms = arguments.get('wait_ms', 10000)
                        record = (await runtime.processes.wait(result['id'], session_id=context.session_id,
                            run_id=context.trace_id, timeout_ms=wait_ms)) if wait_ms else runtime.processes.status(
                                result['id'],session_id=context.session_id,run_id=context.trace_id)
                    except ProcessServiceError as error:
                        if error.code != 'process_wait_timeout':
                            raise
                        record = runtime.processes.status(result['id'], session_id=context.session_id,
                            run_id=context.trace_id)
                    result = _record(record)
                logs = runtime.processes.logs(result['id'], session_id=context.session_id,
                    run_id=context.trace_id, limit=200)
                result.update(stdout=''.join(i.content for i in logs if i.stream == 'stdout')[-32768:],
                    stderr=''.join(i.content for i in logs if i.stream == 'stderr')[-32768:],
                    output_after=logs[-1].sequence if logs else 0,
                    command_failed=result.get('exit_code') is not None and result['exit_code'] != 0)
            return result

        instructions = [_PROCESS_START if name == "process.start" else tool.description]
        if name.startswith("process.") and name != "process.start":
            instructions.append("Use only a process ID from the current Run.")
        if name == "process.write_stdin":
            instructions.append("Send at most 64 KiB of UTF-8 to the owned live process. Set close=true to send EOF. Input can execute commands or affect the process: retain operation confirmation. Do not treat input accepted as process completion; inspect process.wait/status and logs.")
        if name == "document.preview":
            instructions.append("Returns a short text preview, not rendered page images. If truncated=true, read further using document.read with next_offset; preview is not evidence that the entire document was read.")
        if name == "document.create_pdf":
            instructions.append("Typeset supplied Markdown or plain text with the existing local PDF engine, without an AI drawing call. Returns a real Session artifact; use its ID for export. Paths stay in this Session workspace. For reading an existing PDF use document.read/search instead.")
        router.register(CapabilityProvider(
            f"{APP_ID}.{name}", name, APP_ID, execute,
            prepare=offline_process if name == "process.start" else directories.prepare if name in ('host.directory.list', 'host.directory.import') else files.prepare if name in FILE_TOOLS else None,
            version="2" if name in ("process.start", "process.wait", "process.status") else "1",
            display_name=tool.display_name, summary=instructions[0],
            agent_context={"schema": "ai2apps.aaat-declaration/v1", "instructions": instructions},
            discovery_context=runtime.harness_continuity.observation if name == 'task.resume' else None,
        ))

        async def dispatch(arguments, context, capability=name, handler=bound.handler):
            # App Chat and explicitly selected Providers use the normal router.
            # Keep the platform service entry point for existing non-App callers.
            if (arguments.get("provider") or context.agent_provider_binding
                    or runtime.app_chat.binding(context.session_id)):
                return await router.invoke(capability, arguments, context)
            return await handler(arguments, context)

        registry.bind_tool(name, provider_key=bound.provider_key, handler=dispatch)

    logging.getLogger(__name__).info("Installed Harness App providers from %s", __file__)
