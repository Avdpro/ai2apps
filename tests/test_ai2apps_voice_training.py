from io import BytesIO
from types import SimpleNamespace
import wave

import pytest
from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.testclient import TestClient

from ai2apps.api.readaloud import create_readaloud_router
from ai2apps.config import PlatformConfig
from ai2apps.events import EventStore
from ai2apps.gallery import GalleryRepository
from ai2apps.identity import RequestPrincipal
from ai2apps.readaloud import ReadAloudRepository
from ai2apps.readaloud.materials import VoiceMaterials
from ai2apps.readaloud.training import prepare, requirements
from ai2apps.storage import PlatformDatabase


def wav_bytes(seconds=1):
    out = BytesIO()
    with wave.open(out, 'wb') as audio:
        audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(16000)
        audio.writeframes(b'\x00\x00' * int(16000 * seconds))
    return out.getvalue()


@pytest.fixture
def setup(tmp_path):
    config = PlatformConfig.from_base_path(tmp_path)
    database = PlatformDatabase(config.paths.database_path); database.initialize()
    repository = ReadAloudRepository(database, EventStore(database))
    gallery = GalleryRepository(database, config.paths.artifacts_path / 'gallery')
    asset, _ = gallery.import_stream('local', BytesIO(wav_bytes()), name='sample.wav', media_type='audio/wav')
    other, _ = gallery.import_stream('other', BytesIO(wav_bytes()), name='other.wav', media_type='audio/wav')
    model = SimpleNamespace(id='clone/model', display_name='Clone', weights={'revision':'revision-1'}, checkpoint_ready=True,
        audio_capabilities={'tts':{'voice_profiles':{'mode':'native','reference_transcript':'required','reference_requirements':{'min_seconds':0.5,'max_seconds':2}}}})
    calls = []
    async def invoke(*args, **kwargs):
        calls.append((args, kwargs)); return Response(wav_bytes(), media_type='audio/wav')
    invocations = SimpleNamespace(model=lambda model_id: model if model_id == model.id else None,
        invoke_foreground_multipart=invoke, context_for_actor=lambda *a, **kw: kw)
    runtime = SimpleNamespace(config=config, database=database, readaloud=repository, model_invocations=invocations,
        readaloud_tasks=SimpleNamespace(save_quick_audio=lambda *a, **kw:'/saved-preview.wav'))
    # Router uses readaloud_repository in the Runtime contract.
    runtime.readaloud_repository = repository
    app = FastAPI(); app.include_router(create_readaloud_router(lambda:runtime, lambda:RequestPrincipal.legacy_local()))
    request = {'name':'Voice','source_type':'self_voice','model_id':model.id,
        'samples':[{'asset_id':asset['id'],'transcript':'hello','confirmed':True}],
        'rights_scope':{'consent_confirmed':True,'usage_rights_confirmed':True,'prohibited_impersonation_acknowledged':True}}
    return SimpleNamespace(client=TestClient(app), runtime=runtime, model=model, request=request, asset=asset, other=other, gallery=gallery, calls=calls, repository=repository)


def test_training_profile_binding_materials_and_update(setup):
    result = setup.client.post('/readaloud/training/profiles', json=setup.request)
    assert result.status_code == 201, result.text
    profile = result.json()
    assert profile['modelId'] == 'clone/model'
    assert profile['training']['model_revision'] == 'revision-1'
    assert profile['training']['samples'][0]['duration'] == 1
    assert profile['status'] == 'unverified'
    setup.request.update(profile_id=profile['id'], name='Updated')
    result = setup.client.post('/readaloud/training/profiles', json=setup.request)
    assert result.status_code == 201, result.text
    assert result.json()['id'] == profile['id']
    assert len(setup.repository.list_voice_profiles('local')) == 1


def test_preview_requires_review_and_uses_bound_reference(setup):
    setup.request['samples'][0]['confirmed'] = False
    assert setup.client.post('/readaloud/training/preview',json=setup.request).status_code == 422
    assert not setup.calls
    setup.request['samples'][0]['confirmed'] = True
    result = setup.client.post('/readaloud/training/preview',json=setup.request)
    assert result.status_code == 200, result.text
    assert result.content == wav_bytes()
    args, kwargs = setup.calls[0]
    assert args == ('clone/model','audio_speech')
    assert kwargs['data']['ref_text'] == 'hello'
    assert kwargs['files']['reference_audio'][1] == wav_bytes()
    assert kwargs['context']['consumer_app_id'] == 'ai2apps.readaloud'


