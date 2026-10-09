"""Development Qwen3.8 CUDA adapter for the standard Model Worker protocol.

BF16 correctness baseline. Not yet a signed/published model Package.
"""
import asyncio
import base64
import io
import json
import queue
import threading
import time

from ai2apps.model_worker.protocol import ModelWorkerError, ModelWorkerStream
from ai2apps.model_worker.qwen_output import OutputParser


def invalid(message):
    raise ModelWorkerError(message, code="invalid_request_error", status_code=400)


def messages_for_processor(messages):
    from PIL import Image
    if not isinstance(messages, list) or not messages:
        invalid("messages must be a non-empty array")
    result = []
    for message in messages:
        if not isinstance(message, dict) or message.get("role") not in {"system", "user", "assistant", "tool"}:
            invalid("Invalid message role")
        item = dict(message)
        content = item.get("content") or ""
        if isinstance(content, list):
            parts = []
            for part in content:
                if not isinstance(part, dict):
                    invalid("Message content parts must be objects")
                if part.get("type") == "text":
                    if not isinstance(part.get("text"), str):
                        invalid("Text parts require a string")
                    parts.append({"type": "text", "text": part["text"]})
                elif part.get("type") == "image_url":
                    url = part.get("image_url", {})
                    url = url.get("url") if isinstance(url, dict) else url
                    if not isinstance(url, str) or not url.startswith("data:image/") or ";base64," not in url or len(url) > 45000000:
                        invalid("Images must be bounded inline base64 data URLs")
                    try:
                        raw = base64.b64decode(url.split(",", 1)[1], validate=True)
                        image = Image.open(io.BytesIO(raw))
                        if image.width * image.height > 16000000:
                            invalid("Image exceeds 16 million pixels")
                        image.load()
                        parts.append({"type": "image", "image": image.convert("RGB")})
                    except ModelWorkerError:
                        raise
                    except Exception as error:
                        invalid(f"Invalid image: {type(error).__name__}")
                else:
                    invalid("Unsupported message content part")
            content = parts
        elif not isinstance(content, str):
            invalid("Invalid message content")
        item["content"] = content
        if item.get("tool_calls"):
            item["tool_calls"] = json.loads(json.dumps(item["tool_calls"]))
            try:
                if not isinstance(item["tool_calls"], list):
                    raise ValueError()
                for call in item["tool_calls"]:
                    args = call["function"]["arguments"]
                    if isinstance(args, str):
                        args = json.loads(args)
                    if not isinstance(args, dict):
                        raise ValueError()
                    call["function"]["arguments"] = args
            except (KeyError, TypeError, ValueError):
                invalid("Invalid tool-call history")
        result.append(item)
    return result


