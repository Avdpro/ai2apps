"""Read-only verification of fetched wheels for managed Runtime plans.

Does not extract, import or install wheel code. The caller supplies the complete
probed target marker environment; evaluating Linux dependencies on the Mac
host's default marker values would produce an incorrect lock.
"""
from email.parser import BytesParser
from email.policy import compat32
import hashlib
from pathlib import Path, PurePosixPath
import stat
import zipfile

from packaging.requirements import Requirement, InvalidRequirement
from packaging.utils import canonicalize_name
from packaging.version import Version

from .runtime_install_descriptor import DescriptorError, plan_install

_MARKERS = frozenset(("implementation_name", "implementation_version", "os_name",
    "platform_machine", "platform_release", "platform_system", "platform_version",
    "python_full_version", "platform_python_implementation", "python_version", "sys_platform"))


def verify_wheel_closure(document: dict, profiles: list[str], wheel_paths: dict[str, Path],
                         *, marker_environment: dict[str, str]) -> dict:
    """Verify selected signed hashes and actual METADATA direct dependencies.

    Returns evidence only. A materializer must recheck immutable inputs, wheel
    tags/ELF compatibility and installed files before any activation.
    """
    plan = plan_install(document, profiles, target=document['target'])
    if set(marker_environment) != _MARKERS or any(not isinstance(v, str) for v in marker_environment.values()):
        raise DescriptorError('complete target marker environment required')
    env = dict(marker_environment, extra='')
    if (env['sys_platform'], env['os_name'], env['platform_machine'], env['platform_system']) != ('linux', 'posix', 'aarch64', 'Linux'):
        raise DescriptorError('marker target mismatch')
    python_version = Version(env['python_full_version'])
    if env['python_version'] != '.'.join(map(str, python_version.release[:2])) or document['target']['python_abi'] != f'cp{python_version.major}{python_version.minor}' or env['implementation_name'] != 'cpython':
        raise DescriptorError('marker Python mismatch')
    if set(wheel_paths) != set(plan.artifacts):
        raise DescriptorError('wheel inputs must exactly match selected closure')
    artifacts = document['artifacts']
    evidence = {}
    metadata_rows = {}
    for key in plan.artifacts:
        artifact = artifacts[key]
        with Path(wheel_paths[key]).open('rb') as stream:
            sha = hashlib.sha256()
            size = 0
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                size += len(block)
                if size > artifact['bytes']:
                    raise DescriptorError(f'{key}: size mismatch')
                sha.update(block)
            if size != artifact['bytes'] or sha.hexdigest() != artifact['sha256']:
                raise DescriptorError(f'{key}: size/SHA256 mismatch')
            stream.seek(0)
            with zipfile.ZipFile(stream) as wheel:
                entries = wheel.infolist()
                if len(entries) > 100000 or sum(i.file_size for i in entries) > 32 * 1024**3:
                    raise DescriptorError(f'{key}: wheel expansion limits exceeded')
                names = set()
                for info in entries:
                    path = PurePosixPath(info.filename)
                    mode = info.external_attr >> 16
                    if info.filename in names or path.is_absolute() or '..' in path.parts or '\\' in info.filename or stat.S_ISLNK(mode) or info.flag_bits & 1:
                        raise DescriptorError(f'{key}: unsafe wheel member')
                    names.add(info.filename)
                metadata = [i for i in entries if len(PurePosixPath(i.filename).parts) == 2 and i.filename.endswith('.dist-info/METADATA')]
                if len(metadata) != 1 or metadata[0].file_size > 4 * 1024**2:
                    raise DescriptorError(f'{key}: ambiguous or oversized METADATA')
                message = BytesParser(policy=compat32).parsebytes(wheel.read(metadata[0]), headersonly=True)
        if len(message.get_all('Name', [])) != 1 or len(message.get_all('Version', [])) != 1:
            raise DescriptorError(f'{key}: missing/duplicate identity')
        if canonicalize_name(message['Name']) != canonicalize_name(artifact['name']) or Version(message['Version']) != Version(artifact['version']):
            raise DescriptorError(f'{key}: METADATA identity mismatch')
        # Core Metadata / PEP 643: Dynamic is informational in a built wheel.
        # The signed wheel's actual Requires-Dist is still checked below.
        if any(value.lower() in {'name', 'version', 'metadata-version'} for value in message.get_all('Dynamic', [])):
            raise DescriptorError(f'{key}: invalid Dynamic identity field')
        from packaging.specifiers import SpecifierSet
        if python_version not in SpecifierSet(message.get('Requires-Python', '')):
            raise DescriptorError(f'{key}: Requires-Python mismatch')
        metadata_rows[key] = {
            'requires_dist': message.get_all('Requires-Dist', []),
            'provides_extra': message.get_all('Provides-Extra', []),
        }
        evidence[key] = {'sha256': artifact['sha256'], 'bytes': size}
    closure = verify_metadata_dependencies(artifacts, plan.artifacts, metadata_rows, env)
    for key in plan.artifacts:
        evidence[key].update(closure[key])
    return {'environment_digest': plan.environment_digest, 'artifacts': evidence,
            'scope': 'fetched wheel hashes and target METADATA dependency closure; not installation/ELF/GPU acceptance'}


def verify_metadata_dependencies(artifacts, selected, metadata_rows, environment):
    """Expand requested extras to a fixed point using the target's markers.

    Input metadata must originate from the exact hashed wheels. This helper can
    also audit pip reports, but such results are not wheel verification evidence.
    Top-level extra selections are not yet supported by the descriptor schema.
    """
    by_name = {canonicalize_name(artifacts[k]['name']): k for k in selected}
    enabled = {key: set() for key in selected}
    active = {key: set() for key in selected}
    requirements = {}
    for key in selected:
        try:
            requirements[key] = [Requirement(raw) for raw in metadata_rows[key]['requires_dist']]
        except InvalidRequirement as exc:
            raise DescriptorError(f'{key}: malformed dependency') from exc
    changed = True
    while changed:
        changed = False
        for key in selected:
            for requirement in requirements[key]:
                contexts = ('', *sorted(enabled[key]))
                if requirement.marker and not any(requirement.marker.evaluate(dict(environment, extra=extra)) for extra in contexts):
                    continue
                if requirement.url:
                    raise DescriptorError(f'{key}: active URL dependency unsupported')
                dep = by_name.get(canonicalize_name(requirement.name))
                if dep is None or dep not in artifacts[key]['requires']:
                    raise DescriptorError(f'{key}: undeclared active dependency {requirement.name}')
                if Version(artifacts[dep]['version']) not in requirement.specifier:
                    raise DescriptorError(f'{key}: dependency version mismatch {requirement.name}')
                requested = {canonicalize_name(extra) for extra in requirement.extras}
                provided = {canonicalize_name(extra) for extra in metadata_rows[dep]['provides_extra']}
                if not requested <= provided:
                    raise DescriptorError(f'{dep}: unknown requested extras')
                if not requested <= enabled[dep]:
                    enabled[dep].update(requested); changed = True
                active[key].add(dep)
    return {key: {'active_metadata_dependencies': sorted(active[key]),
                  'enabled_extras': sorted(enabled[key])} for key in selected}
