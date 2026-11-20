"""Owner-scoped background delivery from iLink to the existing Bot dialogue."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import secrets
import time
from dataclasses import asdict, dataclass

from ai2apps.apps.access import has_app_capability
from ai2apps.core import RepositoryError
from ai2apps.identity import IdentityRepository
from ai2apps.messager.conversation_profile import settings
from ai2apps.messager.dialogue import CHAT
from ai2apps.messager.flash_conversation import submit as submit_flash_conversation
from ai2apps.messager.presentation import text_content
from ai2apps.storage.repositories import MessageRepository

from . import APP_ID
from .access_menu import CHOICE, REVIEW_IN_APP, AccessMenus, track
from .command_menu import BOT_COMMAND, bot_menu, conversation_bot
from .media import (
    IMAGE_TYPES,
    MAX_FILES,
    MediaTransport,
    inbound_ref,
    read_artifact,
    store_attachment,
)
from .service import delivery_status, record_activity
from .weixin import ConnectorError

LOGGER = logging.getLogger(__name__)
REPLY_PREFIX = "[🤖AI2Apps]: "
TERMINAL = {"completed", "failed", "cancelled", "interrupted", "timed_out"}
MAX_FLASH_JOBS = 32
SEND_IMAGE = re.compile(r"发图\s+(art_[0-9a-f]{32})")


@dataclass(frozen=True)
class FlashInput:
    session_id: str
    request_id: str
    text: str
    attachments: list[str]
    task_session_id: str | None = None
    language: str = "zh"

    def model_dump(self):
        return asdict(self)


def incoming(batch, config):
    if not isinstance(batch, list):
        raise ConnectorError("ilink_invalid_response")
    for msg in batch:
        if not isinstance(msg, dict) or (
            msg.get("message_type") != 1
            or msg.get("from_user_id") != config["user"]
            or msg.get("to_user_id") not in (None, "", config["bot"])
            or msg.get("group_id")
        ):
            continue
        mid, token, items = (
            msg.get(k) for k in ("message_id", "context_token", "item_list")
        )
        if (
            type(mid) not in (str, int)
            or not 1 <= len(str(mid)) <= 20
            or not str(mid).isascii()
            or not str(mid).isdigit()
            or not isinstance(token, str)
            or not 0 < len(token) <= 4096
            or not isinstance(items, list)
        ):
            continue
        parts, files = [], []
        unsupported = False
        for item in items[:16]:
            if not isinstance(item, dict):
                continue
            if item.get("type") == 1:
                text = item.get("text_item")
                if isinstance(text, dict) and isinstance(text.get("text"), str):
                    parts.append(text["text"][:2000])
            else:
                try:
                    ref = inbound_ref(item)
                    if ref and len(files) < MAX_FILES:
                        files.append(ref)
                    else:
                        unsupported = True
                except ConnectorError:
                    unsupported = True
        text = "\n".join(parts).strip()[:2000]
        if text or files or unsupported:
            stamp = msg.get("create_time_ms")
            yield {
                "mid": str(mid),
                "text": text,
                "token": token,
                "created_ms": stamp if type(stamp) is int else 0,
                "files": files,
                "media_skipped": unsupported,
            }


class BotChannel:
    def __init__(self, runtime, service):
        self.runtime = runtime
        self.service = service
        self.db = runtime.database
        self.runner = None
        self.workers = {}
        self.access_menus = AccessMenus(runtime)
        with self.db.transaction(write=True) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS comapps_bot_channels(
                scope TEXT PRIMARY KEY, actor TEXT NOT NULL, installation TEXT NOT NULL,
                instance_id TEXT NOT NULL, generation TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS comapps_bot_deliveries(
                scope TEXT NOT NULL, request_key TEXT NOT NULL,
                PRIMARY KEY(scope, request_key))""")

    def enable(self, scope, principal, instance_id, config):
        generation = secrets.token_urlsafe(18)
        # Do not replay the last manually handled message or an old queue.
        config.update(
            auto_generation=generation,
            pending=[],
            reply=None,
            delivery=None,
            access_jobs={},
        )
        with self.db.transaction(write=True) as db:
            db.execute(
                "INSERT OR REPLACE INTO comapps_bot_channels VALUES(?,?,?,?,?)",
                (
                    scope,
                    principal.actor_user_id,
                    principal.installation_id,
                    instance_id,
                    generation,
                ),
            )
        self.service._store(scope, "ilink", config)

    def disable(self, scope):
        with self.db.transaction(write=True) as db:
            db.execute("DELETE FROM comapps_bot_channels WHERE scope=?", (scope,))

    def start(self):
        if self.runner is None:
            self.runner = asyncio.create_task(self._supervise(), name="comapps-ilink")
            LOGGER.info(
                "ComApps iLink Bot channel started; source=%s; media=%s; commands=%s",
                __file__,
                MediaTransport.download.__code__.co_filename,
                bot_menu.__code__.co_filename,
            )

    async def stop(self):
        if self.runner:
            self.runner.cancel()
            await asyncio.gather(self.runner, return_exceptions=True)
            self.runner = None
        tasks = [task for _, task in self.workers.values()]
        self.workers.clear()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _supervise(self):
        while True:
            try:
                with self.db.transaction() as db:
                    rows = db.execute("SELECT * FROM comapps_bot_channels").fetchall()
                current = {row["scope"]: row for row in rows}
                for scope, (generation, task) in list(self.workers.items()):
                    row = current.get(scope)
                    if task.done() and (row is None or row["generation"] != generation):
                        self.workers.pop(scope)
                for scope, row in current.items():
                    if scope not in self.workers:
                        self.workers[scope] = (
                            row["generation"],
                            asyncio.create_task(self._worker(dict(row))),
                        )
            except Exception:
                LOGGER.error("ComApps iLink worker discovery failed")
            await asyncio.sleep(2)

    def _principal(self, row):
        principal = IdentityRepository(self.db).principal_for(row["actor"])
        if principal.installation_id != row["installation"] or not has_app_capability(
            principal, "app.use"
        ):
            raise PermissionError
        # A closed Shell App is not a revocation of a saved channel.
        self.runtime.extension_manager.require_instance_access(
            row["instance_id"], principal
        )
        with self.db.transaction() as db:
            definition = db.execute(
                """SELECT d.package_id, d.source, d.status
                FROM app_instances i JOIN app_definitions d ON d.id=i.app_definition_id
                WHERE i.id=? AND i.owner_user_id=?""",
                (row["instance_id"], row["actor"]),
            ).fetchone()
        if (
            not definition
            or definition["package_id"] != APP_ID
            or definition["status"] != "enabled"
            or definition["source"] != "builtin"
        ):
            raise PermissionError
        return principal

    def _config(self, row):
        config = self.service._load(row["scope"], "ilink")
        with self.db.transaction() as db:
            active = db.execute(
                "SELECT generation FROM comapps_bot_channels WHERE scope=?",
                (row["scope"],),
            ).fetchone()
        if (
            not active
            or active[0] != row["generation"]
            or not config
            or config.get("auto_generation") != row["generation"]
        ):
            return None
        return config

    def _save(self, row, config):
        self.service._store(row["scope"], "ilink", config)

    async def _worker(self, row):
        while True:
            config = None
            try:
                with self.service.claim(row["scope"]):
                    config = self._config(row)
                    if config is None:
                        return
                    self._principal(row)
                    if config.get("delivery") == "dispatching":
                        config["delivery"] = "unknown"
                        self._save(row, config)
                    if config.get("delivery") == "reconnect":
                        return
                    pending = bool(config["pending"])
                if pending:
                    delay = await self._turn(row)
                elif await self._notice(row):
                    delay = 0.25
                else:
                    await self._poll(row, config)
                    delay = 0.5
            except ConnectorError as error:
                delay = (
                    1
                    if str(error) == "comapps_busy"
                    or (
                        str(error) == "ilink_request_failed"
                        and config
                        and (config.get("access_jobs") or config.get("flash_jobs"))
                    )
                    else 8
                )
                if str(error) == "ilink_reconnect_required":
                    await self._delivery(row, "reconnect")
                    return
            except Exception:
                LOGGER.warning("ComApps iLink channel temporarily unavailable")
                delay = 15
            await asyncio.sleep(delay)

    async def _poll(self, row, snapshot):
        result = await asyncio.to_thread(
            self.service.ilink.request,
            "getupdates",
            base=snapshot["base"],
            token=snapshot["token"],
            data={"get_updates_buf": snapshot["cursor"]},
            timeout=5
            if snapshot.get("access_jobs") or snapshot.get("flash_jobs")
            else 45,
        )
        with self.service.claim(row["scope"]):
            config = self._config(row)
            if config is None:
                return
            self._principal(row)
            cursor = result.get("get_updates_buf")
            if cursor is not None and (
                not isinstance(cursor, str) or len(cursor) > 8192
            ):
                raise ConnectorError("ilink_invalid_response")
            for item in incoming(result.get("msgs", []), config):
                if item["mid"] not in config["seen"]:
                    config["pending"].append(item)
                    config["seen"] = [*config["seen"][-127:], item["mid"]]
                    summary = [item["text"][:400]]
                    summary.extend(
                        "［图片］" if file["kind"] == "image" else "［PDF］"
                        for file in item["files"]
                    )
                    if item["media_skipped"]:
                        summary.append("［其他附件］")
                    record_activity(config, "in", " ".join(filter(None, summary)))
            # The provider response is bounded; keep cursor and all its turns together.
            now = int(time.time())
            if (
                config["pending"]
                or (cursor and cursor != config["cursor"])
                or now - config.get("checked_at", 0) >= 30
            ):
                config["cursor"] = cursor or config["cursor"]
                config["checked_at"] = now
                self._save(row, config)

    def _admit(self, row, principal, config, item):
        runtime = self.runtime
        bot = conversation_bot(runtime.messager_bots, row["actor"], config)
        mode = runtime.messager_bots.definition(row["actor"], bot)["execution_mode"]
        model = None
        if mode == "agent":
            model = (
                item.get("model")
                or settings(runtime, row["actor"], bot)["effective_model"]
            )
            if not model:
                raise ValueError("Configure the Bot conversation model")
        session = runtime.app_chat.open(principal, CHAT, {"bot_id": bot}, {})
        return model, bot, session, mode

    async def _prepare_media(self, row):
        # Resolve the destination before network I/O and recheck it before import.
        with self.service.claim(row["scope"]):
            config = self._config(row)
            if not config or not config["pending"]:
                return
            item = config["pending"][0]
            if not item.get("files") or self._handled(
                row, self._message_key(config, item)
            ):
                return
            principal = self._principal(row)
            bot = conversation_bot(self.runtime.messager_bots, row["actor"], config)
            session = self.runtime.app_chat.open(principal, CHAT, {"bot_id": bot}, {})
            ref = item["files"][0]
            mid = item["mid"]
        transport = MediaTransport(self.service.ilink)
        try:
            material = await asyncio.to_thread(transport.download, ref)
        except ConnectorError:
            material = None
        with self.service.claim(row["scope"]):
            current = self._config(row)
            if (
                not current
                or not current["pending"]
                or current["pending"][0]["mid"] != mid
            ):
                return
            principal = self._principal(row)
            self.runtime.app_chat.access(principal, session)
            pending = current["pending"][0]
            if pending.get("media_session", session) != session:
                raise PermissionError("Attachment destination changed")
            if material:
                try:
                    # Hold the channel claim only for bounded local work.
                    aid = await asyncio.to_thread(
                        store_attachment, self.runtime.documents, session, *material
                    )
                except (ConnectorError, ValueError, OSError):
                    material = None
            if material:
                pending["media_session"] = session
                pending.setdefault("attachment_ids", []).append(aid)
            else:
                pending["media_skipped"] = True
            pending["files"].pop(0)
            self._save(row, current)

    async def _turn(self, row):
        await self._prepare_media(row)
        flash = None
        image = None
        with self.service.claim(row["scope"]):
            config = self._config(row)
            if config is None or not config["pending"]:
                return 1
            principal = self._principal(row)
            item = config["pending"][0]
            key = self._message_key(config, item)
            if self._handled(row, key):
                config["pending"].pop(0)
                self._save(row, config)
                return 0
            if item.get("files"):
                return 0
            plain_new_text = (
                item.get("text")
                and not item.get("run_id")
                and not item.get("attachment_ids")
                and not item.get("media_skipped")
            )
            menu_command = (
                BOT_COMMAND.fullmatch(item["text"]) if plain_new_text else None
            )
            poke = bool(plain_new_text and item["text"] == "p")
            image_request = (
                SEND_IMAGE.fullmatch(item["text"]) if plain_new_text else None
            )
            if not item.get("text"):
                if not self._claim_delivery(row, key):
                    return 0
                attachments = item.get("attachment_ids", [])
                if attachments:
                    staged = config.get("staged_media")
                    if (
                        staged
                        and staged["until"] >= time.time()
                        and staged["session"] == item["media_session"]
                    ):
                        attachments = staged["ids"] + attachments
                    if len(attachments) > MAX_FILES:
                        attachments = attachments[-MAX_FILES:]
                        item["media_skipped"] = True
                    config["staged_media"] = {
                        "ids": attachments,
                        "session": item["media_session"],
                        "until": time.time() + 900,
                    }
                    text = f"已收到 {len(attachments)} 个附件。请在 15 分钟内发下一条文字说明要怎么处理。"
                else:
                    text = "没能读取附件。目前仅支持 JPEG、PNG 图片和可提取文字的 PDF。"
                if item.get("media_skipped") and attachments:
                    text += " 另有附件未读取。"
            elif image_request:
                bot = conversation_bot(self.runtime.messager_bots, row["actor"], config)
                session = self.runtime.app_chat.open(
                    principal, CHAT, {"bot_id": bot}, {}
                )
                ref = image_request[1]
                try:
                    asset = self.runtime.workspace.get_artifact(session, ref)
                except RepositoryError:
                    asset = None
                if asset and asset.media_type in IMAGE_TYPES:
                    image = (session, [ref])
                else:
                    text = "当前 Bot 会话里找不到这张 PNG 或 JPEG 图片。"
                if not self._claim_delivery(row, key):
                    return 0
            elif menu_command:
                text = bot_menu(
                    self.runtime.messager_bots, row["actor"], config, menu_command
                )
                if not self._claim_delivery(row, key):
                    return 0
            elif plain_new_text and self._is_menu_choice(config, item):
                if not self._claim_delivery(row, key):
                    return 0
                text = self.access_menus.choice(row["actor"], config, item)
            else:
                run_id = item.get("run_id")
                if not run_id:
                    if "session" not in item:
                        model, bot, session, mode = self._admit(
                            row, principal, config, item
                        )
                        item.update(model=model, bot=bot, session=session, mode=mode)
                        staged = config.get("staged_media")
                        if staged and staged["until"] < time.time():
                            config.pop("staged_media")
                            staged = None
                        if (
                            not poke
                            and not item.get("attachment_ids")
                            and not item.get("media_skipped")
                            and staged
                            and staged["session"] == session
                        ):
                            config.pop("staged_media")
                            item["attachment_ids"] = staged["ids"]
                            item["media_session"] = session
                        if (
                            item.get("attachment_ids")
                            and item["media_session"] != session
                        ):
                            item["attachment_ids"] = []
                            item["media_skipped"] = True
                        self._save(row, config)
                    if item.get("mode") == "flash":
                        if poke or len(config.get("flash_jobs", {})) >= MAX_FLASH_JOBS:
                            text = (
                                "Flash-Bot 请直接发送工作流输入。"
                                if poke
                                else "请等正在处理的 Flash 任务完成后再发送。"
                            )
                            if not self._claim_delivery(row, key):
                                return 0
                        else:
                            flash = FlashInput(
                                item["session"],
                                key,
                                item["text"],
                                item.get("attachment_ids", []),
                            )
                    else:
                        item["run_id"] = self.runtime.messager_dialogue.submit(
                            principal,
                            item["bot"],
                            item["session"],
                            key,
                            "👋 Poke" if poke else item["text"],
                            item["model"],
                            item.get("attachment_ids", []),
                            poke=poke,
                        )
                        self._save(row, config)
                        return 0.5
                else:
                    run = self.runtime.agents.get_run(run_id)
                    if run.status.value not in TERMINAL:
                        return 0.5
                    content = (
                        (run.output or {}).get("content")
                        if run.status.value == "completed"
                        else None
                    )
                    text = (
                        content.strip()
                        if isinstance(content, str) and content.strip()
                        else "这条消息没有处理完成，请在 AI2Apps 中查看。"
                    )
                    if (
                        run.status.value == "completed"
                        and (run.output or {}).get("job_id")
                        and not track(config, item, run)
                    ):
                        text += "\n后续状态请在 AI2Apps 中查看。"
                    if not self._claim_delivery(row, key):
                        return 0
            if flash is None:
                self._finish_turn(row, config)
        if flash is not None:
            return await self._flash_turn(row, principal, item, flash)
        if image:
            await self._send_assets(row, item["token"], image, compact_image=False)
            return 0.5
        if item.get("media_skipped") and item.get("run_id"):
            text = "部分或全部附件未读取。\n" + text
        await self._send(row, config, item["token"], text)
        return 0.5

    def _finish_turn(self, row, config):
        config["pending"].pop(0)
        config["delivery"] = "dispatching"
        self._save(row, config)

    async def _flash_turn(self, row, principal, item, body):
        try:
            result = await submit_flash_conversation(
                self.runtime, principal, item["bot"], body
            )
        except (ValueError, PermissionError, RepositoryError):
            result = {
                "message": "Flash-Bot 无法处理这条消息，请在 AI2Apps 中查看工作流和输入要求。"
            }
        with self.service.claim(row["scope"]):
            config = self._config(row)
            if (
                not config
                or not config["pending"]
                or config["pending"][0]["mid"] != item["mid"]
            ):
                return 0
            self._principal(row)
            if not self._claim_delivery(row, body.request_id):
                return 0
            text = result.get("message", "Flash-Bot 已收到，处理完成后会回复。")
            if result.get("kind") == "execution":
                config.setdefault("flash_jobs", {})[result["run_id"]] = {
                    "bot": item["bot"],
                    "session": item["session"],
                    "token": item["token"],
                }
            elif result.get("kind") == "workflow_review":
                text += "\n请在 AI2Apps 的 Bot 对话中审阅草案。"
            if item.get("media_skipped"):
                text = "部分或全部附件未读取。\n" + text
            self._finish_turn(row, config)
        await self._send(row, config, item["token"], text)
        return 0.5

    @staticmethod
    def _message_key(config, item):
        address = f"{config['bot']}:{config['user']}:{item['mid']}"
        return "ilink-" + hashlib.sha256(address.encode()).hexdigest()

    def _handled(self, row, key):
        with self.db.transaction() as db:
            return db.execute(
                "SELECT 1 FROM comapps_bot_deliveries WHERE scope=? AND request_key=?",
                (row["scope"], key),
            ).fetchone()

    @staticmethod
    def _is_menu_choice(config, item):
        return bool(config.get("access_menu_number") and CHOICE.fullmatch(item["text"]))

    def _claim_delivery(self, row, key):
        with self.db.transaction(write=True) as db:
            return db.execute(
                "INSERT OR IGNORE INTO comapps_bot_deliveries VALUES(?,?)",
                (row["scope"], key),
            ).rowcount

    async def _notice(self, row):
        with self.service.claim(row["scope"]):
            config = self._config(row)
            if config is None or not (
                config.get("access_jobs") or config.get("flash_jobs")
            ):
                return False
            principal = self._principal(row)
            before = json.dumps((config.get("access_jobs"), config.get("flash_jobs")))
            notice = self.access_menus.notices(
                row["actor"], config
            ) or self._flash_notice(principal, config)
            if notice:
                config["delivery"] = "dispatching"
            if notice or before != json.dumps(
                (config.get("access_jobs"), config.get("flash_jobs"))
            ):
                self._save(row, config)
            if not notice:
                return False
            token, text, menu = notice[:3]
            assets = notice[3] if len(notice) == 4 else None
        delivery = await self._send(row, config, token, text, menu)
        if delivery == "submitted" and assets:
            await self._send_assets(row, token, assets)

        return True

    def _flash_notice(self, principal, config):
        flash = self.runtime.messager_flash
        jobs = config.get("flash_jobs", {})
        for ref, job in list(jobs.items()):
            try:
                original = flash.row(ref)
                binding = self.runtime.app_chat.access(principal, job["session"])
                if (
                    (original["actor"], original["bot_id"], original["session_id"])
                    != (principal.actor_user_id, job["bot"], job["session"])
                    or binding["registration"] != CHAT
                    or binding["scope"] != {"bot_id": job["bot"]}
                ):
                    raise PermissionError
                flash.reconcile(original)
                current = flash.row(ref)
            except (PermissionError, RepositoryError):
                del jobs[ref]
                continue
            if current["status"] not in TERMINAL:
                if current["agent_run"] and not job.get("review_notified"):
                    run = self.runtime.agents.get_run(current["agent_run"])
                    if run.status.value in {"waiting_capability", "waiting_input"}:
                        job["review_notified"] = True
                        return job["token"], REVIEW_IN_APP, None
                continue
            receipt = MessageRepository(self.db).get_by_idempotency_key(
                job["session"], f"flash:{ref}:result"
            )
            del jobs[ref]
            text = ""
            refs = []
            if receipt:
                text = "\n".join(
                    text_content(
                        part.content.get("text", part.content.get("content")) or []
                    )
                    for part in receipt.parts
                    if part.kind in {"text", "openai_content"}
                ).strip()
                if current["status"] == "completed":
                    refs = list(
                        dict.fromkeys(
                            asset["artifact_id"]
                            for asset in receipt.message.metadata.get("artifacts", [])
                            if isinstance(asset, dict)
                            and asset.get("session_id") == job["session"]
                            and asset.get("media_type")
                            in IMAGE_TYPES | {"application/pdf"}
                            and isinstance(asset.get("artifact_id"), str)
                        )
                    )[:MAX_FILES]
            if not text:
                text = (
                    "Flash-Bot 任务已完成。"
                    if current["status"] == "completed"
                    else "Flash-Bot 任务未完成，请在 AI2Apps 中查看。"
                )
            return job["token"], text, None, (job["session"], refs) if refs else None

    async def _send(self, row, config, token, text, menu=None):
        text = REPLY_PREFIX + text.removeprefix(REPLY_PREFIX)
        if len(text) > 1800:
            suffix = "\n…完整回复请在 AI2Apps 中查看。"
            text = text[: 1800 - len(suffix)] + suffix
        payload = self.service.reply_payload(
            config, {"id": secrets.token_urlsafe(18), "token": token}, text
        )
        delivery = "submitted"
        try:
            await asyncio.to_thread(self.service.send_reply, config, payload)
        except ConnectorError as error:
            delivery = delivery_status(error)
        await self._delivery(row, delivery, menu, text=text)
        return delivery

    async def _send_assets(self, row, token, assets, *, compact_image=True):
        session, refs = assets
        for ref in refs:
            sending = False
            stage = "read"
            try:
                with self.service.claim(row["scope"]):
                    config = self._config(row)
                    if not config:
                        return
                    principal = self._principal(row)
                    self.runtime.app_chat.access(principal, session)
                material = await asyncio.to_thread(
                    read_artifact, self.runtime.workspace, session, ref
                )
                with self.service.claim(row["scope"]):
                    config = self._config(row)
                    if not config:
                        return
                    self.runtime.app_chat.access(self._principal(row), session)
                transport = MediaTransport(self.service.ilink)
                stage = "upload"
                media = await asyncio.to_thread(
                    transport.upload, config, *material, compact_image=compact_image
                )
                with self.service.claim(row["scope"]):
                    config = self._config(row)
                    if not config:
                        return
                    self.runtime.app_chat.access(self._principal(row), session)
                    config["delivery"] = "dispatching"
                    self._save(row, config)
                    payload = self.service.reply_payload(
                        config, {"id": secrets.token_urlsafe(18), "token": token}, ""
                    )
                    payload["msg"]["item_list"] = [media]
                sending = True
                stage = "send"
                await asyncio.to_thread(self.service.send_reply, config, payload)
            except PermissionError:
                return
            except (
                ConnectorError,
                OSError,
                RepositoryError,
                ValueError,
            ) as error:
                LOGGER.warning(
                    "ComApps iLink attachment failed (stage=%s, reason=%s)",
                    stage,
                    str(error)
                    if isinstance(error, ConnectorError)
                    else type(error).__name__,
                )
                if str(error) == "ilink_reconnect_required":
                    await self._delivery(row, "reconnect")
                    return
                if sending:
                    delivery = (
                        "rejected"
                        if str(error) == "ilink_request_rejected"
                        else "unknown"
                    )
                    await self._delivery(
                        row,
                        delivery,
                        text="［图片］" if media["type"] == 2 else "［PDF］",
                    )
                else:
                    with self.service.claim(row["scope"]):
                        config = self._config(row)
                        if not config:
                            return
                        self._principal(row)
                    await self._send(
                        row,
                        config,
                        token,
                        "附件未能发回微信，请在 AI2Apps 的 Bot 对话中查看。",
                    )
                return
            await self._delivery(
                row, "submitted", text="［图片］" if media["type"] == 2 else "［PDF］"
            )

    async def _delivery(self, row, delivery, menu=None, *, text=None):
        while True:
            try:
                with self.service.claim(row["scope"]):
                    current = self._config(row)
                    if current:
                        if menu and delivery == "submitted":
                            for job in current.get("access_jobs", {}).values():
                                stored = job.get("menu")
                                if stored and stored["code"] == menu["code"]:
                                    stored["offered_at"] = time.time_ns() // 1_000_000
                        current["delivery"] = delivery
                        if text is not None:
                            record_activity(current, "out", text, delivery=delivery)
                        self._save(row, current)
                break
            except ConnectorError as error:
                if str(error) != "comapps_busy":
                    raise
                await asyncio.sleep(0.25)