def test_training_rejects_wrong_owner_invalid_model_and_missing_rights(setup):
    setup.request['samples'][0]['asset_id'] = setup.other['id']
    assert setup.client.post('/readaloud/training/profiles',json=setup.request).status_code == 422
    setup.request['samples'][0]['asset_id'] = setup.asset['id']
    setup.request['model_id'] = 'missing'
    assert setup.client.post('/readaloud/training/profiles',json=setup.request).status_code == 422
    setup.request['model_id'] = setup.model.id
    setup.request['rights_scope'] = {}
    assert setup.client.post('/readaloud/training/preview',json=setup.request).status_code == 422
    assert not setup.calls


def test_requirements_validate_duration_and_optional_transcript(setup):
    sample = {'asset_id':setup.asset['id'],'selected':True}
    feature = setup.model.audio_capabilities['tts']['voice_profiles']
    feature['reference_transcript']='optional'
    spec, samples, files = prepare(setup.model,[sample],setup.gallery,'local',for_execution=True)
    assert spec['maxSamples']==1 and samples[0]['duration']==1
    feature['reference_requirements']['min_seconds']=2
    with pytest.raises(ValueError,match='duration'):
        prepare(setup.model,[sample],setup.gallery,'local')


def test_multi_reference_and_training_are_not_silently_single_reference(setup):
    feature = setup.model.audio_capabilities['tts']['voice_profiles']
    feature['reference_requirements']['max_samples']=3
    assert not requirements(setup.model)['executable']
    assert setup.client.post('/readaloud/training/preview',json=setup.request).status_code == 409
    setup.model.audio_capabilities={'processing':{'voice_training':{'mode':'native'}}}
    assert requirements(setup.model)['method']=='training'
    assert setup.client.post('/readaloud/training/preview',json=setup.request).status_code == 409
    assert not setup.calls


def test_model_revision_change_requires_explicit_rebinding(setup):
    setup.request['model_revision']='old-revision'
    assert setup.client.post('/readaloud/training/preview',json=setup.request).status_code == 409
    assert setup.client.post('/readaloud/training/profiles',json=setup.request).status_code == 409
    assert not setup.calls


def test_saved_transcripts_can_be_incomplete_but_cannot_preview(setup):
    setup.request['samples'][0].update(transcript='',confirmed=False)
    assert setup.client.post('/readaloud/training/profiles',json=setup.request).status_code == 201
    assert setup.client.post('/readaloud/training/preview',json=setup.request).status_code == 422
    assert not setup.calls


def test_duplicate_samples_and_foreign_profile_updates_are_rejected(setup):
    setup.request['samples'] *= 2
    assert setup.client.post('/readaloud/training/profiles',json=setup.request).status_code == 422
    setup.request['samples'] = setup.request['samples'][:1]
    foreign = setup.repository.create_voice_profile('other',name='Other',source_type='self_voice',model_id=None,
        provider_voice_id=None,reference_transcript='',rights_scope={})
    setup.request['profile_id']=foreign['id']
    assert setup.client.post('/readaloud/training/profiles',json=setup.request).status_code == 404
    assert setup.repository.list_voice_profiles('other')[0]['name']=='Other'


def test_design_profile_rejects_instruction_only_models(setup):
    setup.model.model_type='audio_tts'
    setup.model.capabilities=['voice_instructions','named_voices']
    payload={'name':'Design','source_type':'synthetic_designed','model_id':setup.model.id}
    assert setup.client.post('/readaloud/voice-profiles',json=payload).status_code == 422
    setup.model.capabilities=['voice_design','voice_instructions']
    assert setup.client.post('/readaloud/voice-profiles',json=payload).status_code == 201


