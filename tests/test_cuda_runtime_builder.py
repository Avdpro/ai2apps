import importlib.util
import json
from pathlib import Path
import pytest


def builder():
    path = Path(__file__).resolve().parents[1] / "scripts/build_cuda_torch_runtime_package.py"
    spec = importlib.util.spec_from_file_location("cuda_runtime_builder", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('mutation', ['stale-capability', 'package-version', 'descriptor-version', 'identity', 'duplicate', 'valid'])
def test_runtime_source_metadata_rejects_stale_release_declarations(tmp_path, mutation):
    service = {'id': 'ai2apps.runtime.cuda-torch', 'version': '0.6.0',
               'capabilities': ['cuda', 'model-worker-v1', 'liveportrait']}
    package = {'id': 'ai2apps/runtime-cuda-torch', 'version': '0.6.0'}
    descriptor = {'service_id': service['id'], 'version': '0.6.0',
                  'capabilities': list(reversed(service['capabilities']))}
    if mutation == 'stale-capability':
        descriptor['capabilities'] += ['musetalk', 'infinitetalk', 'exomni']
    elif mutation == 'package-version':
        package['version'] = '0.6.0-dev.1'
    elif mutation == 'descriptor-version':
        descriptor['version'] = '0.5.0'
    elif mutation == 'identity':
        descriptor['service_id'] = 'ai2apps.runtime.omlx'
    elif mutation == 'duplicate':
        descriptor['capabilities'].append('cuda')
    (tmp_path / 'META').mkdir()
    (tmp_path / 'ai2apps.json').write_text(json.dumps({'package': package}))
    (tmp_path / 'META/runtime-manifest.json').write_text(json.dumps(descriptor))
    if mutation == 'valid':
        builder()._validate_source_metadata(tmp_path, service)
    else:
        with pytest.raises(RuntimeError):
            builder()._validate_source_metadata(tmp_path, service)


def test_framework_records_cannot_escape_site_packages(tmp_path, monkeypatch):
    module = builder()
    site = tmp_path / "site"
    site.mkdir()
    (site / "valid.py").write_text("value = 1")
    (tmp_path / "outside").write_text("do not export")

    class Distribution:
        metadata = {"Name": "fixture"}
        version = "1.0"
        files = [Path("valid.py"), Path("../outside")]

        def locate_file(self, entry):
            return site / entry

    monkeypatch.setattr(module, "_site_roots", lambda: (site,))
    monkeypatch.setattr(module, "_distribution_closure", lambda: (Distribution(),))
    output = tmp_path / "runtime/site-packages"
    module._copy_framework(output)
    assert (output / "valid.py").is_file()
    assert not (output.parent / "outside").exists()


def test_sbom_records_exported_versions(tmp_path):
    module = builder()
    meta = tmp_path / "META"
    meta.mkdir()
    (meta / "sbom.spdx.json").write_text('{"SPDXID":"SPDXRef-DOCUMENT"}')
    module._write_sbom(tmp_path, [{"name": "Torch", "version": "2.10.0+cu130"}])
    result = json.loads((meta / "sbom.spdx.json").read_text())
    assert result["packages"][0]["versionInfo"] == "2.10.0+cu130"
    assert result["relationships"][0]["relatedSpdxElement"] == result["packages"][0]["SPDXID"]


def test_framework_overlay_roots_are_explicit_sites(tmp_path, monkeypatch):
    module = builder()
    site = tmp_path / "framework" / "site-packages"
    site.mkdir(parents=True)
    arbitrary = tmp_path / "unrelated"
    arbitrary.mkdir()
    monkeypatch.setattr(module.site, "getsitepackages", lambda: [])
    monkeypatch.setattr(module.site, "getusersitepackages", lambda: "")
    monkeypatch.setattr(module.sys, "path", [str(site), str(arbitrary)])
    assert site in module._site_roots()
    assert arbitrary not in module._site_roots()


def test_qwen_dependencies_are_bundled_without_experimental_fla():
    module = builder()
    assert {"compressed-tensors", "accelerate", "torchvision", "jsonschema"} <= set(module.ROOT_DISTRIBUTIONS)
    assert not module._excluded_distribution("triton")
    assert "flash-linear-attention" not in module.ROOT_DISTRIBUTIONS


def test_nvfp4_aot_rejects_wrong_architecture_and_missing_modules(tmp_path, monkeypatch):
    import pytest
    module = builder()
    monkeypatch.setattr(module.importlib.metadata, "version", lambda name: "0.7.0.post1")
    cache = tmp_path / "0.7.0.post1/121a/cached_ops"
    name = "fp4_gemm_cutlass_sm120"
    source = cache / name / f"{name}.so"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"invalid")
    with pytest.raises(RuntimeError, match="ELF64 AArch64"):
        module._copy_nvfp4_aot(tmp_path / "output", cache)
    source.write_bytes(b"\x7fELF\x02" + b"\0" * 13 + b"\xb7\x00")
    with pytest.raises(RuntimeError, match="Missing regular AOT"):
        module._copy_nvfp4_aot(tmp_path / "output", cache)
    with pytest.raises(RuntimeError, match="SM121a"):
        module._copy_nvfp4_aot(tmp_path / "output", cache.parent / "wrong")


def test_nvfp4_python_dependencies_are_not_mistaken_for_host_cuda_libraries():
    module = builder()
    assert "flashinfer-python" in module.ROOT_DISTRIBUTIONS
    for name in ("cuda-bindings", "cuda-pathfinder", "nvidia-cutlass-dsl",
                 "nvidia-cudnn-frontend", "nvidia-ml-py"):
        assert not module._excluded_distribution(name)


def test_distribution_index_matches_import_precedence(monkeypatch):
    module = builder()
    class Distribution:
        metadata = {"Name": "Click"}
    wheel, system = Distribution(), Distribution()
    monkeypatch.setattr(module.importlib.metadata, "distributions", lambda: [wheel, system])
    assert module._distribution_index()["click"] is wheel


def test_conflicting_dependency_fails_export(monkeypatch):
    import pytest
    module = builder()
    class Distribution:
        metadata = {'Name': 'fixture'}
        version = '1.0'
        requires = ['dependency<2']
    class Dependency:
        version = '3.0'
    monkeypatch.setattr(module, 'ROOT_DISTRIBUTIONS', ('fixture',))
    monkeypatch.setattr(module, '_distribution_index', lambda: {
        'fixture': Distribution(), 'dependency': Dependency()})
    with pytest.raises(RuntimeError, match='Unsatisfied Runtime dependency'):
        module._distribution_closure()


def test_profile_sbom_does_not_alias_versions(tmp_path):
    module = builder()
    (tmp_path / 'META').mkdir()
    (tmp_path / 'META/sbom.spdx.json').write_text('{}')
    module._write_sbom(tmp_path, [
        {'name': 'transformers', 'version': '5.18.0'},
        {'name': 'transformers', 'version': '4.57.3', 'profile': 'audio'}])
    result = json.loads((tmp_path / 'META/sbom.spdx.json').read_text())
    assert len({p['SPDXID'] for p in result['packages']}) == 2


