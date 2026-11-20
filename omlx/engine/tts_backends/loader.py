"""Offline, strict loading for the four evaluated MLX TTS families."""
import importlib
import json
from pathlib import Path

FAMILIES = {'zonos3': 'zonos3', 'zonos3_mini': 'zonos3',
            'fish_drama3': 'fish_drama3', 'breeze': 'breeze_tts',
            'breeze_tts': 'breeze_tts', 'moss_tts_nano': 'moss_tts_nano'}


def family_for(path):
    config = Path(path) / 'config.json'
    if not config.is_file():
        return None
    return FAMILIES.get(json.loads(config.read_text()).get('model_type'))


def load_local(path, dependency_checkpoints=None):
    """No Hub resolution or permissive shape fallback for these checkpoints."""
    import mlx.core as mx
    from mlx_audio.utils import load_weights, apply_quantization
    # Host supplies an already selected local checkpoint. Do not resolve its
    # ancestors: sandbox grants cover the checkpoint, not parent directories.
    root = Path(path).absolute()
    config = json.loads((root / 'config.json').read_text())
    family = FAMILIES[config['model_type']]
    required = {'zonos3': ['codec', 'speaker_encoder', 'voices.json'],
                'fish_drama3': ['tokenizer.json', 'codec.safetensors'],
                'breeze_tts': ['tokenizer.json', 'audio_tokenizer/config.json'],
                'moss_tts_nano': ['tokenizer.model']}[family]
    for relative in required:
        if not (root / relative).exists():
            raise FileNotFoundError(f'{family} checkpoint missing {relative}; install the complete checkpoint')
    codec_root = root
    if family == 'moss_tts_nano' and not (root / 'audio_tokenizer/config.json').is_file():
        codec_path = (dependency_checkpoints or {}).get('OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano')
        if not codec_path or not (Path(codec_path) / 'config.json').is_file():
            raise FileNotFoundError('MOSS Nano requires the Host-selected audio tokenizer checkpoint')
        codec_root = Path(codec_path).absolute()
    module = importlib.import_module(
        f'omlx.engine.tts_backends.{family}' if family in ('zonos3', 'fish_drama3')
        else f'mlx_audio.tts.models.{family}')
    config['model_path'] = str(root)
    model = module.Model(module.ModelConfig.from_dict(config))
    weights = load_weights(root)
    if hasattr(model, 'sanitize'):
        weights = model.sanitize(weights)
    apply_quantization(model, config, weights, getattr(model, 'model_quant_predicate', None))
    model.load_weights(list(weights.items()), strict=True)
    mx.eval(model.parameters())
    model.eval()
    model = module.Model.post_load_hook(model, root)
    if family == 'moss_tts_nano':
        # Eagerly bind the bundled codec; never allow a lazy Hub fallback.
        from mlx_audio.codec import MossAudioTokenizer
        model.audio_tokenizer = MossAudioTokenizer.from_pretrained(
            codec_root / 'audio_tokenizer' if (codec_root / 'audio_tokenizer').is_dir() else codec_root
        )
    return model
