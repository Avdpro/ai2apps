import json
from pathlib import Path
import pytest
from test_runtime_wheel_verification import setup, ENV
from ai2apps.packages.runtime_wheelhouse import prepare_wheelhouse, offline_pip_arguments
from ai2apps.packages.runtime_install_descriptor import DescriptorError


def test_copies_exact_verified_inputs_and_offline_command(tmp_path):
    d,paths=setup(tmp_path)
    target=tmp_path/'private input'
    result=prepare_wheelhouse(d,['audio'],paths,target,marker_environment=ENV)
    assert result['status']=='verified_offline_input'
    for key,path in paths.items():
        copied=target/'wheels'/path.name
        assert copied.read_bytes()==path.read_bytes()
        assert copied.stat().st_ino!=path.stat().st_ino
    requirements=(target/'requirements.txt').read_text()
    assert '%20' in requirements and requirements.count('--hash=sha256:')==2
    command=offline_pip_arguments(tmp_path/'venv/bin/python',target)
    assert '--no-index' in command and '--require-hashes' in command and '--no-deps' in command


def test_failed_copy_is_not_reused(tmp_path):
    d,paths=setup(tmp_path);paths['audio'].write_bytes(b'corrupt')
    target=tmp_path/'failed'
    with pytest.raises(DescriptorError):prepare_wheelhouse(d,['audio'],paths,target,marker_environment=ENV)
    assert json.loads((target/'receipt.json').read_text())['status']=='failed'
    assert not (target/'requirements.txt').exists()
    with pytest.raises(FileExistsError):prepare_wheelhouse(d,['audio'],paths,target,marker_environment=ENV)


def test_metadata_failure_does_not_create_install_input(tmp_path):
    d,paths=setup(tmp_path,'torch>=2')
    target=tmp_path/'bad-metadata'
    with pytest.raises(DescriptorError):prepare_wheelhouse(d,['audio'],paths,target,marker_environment=ENV)
    assert not (target/'requirements.txt').exists()


def test_real_offline_venv_install_and_import(tmp_path):
    import base64
    import csv
    import hashlib
    import io
    import subprocess
    import sys
    import zipfile
    d,paths=setup(tmp_path)
    # Complete pure-Python wheels, installed by real pip rather than a mock.
    for key,path in paths.items():
        with zipfile.ZipFile(path) as archive:
            files={name:archive.read(name) for name in archive.namelist()}
        files[f'{key}-1.0.dist-info/WHEEL']=b'Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n'
        files[f'{key}/__init__.py']=b'VALUE = 42\n'
        record=io.StringIO();writer=csv.writer(record)
        for name,content in files.items():
            digest=base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b'=').decode()
            writer.writerow([name,'sha256='+digest,len(content)])
        writer.writerow([f'{key}-1.0.dist-info/RECORD','',''])
        files[f'{key}-1.0.dist-info/RECORD']=record.getvalue().encode()
        with zipfile.ZipFile(path,'w') as archive:
            for name,content in files.items():archive.writestr(name,content)
        d['artifacts'][key]['bytes']=path.stat().st_size
        d['artifacts'][key]['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    inputs=tmp_path/'offline'
    prepare_wheelhouse(d,['audio'],paths,inputs,marker_environment=ENV)
    environment=tmp_path/'venv'
    subprocess.run([sys.executable,'-I','-m','venv',str(environment)],check=True,capture_output=True,timeout=60)
    python=environment/'bin/python'
    subprocess.run(offline_pip_arguments(python,inputs),check=True,capture_output=True,timeout=60,
                   env={'PATH':'/usr/bin:/bin','HOME':str(tmp_path),'PIP_CONFIG_FILE':'/dev/null'})
    result=subprocess.run([str(python),'-I','-c','import audio, torch; print(audio.VALUE + torch.VALUE)'],check=True,capture_output=True,text=True,timeout=10)
    assert result.stdout.strip()=='84'
    from ai2apps.packages.runtime_installed_files import verify_installed_wheel_files
    installed_paths=json.loads(subprocess.run([str(python),'-I','-c','import sysconfig,json; print(json.dumps(sysconfig.get_paths()))'],check=True,capture_output=True,text=True,timeout=10).stdout)
    scheme={key:Path(installed_paths[key]) for key in ('purelib','platlib','scripts','data')}
    scheme['headers']=environment/'include'
    for key,path in paths.items():
        evidence=verify_installed_wheel_files(inputs/'wheels'/path.name,environment_root=environment,scheme=scheme,root_is_purelib=True,python=python)
        assert any(name.endswith(f'{key}/__init__.py') for name in evidence['checked_files'])

