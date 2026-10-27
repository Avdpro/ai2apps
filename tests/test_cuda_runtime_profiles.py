import json

import pytest

from ai2apps.model_worker.runtime_profiles import framework_profile


def setup_profile(tmp_path, service='tts', relative='profiles/audio/site-packages'):
    (tmp_path / 'META').mkdir()
    (tmp_path / 'META/framework-profiles.json').write_text(json.dumps({
        'format': 'ai2apps.framework-profiles/v1',
        'services': {'tts': 'audio'}, 'profiles': {'audio': {'site_packages': relative}},
    }))
    config = tmp_path / 'config.json'
    config.write_text(json.dumps({'service_id': service, 'framework_profile': '/untrusted'}))
    return ['--config', str(config), '--port', '1234']


def test_legacy_runtime_needs_no_config(tmp_path):
    assert framework_profile(tmp_path, []) is None


def test_only_signed_service_mapping_selects_profile(tmp_path):
    args = setup_profile(tmp_path)
    expected = tmp_path / 'profiles/audio/site-packages'
    expected.mkdir(parents=True)
    assert framework_profile(tmp_path, args) == expected
    (tmp_path / 'config.json').write_text('{"service_id":"conversation"}')
    assert framework_profile(tmp_path, args) is None


@pytest.mark.parametrize('relative', ['/tmp/external', '../external'])
def test_profile_rejects_escape(tmp_path, relative):
    args = setup_profile(tmp_path, relative=relative)
    with pytest.raises(RuntimeError, match='escapes'):
        framework_profile(tmp_path, args)


def test_profile_rejects_symlink_escape(tmp_path):
    args = setup_profile(tmp_path, relative='external')
    (tmp_path / 'external').symlink_to(tmp_path.parent)
    with pytest.raises(RuntimeError, match='escapes'):
        framework_profile(tmp_path, args)


def test_missing_audio_layer_fails_closed(tmp_path):
    args = setup_profile(tmp_path)
    with pytest.raises(FileNotFoundError):
        framework_profile(tmp_path, args)


def test_generic_service_uses_same_signed_mapping_and_escape_checks(tmp_path):
    from ai2apps.model_worker.runtime_profiles import framework_profile_for_service
    setup_profile(tmp_path)
    selected = tmp_path / 'profiles/audio/site-packages'
    selected.mkdir(parents=True)
    assert framework_profile_for_service(tmp_path, 'tts') == selected
    assert framework_profile_for_service(tmp_path, 'unmapped') is None
    manifest = tmp_path / 'META/framework-profiles.json'
    value = json.loads(manifest.read_text())
    value['profiles']['audio']['site_packages'] = '../untrusted'
    manifest.write_text(json.dumps(value))
    with pytest.raises(RuntimeError, match='escapes'):
        framework_profile_for_service(tmp_path, 'tts')


def test_independent_stage_layers_do_not_replace_primary_profile(tmp_path):
    from ai2apps.model_worker.runtime_profiles import framework_profile_for_stage
    args=setup_profile(tmp_path)
    primary=tmp_path/'profiles/audio/site-packages';primary.mkdir(parents=True)
    manifest=tmp_path/'META/framework-profiles.json';value=json.loads(manifest.read_text())
    for name in ('qwen','nemo'):
        relative=f'profiles/{name}/site-packages';(tmp_path/relative).mkdir(parents=True)
        value['profiles'][name]={'site_packages':relative}
    value['stages']={'tts':{'recognition':'qwen','diarization':'nemo'}}
    manifest.write_text(json.dumps(value))
    assert framework_profile(tmp_path,args)==primary
    assert framework_profile_for_stage(tmp_path,'tts','recognition')==tmp_path/'profiles/qwen/site-packages'
    assert framework_profile_for_stage(tmp_path,'tts','diarization')==tmp_path/'profiles/nemo/site-packages'
    for service,stage in [('other','recognition'),('tts','unknown')]:
        with pytest.raises(RuntimeError,match='not declared'):
            framework_profile_for_stage(tmp_path,service,stage)