@pytest.fixture
def design_setup(setup, tmp_path):
    design = SimpleNamespace(id='design/model', display_name='Design', model_type='audio_tts',
        capabilities=['voice_design'], checkpoint_ready=True, weights={'revision':'design-1'})
    setup.runtime.model_invocations.model = lambda mid: {design.id:design, setup.model.id:setup.model}.get(mid)
    async def invoke(*args, **kwargs):
        setup.calls.append((args, kwargs))
        return Response(wav_bytes(), media_type='audio/wav')
    setup.runtime.model_invocations.invoke_foreground_json = invoke
    path = tmp_path / 'output.wav'
    def save(owner, content, **kwargs):
        path.write_bytes(content)
        return '/v1/platform/sessions/session/artifacts/artifact/download'
    setup.runtime.readaloud_tasks.save_quick_audio = save
    setup.runtime.workspace = SimpleNamespace(get_artifact=lambda *a:SimpleNamespace(uri='artifact://preview'), artifact_path=lambda a:path)
    setup.design = design
    setup.design_request = {'name':'Alice','model_id':design.id,'description':'Warm, calm alto','text':'Hello world.'}
    setup.output_path = path
    return setup


def test_design_preview_conversion_preserves_exact_audio_and_source(design_setup):
    s = design_setup
    result = s.client.post('/readaloud/design/preview', json=s.design_request)
    assert result.status_code == 200, result.text
    source = result.json()
    args, kwargs = s.calls[0]
    assert args[:2] == ('design/model','audio_speech')
    assert args[2]['instructions'] == 'Warm, calm alto'
    assert args[2]['input'] == 'Hello world.'
    assert source['status'] == 'ready'
    result = s.client.post('/readaloud/design/profiles/'+source['id']+'/convert', json={'model_id':s.model.id})
    assert result.status_code == 200, result.text
    trained = result.json()
    assert trained['id'] != source['id']
    assert trained['modelId'] == s.model.id
    assert trained['status'] == 'unverified'
    sample = trained['training']['samples'][0]
    assert sample['transcript'] == 'Hello world.' and not sample['confirmed']
    assert trained['training']['model_revision'] == 'revision-1'
    assert s.repository.get_voice_profile('local',source['id'])['training']['design']['preview']
    # The character owns an independent copy after the preview output is retired.
    s.output_path.unlink()
    spec, samples, files = prepare(s.model,[sample],VoiceMaterials(s.runtime.database,s.runtime.config.paths.artifacts_path),'local')
    assert files[sample['asset_id']] == wav_bytes()
    request = {**s.request, 'profile_id':trained['id'], 'source_type':'synthetic_designed','rights_scope':{},'samples':[sample]}
    result = s.client.post('/readaloud/training/profiles',json=request)
    assert result.status_code == 201, result.text
    assert result.json()['training']['origin']['design_profile_id'] == source['id']
    assert s.client.post('/readaloud/training/preview',json=request).status_code == 422
    request['samples'][0]['confirmed'] = True
    request['preview_text'] = 'A new line in the same voice.'
    assert s.client.post('/readaloud/training/preview',json=request).status_code == 200
    request['samples'] = [{'asset_id':s.other['id'],'confirmed':True,'transcript':'replacement'}]
    assert s.client.post('/readaloud/training/profiles',json=request).status_code == 422


def test_design_edits_invalidate_preview_and_reject_foreign_profiles(design_setup):
    s = design_setup
    result = s.client.post('/readaloud/design/preview',json=s.design_request)
    source = result.json()
    request = {**s.design_request,'profile_id':source['id'],'description':'Different voice'}
    result = s.client.post('/readaloud/design/profiles',json=request)
    assert result.status_code == 200, result.text
    assert not result.json()['training']['design'].get('preview')
    assert result.json()['status'] == 'unverified'
    assert s.client.post('/readaloud/design/profiles/'+source['id']+'/convert',json={'model_id':s.model.id}).status_code == 422
    foreign = s.repository.create_voice_profile('other',name='Foreign',source_type='synthetic_designed',model_id=s.design.id,provider_voice_id=None,reference_transcript='',rights_scope={})
    request['profile_id'] = foreign['id']
    assert s.client.post('/readaloud/design/profiles',json=request).status_code == 422
    s.design.capabilities = ['voice_instructions']
    assert s.client.post('/readaloud/design/preview',json=s.design_request).status_code == 422


