from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Any

from .redact import redact_text
from .state import now_text


class CodexDriverError(RuntimeError):
    pass


def _output_excerpt(value: Any, limit: int = 1200) -> str:
    text = redact_text(str(value or "")).strip()
    if len(text) <= limit:
        return text
    return "…" + text[-limit:]


def _event_summary(event: dict[str, Any]) -> dict[str, str] | None:
    event_type = str(event.get("type", ""))
    if event_type == "thread.started":
        return {
            "kind": "lifecycle",
            "status": "completed",
            "title": "Codex 会话已启动",
            "detail": _output_excerpt(event.get("thread_id"), 120),
        }
    if event_type == "turn.started":
        return {
            "kind": "lifecycle",
            "status": "running",
            "title": "Codex 开始执行测试任务",
            "detail": "",
        }
    if event_type not in {"item.started", "item.completed"}:
        return None
    item = event.get("item")
    if not isinstance(item, dict):
        return None
    item_type = str(item.get("type", ""))
    status = str(
        item.get("status")
        or ("running" if event_type == "item.started" else "completed")
    )
    if item_type == "agent_message":
        return {
            "kind": "message",
            "status": status,
            "title": "Codex",
            "detail": _output_excerpt(item.get("text")),
        }
    if item_type == "command_execution":
        detail = _output_excerpt(item.get("command"), 500)
        output = _output_excerpt(item.get("aggregated_output"), 800)
        if output:
            detail = f"{detail}\n{output}" if detail else output
        return {
            "kind": "command",
            "status": status,
            "title": "运行命令" if event_type == "item.started" else "命令执行结果",
            "detail": detail,
        }
    if item_type == "mcp_tool_call":
        arguments = item.get("arguments")
        title = arguments.get("title") if isinstance(arguments, dict) else None
        title = _output_excerpt(
            title or f"{item.get('server', '')}.{item.get('tool', '')}", 200
        )
        result = item.get("result")
        result_text = ""
        if isinstance(result, dict):
            content = result.get("content")
            if isinstance(content, list):
                result_text = "\n".join(
                    str(value.get("text", ""))
                    for value in content
                    if isinstance(value, dict) and value.get("type") == "text"
                )
        return {
            "kind": "tool",
            "status": status,
            "title": title,
            "detail": _output_excerpt(result_text or item.get("error"), 1000),
        }
    return None


def read_codex_output(
    log_path: Path, *, max_events: int = 40, max_bytes: int = 512_000
) -> dict[str, Any]:
    """Return a bounded, redacted view of the append-only Codex JSONL log."""
    try:
        stat = log_path.stat()
        with log_path.open("rb") as stream:
            offset = max(0, stat.st_size - max_bytes)
            stream.seek(offset)
            data = stream.read(max_bytes)
    except OSError:
        return {"entries": [], "updatedAt": None}
    if offset:
        _, separator, data = data.partition(b"\n")
        if not separator:
            data = b""
    entries: list[dict[str, str]] = []
    for raw_line in data.splitlines():
        try:
            event = json.loads(raw_line)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(event, dict):
            continue
        summary = _event_summary(event)
        if summary and (summary["detail"] or summary["title"]):
            entries.append(summary)
    return {
        "entries": entries[-max_events:],
        "updatedAt": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "sizeBytes": stat.st_size,
    }


def handoff_prompt(run_id: str) -> str:
    return f"接管并完成 Run `{run_id}`"


def driver_prompt(run_id: str) -> str:
    return f"""接管并完成 AI2Apps Test Run `{run_id}`。

这是无人值守 UI 测试执行任务。完整遵循当前项目 `.agents/skills/ai2apps-test/SKILL.md`：
- 只操作固定的 `com.ai2apps.desktop.test` / instance `test`，禁止操作 default、dev 或 app-dev。
- Computer Use 必须使用 next 返回的已校验 shellAppPath 完整路径连接当前内层 Test Shell。禁止外层启动器、归档副本、显示名称；路径校验失败则 blocked。
- Computer Use 超时或身份歧义时重新读取 next，只重试已校验 shellAppPath；仍失败则记录实际目标、调用、错误和重试结果，禁止切换实例。
- 不修改 AI2Apps 产品代码、测试框架、测试计划或视觉基线。
- Pipeline 初始启动和登录由 Harness 动作负责。但当前 Case 安装模型/Runtime 时，若 Test UI 明确要求重启以完成安装，可以通过该 UI 确认重启 Test。先记录提示和安装进度并检查 next；重启后再次检查 next，丢弃旧 Computer Use 句柄/元素 ID，用新返回的 shellAppPath 重新连接并读取状态，核验身份、Session 和安装完成后继续同一 Case。取消立即停止；重启失败、反复要求重启或 Session 不可用则记录 blocked。不得自行登录、清数据、删除 checkpoint 缓存或用任意命令强杀/启动进程；重启本身不代表 Case 通过。
- 从 `./bin/ai2apps-test next --run {run_id}` 领取 Case；每个实质 UI 动作前后都重新执行 next 检查取消状态。
- AI2Apps 特权 Shell chrome 不是 WebDriver BiDi browsing context；Shell 导航、App/Mini-Entry 启动、原生窗口、可见状态检查和跨上下文/macOS 拖拽一律使用 Computer Use。
- 只有 Case 明确测试 AI Browser 网页、且 Harness 已提供并验证绑定 Test 实例的受保护 Gateway/context 时，才使用 AI2Apps WebDriver BiDi。禁止用通用 Chrome/Firefox BiDi 连接代替 Test Shell，也不要为 Shell Case 枚举通用浏览器 context。
- 每个 Case 独立保存证据到该 Run 目录并调用 record；失败或 blocked 后继续独立 Case。
- 不读取、显示、请求、输入或记录测试账号密码、lease token、Cookie、Bearer 或其他 Secret；账号已由 Harness 自动登录。
- next 返回 waiting_controller 或 waiting_human 时等待并轮询，不执行宿主动作、不提交结果或 finalize。
- next 返回 cancelled 时立即停止；返回 done 时结束，不要再次 finalize。
"""


