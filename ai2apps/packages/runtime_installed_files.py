"""Compare installed wheel-owned bytes before managed environment activation.

Input wheel verification and sandboxed installation are prerequisites. This is
one readiness gate, not a signature, ELF, GPU, entry-point or whole-tree audit.
"""
import hashlib
from pathlib import Path, PurePosixPath
import zipfile

from .runtime_install_descriptor import DescriptorError


def verify_installed_wheel_files(wheel: Path, *, environment_root: Path,
                                 scheme: dict[str, Path], root_is_purelib: bool,
                                 python: Path) -> dict:
    """Verify original wheel payload against an explicitly probed venv scheme.

    No scheme or paths are inferred from the current Host interpreter. Pip's
    rewritten RECORD is excluded; generated launchers/pyc need separate gates.
    """
    root = Path(environment_root).resolve(strict=True)
    keys = {'purelib','platlib','scripts','data','headers'}
    if set(scheme) != keys:
        raise DescriptorError('complete target installation scheme required')
    resolved = {}
    for key,value in scheme.items():
        path=Path(value).resolve()
        if not path.is_relative_to(root):
            raise DescriptorError('installation scheme escapes environment')
        resolved[key]=path
    if type(root_is_purelib) is not bool:
        raise DescriptorError('invalid purelib flag')
    destinations=set(); checked={}; skipped=[]
    with zipfile.ZipFile(wheel) as archive:
        for info in archive.infolist():
            if info.is_dir():continue
            name=PurePosixPath(info.filename)
            if name.is_absolute() or '..' in name.parts or '\\' in info.filename:
                raise DescriptorError('unsafe wheel path')
            if len(name.parts)==2 and name.parts[0].endswith('.dist-info') and name.name=='RECORD':
                skipped.append(info.filename);continue
            script=False
            if name.parts[0].endswith('.data'):
                if len(name.parts)<3 or name.parts[1] not in resolved:
                    raise DescriptorError('unsupported wheel data scheme')
                kind=name.parts[1];relative=Path(*name.parts[2:]);script=kind=='scripts'
            else:
                kind='purelib' if root_is_purelib else 'platlib';relative=Path(*name.parts)
            destination=(resolved[kind]/relative).resolve(strict=True)
            if not destination.is_relative_to(root) or destination in destinations:
                raise DescriptorError('installed path escape/collision')
            destinations.add(destination)
            # Stream large native libraries instead of loading Torch into memory.
            if script:
                original=archive.read(info)
                actual=destination.read_bytes()
                first,separator,rest=original.partition(b'\n')
                if first.rstrip(b'\r') in (b'#!python',b'#!pythonw'):
                    expected=b'#!'+str(python).encode()+b'\n'+rest
                    if actual!=expected:
                        raise DescriptorError('installed script rewrite mismatch')
                elif actual!=original:
                    raise DescriptorError('installed script bytes mismatch')
                digest=hashlib.sha256(actual).hexdigest()
            else:
                expected=hashlib.sha256();actual=hashlib.sha256()
                with archive.open(info) as source, destination.open('rb') as installed:
                    for block in iter(lambda:source.read(1024*1024),b''):expected.update(block)
                    for block in iter(lambda:installed.read(1024*1024),b''):actual.update(block)
                if expected.digest()!=actual.digest():
                    raise DescriptorError(f'installed file mismatch: {info.filename}')
                digest=actual.hexdigest()
            checked[str(destination.relative_to(root))]=digest
    return {'checked_files':checked,'excluded_generated_records':skipped,
            'scope':'wheel-owned installed bytes only; generated entry points/extra files/ELF/GPU remain separate gates'}
