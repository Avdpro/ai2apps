"""Native staged YuE2 inference, confined to Host-granted checkpoints/output."""
import os

# This must precede the first MLX import in the isolated Worker.
os.environ['MLX_ENABLE_TF32'] = '0'


def generate(checkpoints, config, params, output, check, report):
    import soundfile as sf
    from yue2_native.pipeline import Pipeline
    from yue2_native.protocol import GenerationConfig, SongRequest

    g = params['generation']
    generation = GenerationConfig.from_dict({
        'ode_steps': params['steps'],
        'abc': {'max_tokens': g.get('max_abc_tokens', 4096)},
        'semantic': {'max_tokens': g['max_semantic_tokens']},
    })
    song = SongRequest(style=params['prompt'], lyrics=params['lyrics'],
        cot=g.get('planning_mode', 'full'), abc=g.get('abc'),
        cfg_scale=g.get('guidance_scale'), seed=params['seed'])
    pipeline = Pipeline(checkpoints[0], checkpoints[1], generation)
    def cancelled():
        check()
        return False
    try:
        check(); report('plan')
        plan = pipeline.plan(song, cancelled=cancelled, on_token=lambda *_: check())
        report('semantic')
        semantic = pipeline.generate_semantic(plan, cancelled=cancelled, on_token=lambda *_: check())
        report('synthesis')
        latent = pipeline.synthesize(semantic, cancelled=cancelled)
        report('decode')
        audio = pipeline.decode(latent, cancelled=cancelled)
        check()
        sf.write(output, audio, 48000, subtype='PCM_16')
        check()
    finally:
        pipeline.close()
