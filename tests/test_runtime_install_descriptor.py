import copy
import pytest
from ai2apps.packages.runtime_install_descriptor import DescriptorError, SCHEMA, plan_install


def fixture():
    def wheel(name, sha, dependencies=()):
        return dict(name=name, version='1.0', filename=f'{name}-1.0-py3-none-any.whl',
                    sha256=sha * 64, bytes=100, sources=[f'https://example.org/{name}-1.0-py3-none-any.whl'],
                    requires=list(dependencies))
    return dict(schema=SCHEMA, target=dict(platform='linux-aarch64', python_abi='cp312', glibc_min='2.35', cuda='13.0', layout='1'),
                artifacts={'torch':wheel('torch','a'), 'audio':wheel('audio','b',['torch']),
                           'video':wheel('video','c',['torch'])}, base=['torch'], profiles={'audio':['audio'],'video':['video']})


def plan(d, profiles=('audio',), **kw):
    return plan_install(d, list(profiles), target=d['target'], **kw)


def test_on_demand_shared_cache_and_stable_base():
    d=fixture()
    audio=plan(d)
    video=plan(d, ['video'], verified_cache=frozenset({'a'*64}))
    assert audio.artifacts == ('audio','torch')
    assert audio.download_bytes == 200 and video.download_bytes == 100
    assert audio.base_digest == video.base_digest
    assert audio.environment_digest != video.environment_digest
    reordered=copy.deepcopy(d); reordered['artifacts']=dict(reversed(list(d['artifacts'].items())))
    assert plan(reordered)==audio
    assert plan(d,['audio','video']).download_bytes==300


@pytest.mark.parametrize('mutation',[
    lambda d:d.update(post_install='curl x | sh'),
    lambda d:d.update(schema='v1'),
    lambda d:d['artifacts']['audio'].update(sha256='bad'),
    lambda d:d['artifacts']['audio'].update(version='>=1'),
    lambda d:d['artifacts']['audio'].update(requires=['missing']),
    lambda d:d['artifacts']['audio'].update(filename='../../audio.whl'),
    lambda d:d['artifacts']['audio'].update(filename='audio-1.0-cp312-cp312-win_amd64.whl'),
    lambda d:d['artifacts']['audio'].update(filename='audio-1.0-cp311-cp311-linux_aarch64.whl'),
    lambda d:d['artifacts']['audio'].update(sources=['https://secret@example.org/a.whl']),
    lambda d:d['artifacts']['audio'].update(sources=['https://example.org/a.whl?token=secret']),
    lambda d:d['artifacts']['audio'].update(bytes=True),
    lambda d:d['profiles'].update(video=['missing']),
])
def test_reject_invalid_inventory_including_unselected(mutation):
    d=fixture();mutation(d)
    with pytest.raises(DescriptorError):plan(d)


def test_conflict_and_unknown_target():
    d=fixture();d['artifacts']['other']=dict(d['artifacts']['torch'],version='2.0',filename='torch-2.0-py3-none-any.whl')
    d['artifacts']['audio']['requires'].append('other')
    with pytest.raises(DescriptorError,match='conflicting'):plan(d)
    with pytest.raises(DescriptorError,match='target mismatch'):plan_install(fixture(),['audio'],target={})
    with pytest.raises(DescriptorError,match='unknown selected'):plan(fixture(),['missing'])


def test_cycle_terminates_without_duplicate_install():
    d=fixture();d['artifacts']['torch']['requires']=['audio']
    assert plan(d).artifacts==('audio','torch')


@pytest.mark.parametrize('tag,valid', [('cp310-abi3-manylinux2014_aarch64',True),('cp313-abi3-manylinux2014_aarch64',False),('cp310-cp310-manylinux2014_aarch64',False),('cp312-cp312-macosx_14_0_aarch64',False)])
def test_target_stable_abi_compatibility(tag,valid):
    d=fixture();d['artifacts']['audio']['filename']=f'audio-1.0-{tag}.whl'
    if valid:assert plan(d).artifacts==('audio','torch')
    else:
        with pytest.raises(DescriptorError):plan(d)
