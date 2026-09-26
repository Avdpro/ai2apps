import pytest

from ai2apps_test.audio_check import compare_text, check_audio


def test_text_comparison_normalizes_only_punctuation_and_case():
    assert compare_text('Hello，一、二、三！', 'hello 一二三')['normalizedMatch']
    assert not compare_text('一二三', '一三')['normalizedMatch']
    assert compare_text('你好', '')['status'] == 'needs-listening-review'
    with pytest.raises(ValueError):
        compare_text('！', '你好')


def test_audio_must_be_run_evidence(tmp_path):
    run = tmp_path / 'run'
    run.mkdir()
    audio = tmp_path / 'other.wav'
    audio.write_bytes(b'audio')
    with pytest.raises(ValueError, match='inside this Run'):
        check_audio(run, audio, tmp_path, 'hello')
