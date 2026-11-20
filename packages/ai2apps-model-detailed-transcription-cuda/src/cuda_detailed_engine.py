"""CUDA detailed transcription orchestration over pinned official stage processes.

Consumes normalized 16 kHz mono PCM WAV. Transport decoding belongs to the
Worker boundary. Shared product timeline/VAD/schema helpers remain unchanged.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import math
import tempfile
import threading
import wave
from cuda_detailed_process import DetailedCancelled, DetailedStageProcess
from mlx_whisperx.audio import read_audio
from mlx_whisperx.assignment import assign_speakers
from mlx_whisperx.pipeline import clip_segments, normalize_language, split_spans
from mlx_whisperx.schema import DiarizationSpan, Segment, Transcript, Word
from mlx_whisperx.service import DetailedTranscriptionService
from mlx_whisperx.vad import EnergyVAD, FullAudioVAD, MeetingEnergyVAD

LANGUAGES={'zh':'Chinese','yue':'Cantonese','en':'English','de':'German','es':'Spanish',
           'fr':'French','it':'Italian','pt':'Portuguese','ru':'Russian','ko':'Korean','ja':'Japanese'}

@dataclass(frozen=True)
class DetailedCheckpoints:
    compact: Path
    quality: Path
    aligner: Path
    diarizer: Path


class CudaDetailedEngine:
    def __init__(self, stages: DetailedStageProcess, checkpoints: DetailedCheckpoints):
        self.stages, self.checkpoints = stages, checkpoints

    def transcribe_wav(self, path: Path, cancelled: threading.Event, *, profile='quality',
                       language=None, prompt=None, timestamps='word', diarization=True,
                       speech_rate_analysis=False, emotion_recognition=False,
                       speaker_recognition=False, unsupported_policy='reject', vad='meeting-energy'):
        def check():
            if cancelled.is_set(): raise DetailedCancelled('Detailed transcription cancelled')
        check()
        if profile not in ('compact','quality') or timestamps not in ('word','segment'):
            raise ValueError('Invalid profile or timestamp mode')
        if unsupported_policy not in ('reject','compatibility'):
            raise ValueError('Invalid unsupported policy')
        if speaker_recognition or (emotion_recognition and unsupported_policy != 'compatibility'):
            raise ValueError('Requested recognition feature is unsupported')
        code=normalize_language(language)
        if code is not None and code not in LANGUAGES: raise ValueError('Unsupported language')
        vads={'meeting-energy':MeetingEnergyVAD,'energy':EnergyVAD,'none':FullAudioVAD}
        if vad not in vads: raise ValueError('Invalid VAD mode')
        with wave.open(str(path),'rb') as wav:
            if wav.getnchannels()!=1 or wav.getframerate()!=16000 or wav.getsampwidth()!=2:
                raise ValueError('Worker must normalize to 16 kHz mono PCM16 WAV')
        audio=read_audio(path)
        if not 0 < audio.duration <= 3600: raise ValueError('Audio must be positive and at most one hour')
        detector=vads[vad]();spans=split_spans(detector.detect(audio),30.0)
        segments=[]
        with tempfile.TemporaryDirectory(prefix='cuda-detailed-audio-') as directory:
            chunks=[]
            for index,span in enumerate(spans):
                check();chunk=Path(directory)/f'{index:05d}.wav';audio.slice(span.start,span.end).write_wav(chunk);chunks.append(str(chunk))
            if chunks:
                result=self.stages.run({'stage':'qwen','audio':chunks,'language':LANGUAGES.get(code),
                    'prompt':prompt,'word_timestamps':timestamps=='word',
                    'asr_checkpoint':str(getattr(self.checkpoints,profile)),
                    'aligner_checkpoint':str(self.checkpoints.aligner)},cancelled)
                if len(result['items'])!=len(spans): raise ValueError('ASR segment count mismatch')
                for span,item in zip(spans,result['items']):
                    if code is None: code=normalize_language(item['language'])
                    words=[]
                    for word in item['words']:
                        start,end=float(word['start_time']),float(word['end_time'])
                        if not math.isfinite(start) or not math.isfinite(end) or start<0 or end<start:
                            raise ValueError('Invalid official word timestamp')
                        words.append(Word(word=word['text'],start=span.start+start,end=span.start+end))
                    if item['text'].strip(): segments.append(Segment(span.start,span.end,item['text'],words=words))
        check();segments=clip_segments(segments,audio.duration,preserve_point_words=True)
        if diarization and segments:
            result=self.stages.run({'stage':'sortformer','audio':str(path),
                'diarizer_checkpoint':str(self.checkpoints.diarizer)},cancelled)
            speaker_spans=[]
            for item in result['spans']:
                start,end=float(item['start']),float(item['end'])
                if not math.isfinite(start) or not math.isfinite(end) or start<0 or end<start:
                    raise ValueError('Invalid official speaker timestamp')
                if start<audio.duration and end>start:
                    speaker_spans.append(DiarizationSpan(start,min(end,audio.duration),item['speaker']))
            assign_speakers(segments,speaker_spans,point_word_speakers=True)
        check()
        features={'transcription':{'status':'native','provider':'official_qwen3_asr','precision':'bfloat16'},
                  'vad':{'status':'pipeline','provider':detector.name},
                  'alignment':{'status':'pipeline' if timestamps=='word' else 'ignored','provider':'official_qwen3_forced_aligner' if timestamps=='word' else None},
                  'forced_alignment':{'status':'pipeline' if timestamps=='word' else 'ignored'},
                  'diarization':{'status':'pipeline' if diarization else 'ignored','provider':'official_nemo_sortformer' if diarization else None,'speaker_identity':'global_streaming' if diarization else None},
                  'emotion':{'status':'fallback','requested':True,'effective':'neutral','reason':'compatibility_policy'} if emotion_recognition else {'status':'ignored','requested':False},
                  'speaker_recognition':{'status':'ignored','requested':False}}
        output=Transcript(' '.join(s.text.strip() for s in segments),code,audio.duration,segments,features).to_dict()
        output.update(schema='ai2apps.detailed-transcription-result/v1',profile=profile)
        if timestamps == 'word':
            output['features']['alignment']['point_word_count'] = sum(
                w.start == w.end for segment in segments for w in segment.words
            )
        if emotion_recognition:
            for segment in output['segments']:segment['emotion']='neutral'
        output['features']['speech_rate']=DetailedTranscriptionService._speech_rates(output,enabled=speech_rate_analysis)
        return output