def test_h3_source_digest_gate_precedes_extraction(tmp_path, monkeypatch):
    import pytest
    module=builder()
    sources=tmp_path/'sources'; sources.mkdir()
    (sources/'h3-comfy-existing.patch').write_bytes(b'patch')
    (sources/'comfy.tar').write_bytes(b'changed archive')
    monkeypatch.setattr(module,'H3_PATCH_SHA256',module._file_sha256(sources/'h3-comfy-existing.patch'))
    monkeypatch.setattr(module,'H3_SOURCES',{'ComfyUI':('comfy.tar','0'*64,'fixed-commit')})
    runtime=tmp_path/'runtime';runtime.mkdir()
    with pytest.raises(RuntimeError,match='source archive digest mismatch'):
        module._copy_h3_sources(runtime,sources)
    assert not (runtime/'h3').exists()


def test_h3_source_retains_nested_model_code_and_license(tmp_path, monkeypatch):
    import tarfile
    module=builder()
    source=tmp_path/'source'
    (source/'comfy/ldm/models').mkdir(parents=True)
    (source/'comfy/ldm/models/autoencoder.py').write_text('model code')
    (source/'LICENSE').write_text('source license')
    (source/'models').mkdir();(source/'models/checkpoint').write_text('not runtime code')
    archive=tmp_path/'comfy.tar'
    with tarfile.open(archive,'w') as tar:
        for path in source.iterdir():tar.add(path,arcname=path.name)
    patch=tmp_path/'h3-comfy-existing.patch';patch.write_bytes(b'patch')
    monkeypatch.setattr(module,'H3_PATCH_SHA256',module._file_sha256(patch))
    monkeypatch.setattr(module,'H3_SOURCES',{'ComfyUI':('comfy.tar',module._file_sha256(archive),'fixed-commit')})
    monkeypatch.setattr(module.subprocess,'run',lambda *args,**kwargs:None)
    runtime=tmp_path/'runtime';(runtime/'META').mkdir(parents=True)
    result=module._copy_h3_sources(runtime,tmp_path)
    assert (runtime/'h3/ComfyUI/comfy/ldm/models/autoencoder.py').read_text()=='model code'
    assert not (runtime/'h3/ComfyUI/models').exists()
    assert (runtime/'h3/ComfyUI/LICENSE').is_file()
    assert result[0]['version']=='fixed-commit'


def test_profile_interpreter_cannot_inherit_parent_framework(monkeypatch):
    module=builder()
    monkeypatch.setenv('PYTHONPATH','/wrong/core-transformers')
    monkeypatch.setenv('PYTHONHOME','/wrong/python')
    monkeypatch.setenv('PATH','/usr/bin:/bin')
    environment=module._profile_build_env()
    assert 'PYTHONPATH' not in environment
    assert 'PYTHONHOME' not in environment
    assert environment['PATH']=='/usr/bin:/bin'


def test_h3_corresponding_sources_require_exact_version_and_bytes(tmp_path, monkeypatch):
    import pytest
    module = builder()
    source = tmp_path / 'sources/compiler'; source.mkdir(parents=True)
    archive = source / 'compiler.tar'; archive.write_bytes(b'fixed source')
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps([{'package':'compiler', 'version':'1', 'files':[
        {'file':archive.name, 'size':archive.stat().st_size, 'sha256':module._file_sha256(archive)}]}]))
    monkeypatch.setattr(module, 'H3_TOOLCHAIN_SOURCES_MANIFEST', manifest)
    runtime = tmp_path / 'runtime'
    inventory = [{'name':'cc', 'source_package':'compiler', 'source_version':'2'}]
    with pytest.raises(RuntimeError, match='source version mismatch'):
        module._copy_h3_corresponding_sources(runtime, source.parent, inventory)
    inventory[0]['source_version'] = '1'
    archive.write_bytes(b'wrong source')
    with pytest.raises(RuntimeError, match='source digest mismatch'):
        module._copy_h3_corresponding_sources(runtime, source.parent, inventory)
    assert not runtime.exists()
    archive.write_bytes(b'fixed source')
    module._copy_h3_corresponding_sources(runtime, source.parent, inventory)
    assert (runtime / 'h3/toolchain/sources/compiler/compiler.tar').read_bytes() == b'fixed source'
    assert (runtime / 'h3/toolchain/sources/build_cuda_torch_runtime_package.py').is_file()


def test_processing_profile_keeps_existing_service_isolation(tmp_path, monkeypatch):
    module=builder()
    (tmp_path/'META').mkdir()
    path=tmp_path/'META/framework-profiles.json'
    existing={'format':'ai2apps.framework-profiles/v1',
        'profiles':{'audio':{'site_packages':'profiles/audio/site-packages'},'h3':{'site_packages':'profiles/h3/site-packages'}},
        'services':{'ai2apps.model.qwen3-tts-1.7b-cuda':'audio','ai2apps.model.minimax-h3-cuda':'h3'}}
    path.write_text(json.dumps(existing))
    monkeypatch.setenv('PYTHONPATH','/wrong/core')
    def run(argv, **kwargs):
        assert 'PYTHONPATH' not in kwargs['env']
        (tmp_path/'META/audio-processing-distributions.json').write_text('[{"name":"demucs","version":"4.0.1"}]')
    monkeypatch.setattr(module.subprocess,'run',run)
    inventory=module._copy_audio_processing_profile(tmp_path,Path('/selected/interpreter'))
    result=json.loads(path.read_text())
    for key,value in existing['services'].items():assert result['services'][key]==value
    for key,value in existing['profiles'].items():assert result['profiles'][key]==value
    assert result['services']['ai2apps.model.demucs-cuda']=='audio-processing'
    assert inventory==[{'name':'demucs','version':'4.0.1','profile':'audio-processing'}]


@pytest.mark.parametrize('profile,distribution,version', [
    ('sensevoice','numpy','1.26.4'), ('punctuation','sherpa-onnx','1.13.8'),
    ('flashhead','diffusers','0.35.1'),
    ('ace','transformers','4.57.6'),
    ('fish-s2','protobuf','3.19.6'),
])
def test_speech_profile_preserves_other_services_and_selected_versions(tmp_path, monkeypatch, profile, distribution, version):
    module=builder()
    (tmp_path/'META').mkdir()
    path=tmp_path/'META/framework-profiles.json'
    existing={'format':'ai2apps.framework-profiles/v1',
        'profiles':{'h3':{'site_packages':'profiles/h3/site-packages'}},
        'services':{'ai2apps.model.minimax-h3-cuda':'h3'}}
    path.write_text(json.dumps(existing))
    monkeypatch.setenv('PYTHONPATH','/wrong/core-numpy2')
    monkeypatch.setenv('PYTHONHOME','/wrong/python')
    def run(argv, **kwargs):
        assert argv[0]=='/selected/interpreter'
        assert 'PYTHONPATH' not in kwargs['env'] and 'PYTHONHOME' not in kwargs['env']
        (tmp_path/'META'/f'{profile}-distributions.json').write_text(json.dumps([
            {'name':distribution,'version':version}]))
    monkeypatch.setattr(module.subprocess,'run',run)
    inventory=module._copy_isolated_profile(tmp_path,Path('/selected/interpreter'),profile)
    result=json.loads(path.read_text())
    assert result['services']['ai2apps.model.minimax-h3-cuda']=='h3'
    assert result['profiles']['h3']==existing['profiles']['h3']
    assert result['services'][module.ISOLATED_PROFILES[profile][1]]==profile
    assert inventory==[{'name':distribution,'version':version,'profile':profile}]