def test_design_unready_and_invalid_audio_do_not_attach_preview(design_setup):
    s = design_setup
    s.design.checkpoint_ready = False
    assert s.client.post('/readaloud/design/preview',json=s.design_request).status_code == 409
    assert not s.calls
    s.design.checkpoint_ready = True
    async def invalid(*args, **kwargs):
        return Response(b'not audio',media_type='audio/wav')
    s.runtime.model_invocations.invoke_foreground_json = invalid
    assert s.client.post('/readaloud/design/preview',json=s.design_request).status_code == 502
    assert not s.repository.list_voice_profiles('local')[0]['training']['design'].get('preview')


def test_successful_preview_verifies_exact_saved_reference(setup):
    profile = setup.client.post('/readaloud/training/profiles', json=setup.request).json()
    setup.request.update(profile_id=profile['id'], preview_text='A new sentence')
    assert setup.client.post('/readaloud/training/preview', json=setup.request).status_code == 200
    assert setup.repository.get_voice_profile('local', profile['id'])['status'] == 'ready'
    setup.request['name'] = 'Renamed'
    saved = setup.client.post('/readaloud/training/profiles', json=setup.request).json()
    assert saved['status'] == 'ready'
    assert saved['training']['state'] == 'preview_verified'
    setup.request['samples'][0]['transcript'] = 'changed reference text'
    assert setup.client.post('/readaloud/training/profiles', json=setup.request).json()['status'] == 'unverified'
    # A successful request for old materials cannot validate the newly saved materials.
    setup.request['samples'][0]['transcript'] = 'hello'
    assert setup.client.post('/readaloud/training/preview', json=setup.request).status_code == 200
    assert setup.repository.get_voice_profile('local', profile['id'])['status'] == 'unverified'


def test_failed_preview_does_not_verify_saved_reference(setup):
    profile = setup.client.post('/readaloud/training/profiles', json=setup.request).json()
    setup.request.update(profile_id=profile['id'], preview_text='A new sentence')
    async def fail(*args, **kwargs):
        return Response(status_code=500)
    setup.runtime.model_invocations.invoke_foreground_multipart = fail
    assert setup.client.post('/readaloud/training/preview', json=setup.request).status_code == 502
    assert setup.repository.get_voice_profile('local', profile['id'])['status'] == 'unverified'


def test_single_reference_model_merges_clips_and_matching_text(setup):
    second, _ = setup.gallery.import_stream('local', BytesIO(wav_bytes(0.5)), name='second.wav', media_type='audio/wav')
    setup.request['samples'].append({'asset_id':second['id'], 'transcript':'second sentence', 'confirmed':True})
    setup.request['preview_text']='Preview'
    assert setup.client.post('/readaloud/training/profiles',json=setup.request).status_code == 201
    response=setup.client.post('/readaloud/training/preview',json=setup.request)
    assert response.status_code == 200, response.text
    kwargs=setup.calls[-1][1]
    assert kwargs['data']['ref_text']=='hello\nsecond sentence'
    with wave.open(BytesIO(kwargs['files']['reference_audio'][1])) as audio:
        assert audio.getnframes()==24000
        assert audio.getframerate()==16000
        assert audio.getnchannels()==1
    # Partial optional text cannot describe the combined audio accurately.
    setup.model.audio_capabilities['tts']['voice_profiles']['reference_transcript']='optional'
    setup.request['samples'][1]['transcript']=''
    assert setup.client.post('/readaloud/training/preview',json=setup.request).status_code == 422
    setup.request['samples'][0]['transcript']=''
    assert setup.client.post('/readaloud/training/preview',json=setup.request).status_code == 200
    assert 'ref_text' not in setup.calls[-1][1]['data']
    setup.model.audio_capabilities['tts']['voice_profiles']['reference_requirements']['max_seconds']=1.2
    assert setup.client.post('/readaloud/training/profiles',json=setup.request).status_code == 422


def test_private_upload_does_not_create_gallery_asset(setup):
    with setup.runtime.database.transaction() as connection:
        before=connection.execute('SELECT COUNT(*) FROM gallery_assets').fetchone()[0]
    result=setup.client.post('/readaloud/training/materials',files={'file':('recording.wav',wav_bytes(),'audio/wav')})
    assert result.status_code==201,result.text
    asset=result.json()['asset']
    assert asset['id'].startswith('vref_')
    assert setup.client.get('/readaloud/training/materials/'+asset['id']+'/content').content==wav_bytes()
    with setup.runtime.database.transaction() as connection:
        assert connection.execute('SELECT COUNT(*) FROM gallery_assets').fetchone()[0]==before
    store=VoiceMaterials(setup.runtime.database,setup.runtime.config.paths.artifacts_path)
    foreign=store.save('other',wav_bytes(),'private.wav','audio/wav')
    assert setup.client.get('/readaloud/training/materials/'+foreign['id']+'/content').status_code==404
    setup.request['samples'][0]['asset_id']=asset['id']
    setup.request['preview_text']='Hello'
    assert setup.client.post('/readaloud/training/preview',json=setup.request).status_code==200


