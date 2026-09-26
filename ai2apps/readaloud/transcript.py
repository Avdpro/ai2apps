"""Render the selected primary transcript format without changing the editor payload."""
import json


def transcript_output(content: bytes, output_format: str) -> tuple[bytes, str, str]:
    if output_format == 'json':
        return content, 'transcript.json', 'application/json'
    result = json.loads(content)
    segments = result.get('segments') or []
    speakers = list(dict.fromkeys(segment.get('speaker') for segment in segments if segment.get('speaker')))
    names = {speaker: f'角色 {index + 1}' for index, speaker in enumerate(speakers)}
    def name(segment):
        return names.get(segment.get('speaker'), '未分配')
    def clock(seconds):
        value = max(0, float(seconds or 0))
        return f'{int(value // 60):02d}:{value % 60:04.1f}'
    def stamp(seconds):
        value = max(0, round(float(seconds or 0) * 1000))
        return f'{value // 3600000:02d}:{value // 60000 % 60:02d}:{value // 1000 % 60:02d},{value % 1000:03d}'
    if output_format == 'markdown':
        rows = [f"**{name(segment)}** · {clock(segment.get('start'))}–{clock(segment.get('end'))}\n\n{segment.get('text') or ''}" for segment in segments]
        text = '# 录音文本记录\n\n' + '\n\n'.join(rows) + '\n'
        return text.encode(), 'transcript.md', 'text/markdown'
    if output_format == 'srt':
        rows = [f"{index + 1}\n{stamp(segment.get('start'))} --> {stamp(segment.get('end'))}\n[{name(segment)}] {segment.get('text') or ''}\n" for index, segment in enumerate(segments)]
        return '\n'.join(rows).encode(), 'transcript.srt', 'application/x-subrip'
    raise ValueError('Unsupported transcript output format')
