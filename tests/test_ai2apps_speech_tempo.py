import io
import wave
import numpy as np
import pytest
from ai2apps.audio_codecs import change_speech_tempo


@pytest.mark.parametrize('speed', [0.5, 0.75, 1.25, 2.0])
def test_tempo_changes_duration_without_changing_pitch(speed):
    buffer = io.BytesIO()
    rate = 24000
    with wave.open(buffer, 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        samples = (10000*np.sin(np.arange(rate*2)*2*np.pi*440/rate)).astype('<i2')
        audio.writeframes(samples.tobytes())
    result = change_speech_tempo(buffer.getvalue(), speed)
    with wave.open(io.BytesIO(result)) as audio:
        assert audio.getframerate() == rate
        assert audio.getnframes()/rate == pytest.approx(2/speed, abs=0.06)
        values = np.frombuffer(audio.readframes(audio.getnframes()), dtype='<i2')
    frequency = np.fft.rfftfreq(len(values), 1/rate)[np.argmax(abs(np.fft.rfft(values)))]
    assert frequency == pytest.approx(440, abs=2)


def test_normal_speed_preserves_original_bytes():
    assert change_speech_tempo(b'original', 1) == b'original'
