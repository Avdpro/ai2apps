import importlib.util
import json
from pathlib import Path
import pytest
import yaml
from ai2apps.packages.archive import ServicePackageArchive
from ai2apps.packages.discovery import validate_model_profile
from ai2apps.model_worker import OmlxTTSAdapter, ModelWorkerError

ROOT=Path(__file__).resolve().parents[2]/'packages'
SLUGS=['zonos3-mini','moss-tts-nano','fish-s2-pro','breeze-tts2']
@pytest.mark.parametrize('slug',SLUGS)
def test_release_capabilities_and_scores(slug):
    p=ROOT/('omlx-model-'+slug)
    service=yaml.safe_load((p/'service.yaml').read_text())
    ServicePackageArchive._manifest(service)
    outer=json.loads((p/'ai2apps.json').read_text())
    validate_model_profile(outer['modelProfile'])
    fish=slug=='fish-s2-pro';model=service['models'][0]
    assert model['metadata']['experimental'] is not fish
    assert outer['modelProfile']['scores']['capability']==(5 if fish else 3)
    assert model['audio_capabilities']['tts']['emotion']['mode']==('native' if fish else 'unsupported')
    assert ('emotion-control' in outer['discovery']['tasks']) is fish
    assert service['requires']['services'][0]['version']=='>=1.8.20,<2.0.0'
    assert model['audio_capabilities']['tts']['multi_speaker']['mode']=='unsupported'

def test_fish_preserves_existing_bindings_and_maps_native_cues():
    p=ROOT/'omlx-model-fish-s2-pro'
    d=yaml.safe_load((p/'service.yaml').read_text())
    assert d['models'][0]['id']=='ai2apps.model.fish-s2-pro/bf16'
    assert d['models'][0]['upstream_id']=='mlx-community/fish-audio-drama-3-4bit'
    spec=importlib.util.spec_from_file_location('drama_adapter',p/'src/worker_adapter.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    a=module.DramaAdapter(None)
    for emotion in ['happy','scared','angry']:
        opts=a.synthesis_options(d['models'][0]['id'],{'language':'zh'},speed=1,emotion=emotion,emotion_strength=1,instructions=None)
        assert opts['instructions']==emotion
    assert a.synthesis_options('',{},speed=1,emotion='angry',emotion_strength=0,instructions=None)['instructions'] is None

def test_moss_codec_is_required_but_not_a_tts_choice():
    p=ROOT/'omlx-model-moss-tts-nano';d=yaml.safe_load((p/'service.yaml').read_text());outer=json.loads((p/'ai2apps.json').read_text())
    assert d['models'][0]['metadata']['required_model_ids']==[d['models'][1]['id']]
    assert d['models'][1]['metadata']['internal'] is True
    assert [m['id'] for m in outer['modelInstall']['models']]==[d['models'][0]['id']]