def test_migrate_legacy_character_survives_gallery_deletion(setup):
    profile=setup.repository.create_voice_profile('local',name='Legacy',source_type='self_voice',model_id=setup.model.id,
        provider_voice_id=None,reference_transcript='hello',reference_asset_id=setup.asset['id'],rights_scope={},
        training={'samples':setup.request['samples']})
    store=VoiceMaterials(setup.runtime.database,setup.runtime.config.paths.artifacts_path)
    assert store.migrate_profiles()=={'references':1,'missing':0}
    setup.gallery.delete_asset('local',setup.asset['id'])
    assert store.asset_path('local',setup.asset['id'])[1].read_bytes()==wav_bytes()
    assert store.migrate_profiles()=={'references':1,'missing':0}
    setup.request.update(profile_id=profile['id'],preview_text='After deletion')
    assert setup.client.post('/readaloud/training/preview',json=setup.request).status_code==200


def test_explicit_gallery_import_is_independent(setup):
    result=setup.client.post('/readaloud/training/materials/from-gallery/'+setup.asset['id'])
    assert result.status_code==201,result.text
    setup.gallery.delete_asset('local',setup.asset['id'])
    result=setup.client.get('/readaloud/training/materials/'+result.json()['asset']['id']+'/content')
    assert result.status_code==200
    assert result.content==wav_bytes()


def test_synthetic_gallery_reference_can_create_update_and_preview(setup):
    s = setup
    request = {**s.request, 'source_type': 'synthetic_designed', 'rights_scope': {},
               'preview_text': 'A new preview.'}
    response = s.client.post('/readaloud/training/profiles', json=request)
    assert response.status_code == 201, response.text
    request['profile_id'] = response.json()['id']
    # A different owned Gallery asset must work, not only a converted asset ID.
    asset, _ = s.gallery.import_stream('local', BytesIO(wav_bytes(1.5)),
                                     name='designed.wav', media_type='audio/wav')
    request['samples'] = [{'asset_id': asset['id'], 'transcript': 'new sample', 'confirmed': True}]
    response = s.client.post('/readaloud/training/profiles', json=request)
    assert response.status_code == 201, response.text
    assert response.json()['referenceAssetId'] == asset['id']
    # The reference is now owned by the character, independently of Gallery.
    _, path = s.gallery.asset_path('local', asset['id'])
    path.unlink()
    response = s.client.post('/readaloud/training/preview', json=request)
    assert response.status_code == 200, response.text
    assert s.calls[-1][1]['files']['reference_audio'][1] == wav_bytes(1.5)
    request['samples'][0]['asset_id'] = s.other['id']
    assert s.client.post('/readaloud/training/profiles', json=request).status_code == 422
    assert s.client.post('/readaloud/training/preview', json=request).status_code == 422


def test_delete_voice_profile_is_owner_scoped_and_preserves_materials(setup):
    s = setup
    profile = s.client.post('/readaloud/training/profiles', json=s.request).json()
    foreign = s.repository.create_voice_profile('other', name='Other', source_type='synthetic_designed',
        model_id=s.model.id, provider_voice_id=None, reference_transcript='', rights_scope={})
    assert s.client.delete('/readaloud/voice-profiles/' + foreign['id']).status_code == 404
    response = s.client.delete('/readaloud/voice-profiles/' + profile['id'])
    assert response.status_code == 200, response.text
    assert response.json()['deleted'] is True
    assert not s.repository.list_voice_profiles('local')
    assert s.client.delete('/readaloud/voice-profiles/' + profile['id']).status_code == 404
    assert s.gallery.asset_path('local', s.asset['id'])[1].is_file()
    assert VoiceMaterials(s.runtime.database, s.runtime.config.paths.artifacts_path).asset_path('local', s.asset['id'])[1].is_file()