@pytest.mark.parametrize('tamper', ['archive', 'patch'])
def test_flashhead_rejects_changed_source_before_extracting(tmp_path, monkeypatch, tamper):
    module=builder()
    source=tmp_path/'source';source.mkdir()
    (source/'source.tar.gz').write_bytes(b'changed archive')
    (source/'single-gpu.patch').write_bytes(b'changed patch')
    if tamper=='patch':
        monkeypatch.setattr(module,'FLASHHEAD_ARCHIVE_SHA256',module._file_sha256(source/'source.tar.gz'))
    target=tmp_path/'runtime'
    with pytest.raises(RuntimeError,match='digest mismatch'):
        module._copy_flashhead_sources(target,source)
    assert not target.exists()


@pytest.mark.parametrize('tamper', [None, 'changed', 'extra'])
def test_sol_export_checks_exact_diffusers_source(tmp_path, monkeypatch, tamper):
    import hashlib
    import tarfile
    module = builder()
    staging = tmp_path / 'staging'
    entries = {
        'sana/README.md': 'Code released under Apache-2.0',
        'sana/models/sol-refiner/LTX-2.3/sol_refiner/__init__.py': 'value = 1\n',
        'diffusers/LICENSE': 'Apache-2.0 fixture',
        'diffusers/src/diffusers/__init__.py': 'value = 2\n',
        'diffusers/src/diffusers/models/README.md': 'Upstream directory documentation',
    }
    for name, value in entries.items():
        path = staging / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)
    sources = tmp_path / 'sources'
    sources.mkdir()
    for name, constant in [('sana','SOL_SANA_SHA256'), ('diffusers','SOL_DIFFUSERS_SHA256')]:
        archive = sources / (name+'.tar.gz')
        with tarfile.open(archive, 'w:gz') as out:
            out.add(staging/name, arcname=name)
        monkeypatch.setattr(module, constant, hashlib.sha256(archive.read_bytes()).hexdigest())
    runtime = tmp_path/'runtime'
    (runtime/'META').mkdir(parents=True)
    installed = runtime/'profiles/sol/site-packages/diffusers'
    installed.mkdir(parents=True)
    (installed/'__init__.py').write_text('value = 3\n' if tamper=='changed' else 'value = 2\n')
    if tamper=='extra': (installed/'unexpected.py').write_text('extra = True\n')
    if tamper:
        with pytest.raises(RuntimeError, match='differs from the pinned'):
            module._copy_sol_sources(runtime, sources)
    else:
        records = module._copy_sol_sources(runtime, sources)
        assert 'sol_refiner/__init__.py' in records[0]['files']
        assert (installed/'models/README.md').read_text() == 'Upstream directory documentation'
        assert (runtime/'sources/sol/SANA_README.md').is_file()
        assert (runtime/'sources/sol/DIFFUSERS_LICENSE').is_file()
        assert (runtime/'profiles/sol/site-packages/sol_mac_video_engine.py').is_file()


@pytest.mark.parametrize('changed', [False, True])
def test_ace_source_export_requires_exact_model_patch(tmp_path,monkeypatch,changed):
    import tarfile
    module=builder()
    root=tmp_path/'stage/ace-step'
    model=root/'acestep/models/turbo/modeling_acestep_v15_turbo.py'
    model.parent.mkdir(parents=True)
    original=module.REPO/'experiments/music_mlx/vendor/ACE-Step-1.5/acestep/models/turbo/modeling_acestep_v15_turbo.py'
    model.write_bytes(original.read_bytes()+(b'\n' if changed else b''))
    (root/'LICENSE').write_text('MIT fixture')
    (root/'README.md').write_text('ACE-Step fixture')
    sources=tmp_path/'sources';sources.mkdir()
    archive=sources/'source.tar.gz'
    with tarfile.open(archive,'w:gz') as out:out.add(root,arcname='ace-step')
    monkeypatch.setattr(module,'ACE_ARCHIVE_SHA256',module._file_sha256(archive))
    runtime=tmp_path/'runtime';(runtime/'META').mkdir(parents=True)
    if changed:
        with pytest.raises(ValueError,match='pinned official source'):
            module._copy_ace_sources(runtime,sources)
    else:
        record=module._copy_ace_sources(runtime,sources)[0]
        assert record['patched_model_sha256']==module.ACE_PATCHED_MODEL_SHA256
        assert 'cuda_ace_engine.py' in record['files']
        assert (runtime/'sources/ace/source.tar.gz').read_bytes()==archive.read_bytes()
        assert (runtime/'sources/ace/LICENSE').is_file()


@pytest.mark.parametrize('tampered', [False, True])
def test_stable_source_export_pins_archive_and_retains_licenses(tmp_path, monkeypatch, tampered):
    import tarfile
    module = builder()
    root = tmp_path/'stage/stable-audio-3'
    for name in ('stable_audio_3/__init__.py', 'optimized/tflite/build/torch_defs/same_s_decoder_torch.py', 'LICENSE', 'README.md'):
        path = root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('fixed source fixture\n')
    sources=tmp_path/'sources';sources.mkdir()
    archive=sources/'source.tar.gz'
    with tarfile.open(archive,'w:gz') as out:out.add(root,arcname='stable-audio-3')
    monkeypatch.setattr(module,'STABLE_ARCHIVE_SHA256',module._file_sha256(archive))
    if tampered:archive.write_bytes(archive.read_bytes()+b'changed')
    runtime=tmp_path/'runtime';(runtime/'META').mkdir(parents=True)
    if tampered:
        with pytest.raises(RuntimeError,match='digest mismatch'):
            module._copy_stable_sources(runtime,sources)
    else:
        record=module._copy_stable_sources(runtime,sources)[0]
        assert 'cuda_stable_engine.py' in record['files']
        assert 'optimized/tflite/build/torch_defs/same_s_decoder_torch.py' in record['files']
        assert (runtime/'sources/stable/LICENSE').read_text()=='fixed source fixture\n'
        assert (runtime/'sources/stable/source.tar.gz').read_bytes()==archive.read_bytes()
        assert module.ISOLATED_PROFILES['stable'][1]=='ai2apps.model.stable-audio-cuda'


@pytest.mark.parametrize('value',['torch==2.10.0+cu130','PyYAML==6.0.3'])
def test_exact_dependency_lock_accepts_selected_distribution(tmp_path,monkeypatch,value):
    from types import SimpleNamespace
    module=builder();name,version=value.split('==')
    lock=tmp_path/'requirements.lock';lock.write_text('# fixed\n'+value+'\n')
    monkeypatch.setattr(module,'_distribution_index',lambda:{module.canonicalize_name(name):SimpleNamespace(version=version)})
    module._verify_dependency_lock(lock)


