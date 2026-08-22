import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "ai2apps/web/static/js/streaming_tts.js"


def _segment(script: str) -> list[str]:
    program = f"""
const {{ StreamingTextSegmenter }} = require({json.dumps(str(MODULE))});
const segmenter = new StreamingTextSegmenter();
{script}
"""
    completed = subprocess.run(
        ["node", "-e", program],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_streaming_segmenter_preserves_question_and_sentence_boundaries():
    segments = _segment(
        """
const result = [
  ...segmenter.append('你帮我看一下那个文档有没有什么错误？另外你再看一下'),
  ...segmenter.append('我今天的安排能不能去商场逛一逛。'),
  ...segmenter.finish(),
];
console.log(JSON.stringify(result));
"""
    )

    assert segments == [
        "你帮我看一下那个文档有没有什么错误？",
        "另外你再看一下我今天的安排能不能去商场逛一逛。",
    ]


def test_streaming_segmenter_flushes_markdown_tail_without_reading_markup():
    segments = _segment(
        """
const result = [
  ...segmenter.append('**结论**：请查看[文档](https://example.com)'),
  ...segmenter.finish(),
];
console.log(JSON.stringify(result));
"""
    )

    assert segments == ["结论：请查看文档"]


def test_streaming_segmenter_emits_a_short_question_immediately():
    segments = _segment(
        """
const result = [
  ...segmenter.append('好吗？现在开始播放后续生成的语音。'),
  ...segmenter.finish(),
];
console.log(JSON.stringify(result));
"""
    )

    assert segments == ["好吗？", "现在开始播放后续生成的语音。"]
