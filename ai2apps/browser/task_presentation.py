"""Shared task labels for HTTP snapshots and SSE projections."""

def browser_task_wait_presentation(interactions) -> dict[str, str]:
    pending = [item for item in interactions if getattr(item.status, "value", item.status) == "pending"]
    for control, label in (("browser_user_assistance", "等待协助"), ("agent_confirmation", "等待确认")):
        item = next((item for item in pending if item.request.get("control") == control), None)
        if item is not None:
            return {"status_label": label, "message": item.prompt}
    if any(item.request.get("control") == "browser_bidi_action" for item in pending):
        return {"status_label": "等待浏览器响应", "message": "浏览器操作正在执行，无需人工介入。"}
    return {"status_label": "等待响应", "message": ""}
