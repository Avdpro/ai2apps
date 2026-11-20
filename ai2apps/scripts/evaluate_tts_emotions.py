"""Generate comparable emotion takes through TTSEngine, offline."""
import asyncio, hashlib, io, json, time, wave, os
from pathlib import Path
import mlx.core as mx
from omlx.engine.tts import TTSEngine

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'docs/evidence/tts-emotions-20261119'
TEXT = '你终于来了！我一直在这里等你。快过来，看看这里发生了什么。'
REFERENCE_TEXT = '你好，这是本地语音测试。今天阳光很好。'
PROMPTS = {'neutral':'用平静自然的语气说话。', 'happy':'用开心、喜悦、兴奋的语气说话。',
           'scared':'用害怕、紧张、恐惧的语气说话。', 'angry':'用生气、愤怒的语气说话。'}

async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = json.loads((ROOT/'docs/evidence/four-mlx-tts-20261119/checkpoints.local.json').read_text())
    ref = str(ROOT/'docs/evidence/four-mlx-tts-20261119/speech/ZONOS3-Mini.wav')
    for row in rows:
        name = row['repo'].split('/')[-1]
        if not any(s in name for s in ['ZONOS3', 'drama', 'Breeze']):
            continue
        engine = TTSEngine(row['path'])
        await engine.start()
        try:
            for emotion in PROMPTS:
                mx.random.seed(20261119)
                args = dict(language='zh', ref_audio=ref, ref_text=REFERENCE_TEXT, max_tokens=512)
                if 'ZONOS3' in name:
                    args.update(emotion=emotion, emotion_strength=3.5, seed=20261119)
                elif 'drama' in name:
                    if emotion != 'neutral': args['instructions'] = emotion
                else:
                    args['instructions'] = PROMPTS[emotion]
                started = time.monotonic()
                audio = await engine.synthesize(TEXT, **args)
                target=OUT/f'{name}-{emotion}.wav';target.write_bytes(audio)
                with wave.open(io.BytesIO(audio)) as wav:
                    seconds=wav.getnframes()/wav.getframerate()
                receipt = dict(repo=row['repo'], revision=row['revision'], text=TEXT, emotion=emotion,
                               arguments=args, seconds=seconds, elapsed=time.monotonic()-started,
                               sha256=hashlib.sha256(audio).hexdigest())
                target.with_suffix('.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
                print(name,emotion,seconds,flush=True)
        finally:
            await engine.stop()

if __name__ == '__main__':
    os.environ['HF_HUB_OFFLINE']='1'
    asyncio.run(main())
