"""iLink command menus for the bound account."""

import re

BOT_PAGE_SIZE = 20
BOT_COMMAND = re.compile(r"b(?:(p)?([0-9]{1,6}))?")
CONVERSATION_MODES = {"agent", "flash"}


def conversation_bot(directory, actor, config):
    selected = config.get("conversation_bot")
    if selected:
        try:
            if (
                directory.definition(actor, selected)["execution_mode"]
                in CONVERSATION_MODES
            ):
                return selected
        except PermissionError:
            pass
        config.pop("conversation_bot", None)
    return directory.ensure_default(actor)


def bot_menu(directory, actor, config, match):
    default = directory.ensure_default(actor)
    current = conversation_bot(directory, actor, config)
    bots = [
        bot
        for bot in directory.list(actor)
        if bot["definition"]["execution_mode"] in CONVERSATION_MODES
    ]
    page_marker, digits = match.groups()
    number = int(digits) if digits else 1
    if digits and not page_marker:
        # A number identifies a Bot only if it was displayed at that position.
        shown = config.get("bot_menu_choices", {}).get(str(number))
        if not shown or not 1 <= number <= len(bots) or bots[number - 1]["id"] != shown:
            return "该编号尚未显示或列表已变化。请回复 b 查看最新 Bot 列表。"
        bot = bots[number - 1]
        config["conversation_bot"] = bot["id"]
        name = " ".join(bot["name"].split())
        return f"当前对话 Bot：{name}。接下来的消息将发给它。"

    pages = max(1, (len(bots) + BOT_PAGE_SIZE - 1) // BOT_PAGE_SIZE)
    if not 1 <= number <= pages:
        return f"Bot 列表共 {pages} 页。回复 b 查看首页。"
    start = (number - 1) * BOT_PAGE_SIZE
    lines = [f"我的 Bot（{number}/{pages} 页，共 {len(bots)} 个）"]
    if not digits:
        config.pop("bot_menu_choices", None)
    choices = config.setdefault("bot_menu_choices", {})
    # Discard previously shown positions whose Bot changed since rendering.
    config["bot_menu_choices"] = choices = {
        position: bot_id
        for position, bot_id in choices.items()
        if 1 <= int(position) <= len(bots) and bots[int(position) - 1]["id"] == bot_id
    }
    for index, bot in enumerate(bots[start : start + BOT_PAGE_SIZE], start + 1):
        name = " ".join(bot["name"].split())
        markers = []
        if bot["id"] == current:
            markers.append("当前对话")
        if bot["id"] == default:
            markers.append("默认")
        label = "（" + "，".join(markers) + "）" if markers else ""
        choices[str(index)] = bot["id"]
        lines.append(f"{index}｜{name}{label}")
    if len(bots) > 1:
        lines.append(f"回复 b{start + 1} 可切换到编号 {start + 1} 的 Bot。")
    if number < pages:
        lines.append(f"回复 bp{number + 1} 查看下一页。")
    if number > 1:
        lines.append("回复 b 返回首页。")
    if any(
        bot["id"] == current and bot["definition"]["execution_mode"] == "agent"
        for bot in bots
    ):
        lines.append("回复 p 可 Poke 当前 Bot。")
    return "\n".join(lines)
