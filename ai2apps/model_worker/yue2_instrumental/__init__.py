"""Checked instrumental planning shared by YuE2 MLX and CUDA engines."""
from dataclasses import replace
import json
from pathlib import Path
import re

from .instrumentalize import convert_score
from .abc_tools import parse_abc


def instrumental_request(request):
    # Section tags contain no lyrics and are also treated as instrumental.
    return not re.sub(r'\[(?:intro|verse|pre-chorus|chorus|bridge|interlude|outro|instrumental)\]', '', request.lyrics, flags=re.IGNORECASE).strip()


def plan_song(pipeline, request, output, *, cancelled, on_token):
    """Never pass a vocal score through merely because lyrics are empty."""
    directory = Path(output).parent / (Path(output).stem + '-evidence')
    directory.mkdir(parents=True, exist_ok=True)
    def save(name, value):
        (directory / name).write_text(value, encoding='utf-8')
    save('original-request.json', json.dumps(request.to_dict(), ensure_ascii=False, indent=2))
    instrumental = instrumental_request(request)
    if instrumental:
        style = request.style + '\nInstrumental, no vocals, no singing, no choir, no spoken words.'
        request = replace(request, style=style, lyrics='', cot='full' if request.cot == 'off' else request.cot)
    plan = pipeline.plan(request=request, cancelled=cancelled, on_token=on_token)
    if plan.abc:
        save('original.abc', plan.abc)
    if instrumental:
        if plan.truncated:
            raise ValueError('Instrumental score planning was truncated; no audio was generated. Retry with a shorter composition.')
        converted, check = convert_score(plan.abc, keep_chords=True)
        save('instrumental.abc', converted)
        save('transfer.json', json.dumps(check, ensure_ascii=False, indent=2))
        score = parse_abc(converted)
        if score.voices['Vocal'].notes or not score.voices['Ins'].notes:
            raise ValueError('Instrumental score validation failed')
        request = replace(request, abc=converted, cot='full' if score.voices['Vocal'].chords else 'melody')
        # Rebuild conditioning from the converted score, never reuse old prefix IDs.
        plan = pipeline.plan(request=request, cancelled=cancelled, on_token=on_token)
        if plan.abc != converted or plan.request.style != request.style:
            raise ValueError('Instrumental plan lost the intended score or style')
    # Verify the actual AR prefix contains the complete style/lyrics prompt.
    encoded = list(pipeline.tokenizer.encode(request.text()))
    if list(plan.prefix[1:1 + len(encoded)]) != encoded:
        raise ValueError('YuE2 conditioning prefix does not contain the intended prompt')
    save('effective-request.json', json.dumps(request.to_dict(), ensure_ascii=False, indent=2))
    save('prompt.txt', request.text())
    save('prefix.json', json.dumps(plan.prefix))
    return plan
