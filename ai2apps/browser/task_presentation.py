"""Shared task labels for HTTP snapshots and SSE projections."""

def browser_task_wait_presentation(interactions, browser_context=None) -> dict[str, object]:
    pending = [item for item in interactions if getattr(item.status, "value", item.status) == "pending"]
    for control, label in (("browser_user_assistance", "等待协助"), ("agent_confirmation", "等待确认"), ("agent_budget", "等待续额")):
        item = next((item for item in pending if item.request.get("control") == control), None)
        if item is not None:
            page={}
            if browser_context:
                origin=getattr(item,'request_key','').removeprefix('browser-assistance:')
                action=next((v for v in interactions if getattr(v,'id',None)==origin),None)
                response=getattr(action,'response',None) or {}
                context=response.get('evidence',{}).get('result',{}).get('context')
                if context and (context==browser_context.get('bidi_context') or context in browser_context.get('owned_contexts',{})):
                    page['assistance_context']=context
            return {**page,"status_label": label, "message": item.prompt, "requires_user": True,
                    "assistance_kind":"confirmation" if control=="agent_confirmation" else item.request.get("assistance_kind") or item.request.get("reason", ""),
                    "interaction_id":getattr(item,"id",None)}
    if any(item.request.get("control") == "browser_bidi_action" for item in pending):
        return {"status_label": "等待浏览器响应", "message": "浏览器操作正在执行，无需人工介入。", "requires_user": False}
    return {"status_label": "等待响应", "message": "", "requires_user": False}
