"""Cross-request bank ownership and raw completion protocol regressions."""
import copy
from types import SimpleNamespace
import pytest
import mlx.core as mx
from omlx.patches.deepseek_v41.engine import DeepseekV41Engine
from omlx.patches.deepseek_v41 import model as model_module
from omlx.patches.deepseek_v41.encoding import encode_messages, eos_token, IMAGE_PLACEHOLDER

TOOLS=[{'type':'function','function':{'name':'get_weather','description':'Get weather','parameters':{'type':'object','properties':{'city':{'type':'string'}},'required':['city']}}}]

@pytest.mark.parametrize('system',[False,True])
def test_tool_schema_reaches_encoded_prompt_without_mutating_input(system):
    messages=([{'role':'system','content':'Be concise.'}] if system else [])+[{'role':'user','content':'Weather?'}]
    original=copy.deepcopy(messages)
    prepared=DeepseekV41Engine._messages(messages,TOOLS)
    prompt=encode_messages(prepared,thinking_mode='chat')
    assert 'get_weather' in prompt and 'Get weather' in prompt
    assert messages==original
    assert sum(m['role']=='system' for m in prepared)==1

@pytest.mark.asyncio
@pytest.mark.parametrize('tool_call',[False,True])
async def test_tool_completion_parses_raw_eos_but_stream_never_emits_it(tmp_path,monkeypatch,tool_call):
    body=('\n\n<｜DSML｜ calls>\n<｜DSML｜ invoke name="get_weather">\n<｜DSML｜ parameter name="city" string="true">北京</｜DSML｜ parameter>\n</｜DSML｜ invoke>\n</｜DSML｜ calls>' if tool_call else 'No tool needed.')
    class Tokenizer:
        def token_to_id(self,token):return 1
        def decode(self,ids,*,skip_special_tokens):
            return (body if 2 in ids else '')+(eos_token if 1 in ids else '')
    engine=DeepseekV41Engine(tmp_path)
    engine._tokenizer=Tokenizer()
    async def start():pass
    monkeypatch.setattr(engine,'start',start)
    monkeypatch.setattr(engine,'_prepare_sync',lambda *a:([0],mx.array([[0.,0.,10.]])))
    monkeypatch.setattr(engine,'_decode_sync',lambda *a:mx.array([[0.,10.,0.]]))
    monkeypatch.setattr(engine,'_record_ssd_window',lambda *a:None)
    outputs=[x async for x in engine.stream_chat([{'role':'user','content':'Weather?'}],tools=TOOLS,temperature=0,max_tokens=3,chat_template_kwargs={'thinking_mode':'chat'})]
    assert outputs[-1].finish_reason=='stop'
    assert eos_token not in ''.join(x.new_text for x in outputs)
    assert bool(outputs[-1].tool_calls)==tool_call
    if tool_call:assert outputs[-1].tool_calls[0]['function']['name']=='get_weather'

def test_reset_discards_stale_decode_mapping_without_dropping_resident_banks(monkeypatch):
    model=object.__new__(model_module.Model)
    model.c=SimpleNamespace(n_layers=0);model.tokenizer=None;model.max_seq=4096
    model.prefill_executor=None
    model.lookups={0:'old-hot-slots'};model.ages={0:'old-ages'};model.ticks={0:100};model.main_slot_masks={0:'old-mask'}
    banks={0:object()};model.banks=banks
    monkeypatch.setattr(model_module,'HashState',lambda *a:None)
    model.reset_sequence()
    assert model.lookups=={} and model.ages=={} and model.ticks=={} and model.main_slot_masks=={}
    assert model.banks is banks


# Regression cases from pinned DeepSeek 1017 encoding tests (upstream MIT).
@pytest.mark.parametrize(
    "input_format",
    ["content_blocks", "tool_messages", "tool_content_blocks", "context"],
)
def test_v41_tool_result_images_follow_prompt_order(input_format: str) -> None:
    history = [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": "history.png"}},
            ],
        },
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": name,
                    "type": "function",
                    "function": {"name": name, "arguments": "{}"},
                }
                for name in ("a", "b")
            ],
        },
    ]
    results = [
        {
            "type": "tool_result",
            "tool_use_id": name,
            "content": [
                {"type": "text", "text": f"result {name}"},
                {"type": "image_url", "image_url": {"url": f"{name}.png"}},
            ],
        }
        for name in ("b", "a")
    ]
    if input_format in ("tool_messages", "tool_content_blocks"):
        content_field = (
            "content_blocks" if input_format == "tool_content_blocks" else "content"
        )
        messages = history + [
            {
                "role": "tool",
                "tool_call_id": block["tool_use_id"],
                content_field: block["content"],
            }
            for block in results
        ]
        context = []
    elif input_format == "context":
        messages = [{"role": "user", "content_blocks": results}]
        context = history
    else:
        messages = history + [{"role": "user", "content_blocks": results}]
        context = []
    original = copy.deepcopy((messages, context))

    prompt, media = encode_messages(
        messages,
        thinking_mode="chat",
        context=context,
        return_multi_modal_data=True,
    )

    assert prompt.endswith(
        f"<｜User｜><tool_result>result a\n\n{IMAGE_PLACEHOLDER}</tool_result>\n\n"
        f"<tool_result>result b\n\n{IMAGE_PLACEHOLDER}</tool_result><｜Assistant｜></think>"
    )
    expected_urls = ["a.png", "b.png"] if context else ["history.png", "a.png", "b.png"]
    assert media == {"images": [{"type": "image", "url": url} for url in expected_urls]}
    assert (messages, context) == original


def test_v41_drop_thinking_without_tools() -> None:
    messages = [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1", "reasoning_content": "r1"},
        {"role": "user", "content": "q2"},
        {
            "role": "assistant",
            "reasoning_content": "r2",
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "lookup", "arguments": "{}"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "c1", "content": "value"},
    ]
    prompt = encode_messages(
        messages,
        thinking_mode="thinking",
        drop_thinking=True,
    )
    # Drop completed-turn reasoning, but keep the current turn across tool results.
    assert "<｜User｜>q1<｜Assistant｜></think>a1<｜end▁of▁sentence｜>" in prompt
    assert "r1" not in prompt
    assert "<think>r2</think>" in prompt
    assert prompt.endswith("<tool_result>value</tool_result><｜Assistant｜><think>")

    next_turn = encode_messages(
        messages + [{"role": "user", "content": "q3"}],
        thinking_mode="thinking",
    )
    assert "r2" not in next_turn
    assert next_turn.endswith("q3<｜Assistant｜><think>")