@pytest.mark.parametrize('value',['torch==2.10.0+cu130','torch>=2.10','torch==2.10.*','missing==1.0'])
def test_dependency_lock_rejects_drift_and_nonexact_pins(tmp_path,monkeypatch,value):
    from types import SimpleNamespace
    module=builder();lock=tmp_path/'requirements.lock';lock.write_text(value+'\n')
    monkeypatch.setattr(module,'_distribution_index',lambda:{'torch':SimpleNamespace(version='2.13.0')})
    with pytest.raises(RuntimeError):module._verify_dependency_lock(lock)


def test_echomimic_export_rejects_wrong_source_before_extraction(tmp_path):
    module=builder();source=tmp_path/'source';source.mkdir()
    (source/'source.tar.gz').write_bytes(b'wrong source')
    runtime=tmp_path/'runtime';runtime.mkdir()
    with pytest.raises(RuntimeError,match='digest mismatch'):module._copy_echomimic_sources(runtime,source)
    assert list(runtime.iterdir())==[]


def test_avtr_export_covers_weights_and_preserves_licenses(tmp_path):
    module=builder();runtime=tmp_path/'runtime';(runtime/'META').mkdir(parents=True)
    record=module._copy_avtr_sources(runtime)[0]
    site=runtime/'profiles/avtr/site-packages'
    assert 'cuda_avtr_weights.lock.json' in record['files']
    assert 'cuda_avtr_support/source-provenance.json' in record['files']
    assert (runtime/'sources/avtr1/LICENSE-MODEL.md').read_bytes()==(module.REPO/'spark/cuda_avtr_support/LICENSE-MODEL.md').read_bytes()
    for name,digest in record['files'].items():assert module._file_sha256(site/name)==digest


def test_avtr_export_rejects_changed_unchanged_helper(tmp_path,monkeypatch):
    import shutil
    module=builder();root=tmp_path/'repo';helpers=root/'spark/cuda_avtr_support'
    shutil.copytree(module.REPO/'spark/cuda_avtr_support',helpers)
    (helpers/'image.py').write_text('tampered geometry')
    monkeypatch.setattr(module,'REPO',root)
    with pytest.raises(RuntimeError,match='unchanged helper digest mismatch'):
        module._copy_avtr_sources(tmp_path/'runtime')


def test_avtr_export_requires_retained_model_license(tmp_path,monkeypatch):
    import shutil
    module=builder();root=tmp_path/'repo';helpers=root/'spark/cuda_avtr_support'
    shutil.copytree(module.REPO/'spark/cuda_avtr_support',helpers)
    (helpers/'LICENSE-MODEL.md').unlink()
    monkeypatch.setattr(module,'REPO',root)
    with pytest.raises(RuntimeError,match='license missing'):
        module._copy_avtr_sources(tmp_path/'runtime')


def test_voxcpm_export_rejects_wrong_archive_before_extraction(tmp_path):
    module=builder();source=tmp_path/'source';source.mkdir()
    (source/'source.tar.gz').write_bytes(b'wrong source')
    runtime=tmp_path/'runtime';runtime.mkdir()
    with pytest.raises(RuntimeError,match='digest mismatch'):
        module._copy_voxcpm2_sources(runtime,source)
    assert list(runtime.iterdir())==[]


def test_indextts_export_rejects_changed_archive_before_extraction(tmp_path):
    module=builder();source=tmp_path/'source';source.mkdir()
    (source/'windextts-source.tar.gz').write_bytes(b'changed source')
    runtime=tmp_path/'runtime';runtime.mkdir()
    with pytest.raises(RuntimeError,match='digest mismatch'):
        module._copy_indextts25_sources(runtime,source)
    assert list(runtime.iterdir())==[]


@pytest.mark.parametrize('tampered_data',[False,True])
def test_indextts_export_retains_notices_and_verifies_frontend(tmp_path,monkeypatch,tampered_data):
    import tarfile,shutil
    module=builder();source=tmp_path/'source';source.mkdir()
    root=tmp_path/('WIndexTTS-'+module.INDEXTTS25_COMMIT)
    for name in ('models','frontend','data'):(root/'windextts'/name).mkdir(parents=True)
    (root/'windextts/__init__.py').write_text('# source fixture\n')
    for name in ('LICENSE','README.md','pyproject.toml'):(root/name).write_text('retained '+name)
    for name in ('seamless_frontend.npz','mel_basis_hifigan.npz'):
        shutil.copy2(module.REPO/'omlx/vendor/indextts25/data'/name,root/'windextts/data'/name)
    if tampered_data:(root/'windextts/data/seamless_frontend.npz').write_bytes(b'changed coefficients')
    archive=source/'windextts-source.tar.gz'
    with tarfile.open(archive,'w:gz') as handle:handle.add(root,arcname=root.name)
    monkeypatch.setattr(module,'INDEXTTS25_ARCHIVE_SHA256',module._file_sha256(archive))
    runtime=tmp_path/'runtime';(runtime/'META').mkdir(parents=True)
    if tampered_data:
        with pytest.raises(RuntimeError,match='frontend data digest mismatch'):
            module._copy_indextts25_sources(runtime,source)
        return
    record=module._copy_indextts25_sources(runtime,source)[0]
    assert (runtime/'sources/indextts25/LICENSE').read_bytes()==(root/'LICENSE').read_bytes()
    assert 'AI2Apps-NOTICE.txt' in record['retained_files']
    assert 'windextts-source.tar.gz' in record['retained_files']
    assert 'cuda_indextts_weights.lock.json' in record['files']
    for name,digest in record['files'].items():
        assert module._file_sha256(runtime/'profiles/indextts25/site-packages'/name)==digest


def test_voxcpm_export_retains_source_license_and_weight_lock(tmp_path,monkeypatch):
    import tarfile
    module=builder();source=tmp_path/'source';source.mkdir()
    root=tmp_path/('VoxCPM-'+module.VOXCPM2_COMMIT)
    (root/'src/voxcpm').mkdir(parents=True)
    (root/'src/voxcpm/__init__.py').write_text('# fixed test source\n')
    for name in ('LICENSE','README.md','pyproject.toml'):(root/name).write_text('retained '+name)
    archive=source/'source.tar.gz'
    with tarfile.open(archive,'w:gz') as handle:handle.add(root,arcname=root.name)
    monkeypatch.setattr(module,'VOXCPM2_ARCHIVE_SHA256',module._file_sha256(archive))
    runtime=tmp_path/'runtime';(runtime/'META').mkdir(parents=True)
    record=module._copy_voxcpm2_sources(runtime,source)[0]
    assert (runtime/'sources/voxcpm2/LICENSE').read_bytes()==(root/'LICENSE').read_bytes()
    assert 'cuda_voxcpm_weights.lock.json' in record['files']
    for name,digest in record['files'].items():
        assert module._file_sha256(runtime/'profiles/voxcpm2/site-packages'/name)==digest


