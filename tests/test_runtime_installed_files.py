from pathlib import Path
import zipfile
import pytest
from ai2apps.packages.runtime_installed_files import verify_installed_wheel_files
from ai2apps.packages.runtime_install_descriptor import DescriptorError


def fixture(tmp_path):
    root=tmp_path/'venv';root.mkdir()
    scheme={key:root/key for key in ('purelib','platlib','scripts','data','headers')}
    for path in scheme.values():path.mkdir()
    wheel=tmp_path/'fixture.whl'
    files={'audio/__init__.py':b'VALUE=42\n','audio-1.0.dist-info/RECORD':b'old record',
           'audio-1.0.data/data/share/config.json':b'{}','audio-1.0.data/scripts/tool':b'#!python\nprint(42)\n'}
    with zipfile.ZipFile(wheel,'w') as z:
        for name,content in files.items():z.writestr(name,content)
    (scheme['purelib']/'audio').mkdir();(scheme['purelib']/'audio/__init__.py').write_bytes(files['audio/__init__.py'])
    (scheme['data']/'share').mkdir();(scheme['data']/'share/config.json').write_bytes(b'{}')
    python=root/'bin/python'
    (scheme['scripts']/'tool').write_bytes(b'#!'+str(python).encode()+b'\nprint(42)\n')
    return wheel,dict(environment_root=root,scheme=scheme,root_is_purelib=True,python=python)


def test_payload_and_pip_script_rewrite(tmp_path):
    wheel,kw=fixture(tmp_path)
    result=verify_installed_wheel_files(wheel,**kw)
    assert len(result['checked_files'])==3
    assert result['excluded_generated_records']==['audio-1.0.dist-info/RECORD']


@pytest.mark.parametrize('corrupt',['purelib/audio/__init__.py','data/share/config.json','scripts/tool'])
def test_mutation_fails(tmp_path,corrupt):
    wheel,kw=fixture(tmp_path);(kw['environment_root']/corrupt).write_bytes(b'tampered')
    with pytest.raises(DescriptorError):verify_installed_wheel_files(wheel,**kw)


def test_installed_symlink_escape(tmp_path):
    wheel,kw=fixture(tmp_path);target=kw['scheme']['purelib']/'audio/__init__.py'
    target.unlink();outside=tmp_path/'outside';outside.write_bytes(b'VALUE=42\n');target.symlink_to(outside)
    with pytest.raises(DescriptorError,match='escape'):verify_installed_wheel_files(wheel,**kw)
