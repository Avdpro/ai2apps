"""WeChat presentation for existing Bot App Access interactions."""

from __future__ import annotations

import re

from ai2apps.capabilities.effects import EXACT_EFFECT_CONFIRMATION
from ai2apps.core import RepositoryError, utc_now
from ai2apps.messager.presentation import text_content
from ai2apps.storage.repositories import MessageRepository

from .media import IMAGE_TYPES, MAX_FILES

CHOICE = re.compile(r"([A-Z]{1,8})?([123])", re.ASCII | re.IGNORECASE)
MAX_JOBS = 32
TERMINAL = {"completed", "failed", "cancelled", "interrupted", "timed_out"}
STALE = "这项申请已失效或已处理。请查看最新菜单，或在 AI2Apps 的 Bot 对话中处理。"
REVIEW_IN_APP = "请在 AI2Apps → 消息 → 对应 Bot 中完成确认或补充信息。"


def clean(value, limit):
    # Never render raw argument payloads or let names insert fake menu rows.
    return " ".join(str(value or "").split())[:limit]


def menu_code(n):
    result = ""
    while n:
        n, i = divmod(n - 1, 26)
        result = chr(ord("A") + i) + result
    return result


def track(config, item, run):
    ref = (run.output or {}).get("job_id")
    if not isinstance(ref, str) or not ref:
        return False
    jobs = config.setdefault("access_jobs", {})
    if ref in jobs:
        return True
    if len(jobs) >= MAX_JOBS:
        return False
    jobs[ref] = {
        "source_run": run.id,
        "session": run.session_id,
        "bot": item["bot"],
        "token": item["token"],
        "seen": {},
        "menu": None,
    }
    return True