def build_command(executable: str, project_root: Path) -> list[str]:
    return [
        executable,
        "-a",
        "never",
        "exec",
        "--sandbox",
        "workspace-write",
        "-C",
        str(project_root),
        "--json",
        "-",
    ]


@dataclass
class CodexDriverProcess:
    process: subprocess.Popen[bytes]
    log: IO[bytes]
    log_path: Path

    def public_state(self) -> dict[str, Any]:
        code = self.process.poll()
        return {
            "status": "running" if code is None else ("completed" if code == 0 else "failed"),
            "pid": self.process.pid,
            "startedAt": now_text(),
            "log": str(self.log_path),
            **({"exitCode": code} if code is not None else {}),
        }

    def poll(self) -> int | None:
        return self.process.poll()

    def wait(self, timeout: float) -> int | None:
        try:
            return self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return None

    def stop(self) -> None:
        if self.process.poll() is not None:
            self.log.close()
            return
        try:
            os.killpg(self.process.pid, signal.SIGTERM)
            self.process.wait(timeout=5)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            if self.process.poll() is None:
                with suppress(ProcessLookupError):
                    os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait(timeout=5)
        finally:
            self.log.close()

    def close_log(self) -> None:
        if not self.log.closed:
            self.log.close()


def codex_environment() -> tuple[str, dict[str, str]]:
    """Resolve CLI dependencies for GUI launches without running shell profiles."""
    environment = os.environ.copy()
    directories = [p for p in environment.get("PATH", "").split(os.pathsep)
                   if p and Path(p).is_absolute()]
    directories.extend([
        str(Path.home() / ".local" / "bin"),
        "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin",
    ])
    environment["PATH"] = os.pathsep.join(dict.fromkeys(directories))
    executable = shutil.which("codex", path=environment["PATH"])
    if executable is None:
        raise CodexDriverError(
            "找不到 Codex CLI：已检查 PATH、~/.local/bin、/opt/homebrew/bin 和 /usr/local/bin"
        )
    try:
        with open(executable, "rb") as stream:
            shebang = stream.readline(256)
    except OSError as error:
        raise CodexDriverError("Codex CLI 无法读取") from error
    if shebang.startswith(b"#!") and b"node" in shebang:
        if shutil.which("node", path=environment["PATH"]) is None:
            raise CodexDriverError("已找到 Codex CLI，但缺少其所需的 Node.js；请安装 Node.js 或配置 PATH")
    return executable, environment


def start_codex_driver(
    repo_root: Path, run_id: str, run_dir: Path
) -> CodexDriverProcess:
    executable, environment = codex_environment()
    log_path = run_dir / "logs" / "codex-driver.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = log_path.open("ab", buffering=0)
    project_root = repo_root / "ai2apps-test-system"
    skill = project_root / ".agents" / "skills" / "ai2apps-test" / "SKILL.md"
    if not skill.is_file():
        log.close()
        raise CodexDriverError("AI2Apps test system Codex skill is unavailable")
    try:
        process = subprocess.Popen(
            build_command(executable, project_root),
            stdin=subprocess.PIPE,
            stdout=log,
            stderr=subprocess.STDOUT,
            cwd=project_root,
            env=environment,
            start_new_session=True,
        )
        assert process.stdin is not None
        process.stdin.write(driver_prompt(run_id).encode("utf-8"))
        process.stdin.close()
    except Exception as error:
        log.close()
        raise CodexDriverError("failed to start the Codex driver") from error
    return CodexDriverProcess(process=process, log=log, log_path=log_path)