@pytest.mark.parametrize('relative',['/tmp/foreign','../foreign','symlink'])
def test_stage_layers_enforce_same_runtime_boundary(tmp_path,relative):
    from ai2apps.model_worker.runtime_profiles import framework_profile_for_stage
    setup_profile(tmp_path,relative=relative)
    if relative=='symlink':(tmp_path/'symlink').symlink_to(tmp_path.parent)
    manifest=tmp_path/'META/framework-profiles.json';value=json.loads(manifest.read_text())
    value['stages']={'tts':{'recognition':'audio'}};manifest.write_text(json.dumps(value))
    with pytest.raises(RuntimeError,match='escapes'):
        framework_profile_for_stage(tmp_path,'tts','recognition')


def test_legacy_runtime_cannot_silently_supply_an_undeclared_stage(tmp_path):
    from ai2apps.model_worker.runtime_profiles import framework_profile_for_stage
    setup_profile(tmp_path)
    with pytest.raises(RuntimeError,match='not declared'):
        framework_profile_for_stage(tmp_path,'tts','recognition')


def test_stage_entrypoint_must_be_declared_inside_runtime(tmp_path):
    from ai2apps.model_worker.runtime_profiles import framework_stage_entrypoint
    setup_profile(tmp_path)
    manifest=tmp_path/'META/framework-profiles.json';value=json.loads(manifest.read_text())
    entry=tmp_path/'app/stage.py';entry.parent.mkdir();entry.write_text('pass')
    value['stage_entrypoints']={'tts':{'recognition':'app/stage.py'}}
    manifest.write_text(json.dumps(value))
    assert framework_stage_entrypoint(tmp_path,'tts','recognition')==entry
    with pytest.raises(RuntimeError,match='not declared'):
        framework_stage_entrypoint(tmp_path,'tts','other')
    value['stage_entrypoints']['tts']['recognition']='../foreign.py'
    manifest.write_text(json.dumps(value))
    with pytest.raises(RuntimeError,match='escapes'):
        framework_stage_entrypoint(tmp_path,'tts','recognition')


def test_isolated_launcher_uses_declared_profile_not_pythonpath(tmp_path):
    import shutil,subprocess,sys
    from pathlib import Path
    source=Path(__file__).parents[1]/'ai2apps/model_worker'
    target=tmp_path/'app/ai2apps/model_worker';target.mkdir(parents=True)
    (target.parent/'__init__.py').write_text('');(target/'__init__.py').write_text('')
    for name in ('runtime_profiles.py','stage_launcher.py'):shutil.copy2(source/name,target/name)
    (tmp_path/'META').mkdir();profile=tmp_path/'profiles/qwen/site-packages';profile.mkdir(parents=True)
    core=tmp_path/f'Python/lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages';core.mkdir(parents=True)
    (profile/'stage_dependency.py').write_text('value="declared"')
    entry=tmp_path/'app/stage.py';entry.write_text('import stage_dependency,sys,pathlib\npathlib.Path(sys.argv[sys.argv.index("--result")+1]).write_text(stage_dependency.value)')
    (tmp_path/'META/framework-profiles.json').write_text(json.dumps({'format':'ai2apps.framework-profiles/v1','profiles':{'qwen':{'site_packages':'profiles/qwen/site-packages'}},'stages':{'service':{'asr':'qwen'}},'stage_entrypoints':{'service':{'asr':'app/stage.py'}}}))
    hostile=tmp_path/'hostile';hostile.mkdir();(hostile/'stage_dependency.py').write_text('raise RuntimeError("hostile import")')
    import os
    command=[sys.executable,'-I',str(target/'stage_launcher.py'),'--service-id','service','--stage','asr','--job',str(tmp_path/'job.json'),'--result',str(tmp_path/'result')]
    subprocess.run(command,env=dict(os.environ,PYTHONPATH=str(hostile)),check=True,capture_output=True)
    assert (tmp_path/'result').read_text()=='declared'