def test_cast_role_and_notes_roundtrip(setup):
    s = setup
    project = s.repository.create_project('local', title='Book', purpose='private', source_rights='user_owned', source_text='')
    base = '/readaloud/projects/' + project['id'] + '/characters'
    response = s.client.post(base, json={'name':'Anna','role':'female_lead','description':'Quiet and observant'})
    assert response.status_code == 201, response.text
    cast = response.json()
    assert cast['role'] == 'female_lead'
    response = s.client.patch(base + '/' + cast['id'], json={'name':'Anna','role':'narrator','description':'Warm narration'})
    assert response.status_code == 200, response.text
    actor = response.json()['characters'][0]
    assert actor['role'] == 'narrator' and actor['description'] == 'Warm narration'
    assert s.repository.get_project('local', project['id'])['characters'][0]['role'] == 'narrator'
    response = s.client.post(base, json={'name':'Default'})
    assert response.json()['role'] == 'auto'
    assert s.client.patch(base + '/' + cast['id'], json={'name':'Anna','role':'invalid'}).status_code == 422

def test_source_analysis_review_and_atomic_insertion(setup):
    import json
    s = setup
    repo = s.repository
    project = repo.create_project('local', title='Story', purpose='private', source_rights='user_owned', source_text='')
    actor = repo.create_character('local', project['id'], name='Narrator', description='Calm storyteller', voice_profile_id=None, role='narrator')
    def line(text):
        return repo.create_segment('local', project['id'], speaker_id=actor['id'], text=text, emotion='neutral', emotion_strength=1, speed=1, pause_after_ms=300)
    first, last = line('Before'), line('After')
    selected = []
    s.runtime.model_manager = SimpleNamespace(resolve_default_model=lambda task: selected.append(task) or 'standard/model')
    standard = SimpleNamespace(id='standard/model', endpoints={'chat_completions':{}})
    s.runtime.model_invocations.model = lambda mid: standard if mid == standard.id else None
    proposals = {'actors':[{'key':'alice','name':'Alice','role':'female_lead','notes':'Curious','voice_profile_id':'made-up-voice'}],
                 'lines':[{'text':'The door opened.','speaker_id':actor['id']}, {'text':'Hello!','speaker_id':'alice','emotion':'happy'}]}
    async def invoke(*args, **kwargs):
        context = json.loads(args[2]['messages'][1]['content'])
        assert context['actors'][0]['role'] == 'narrator'
        assert context['actors'][0]['notes'] == 'Calm storyteller'
        assert [x['text'] for x in context['before']] == ['Before']
        assert [x['text'] for x in context['after']] == ['After']
        return Response(json.dumps({'choices':[{'finish_reason':'stop','message':{'content':json.dumps(proposals)}}]}), media_type='application/json')
    s.runtime.model_invocations.invoke_foreground_json = invoke
    base = '/readaloud/projects/' + project['id'] + '/source/'
    before = repo.get_project('local', project['id'])
    response = s.client.post(base+'analyze', json={'text':'The door opened. Hello!', 'after_id':first['id']})
    assert response.status_code == 200, response.text
    assert selected == ['work_standard']
    assert repo.get_project('local', project['id']) == before
    assert response.json()['actors'][0]['voice_profile_id'] is None
    # Explicit model selection works even when Standard tasks has no default.
    s.runtime.model_manager.resolve_default_model = lambda task: None
    response = s.client.post(base+'analyze', json={'text':'The door opened. Hello!', 'after_id':first['id'], 'model_id':'standard/model'})
    assert response.status_code == 200, response.text
    assert response.json()['model_id'] == 'standard/model'
    proposal = response.json(); proposal.pop('model_id')
    proposal['actors'][0]['name'] = 'Alice reviewed'
    proposal['lines'][1]['text'] = 'Hello, everyone!'
    response = s.client.post(base+'apply', json=proposal)
    assert response.status_code == 200, response.text
    result = repo.get_project('local', project['id'])
    assert [x['text'] for x in result['segments']] == ['Before','The door opened.','Hello, everyone!','After']
    new_actor = next(a for a in result['characters'] if a['name']=='Alice reviewed')
    assert result['segments'][2]['speaker_id'] == new_actor['id']
    assert new_actor['role'] == 'female_lead' and new_actor['description']=='Curious'
    # Retry cannot duplicate actors or lines.
    assert s.client.post(base+'apply', json=proposal).status_code == 200
    assert repo.get_project('local', project['id']) == result
    # Reject stale review and foreign actor bindings without partial inserts.
    proposal['batch_id'] = 'a'*32
    assert s.client.post(base+'apply', json=proposal).status_code == 422
    assert repo.get_project('local', project['id']) == result
    proposal.update(revision=result['revision'], after_id=None, actors=[])
    proposal['lines'] = [{'text':'Tail', 'speaker_id':'foreign'}]
    assert s.client.post(base+'apply', json=proposal).status_code == 422
    assert repo.get_project('local', project['id']) == result
    proposal['lines'][0]['speaker_id'] = ''
    assert s.client.post(base+'apply', json=proposal).status_code == 200
    assert repo.get_project('local', project['id'])['segments'][-1]['text']=='Tail'


