from dataclasses import dataclass, asdict
from types import SimpleNamespace
import json
import pytest
from ai2apps.model_worker.yue2_instrumental import plan_song, instrumental_request
from ai2apps.model_worker.yue2_instrumental.compile_score import compile_events
from ai2apps.model_worker.yue2_instrumental.abc_tools import parse_abc
from ai2apps.model_worker.yue2_instrumental.instrumentalize import convert_score

@dataclass
class Request:
    style: str = '重金属，旋律深沉'
    lyrics: str = ''
    cot: str = 'full'
    abc: str | None = None
    def to_dict(self): return asdict(self)
    def text(self): return f'[Tags]\n{self.style}\n[Lyrics]\n{self.lyrics}'


def score():
    text,_=compile_events({'bpm':100,'key':'C','bars':[{'section':'intro'},{'section':'verse'}],
                          'notes':[['0','1',60],['2','1',64]],'chords':[]})
    # Move the compiler's instrumental notes into Vocal for the fixture.
    lines=text.splitlines()
    for i,line in enumerate(lines):
        if line=='V: Vocal':
            lines[i+1],lines[i+3]=lines[i+3],lines[i+1]
    text='\n'.join(lines)+'\n'
    return text

class Pipeline:
    def __init__(self, truncated=False):
        self.requests=[]; self.truncated=truncated
        self.tokenizer=SimpleNamespace(encode=lambda text:list(text.encode()))
    def plan(self, request, **kwargs):
        self.requests.append(request)
        abc=request.abc or score()
        return SimpleNamespace(request=request,abc=abc,prefix=[len(self.requests)]+self.tokenizer.encode(request.text()),truncated=self.truncated)

@pytest.mark.parametrize('lyrics', ['', '  ', '[Intro]\n[Verse]'])
def test_instrumental_rebuilds_plan_preserving_style(tmp_path, lyrics):
    pipe=Pipeline();request=Request(lyrics=lyrics,cot='off')
    plan=plan_song(pipe,request,tmp_path/'out.wav',cancelled=lambda:False,on_token=lambda *a:None)
    assert len(pipe.requests)==2
    assert pipe.requests[0].cot=='full'
    assert request.style in plan.request.style
    assert 'no vocals' in plan.request.style
    target=parse_abc(plan.abc)
    assert not target.voices['Vocal'].notes
    assert target.voices['Ins'].notes
    assert plan.prefix[0]==2
    receipt=json.loads((tmp_path/'out-evidence/transfer.json').read_text())
    assert receipt['vocal_pitch_onset_duration_preserved']
    assert receipt['vocal_notes_after']==0


def test_sung_lyrics_unchanged(tmp_path):
    pipe=Pipeline();request=Request(lyrics='你好世界')
    plan=plan_song(pipe,request,tmp_path/'out.wav',cancelled=lambda:False,on_token=lambda *a:None)
    assert len(pipe.requests)==1 and plan.request==request


def test_supplied_score_used_and_invalid_score_stops(tmp_path):
    pipe=Pipeline();source=score()
    plan=plan_song(pipe,Request(abc=source),tmp_path/'out.wav',cancelled=lambda:False,on_token=lambda *a:None)
    assert pipe.requests[0].abc==source
    assert not parse_abc(plan.abc).voices['Vocal'].notes
    with pytest.raises(ValueError):
        plan_song(Pipeline(),Request(abc='bad'),tmp_path/'bad.wav',cancelled=lambda:False,on_token=lambda *a:None)


def test_truncated_planning_stops(tmp_path):
    with pytest.raises(ValueError,match='truncated'):
        plan_song(Pipeline(True),Request(),tmp_path/'out.wav',cancelled=lambda:False,on_token=lambda *a:None)


def test_unknown_brackets_are_not_silently_removed():
    assert not instrumental_request(Request(lyrics='[我爱你]'))


def test_conditioning_mismatch_is_rejected(tmp_path):
    class WrongPrefix(Pipeline):
        def plan(self, **kwargs):
            plan=super().plan(**kwargs)
            plan.prefix=[0, 1]
            return plan
    with pytest.raises(ValueError,match='prefix'):
        plan_song(WrongPrefix(),Request(),tmp_path/'out.wav',cancelled=lambda:False,on_token=lambda *a:None)


def test_existing_instrumental_score_retains_chords_and_events():
    source,_=compile_events({'bpm':80,'key':'C','bars':[{'section':'intro'},{'section':'verse'}],
        'notes':[['0','1',60],['2','1',64]],'chords':[['0','C'],['4','Am']]})
    converted, receipt=convert_score(source)
    original=parse_abc(source);target=parse_abc(converted)
    assert original.voices['Ins'].notes==target.voices['Ins'].notes
    assert original.voices['Vocal'].chords==target.voices['Vocal'].chords
    assert receipt['chords']=='preserved'
