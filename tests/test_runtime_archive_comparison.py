"""Regression gates for the immutable Runtime comparison tool."""
import importlib.util
import io
from pathlib import Path
import tarfile

import pytest


def comparator():
    path = Path(__file__).resolve().parents[1] / 'spark/compare_runtime_archives.py'
    spec = importlib.util.spec_from_file_location('runtime_compare', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def archive(path, *, shared=False, changed=False, mode=0o644, target='../a/pkg'):
    with tarfile.open(path, 'w:gz') as tar:
        for folder in ('', 'profiles', 'profiles/a', 'profiles/a/pkg', 'profiles/b'):
            info = tarfile.TarInfo('AI2AppsCudaTorchRuntime' + ('/' + folder if folder else ''))
            info.type = tarfile.DIRTYPE; info.mode = 0o755; tar.addfile(info)
        roots = ['profiles/a/pkg'] if shared else ['profiles/a/pkg', 'profiles/b/pkg']
        if shared:
            info = tarfile.TarInfo('AI2AppsCudaTorchRuntime/profiles/b/pkg')
            info.type = tarfile.SYMTYPE; info.linkname = target; info.mode = 0o777; tar.addfile(info)
        for root in roots:
            for name, data in [('code.py', b'changed' if changed else b'value=1'), ('cache.pyc', b'bytecode')]:
                info = tarfile.TarInfo('AI2AppsCudaTorchRuntime/' + root + '/' + name)
                info.size = len(data); info.mode = mode; tar.addfile(info, io.BytesIO(data))
        if shared:
            for name in ('llvmlite', 'pyav', 'scientific'):
                info = tarfile.TarInfo('AI2AppsCudaTorchRuntime/META/' + name + '-sharing.json')
                info.size = 2; info.mode = 0o644; tar.addfile(info, io.BytesIO(b'{}'))


def test_real_tar_directory_sharing_keeps_all_logical_bytes(tmp_path):
    module = comparator()
    a,b=tmp_path/'a.tar.gz',tmp_path/'b.tar.gz'
    archive(a);archive(b,shared=True)
    _,before=module.inventory(a);_,after=module.inventory(b)
    result=module.compare(before,after,'old','new')
    assert result['passed'] and result['baseline_files']==4
    after['profiles/a/pkg/cache.pyc']['sha256']='changed-bytecode'
    result=module.compare(before,after,'old','new')
    assert not result['passed']
    assert {x['path'] for x in result['mismatches']}=={'profiles/a/pkg/cache.pyc','profiles/b/pkg/cache.pyc'}


@pytest.mark.parametrize('kwargs', [{'changed':True},{'mode':0o755},
    {'target':'../../../outside'}, {'target':'pkg'}, {'target':'/tmp/external'}])
def test_real_tar_changed_bytes_permissions_and_bad_links_fail(tmp_path,kwargs):
    module=comparator();a,b=tmp_path/'a.tar.gz',tmp_path/'b.tar.gz'
    archive(a);archive(b,shared=True,**kwargs)
    _,before=module.inventory(a);_,after=module.inventory(b)
    assert not module.compare(before,after,'old','new')['passed']


def test_duplicate_tar_member_is_rejected(tmp_path):
    path=tmp_path/'duplicate.tar'
    with tarfile.open(path,'w:gz') as tar:
        for _ in range(2):tar.addfile(tarfile.TarInfo('AI2AppsCudaTorchRuntime/same'))
    with pytest.raises(ValueError,match='Duplicate'):
        comparator().inventory(path)