class CudaQwenChatAdapter:
    checkpoint_revision = None

    def load_backend(self, checkpoint):
        raise NotImplementedError

    def unload_backend(self):
        pass

    def __init__(self, context):
        self.context = context
        self.model = self.processor = None
        self.lock = asyncio.Lock()
        self.active = {}
        self.pending_cancel = set()

    async def cancel(self, request_id):
        event = self.active.get(request_id)
        if event is not None:
            event.set()
        else:
            self.pending_cancel.add(request_id)

    async def start(self):
        pass

    async def stop(self):
        async with self.lock:
            self.model = self.processor = None
            self.unload_backend()
            import torch
            torch.cuda.empty_cache()

    async def invoke(self, request):
        if request.operation != "chat_completions":
            invalid("This development adapter supports chat_completions")
        body = dict(request.payload)
        checkpoint = self.context.checkpoint_for(body.get("model"))
        if checkpoint is None or checkpoint.path is None:
            invalid("Unknown or unavailable model")
        if checkpoint.revision != self.checkpoint_revision:
            invalid("This adapter requires the validated checkpoint revision")
        if body.get("tool_choice", "auto") not in ("auto", "none"):
            invalid("Explicit/required tool_choice is not yet supported")
        if body.get("n", 1) != 1 or body.get("stop") or body.get("response_format"):
            invalid("n != 1, stop and constrained response_format are not yet supported")
        messages = messages_for_processor(body.get("messages"))
        try:
            maximum = int(body.get("max_tokens", 256))
            temperature = float(body.get("temperature", 0))
            top_p = float(body.get("top_p", 1))
            assert 1 <= maximum <= 2048 and 0 <= temperature <= 2 and 0 < top_p <= 1
        except (ValueError, TypeError, AssertionError):
            invalid("Invalid generation parameters (max_tokens: 1..2048)")
        template = body.get("chat_template_kwargs") or {}
        if not isinstance(template, dict):
            invalid("chat_template_kwargs must be an object")
        thinking = body.get("enable_thinking", template.get("enable_thinking", True))
        if not isinstance(thinking, bool):
            invalid("enable_thinking must be boolean")
        tools = body.get("tools") or []
        if not isinstance(tools, list) or len(tools) > 128:
            invalid("tools must be an array with at most 128 entries")
        for tool in tools:
            if not isinstance(tool, dict) or tool.get("type") != "function" or not isinstance(tool.get("function", {}).get("name"), str):
                invalid("Invalid tool definition")
        if body.get("tool_choice") == "none":
            tools = []
        parameters = {"max_new_tokens": maximum, "do_sample": temperature > 0}
        if temperature > 0:
            parameters.update(temperature=temperature, top_p=top_p)
        events = self._events(checkpoint, messages, tools, thinking, parameters, request.request_id)
        response_id = "chatcmpl-" + request.request_id
        created = int(time.time())

        def envelope(delta, finish=None, usage=None):
            value = {"id": response_id, "object": "chat.completion.chunk", "created": created,
                "model": body["model"], "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
            if usage is not None:
                value["usage"] = usage
            return value

        if body.get("stream"):
            async def chunks():
                try:
                    yield ("data: " + json.dumps(envelope({"role": "assistant"})) + "\n\n").encode()
                    async for event in events:
                        value = envelope(event) if "finish_reason" not in event else envelope({}, event["finish_reason"], event["usage"])
                        yield ("data: " + json.dumps(value, ensure_ascii=False) + "\n\n").encode()
                    yield b"data: [DONE]\n\n"
                finally:
                    await events.aclose()
            return ModelWorkerStream(chunks(), headers={"Cache-Control": "no-cache"})
        message = {"role": "assistant", "content": ""}
        finish = None
        try:
            async for event in events:
                if "finish_reason" in event:
                    finish = event
                for key in ("content", "reasoning_content"):
                    if key in event:
                        message[key] = message.get(key, "") + event[key]
                if "tool_calls" in event:
                    message.setdefault("tool_calls", []).extend({k: v for k, v in call.items() if k != "index"} for call in event["tool_calls"])
        finally:
            await events.aclose()
        return {"id": response_id, "object": "chat.completion", "created": created, "model": body["model"],
            "choices": [{"index": 0, "message": message, "finish_reason": finish["finish_reason"]}], "usage": finish["usage"]}

    async def _events(self, checkpoint, messages, tools, thinking, parameters, request_id):
        import torch
        from transformers import TextIteratorStreamer, StoppingCriteria, StoppingCriteriaList
        async with self.lock:
            if request_id in self.pending_cancel:
                self.pending_cancel.discard(request_id)
                raise ModelWorkerError("Generation cancelled", code="request_cancelled", status_code=499)
            if self.model is None:
                # Shield loading so cancellation cannot release the lock while CUDA loads.
                task = asyncio.create_task(asyncio.to_thread(self.load_backend, checkpoint.path))
                try:
                    self.model, self.processor = await asyncio.shield(task)
                except asyncio.CancelledError:
                    self.model, self.processor = await task
                    raise
            if request_id in self.pending_cancel:
                self.pending_cancel.discard(request_id)
                raise ModelWorkerError("Generation cancelled", code="request_cancelled", status_code=499)
            inputs = self.processor.apply_chat_template(messages, tools=tools or None,
                enable_thinking=thinking, tokenize=True, add_generation_prompt=True,
                return_dict=True, return_tensors="pt").to(self.model.device)
            prompt = int(inputs.input_ids.shape[-1])
            if prompt + parameters["max_new_tokens"] > 8192:
                invalid("Development baseline context limit is 8192 tokens")
            cancel = threading.Event()
            self.active[request_id] = cancel
            class Cancel(StoppingCriteria):
                def __call__(self, input_ids, scores, **kwargs):
                    return cancel.is_set()
            streamer = TextIteratorStreamer(self.processor.tokenizer, skip_prompt=True,
                skip_special_tokens=False, timeout=0.2)
            state = {}
            def generate():
                try:
                    with torch.inference_mode():
                        output = self.model.generate(**inputs, **parameters, streamer=streamer,
                            stopping_criteria=StoppingCriteriaList([Cancel()]))
                    state["count"] = int(output.shape[-1]) - prompt
                except Exception as error:
                    state["error"] = error
                    streamer.end()
            thread = threading.Thread(target=generate, name="qwen38-generation")
            parser = OutputParser(thinking=thinking, tools=tools)
            thread.start()
            try:
                while True:
                    try:
                        text = await asyncio.to_thread(streamer.text_queue.get, True, 0.2)
                    except queue.Empty:
                        if not thread.is_alive():
                            if "error" in state:
                                raise state["error"]
                            break
                        continue
                    if text is None:
                        break
                    for event in parser.feed(text):
                        yield event
                await asyncio.to_thread(thread.join)
                if "error" in state:
                    raise state["error"]
                if cancel.is_set():
                    raise ModelWorkerError("Generation cancelled", code="request_cancelled", status_code=499)
                for event in parser.feed("", final=True):
                    yield event
                count = state["count"]
                yield {"finish_reason": "tool_calls" if parser.calls else "length" if count >= parameters["max_new_tokens"] else "stop",
                    "usage": {"prompt_tokens": prompt, "completion_tokens": count, "total_tokens": prompt + count}}
            finally:
                cancel.set()
                # Do not let a following request race a cancelled GPU generation.
                import anyio
                with anyio.CancelScope(shield=True):
                    await asyncio.to_thread(thread.join)
                self.active.pop(request_id, None)