def test_cosyvoice_source_notice_tamper_rejected_before_export(tmp_path, monkeypatch):
    import hashlib
    module=builder();repo=tmp_path/'repo';(repo/'spark').mkdir(parents=True)
    source=tmp_path/'source';source.mkdir();(source/'NOTICE').write_text('changed')
    (repo/'spark/cosyvoice3-sources.lock.json').write_text(json.dumps({
        'files':{'NOTICE':hashlib.sha256(b'approved').hexdigest()}}))
    monkeypatch.setattr(module,'REPO',repo)
    target=tmp_path/'runtime'
    with pytest.raises(RuntimeError,match='source/notice digest mismatch'):
        module._copy_cosyvoice3_sources(target,source)
    assert not target.exists()


def test_cosyvoice_source_path_escape_rejected(tmp_path, monkeypatch):
    import hashlib
    module=builder();repo=tmp_path/'repo';(repo/'spark').mkdir(parents=True)
    source=tmp_path/'source';source.mkdir();(tmp_path/'outside').write_text('secret')
    (repo/'spark/cosyvoice3-sources.lock.json').write_text(json.dumps({
        'files':{'../outside':hashlib.sha256(b'secret').hexdigest()}}))
    monkeypatch.setattr(module,'REPO',repo)
    with pytest.raises(RuntimeError,match='source/notice digest mismatch'):
        module._copy_cosyvoice3_sources(tmp_path/'runtime',source)
def test_rvc_export_rejects_changed_archive(tmp_path):
    module=builder();source=tmp_path/'source';source.mkdir()
    (source/'source.tar.gz').write_bytes(b'changed archive')
    runtime=tmp_path/'runtime';runtime.mkdir()
    with pytest.raises(RuntimeError,match='RVC source archive digest mismatch'):
        module._copy_rvc_sources(runtime,source)
    assert list(runtime.iterdir())==[]


def test_rvc_source_export_retains_license_and_fixed_modules(tmp_path,monkeypatch):
    import tarfile
    module=builder();source=tmp_path/'source';source.mkdir()
    upstream=tmp_path/('Retrieval-based-Voice-Conversion-WebUI-'+module.RVC_COMMIT)
    upstream.mkdir()
    for name in ('LICENSE','README.md',*module.RVC_UPSTREAM_FILES):
        path=upstream/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('fixture '+name)
    (upstream/'unrelated-server.py').write_text('not runtime')
    archive=source/'source.tar.gz'
    with tarfile.open(archive,'w:gz') as handle:handle.add(upstream,arcname=upstream.name)
    monkeypatch.setattr(module,'RVC_ARCHIVE_SHA256',module._file_sha256(archive))
    runtime=tmp_path/'runtime';(runtime/'META').mkdir(parents=True)
    record=module._copy_rvc_sources(runtime,source)[0]
    assert (runtime/'sources/rvc/LICENSE').read_bytes()==(upstream/'LICENSE').read_bytes()
    assert {'LICENSE','README.md','source.tar.gz','AI2Apps-NOTICE.txt'}==set(record['retained_files'])
    assert 'unrelated-server.py' not in record['files']
    assert set(module.RVC_UPSTREAM_FILES)<=set(record['files'])
    assert set(module.RVC_WRAPPERS)<=set(record['files'])
    for name,digest in record['files'].items():
        assert module._file_sha256(runtime/'profiles/rvc/site-packages'/name)==digest

@pytest.mark.parametrize('failure', ['missing', 'changed', 'escape'])
def test_seed_vc_license_failure_prevents_source_export(tmp_path, monkeypatch, failure):
    import hashlib
    module = builder()
    repo = tmp_path / 'repo'
    (repo / 'spark').mkdir(parents=True)
    sources = tmp_path / 'inputs'
    (sources / 'bigvgan-licenses').mkdir(parents=True)
    archive = sources / 'source.tar.gz'
    archive.write_bytes(b'fixture archive never extracted')
    monkeypatch.setattr(module, 'SEED_VC_ARCHIVE_SHA256', hashlib.sha256(archive.read_bytes()).hexdigest())
    monkeypatch.setattr(module, 'REPO', repo)
    name = '../outside' if failure == 'escape' else 'LICENSE'
    if failure == 'escape':
        (sources / 'outside').write_bytes(b'expected')
    elif failure == 'changed':
        (sources / 'bigvgan-licenses/LICENSE').write_bytes(b'modified')
    (repo / 'spark/seed-vc-bigvgan-licenses.lock.json').write_text(json.dumps({
        'files': {name: hashlib.sha256(b'expected').hexdigest()}}))
    output = tmp_path / 'runtime'
    with pytest.raises((FileNotFoundError, RuntimeError)):
        module._copy_seed_vc_sources(output, sources)
    assert not output.exists()


def test_vibevoice_export_rejects_wrong_archive_before_writes(tmp_path):
    module = builder()
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'source.tar.gz').write_bytes(b'not the pinned upstream archive')
    runtime = tmp_path / 'runtime'
    with pytest.raises(RuntimeError, match='VibeVoice source archive digest mismatch'):
        module._copy_vibevoice_sources(runtime, source)
    assert not runtime.exists()


def test_vibevoice_export_retains_license_and_excludes_dev_converter(tmp_path, monkeypatch):
    import tarfile
    module = builder()
    repo = tmp_path / 'repo'
    (repo / 'spark').mkdir(parents=True)
    for name in module.VIBEVOICE_WRAPPERS:
        (repo / 'spark' / name).write_text('# runtime wrapper\n')
    (repo / 'spark/vibevoice-cuda-requirements.lock').write_text('transformers==4.51.3\n')
    (repo / 'spark/convert_vibevoice_official_voices.py').write_text('raise RuntimeError("development only")\n')
    root = tmp_path / ('VibeVoice-' + module.VIBEVOICE_COMMIT)
    (root / 'vibevoice').mkdir(parents=True)
    (root / 'vibevoice/__init__.py').write_text('# official fixture\n')
    for name in ('LICENSE', 'README.md', 'pyproject.toml'):
        (root / name).write_text('retained ' + name)
    source = tmp_path / 'source'
    source.mkdir()
    with tarfile.open(source / 'source.tar.gz', 'w:gz') as archive:
        archive.add(root, arcname=root.name)
    monkeypatch.setattr(module, 'REPO', repo)
    monkeypatch.setattr(module, 'VIBEVOICE_ARCHIVE_SHA256', module._file_sha256(source / 'source.tar.gz'))
    runtime = tmp_path / 'runtime'
    (runtime / 'META').mkdir(parents=True)
    record = module._copy_vibevoice_sources(runtime, source)[0]
    assert (runtime / 'sources/vibevoice/LICENSE').read_bytes() == (root / 'LICENSE').read_bytes()
    site = runtime / 'profiles/vibevoice/site-packages'
    assert not (site / 'convert_vibevoice_official_voices.py').exists()
    for name, digest in record['files'].items():
        assert module._file_sha256(site / name) == digest