def test_source_analysis_context_bounds_and_invalid_output(setup):
    import json
    from ai2apps.readaloud.source_analysis import analysis_messages, parse_completion
    project = {'characters':[], 'segments':[{'id':str(i),'text':'x'*1200,'speaker_id':None,'emotion':'neutral'} for i in range(30)]}
    data = json.loads(analysis_messages(project, 'Source', '14')[1]['content'])
    assert len(data['before'])==len(data['after'])==8
    assert all(len(x['text'])==1000 for x in data['before']+data['after'])
    with pytest.raises(ValueError):
        analysis_messages(project, 'Source', 'missing')
    with pytest.raises(ValueError, match='truncated'):
        parse_completion(json.dumps({'choices':[{'finish_reason':'length','message':{'content':'{}'}}]}))
    s=setup
    project=s.repository.create_project('local',title='Empty',purpose='private',source_rights='user_owned',source_text='')
    base='/readaloud/projects/'+project['id']+'/source/analyze'
    assert s.client.post(base,json={'text':'Hello'}).status_code==409
    assert s.client.post(base,json={'text':'   '}).status_code==422
    foreign=s.repository.create_project('other',title='Private',purpose='private',source_rights='user_owned',source_text='')
    assert s.client.post('/readaloud/projects/'+foreign['id']+'/source/analyze',json={'text':'Hello'}).status_code==404


def test_source_actor_alias_normalization_preserves_bindings():
    import json
    from ai2apps.readaloud.source_analysis import parse_completion
    def parse(data, existing=()):
        return parse_completion(json.dumps({'choices':[{'message':{'content':json.dumps(data)}}]}), existing)
    data = {'actors':[{'key':'narrator','name':'Narrator'}, {'key':'班纳特太太','name':'Mrs Bennet'}, {'key':'new_actor_1','name':'Mr Bennet'}],
            'lines':[{'text':'Narration','speaker_id':'narrator'}, {'text':'Hello','speaker_id':'班纳特太太'}, {'text':'Yes','speaker_id':'new_actor_1'}, {'text':'Existing','speaker_id':'cast_saved'}]}
    result = parse(data, ['cast_saved'])
    assert len({actor.key for actor in result.actors}) == 3
    assert all(actor.key.startswith('new_') for actor in result.actors)
    assert [line.speaker_id for line in result.lines] == [actor.key for actor in result.actors] + ['cast_saved']
    assert result.actors[2].key == 'new_actor_1'
    with pytest.raises(ValueError, match='duplicate'):
        parse({'actors':[{'key':'same','name':'A'}, {'key':'same','name':'B'}], 'lines':[{'text':'Hi','speaker_id':'same'}]})
    with pytest.raises(ValueError, match='existing'):
        parse(data, ['narrator'])


def test_source_dialogue_duplicate_detection_keeps_plot_narration():
    from ai2apps.readaloud.source_analysis import SourceProposal, dialogue_issues, analysis_messages
    project={'characters':[{'id':'n','name':'旁白','role':'narrator','description':''},{'id':'mrs','name':'班纳特太太','role':'female_lead','description':''}], 'segments':[]}
    proposal=SourceProposal.model_validate({'lines':[
        {'speaker_id':'n','text':'“的确租出去了，”她说，“朗格太太刚刚上这儿来过。”'},
        {'speaker_id':'mrs','text':'的确租出去了，朗格太太刚刚上这儿来过。'}]})
    assert len(dialogue_issues(proposal,project))==1
    proposal.lines[0].text='她推开门，发现走廊已经着火。'
    assert not dialogue_issues(proposal,project)
    prompt=analysis_messages(project,'文本',None)[0]['content']
    assert 'Every spoken passage must occur exactly once' in prompt
    assert 'Preserve the plot-bearing action' in prompt



