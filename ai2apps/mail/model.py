"""Shared model invocation for Mail workflows."""

import asyncio
import json
import logging
from uuid import uuid4

from ai2apps.model_invocation import ModelInvocationContext
from ai2apps.task_llm import resolve_task_model, task_payload

from .imap import MailError


logger = logging.getLogger(__name__)


async def mail_model_json(runtime, principal, system, payload, max_tokens, *,
                          operation, failure_code):
    model = resolve_task_model(runtime, "standard", "privacy")
    invocations = getattr(runtime, "model_invocations", None)
    if not model or invocations is None:
        raise MailError("mail_privacy_model_required")
    context = ModelInvocationContext.from_principal(
        principal, session_id=f"mail-{operation}-{uuid4().hex}", consumer_app_id="ai2apps.mail",
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    request = task_payload(model, messages, "standard", max_tokens=max_tokens)
    try:
        local_model = invocations.model(model) is not None
        if local_model:
            request["chat_template_kwargs"] = {"enable_thinking": False}
        response = await asyncio.wait_for(
            invocations.invoke_chat_json(request, context=context), timeout=165 if local_model else 90,
        )
        content = response["choices"][0]["message"]["content"].strip()
        if content.startswith("```") and content.endswith("```"):
            content = content.split("\n", 1)[1][:-3].strip()
        return json.loads(content)
    except Exception as error:
        logger.warning("Mail %s model call failed: %s", operation, type(error).__name__)
        raise MailError(failure_code) from None