def test_fish_s2_export_rejects_changed_archive_before_writes(tmp_path):
    module = builder()
    source = tmp_path/'source'
    source.mkdir()
    (source/'source.tar.gz').write_bytes(b'changed')
    with pytest.raises(RuntimeError, match='Fish S2 source archive digest mismatch'):
        module._copy_fish_s2_sources(tmp_path/'runtime', source)
    assert not (tmp_path/'runtime').exists()


def test_fish_s2_export_excludes_training_and_retains_license(tmp_path, monkeypatch):
    import tarfile
    module = builder()
    root = tmp_path/('fish-speech-'+module.FISH_S2_COMMIT)
    for name in (*module.FISH_S2_UPSTREAM_FILES, 'LICENSE', 'README.md', 'pyproject.toml',
                 'fish_speech/datasets/protos/text_data_pb2.py',
                 'fish_speech/models/text2semantic/lit_module.py'):
        path = root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('fixture '+name)
    source = tmp_path/'source'
    source.mkdir()
    with tarfile.open(source/'source.tar.gz', 'w:gz') as archive:
        archive.add(root, arcname=root.name)
    monkeypatch.setattr(module, 'FISH_S2_ARCHIVE_SHA256', module._file_sha256(source/'source.tar.gz'))
    runtime = tmp_path/'runtime'
    record = module._copy_fish_s2_sources(runtime, source)[0]
    site = runtime/'profiles/fish-s2/site-packages'
    assert not (site/'fish_speech/datasets').exists()
    assert not (site/'fish_speech/models/text2semantic/lit_module.py').exists()
    assert (site/'fish_speech/LICENSE').read_bytes() == (root/'LICENSE').read_bytes()
    assert (runtime/'sources/fish-s2/LICENSE').read_bytes() == (root/'LICENSE').read_bytes()
    assert 'Built with Fish Audio' in (runtime/'sources/fish-s2/AI2Apps-NOTICE.txt').read_text()
    for name, digest in record['files'].items():
        assert module._file_sha256(site/name) == digest


@pytest.mark.parametrize('declared,flags', [
    (True, []), (True, ['--fish-s2-python','/unused/python']),
    (False, ['--fish-s2-python','/unused/python','--fish-s2-sources','/unused/source']),
    (False, ['--fish-s2-sources','/unused/source']),
])
def test_fish_cli_rejects_incomplete_or_undeclared_payload(tmp_path,monkeypatch,capsys,declared,flags):
    import sys
    from types import SimpleNamespace
    module=builder()
    source=tmp_path/'source';source.mkdir()
    (source/'service.yaml').write_text('capabilities: '+('[fish-s2]' if declared else '[]')+'\n')
    monkeypatch.setattr(module,'SOURCE',source)
    monkeypatch.setattr(module,'sys',SimpleNamespace(platform='linux'))
    monkeypatch.setattr(module.os,'uname',lambda:SimpleNamespace(machine='aarch64'))
    monkeypatch.setattr(sys,'argv',['builder','--nvfp4-aot-cache','/unused/aot',*flags])
    with pytest.raises(SystemExit) as error:module.main()
    assert error.value.code==2
    assert 'Fish S2 capability requires both' in capsys.readouterr().err


@pytest.mark.parametrize('declared,flags', [(True, []), (False, ['--e5-python','/unused/python'])])
def test_e5_cli_requires_matching_capability(tmp_path,monkeypatch,capsys,declared,flags):
    import sys
    from types import SimpleNamespace
    module=builder()
    source=tmp_path/'source';source.mkdir()
    (source/'service.yaml').write_text('capabilities: '+('[e5]' if declared else '[]')+'\n')
    monkeypatch.setattr(module,'SOURCE',source)
    monkeypatch.setattr(module,'sys',SimpleNamespace(platform='linux'))
    monkeypatch.setattr(module.os,'uname',lambda:SimpleNamespace(machine='aarch64'))
    monkeypatch.setattr(sys,'argv',['builder','--nvfp4-aot-cache','/unused/aot',*flags])
    with pytest.raises(SystemExit) as error:module.main()
    assert error.value.code==2
    assert 'E5 capability requires --e5-python' in capsys.readouterr().err


def test_e5_export_requires_inputs_before_writing(tmp_path,monkeypatch):
    module=builder();repo=tmp_path/'repo';(repo/'spark').mkdir(parents=True)
    monkeypatch.setattr(module,'REPO',repo)
    with pytest.raises(RuntimeError,match='Missing E5 runtime input'):
        module._copy_e5_sources(tmp_path/'runtime')
    assert not (tmp_path/'runtime').exists()


@pytest.mark.parametrize('declared,flags', [(True, []), (False, ['--knowledge-python','/unused/python'])])
def test_knowledge_cli_requires_matching_capability(tmp_path,monkeypatch,capsys,declared,flags):
    import sys
    from types import SimpleNamespace
    module=builder()
    source=tmp_path/'source';source.mkdir()
    (source/'service.yaml').write_text('capabilities: '+('[lancedb]' if declared else '[]')+'\n')
    monkeypatch.setattr(module,'SOURCE',source)
    monkeypatch.setattr(module,'sys',SimpleNamespace(platform='linux'))
    monkeypatch.setattr(module.os,'uname',lambda:SimpleNamespace(machine='aarch64'))
    monkeypatch.setattr(sys,'argv',['builder','--nvfp4-aot-cache','/unused/aot',*flags])
    with pytest.raises(SystemExit) as error:module.main()
    assert error.value.code==2
    assert 'LanceDB capability requires --knowledge-python' in capsys.readouterr().err


def test_detailed_profiles_publish_both_stages_without_replacing_primary(tmp_path,monkeypatch):
    module=builder();runtime=tmp_path/'runtime';(runtime/'META').mkdir(parents=True)
    metadata=runtime/'META/framework-profiles.json'
    original={'format':'ai2apps.framework-profiles/v1','profiles':{'audio':{'site_packages':'profiles/audio/site-packages'}},'services':{'existing':'audio'}}
    metadata.write_text(json.dumps(original));calls=[]
    def export(command,**kwargs):
        calls.append(command)
        profile=command[-2];lock=Path(command[-1])
        assert lock.is_file() and 'builder._verify_dependency_lock(lock)' in command[2]
        assert 'builder._copy_framework' in command[2]
        (runtime/'profiles'/profile/'site-packages').mkdir(parents=True)
        (runtime/'META'/f'{profile}-distributions.json').write_text(json.dumps([{'name':profile,'version':'1'}]))
    monkeypatch.setattr(module.subprocess,'run',export)
    inventory=module._copy_detailed_profiles(runtime,Path('/qwen/python'),Path('/nemo/python'))
    value=json.loads(metadata.read_text());service='ai2apps.model.detailed-transcription-cuda'
    assert value['services']==original['services']
    assert value['stages'][service]=={'qwen':'detailed-qwen','sortformer':'detailed-nemo'}
    assert len(inventory)==2 and len(calls)==2
    assert all((runtime/p).is_file() for p in value['stage_entrypoints'][service].values())