def test_source_analysis_repairs_repeated_narrator_dialogue(setup):
    import json
    s=setup
    project=s.repository.create_project('local',title='Story',purpose='private',source_rights='user_owned',source_text='')
    model=SimpleNamespace(id='analysis',endpoints={'chat_completions':{}})
    s.runtime.model_manager=SimpleNamespace(resolve_default_model=lambda task:model.id)
    s.runtime.model_invocations.model=lambda mid:model
    calls=[]
    actors=[{'key':'new_n','name':'旁白','role':'narrator'},{'key':'new_mrs','name':'太太','role':'female_lead'}]
    dialogue={'speaker_id':'new_mrs','text':'的确租出去了，朗格太太刚刚上这儿来过。'}
    async def invoke(*args,**kwargs):
        calls.append(args[2]['messages'])
        lines=[dialogue] if len(calls)>1 else [{'speaker_id':'new_n','text':'“的确租出去了，”她说，“朗格太太刚刚上这儿来过。”'},dialogue]
        return Response(json.dumps({'choices':[{'message':{'content':json.dumps({'actors':actors,'lines':lines})}}]}))
    s.runtime.model_invocations.invoke_foreground_json=invoke
    response=s.client.post('/readaloud/projects/'+project['id']+'/source/analyze',json={'text':'“的确租出去了，”她说，“朗格太太刚刚上这儿来过。”'})
    assert response.status_code==200,response.text
    assert len(calls)==2 and 'Correct the complete proposal' in calls[1][-1]['content']
    assert len(response.json()['lines'])==1
    assert not s.repository.get_project('local',project['id'])['segments']


def test_clone_preview_expression_respects_model_capabilities(setup):
    s=setup
    s.model.audio_capabilities['tts'].update(speed={'mode':'native','minimum':0.8,'maximum':1.5}, emotion={'mode':'native','values':['neutral','happy']})
    request={**s.request,'emotion':'happy','speed':1.2}
    response=s.client.post('/readaloud/training/preview',json=request)
    assert response.status_code==200,response.text
    payload=s.calls[-1][1]['data']
    assert payload['speed']==1.2 and payload['emotion']=='happy'
    assert payload['emotion_strength']==1.0 and 'style' not in payload
    assert all(not isinstance(value, (dict, list)) for value in payload.values())
    s.model.audio_capabilities['tts']['speed']={'mode':'unsupported'}
    request['emotion']='whisper'
    assert s.client.post('/readaloud/training/preview',json=request).status_code==200
    assert 'speed' not in s.calls[-1][1]['data'] and 'style' not in s.calls[-1][1]['data']
    request['speed']=3
    assert s.client.post('/readaloud/training/preview',json=request).status_code==422


def test_design_preview_expression_and_snapshot(design_setup):
    s=design_setup
    s.design.audio_capabilities={'tts':{'speed':{'mode':'fallback'},'emotion':{'mode':'native','values':['neutral','happy']}}}
    request={**s.design_request,'emotion':'happy','speed':0.8}
    response=s.client.post('/readaloud/design/preview',json=request)
    assert response.status_code==200,response.text
    payload=s.calls[-1][0][2]
    assert payload['speed']==0.8 and payload['style']['emotion']=='happy'
    preview=response.json()['training']['design']['preview']
    assert preview['speed']==0.8 and preview['emotion']=='happy'


def test_clone_preview_preserves_worker_error(setup):
    s=setup
    async def invoke(*args, **kwargs):
        return Response('{"error":{"message":"Reference could not be decoded"}}', status_code=400, media_type='application/json')
    s.runtime.model_invocations.invoke_foreground_multipart=invoke
    response=s.client.post('/readaloud/training/preview',json=s.request)
    assert response.status_code==502
    assert 'HTTP 400' in response.text and 'Reference could not be decoded' in response.text
