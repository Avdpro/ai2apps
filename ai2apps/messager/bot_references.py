"""Resolve user-written Bot references without granting collaboration authority."""
import json
import re


_TOKEN = r'"(?:[^"\\\n]|\\["\\])*"|[^\s"<>`/，。！？：；、（）【】,.!?:;()\[\]]+'
_REFERENCE = re.compile(
    r'`{3}[\s\S]*?`{3}|`[^`\n]*`|'
    r'(?<![A-Za-z0-9_/\\])/@(?:'
    r'(?P<label>"(?:[^"\\\n]|\\["\\])*"|[^/\r\n`"()（）]{1,64}?)'
    r'[（(]`(?P<id>[^`\r\n]{0,128})`[）)]|'
    r'(?P<token>' + _TOKEN + r'))|(?<![A-Za-z0-9_/\\])(?P<invalid>/@)'
)


def resolve(directory, access, actor, source_bot, text, language="zh"):
    """Read only current-message references, preserving stable IDs and order."""
    directory.scope(actor, {"bot_id": source_bot})
    zh = language.startswith("zh")
    matches = [match for match in _REFERENCE.finditer(text)
               if match.group("id") is not None or match.group("token") or match.group("invalid")]
    if len(matches) > 8:
        raise ValueError("每条消息最多引用 8 个 Bot。" if zh else "Reference up to 8 Bots per message.")
    references = {}
    for match in matches:
        explicit_id = match.group("id")
        incomplete = explicit_id is None and text[match.end():].startswith(('(', '（'))
        if match.group("invalid") or incomplete or (explicit_id is not None and not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', explicit_id)):
            raise ValueError("Bot 引用格式不完整，请从候选列表重新选择。" if zh else "Incomplete Bot reference. Select it again from the list.")
        token = match.group("id") or match.group("token")
        value = json.loads(token) if token.startswith('"') else token
        # A readable label cannot redirect an explicit stable ID to a name match.
        with directory.db.transaction() as db:
            rows = db.execute(
                """SELECT b.id,b.name FROM messager_bots b
                   WHERE b.actor=? AND (b.id=? OR (?=0 AND b.name=?))
                     AND NOT EXISTS (SELECT 1 FROM messager_bot_archive a
                                     WHERE a.bot_id=b.id AND a.deleted=1)
                   ORDER BY (b.id=?) DESC LIMIT 2""",
                (actor, value, int(bool(match.group("id"))), value, value),
            ).fetchall()
        if not rows:
            raise ValueError("引用的 Bot 不可用，请重新选择。" if zh else "Referenced Bot unavailable. Select it again.")
        row = rows[0]
        if row["id"] != value and len(rows) > 1:
            raise ValueError("有同名 Bot，请从候选列表选择。" if zh else "Multiple Bots have this name. Select one from the list.")
        directory.agent_identity(actor, {"bot_id": row["id"]})
        if not access.visible(actor, source_bot, row["id"]):
            raise ValueError("引用的 Bot 尚未向当前 Bot 开放，请检查 Bot 使用权限。" if zh else "The referenced Bot is unavailable to this Bot. Check Bot use access.")
        references[row["id"]] = {"id": row["id"], "name": row["name"]}
    return list(references.values())
