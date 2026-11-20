"""Offline smoke evaluation through the production TTSEngine entry point.

Pass a JSON list of {repo, revision, path}; dependency checkpoints are included
in the same list. Checkpoints must already be installed/downloaded locally.
"""
import argparse
import asyncio
import hashlib
import io
import json
import os
import time
import traceback
import wave
from pathlib import Path


async def evaluate(args):
    from omlx.engine.tts import TTSEngine
    from omlx.engine.tts_backends.loader import family_for
    rows = json.loads(Path(args.checkpoints).read_text())
    dependencies = {r['repo']: str(Path(r['path']).resolve(strict=True)) for r in rows}
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    failed = False
    for row in rows:
        path = dependencies[row['repo']]
        if not family_for(path):
            continue
        name = row['repo'].split('/')[-1]
        receipt = {k: row[k] for k in ('repo', 'revision')}
        receipt.update(text=args.text, language=args.language,
                       reference_audio=args.reference_audio,
                       reference_text=args.reference_text, max_tokens=args.max_tokens)
        engine = TTSEngine(path, dependency_checkpoints=dependencies)
        started = time.monotonic()
        try:
            await engine.start()
            receipt['load_seconds'] = time.monotonic() - started
            audio = await engine.synthesize(
                args.text, language=args.language, max_tokens=args.max_tokens,
                ref_audio=args.reference_audio, ref_text=args.reference_text)
            (output / f'{name}.wav').write_bytes(audio)
            with wave.open(io.BytesIO(audio)) as wav:
                receipt.update(sample_rate=wav.getframerate(), channels=wav.getnchannels(),
                               seconds=wav.getnframes() / wav.getframerate())
            receipt.update(status='generated', sha256=hashlib.sha256(audio).hexdigest())
        except Exception as exc:
            failed = True
            receipt.update(status='failed', error=str(exc), traceback=traceback.format_exc())
        finally:
            await engine.stop()
        receipt['elapsed_seconds'] = time.monotonic() - started
        (output / f'{name}.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=False)+'\n')
        print(name, receipt['status'], flush=True)
    return int(failed)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoints', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--text', default='你好，这是本地语音测试。今天阳光很好。')
    parser.add_argument('--language', default='zh')
    parser.add_argument('--max-tokens', type=int, default=512)
    parser.add_argument('--reference-audio')
    parser.add_argument('--reference-text')
    args = parser.parse_args()
    os.environ['HF_HUB_OFFLINE'] = '1'
    raise SystemExit(asyncio.run(evaluate(args)))