def test_detailed_second_export_failure_does_not_publish_stage_mapping(tmp_path,monkeypatch):
    module=builder();runtime=tmp_path/'runtime';(runtime/'META').mkdir(parents=True)
    metadata=runtime/'META/framework-profiles.json';metadata.write_text('{"format":"ai2apps.framework-profiles/v1","profiles":{},"services":{}}');before=metadata.read_bytes()
    def export(command,**kwargs):
        profile=command[-2]
        if profile=='detailed-nemo':raise RuntimeError('NeMo dependency mismatch')
        (runtime/'META'/f'{profile}-distributions.json').write_text('[]')
    monkeypatch.setattr(module.subprocess,'run',export)
    with pytest.raises(RuntimeError,match='dependency mismatch'):
        module._copy_detailed_profiles(runtime,Path('/qwen/python'),Path('/nemo/python'))
    assert metadata.read_bytes()==before


def test_yue2_export_reconstructs_pinned_source_and_retains_licenses(tmp_path):
    module = builder()
    sources = module.REPO / 'spark/artifacts/yue2-preparation-r1'
    if not (sources / 'source.tar.gz').exists():
        pytest.skip('Pinned YuE2 source archive not downloaded')
    (tmp_path / 'META').mkdir()
    records = module._copy_yue2_sources(tmp_path, sources)
    site = tmp_path / 'profiles/yue2/site-packages'
    assert records[0]['files']['yue2/cuda_graph.py'] == module.YUE2_GRAPH_SHA256
    assert 'cuda_yue2_engine.py' in records[0]['files']
    assert (tmp_path / 'sources/yue2/MODEL_LICENSE').is_file()
    assert (tmp_path / 'sources/yue2/licenses').is_dir()
    for name, digest in records[0]['files'].items():
        assert module._file_sha256(site / name) == digest


def test_yue2_export_rejects_changed_archive(tmp_path):
    module = builder()
    sources = tmp_path / 'sources'; sources.mkdir()
    (sources / 'source.tar.gz').write_bytes(b'not pinned')
    with pytest.raises(RuntimeError, match='archive digest'):
        module._copy_yue2_sources(tmp_path / 'runtime', sources)


def test_ghostv2_rejects_unpinned_source_before_export(tmp_path):
    module=builder();source=tmp_path/'source';source.mkdir()
    (source/'source.tar.gz').write_bytes(b'untrusted archive')
    target=tmp_path/'runtime'
    with pytest.raises(RuntimeError,match='GhostV2 source archive digest mismatch'):
        module._copy_ghostv2_sources(target,source)
    assert not target.exists()


def test_ghostv2_profile_keeps_official_dependencies():
    module=builder();packages,service=module.ISOLATED_PROFILES['ghostv2']
    assert service=='ai2apps.model.face-swap-cuda'
    assert {'torchvision','numba','scikit-image','opencv-python-headless','av','onnx','onnx2torch'}<=set(packages)


def test_llvmlite_sharing_preserves_versions_modes_and_relocation(tmp_path):
    import shutil
    module = builder()
    runtime = tmp_path / 'runtime'
    for profile, content, mode in [('a', b'v1', 0o644), ('b', b'v1', 0o644),
                                   ('c', b'v2', 0o644), ('d', b'v1', 0o755)]:
        root = runtime / 'profiles' / profile / 'site-packages/llvmlite'
        (root / 'binding').mkdir(parents=True)
        (root / '__init__.py').write_text('')
        library = root / 'binding/libllvmlite.so'
        library.write_bytes(content)
        library.chmod(mode)
    report = module._share_identical_llvmlite(runtime)
    assert len(report['links']) == 1
    assert report['logical_bytes_saved'] == 2
    assert (runtime / 'profiles/b/site-packages/llvmlite').is_symlink()
    assert not (runtime / 'profiles/c/site-packages/llvmlite').is_symlink()
    assert not (runtime / 'profiles/d/site-packages/llvmlite').is_symlink()
    relocated = tmp_path / 'relocated'
    shutil.move(runtime, relocated)
    assert (relocated / 'profiles/b/site-packages/llvmlite/binding/libllvmlite.so').read_bytes() == b'v1'
    assert module._share_identical_llvmlite(relocated)['links'] == []


def test_llvmlite_sharing_rejects_existing_internal_links(tmp_path):
    module = builder()
    root = tmp_path / 'profiles/a/site-packages/llvmlite'
    root.mkdir(parents=True)
    (root / 'external').symlink_to('/tmp')
    with pytest.raises(RuntimeError, match='Unsupported llvmlite'):
        module._share_identical_llvmlite(tmp_path)


def test_scientific_sharing_requires_matching_private_libraries(tmp_path):
    module = builder()
    for profile, library in [('a', b'original'), ('b', b'original'), ('c', b'different')]:
        site = tmp_path / 'profiles' / profile / 'site-packages'
        for name in ('scipy', 'scipy.libs'):
            (site / name).mkdir(parents=True)
        (site / 'scipy/__init__.py').write_text('# identical code')
        (site / 'scipy.libs/libblas.so').write_bytes(library)
    report = module._share_identical_scientific_libraries(tmp_path)
    assert len(report['groups'][1]['links']) == 2
    for name in ('scipy', 'scipy.libs'):
        assert (tmp_path / 'profiles/b/site-packages' / name).is_symlink()
        assert not (tmp_path / 'profiles/c/site-packages' / name).is_symlink()
    assert (tmp_path / 'profiles/b/site-packages/scipy.libs/libblas.so').read_bytes() == b'original'


def test_pyav_sharing_keeps_unpaired_layout_unchanged(tmp_path):
    module = builder()
    for profile in ('a', 'b', 'unpaired'):
        site = tmp_path / 'profiles' / profile / 'site-packages'
        (site / 'av').mkdir(parents=True)
        (site / 'av/__init__.py').write_text('# av')
        if profile != 'unpaired':
            (site / 'av.libs').mkdir()
            (site / 'av.libs/libavcodec.so').write_bytes(b'codec')
    report = module._share_identical_pyav(tmp_path)
    assert len(report['links']) == 2
    assert (tmp_path / 'profiles/b/site-packages/av').is_symlink()
    assert (tmp_path / 'profiles/b/site-packages/av.libs').is_symlink()
    assert not (tmp_path / 'profiles/unpaired/site-packages/av').is_symlink()


def test_transformer_sharing_retains_distinct_code_and_native_versions(tmp_path):
    module = builder()
    for profile, code, native in [('a', b'v1', b'n1'), ('b', b'v1', b'n1'),
                                   ('c', b'v2', b'n1'), ('d', b'v1', b'n2')]:
        site = tmp_path / 'profiles' / profile / 'site-packages'
        for name, data in [('transformers', code), ('tokenizers', native)]:
            (site / name).mkdir(parents=True)
            (site / name / '__init__.py').write_bytes(data)
        (site / 'transformers.dist-info').mkdir()
        (site / 'transformers.dist-info/METADATA').write_text(profile)
    report = module._share_identical_transformer_libraries(tmp_path)
    assert report['logical_bytes_saved'] == 8
    assert not (tmp_path / 'profiles/c/site-packages/transformers').is_symlink()
    assert not (tmp_path / 'profiles/d/site-packages/tokenizers').is_symlink()
    assert (tmp_path / 'profiles/b/site-packages/transformers.dist-info/METADATA').read_text() == 'b'
    assert (tmp_path / 'profiles/d/site-packages/transformers/__init__.py').read_bytes() == b'v1'


