import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

path = Path(__file__).resolve().parents[1]/'packages/omlx-punctuation-restorer/src/worker_adapter.py'
spec = importlib.util.spec_from_file_location('punctuation_style_adapter',path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

@pytest.mark.asyncio
@pytest.mark.parametrize('source,candidate,expected,preserved',[
    ('hello everyone', 'hello，everyone。', 'hello, everyone.', True),
    ('hello 大家好', 'hello，大家好。', 'hello，大家好。', True),
    ('price is 3.14 today', 'price is 3.14 today。', 'price is 3.14 today.', True),
    ('meeting at 930', 'meeting at 930。', 'meeting at 930.', True),
    ('hello everyone', 'hello，somebody。', 'hello everyone.', False),
])
async def test_style_preserves_content_and_rejects_model_rewrites(source,candidate,expected,preserved):
    adapter = module.PunctuationAdapter(None)
    async def restorer(_):
        return SimpleNamespace(add_punctuation=lambda _:candidate)
    adapter._restorer_for = restorer
    result = await adapter.invoke(SimpleNamespace(operation='chat_completions',payload={
        'model':'punctuation','messages':[{'role':'user','content':source}]}))
    assert result['choices'][0]['message']['content'] == expected
    assert result['punctuation']['preserves_words'] is preserved
    assert module._signature(expected) == module._signature(source)
