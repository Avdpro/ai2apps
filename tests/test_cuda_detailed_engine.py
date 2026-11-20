from pathlib import Path
import sys,threading,wave
import pytest
ROOT=Path(__file__).parents[1]
sys.path.insert(0,str(ROOT/'spark'))
sys.path.insert(0,str(ROOT/'packages/omlx-model-detailed-transcription/src'))
from cuda_detailed_engine import CudaDetailedEngine,DetailedCheckpoints
from cuda_detailed_process import DetailedCancelled


def wav(tmp_path,seconds=61):
    p=tmp_path/'input.wav'
    with wave.open(str(p),'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(b'\0\0'*16000*seconds)
    return p


class Stages:
    def __init__(self):self.jobs=[]
    def run(self,job,event):
        self.jobs.append(job)
        if job['stage']=='qwen':
            return {'items':[{'text':'Hello','language':'English','words':[{'text':'Hello','start_time':.1,'end_time':.8}] if job['word_timestamps'] else []} for _ in job['audio']]}
        return {'spans':[{'start':0,'end':30,'speaker':'speaker_0'},{'start':30,'end':61,'speaker':'speaker_1'}]}


def engine(stages):return CudaDetailedEngine(stages,DetailedCheckpoints(*[Path(x) for x in ('compact','quality','aligner','diarizer')]))


def test_batch_offsets_and_global_speakers(tmp_path):
    stages=Stages();output=engine(stages).transcribe_wav(wav(tmp_path),threading.Event(),profile='compact',vad='none',speech_rate_analysis=True)
    assert [j['stage'] for j in stages.jobs]==['qwen','sortformer']
    assert len(stages.jobs[0]['audio'])==3
    assert [s['words'][0]['start'] for s in output['segments']]==[.1,30.1,60.1]
    assert [s['speaker'] for s in output['segments']]==['speaker_0','speaker_1','speaker_1']
    assert all(not Path(p).exists() for p in stages.jobs[0]['audio'])
    assert output['schema']=='ai2apps.detailed-transcription-result/v1'
    assert output['features']['speech_rate']['unit']=='words_per_minute'


def test_optional_stages_and_explicit_neutral_policy(tmp_path):
    stages=Stages();output=engine(stages).transcribe_wav(wav(tmp_path,1),threading.Event(),vad='none',timestamps='segment',diarization=False,emotion_recognition=True,unsupported_policy='compatibility')
    assert len(stages.jobs)==1 and not stages.jobs[0]['word_timestamps']
    assert output['segments'][0]['words']==[] and output['segments'][0]['emotion']=='neutral'
    assert output['features']['diarization']['status']=='ignored'


def test_silence_skips_models(tmp_path):
    stages=Stages();output=engine(stages).transcribe_wav(wav(tmp_path,1),threading.Event())
    assert not stages.jobs and output['segments']==[] and output['text']==''


def test_rejection_and_precancel_before_model_call(tmp_path):
    stages=Stages();service=engine(stages);p=wav(tmp_path,1)
    for options in ({'speaker_recognition':True},{'emotion_recognition':True},{'language':'xx'}):
        with pytest.raises(ValueError):service.transcribe_wav(p,threading.Event(),**options)
    event=threading.Event();event.set()
    with pytest.raises(DetailedCancelled):service.transcribe_wav(p,event)
    assert not stages.jobs


def test_quantized_official_words_preserved_without_fabricating_durations():
    from mlx_whisperx.pipeline import clip_segments
    from mlx_whisperx.schema import Segment,Word
    def sample():
        return [Segment(0,2,'a b c d e',words=[Word('a',1,1),Word('b',-1,-1),Word('c',3,3),Word('d',-1,0),Word('e',.5,1.5)])]
    default=clip_segments(sample(),2)
    assert [w.word for w in default[0].words]==['e']
    official=clip_segments(sample(),2,preserve_point_words=True)
    assert [(w.word,w.start,w.end) for w in official[0].words]==[('a',1,1),('e',.5,1.5)]


def test_retained_official_fixture_has_complete_word_coverage(tmp_path):
    import json,re
    fixture=json.loads((ROOT/'tests/fixtures/cuda_detailed_official_words.json').read_text())
    class Replay:
        def run(self,job,event):return fixture['stages'][job['stage']]
    result=engine(Replay()).transcribe_wav(wav(tmp_path,36),threading.Event(),vad='none')
    normalize=lambda s:re.sub(r'[^a-z0-9]','',s.lower())
    assert all(normalize(s['text'])==normalize(''.join(w['word'] for w in s['words'])) for s in result['segments'])
    assert sum(len(s['words']) for s in result['segments'])==94
    assert result['features']['alignment']['point_word_count']==4


def test_official_point_words_use_containing_speaker_not_segment_majority():
    from mlx_whisperx.assignment import assign_speakers
    from mlx_whisperx.schema import Segment,Word,DiarizationSpan
    spans=[DiarizationSpan(4.32,7.36,'speaker_0'),DiarizationSpan(9.04,11.36,'speaker_1')]
    words=[Word('the',6.09,6.09),Word('later',9.2,9.5),Word('words',10,10.2)]
    segment=Segment(4.17,17.16,'the later words',words)
    assign_speakers([segment],spans,point_word_speakers=True)
    assert words[0].speaker=='speaker_0' and segment.speaker=='speaker_1'
    assert (words[0].word,words[0].start,words[0].end)==('the',6.09,6.09)


def test_point_speaker_boundary_and_default_compatibility():
    from mlx_whisperx.assignment import assign_speakers
    from mlx_whisperx.schema import Segment,Word,DiarizationSpan
    spans=[DiarizationSpan(0,1,'a'),DiarizationSpan(1,2,'b')]
    def segment():return Segment(0,2,'one two three',[Word('one',.1,.3),Word('two',.4,.6),Word('three',1,1)])
    old=segment();assign_speakers([old],spans)
    assert old.words[-1].speaker=='a'
    new=segment();assign_speakers([new],spans,point_word_speakers=True)
    assert new.words[-1].speaker=='b'


def test_ambiguous_point_keeps_existing_fallback():
    from mlx_whisperx.assignment import assign_speakers
    from mlx_whisperx.schema import Segment,Word,DiarizationSpan
    spans=[DiarizationSpan(0,2,'a'),DiarizationSpan(.5,1.5,'b')]
    segment=Segment(0,2,'one two',[Word('one',.1,.3),Word('two',1,1)])
    assign_speakers([segment],spans,point_word_speakers=True)
    assert segment.words[-1].speaker=='a'