class AccessMenus:
    def __init__(self, runtime):
        self.runtime = runtime

    def review(self, actor, job, run_id, item):
        if item.kind.value != "approval" or item.deadline_at <= utc_now():
            return None
        if EXACT_EFFECT_CONFIRMATION in (item.request.get("capabilities") or ()) or (
            item.ui_hints.get("unknown_tool_risk")
        ):
            return None
        access = self.runtime.messager_bot_app_access
        value = access.request(actor, job["bot"], run_id, item.id)
        if not value.get("eligible") or value["special"]:
            return None
        return value

    def owned_job(self, actor, ref, job):
        row = self.runtime.messager_dialogue.row(ref)
        if (row["actor"], row["bot_id"], row["source_session"], row["source_run"]) != (
            actor,
            job["bot"],
            job["session"],
            job["source_run"],
        ):
            raise PermissionError
        return row

    def notices(self, actor, config):
        """Yield one durable presentation at a time, scoped to WeChat-origin tasks."""
        jobs = config.get("access_jobs", {})
        for ref, job in list(jobs.items()):
            try:
                row = self.owned_job(actor, ref, job)
            except (RepositoryError, PermissionError):
                del jobs[ref]
                continue
            title = clean(row["title"], 100) or "Bot 任务"
            if row["status"] in TERMINAL:
                receipt = MessageRepository(
                    self.runtime.database
                ).get_by_idempotency_key(job["session"], "bot-job-result:" + ref)
                content = ""
                if receipt:
                    content = "\n".join(
                        text_content(
                            part.content.get(
                                "text" if part.kind == "text" else "content"
                            )
                            or []
                        )
                        for part in receipt.parts
                        if part.kind in {"text", "openai_content"}
                    ).strip()
                fallback = (
                    "已完成，详情请在 AI2Apps 中查看。"
                    if row["status"] == "completed"
                    else "未完成，详情请在 AI2Apps 中查看。"
                )
                assets = []
                if receipt and row["status"] == "completed":
                    metadata = receipt.message.metadata
                    if (
                        metadata.get("origin") == "bot_agent_chat_task"
                        and metadata.get("bot_job_id") == ref
                        and metadata.get("agent_run_id") == row["worker_run"]
                    ):
                        assets = list(
                            dict.fromkeys(
                                asset["artifact_id"]
                                for asset in metadata.get("artifacts", [])[:64]
                                if isinstance(asset, dict)
                                and asset.get("session_id") == job["session"]
                                and asset.get("media_type")
                                in IMAGE_TYPES | {"application/pdf"}
                                and isinstance(asset.get("artifact_id"), str)
                            )
                        )[:MAX_FILES]
                del jobs[ref]
                notice = (
                    job["token"],
                    f"「{title}」{chr(10) + content if content else fallback}",
                    None,
                )
                return (*notice, (job["session"], assets)) if assets else notice
            run_id = row["worker_run"]
            if not run_id:
                continue
            run = self.runtime.agents.get_run(run_id)
            if run.status.value not in {"waiting_capability", "waiting_input"}:
                job["menu"] = None
                continue
            active = [
                item
                for item in self.runtime.agents.list_interactions(run_id)
                if item.status.value == "pending" and item.deadline_at > utc_now()
            ]
            for item in active:
                try:
                    review = self.review(actor, job, run_id, item)
                except (RepositoryError, ValueError, PermissionError):
                    review = None
                signature = review["request_hash"] if review else "desktop"
                menu = job.get("menu")
                if (
                    menu
                    and menu["interaction"] == item.id
                    and menu["hash"] != signature
                ):
                    job["menu"] = None
                if job["seen"].get(item.id) == signature:
                    continue
                if len(job["seen"]) >= 64 and item.id not in job["seen"]:
                    continue
                job["seen"][item.id] = signature
                if not review:
                    return job["token"], f"「{title}」等待处理。{REVIEW_IN_APP}", None
                number = config.get("access_menu_number", 0) + 1
                config["access_menu_number"] = number
                code = menu_code(number)
                target = clean(review["app"]["name"], 100)
                operation = clean(
                    self.runtime.services.get_tool(
                        item.request["tool_name"]
                    ).display_name,
                    100,
                )
                menu = {
                    "code": code,
                    "run": run_id,
                    "interaction": item.id,
                    "hash": signature,
                    "title": title,
                    "target": target,
                    "operation": operation,
                    "existing": review["access_granted"],
                    "offered_at": None,
                    "bare": number == 1,
                }
                job["menu"] = menu
                return job["token"], self.render(menu), menu
            if job["menu"] and not any(
                i.id == job["menu"]["interaction"] for i in active
            ):
                job["menu"] = None
        return None

    @staticmethod
    def render(menu, details=False):
        label = menu["code"]
        prefix = "" if menu["bare"] else label
        allow = (
            "使用现有权限，仅继续本次操作"
            if menu["existing"]
            else ("允许此 Bot 持续访问该应用，并继续本次操作")
        )
        detail = (
            "\n持续访问覆盖该应用的普通操作（包括普通写入和配置内用量）；特殊操作仍须在 AI2Apps 单独确认。"
            if details or not menu["existing"]
            else ""
        )
        return (
            f"「{menu['title']}」需要访问「{menu['target']}」以执行「{menu['operation']}」。"
            f"任务已暂停。申请 {label}。{detail}\n"
            f"{prefix}1｜{allow}\n{prefix}2｜拒绝\n{prefix}3｜查看权限详情"
            + (f"\n也可回复 {label}1 / {label}2 / {label}3。" if menu["bare"] else "")
        )

    def choice(self, actor, config, item):
        match = CHOICE.fullmatch(item["text"])
        if not match:
            return None
        code, choice = match.groups()
        for ref, job in config.get("access_jobs", {}).items():
            menu = job.get("menu")
            if not menu or not menu["offered_at"]:
                continue
            if (code and code.upper() != menu["code"]) or (
                not code and (not menu["bare"] or config.get("access_menu_number") != 1)
            ):
                continue
            if item.get("created_ms", 0) <= menu["offered_at"]:
                return STALE
            with self.runtime.app_chat.lock:
                try:
                    row = self.owned_job(actor, ref, job)
                    if row["worker_run"] != menu["run"] or row["status"] in TERMINAL:
                        return STALE
                    interaction = next(
                        i
                        for i in self.runtime.agents.list_interactions(menu["run"])
                        if i.id == menu["interaction"] and i.status.value == "pending"
                    )
                    review = self.review(actor, job, menu["run"], interaction)
                    if not review or review["request_hash"] != menu["hash"]:
                        return STALE
                    if choice == "3":
                        return self.render(menu, details=True)
                    job["menu"] = None
                    access = self.runtime.messager_bot_app_access
                    if choice == "1":
                        result = access.allow(
                            actor,
                            job["bot"],
                            menu["run"],
                            menu["interaction"],
                            menu["hash"],
                            existing_access_only=menu["existing"],
                            ordinary_only=True,
                        )
                        return (
                            "已批准，Bot 将继续原任务。"
                            if result["continued"]
                            else REVIEW_IN_APP
                        )
                    self.runtime.agents.respond_interaction(
                        menu["run"],
                        menu["interaction"],
                        response={"decision": "deny"},
                        response_id="ilink-deny:" + menu["interaction"],
                    )
                    self.runtime.agent_runtime.wake()
                    return "已拒绝这项访问申请。"
                except (RepositoryError, ValueError, PermissionError, StopIteration):
                    return STALE
        return STALE if code or config.get("access_menu_number") else None