def test_source_bytecode_cleanup_preserves_sourceless_modules_and_links(tmp_path):
    module = builder()
    root = tmp_path / 'runtime'
    cache = root / '__pycache__'
    cache.mkdir(parents=True)
    (root / 'owned.py').write_text('value = 1')
    for name in ('owned.cpython-312.pyc', 'owned.cpython-312.opt-1.pyc',
                 'only.cpython-312.pyc', 'owned.unknown.pyc'):
        (cache / name).write_bytes(b'cache')
    (root / 'owned.pyc').write_bytes(b'legacy')
    (root / 'only.pyc').write_bytes(b'sourceless')
    (cache / 'linked.cpython-312.pyc').symlink_to(cache / 'only.cpython-312.pyc')
    (root / 'h3').mkdir()
    (root / 'h3/owned.py').write_text('value = 1')
    (root / 'h3/owned.pyc').write_bytes(b'inventoried')
    report = module._remove_source_bytecode(root)
    assert (root / 'h3/owned.pyc').read_bytes() == b'inventoried'
    assert len(report['removed']) == 3
    assert report['bytes_saved'] == 16
    assert (root / 'only.pyc').read_bytes() == b'sourceless'
    assert (cache / 'only.cpython-312.pyc').is_file()
    assert (cache / 'owned.unknown.pyc').is_file()
    assert (cache / 'linked.cpython-312.pyc').is_symlink()
    assert module._remove_source_bytecode(root)['removed'] == []


def test_cutlass_companion_wheels_are_required_and_exported(monkeypatch):
    from types import SimpleNamespace
    module = builder()
    dsl = SimpleNamespace(version='4.8.0', requires=[
        'nvidia-cutlass-dsl-libs-base==4.8.0',
        'nvidia-cutlass-dsl-libs-cu12==4.8.0'])
    base = SimpleNamespace(version='4.8.0', requires=[])
    cuda = SimpleNamespace(version='4.8.0', requires=[])
    index = {'nvidia-cutlass-dsl': dsl, 'nvidia-cutlass-dsl-libs-base': base}
    monkeypatch.setattr(module, 'ROOT_DISTRIBUTIONS', ('nvidia-cutlass-dsl',))
    monkeypatch.setattr(module, '_distribution_index', lambda: index)
    with pytest.raises(RuntimeError, match='nvidia-cutlass-dsl-libs-cu12'):
        module._distribution_closure()
    index['nvidia-cutlass-dsl-libs-cu12'] = cuda
    assert module._distribution_closure() == (dsl, base, cuda)
    cuda.version = '4.7.0'
    with pytest.raises(RuntimeError, match='Unsatisfied Runtime dependency'):
        module._distribution_closure()


def test_cutlass_modules_import_without_processing_pth(tmp_path):
    import subprocess
    import sys
    module = builder()
    site = tmp_path / 'site-packages'
    for name in ('cutlass', 'iket'):
        package = site / 'nvidia_cutlass_dsl' / 'dsl_packages' / name
        package.mkdir(parents=True)
        (package / '__init__.py').write_text('VALUE = 42\n')
    (site / 'untrusted.pth').write_text('import sys; sys.exit(99)\n')
    module._expose_cutlass_modules(site)
    module._expose_cutlass_modules(site)
    result = subprocess.run([sys.executable, '-I', '-S', '-c',
        'import sys; sys.path.insert(0, sys.argv[1]); import cutlass, iket; '
        'assert cutlass.VALUE == iket.VALUE == 42', str(site)], capture_output=True)
    assert result.returncode == 0, result.stderr
    assert (site / 'cutlass').readlink() == Path('nvidia_cutlass_dsl/dsl_packages/cutlass')


def test_cutlass_module_link_rejects_escape_and_collision(tmp_path):
    module = builder()
    site = tmp_path / 'site-packages'
    nested = site / 'nvidia_cutlass_dsl' / 'dsl_packages'
    nested.mkdir(parents=True)
    outside = tmp_path / 'outside'
    outside.mkdir()
    (nested / 'cutlass').symlink_to(outside, target_is_directory=True)
    with pytest.raises(RuntimeError, match='Invalid CUTLASS'):
        module._expose_cutlass_modules(site)
    (nested / 'cutlass').unlink()
    (nested / 'cutlass').mkdir()
    (site / 'cutlass').mkdir()
    with pytest.raises(RuntimeError, match='Conflicting CUTLASS'):
        module._expose_cutlass_modules(site)


def test_cutlass_modules_absent_in_shared_profile(tmp_path):
    module = builder()
    module._expose_cutlass_modules(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_openvdn_shared_inventory_keeps_framework_layers_private():
    from types import SimpleNamespace
    module=builder()
    versions={'torch':'2.13.0+cu130','torchvision':'0.28.0+cu130','triton':'3.7.1',
              'cuda-bindings':'13.3.1','diffusers':'0.36.0','protobuf':'7.36.2',
              'nvidia-cudnn-cu13':'9.20.0'}
    rows=[{'name':name,'version':version} for name,version in versions.items()]
    selected=module._openvdn_shared_inventory(rows,{name:SimpleNamespace(version=value) for name,value in versions.items()})
    assert {row['name'] for row in selected}==set(versions)-{'diffusers','protobuf'}


@pytest.mark.parametrize('name',['torch','torchvision','triton','cuda-bindings'])
@pytest.mark.parametrize('missing',[False,True])
def test_openvdn_shared_core_rejects_incompatible_or_missing_stack(name,missing):
    from types import SimpleNamespace
    module=builder()
    versions={'torch':'2.13.0+cu130','torchvision':'0.28.0+cu130','triton':'3.7.1','cuda-bindings':'13.3.1'}
    rows=[{'name':key,'version':value} for key,value in versions.items()]
    index={key:SimpleNamespace(version=value) for key,value in versions.items()}
    if missing:del index[name]
    else:index[name]=SimpleNamespace(version='different')
    with pytest.raises(RuntimeError,match='version mismatch'):
        module._openvdn_shared_inventory(rows,index)


def test_openvdn_cu129_cannot_opt_into_shared_core():
    from types import SimpleNamespace
    module=builder()
    versions={'torch':'2.13.0+cu129','torchvision':'0.28.0+cu129','triton':'3.7.1','cuda-bindings':'12.9.0'}
    with pytest.raises(RuntimeError,match='requires Torch'):
        module._openvdn_shared_inventory([{'name':k,'version':v} for k,v in versions.items()],
                                         {k:SimpleNamespace(version=v) for k,v in versions.items()})
