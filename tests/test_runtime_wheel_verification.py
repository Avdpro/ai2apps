import hashlib
import zipfile
import pytest
from ai2apps.packages.runtime_install_descriptor import SCHEMA, DescriptorError
from ai2apps.packages.runtime_wheel_verification import verify_wheel_closure

ENV = dict(implementation_name='cpython', implementation_version='3.12.8', os_name='posix',
    platform_machine='aarch64', platform_release='6.0', platform_system='Linux', platform_version='test',
    python_full_version='3.12.8', platform_python_implementation='CPython', python_version='3.12', sys_platform='linux')


def setup(tmp_path, requirement='torch>=1; sys_platform == "linux"', extra=None):
    artifacts={}; paths={}
    for name in ('torch','audio'):
        path=tmp_path/f'{name}-1.0-py3-none-any.whl'
        with zipfile.ZipFile(path,'w') as z:
            text=f'Metadata-Version: 2.1\nName: {name}\nVersion: 1.0\nRequires-Python: >=3.12\n'
            if name=='audio':text+=f'Requires-Dist: {requirement}\n'
            z.writestr(f'{name}-1.0.dist-info/METADATA',text+'\n')
            if extra and name=='audio':z.writestr(extra,'unexpected')
        artifacts[name]=dict(name=name,version='1.0',filename=path.name,bytes=path.stat().st_size,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),sources=['https://example.org/'+path.name],requires=['torch'] if name=='audio' else [])
        paths[name]=path
    d=dict(schema=SCHEMA,target=dict(platform='linux-aarch64',python_abi='cp312',glibc_min='2.35',cuda='13.0',layout='1'),artifacts=artifacts,base=['torch'],profiles={'audio':['audio']})
    return d,paths


def verify(d, paths, env=ENV):return verify_wheel_closure(d,['audio'],paths,marker_environment=env)


def test_target_markers_and_real_zip_metadata(tmp_path):
    d,p=setup(tmp_path)
    assert verify(d,p)['artifacts']['audio']['active_metadata_dependencies']==['torch']


@pytest.mark.parametrize('req', ['torch>=2', 'missing>=1', 'torch[optional]>=1', 'torch @ https://example.org/torch.whl'])
def test_reject_bad_dependency(tmp_path,req):
    d,p=setup(tmp_path,req)
    with pytest.raises(DescriptorError):verify(d,p)


def test_missing_direct_edge_even_when_base_has_dependency(tmp_path):
    d,p=setup(tmp_path);d['artifacts']['audio']['requires']=[]
    with pytest.raises(DescriptorError,match='undeclared'):verify(d,p)


def test_inactive_marker_does_not_pull_other_platform(tmp_path):
    d,p=setup(tmp_path,'windows_only; sys_platform == "win32"')
    assert verify(d,p)['artifacts']['audio']['active_metadata_dependencies']==[]


def test_tamper(tmp_path):
    d,p=setup(tmp_path);p['audio'].write_bytes(p['audio'].read_bytes()+b'bad')
    with pytest.raises(DescriptorError,match='size'):verify(d,p)


def test_no_host_marker_fallback(tmp_path):
    d,p=setup(tmp_path)
    with pytest.raises(DescriptorError,match='complete'):verify(d,p,{})
    with pytest.raises(DescriptorError,match='target'):verify(d,p,dict(ENV,sys_platform='darwin'))


@pytest.mark.parametrize('member',['../escape','/absolute','audio-2.0.dist-info/METADATA'])
def test_unsafe_archive(tmp_path,member):
    d,p=setup(tmp_path,extra=member)
    with pytest.raises(DescriptorError):verify(d,p)


@pytest.mark.parametrize('dynamic,allowed',[('Requires-Dist',True),('License-File',True),('Name',False)])
def test_built_wheel_dynamic_is_informational(tmp_path,dynamic,allowed):
    d,p=setup(tmp_path)
    with zipfile.ZipFile(p['audio']) as archive:
        files={n:archive.read(n) for n in archive.namelist()}
    name='audio-1.0.dist-info/METADATA'
    files[name]=f'Dynamic: {dynamic}\n'.encode()+files[name]
    with zipfile.ZipFile(p['audio'],'w') as archive:
        for n,content in files.items():archive.writestr(n,content)
    d['artifacts']['audio']['bytes']=p['audio'].stat().st_size
    d['artifacts']['audio']['sha256']=hashlib.sha256(p['audio'].read_bytes()).hexdigest()
    if allowed:
        assert verify(d,p)['artifacts']['audio']['active_metadata_dependencies']==['torch']
        d['artifacts']['audio']['requires']=[]
        with pytest.raises(DescriptorError,match='undeclared'):verify(d,p)
    else:
        with pytest.raises(DescriptorError,match='Dynamic'):verify(d,p)


def test_recursive_extras_fixed_point_and_missing_edges():
    from ai2apps.packages.runtime_wheel_verification import verify_metadata_dependencies
    artifacts={k:dict(name=k,version='1',requires=deps) for k,deps in [('torch',['toolkit']),('toolkit',['kernel']),('kernel',['support']),('support',[])]}
    rows={'torch':dict(requires_dist=['toolkit[cuda]==1'],provides_extra=[]),
          'toolkit':dict(requires_dist=['kernel[fast]==1; extra == "cuda"','missing; extra == "unused"'],provides_extra=['cuda','unused']),
          'kernel':dict(requires_dist=['support==1; extra == "fast"'],provides_extra=['fast']),
          'support':dict(requires_dist=[],provides_extra=[])}
    # Reverse traversal forces multiple propagation iterations.
    selected=tuple(reversed(artifacts))
    result=verify_metadata_dependencies(artifacts,selected,rows,ENV)
    assert result['kernel']['active_metadata_dependencies']==['support']
    assert result['toolkit']['enabled_extras']==['cuda']
    artifacts['kernel']['requires']=[]
    with pytest.raises(DescriptorError,match='undeclared'):verify_metadata_dependencies(artifacts,selected,rows,ENV)


def test_extras_cycles_terminate_and_union():
    from ai2apps.packages.runtime_wheel_verification import verify_metadata_dependencies
    a={'a':dict(name='a',version='1',requires=['b']),'b':dict(name='b',version='1',requires=['a'])}
    m={'a':dict(requires_dist=['b[x]'],provides_extra=['y']), 'b':dict(requires_dist=['a[y]; extra == "x"'],provides_extra=['x'])}
    result=verify_metadata_dependencies(a,tuple(a),m,ENV)
    assert result['a']['enabled_extras']==['y']
    assert result['b']['enabled_extras']==['x']
