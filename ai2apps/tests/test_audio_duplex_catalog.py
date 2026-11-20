from ai2apps.model_providers import validate_package_models
from test_audio_duplex_worker import declaration


def test_realtime_model_type_is_distinct_from_stt_and_tts():
    values = validate_package_models('arbitrary.owner', [{
        'id': 'arbitrary.owner/duplex', 'model_type': 'audio_realtime',
        'audio_capabilities': declaration(),
    }], runtime_mode='managed_process', protocol='ai2apps-model-worker/v1')
    assert values[0]['capabilities'] == ['speech_duplex']
    assert values[0]['endpoints']['audio_realtime'] == '/v1/audio/realtime'
    assert values[0]['context_window'] is None
