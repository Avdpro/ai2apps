"""Prepare an immutable-by-convention, verified offline installation input.

Internal draft. Call only after outer signature/audit approval. This does not
activate an environment or execute pip. A sandboxed materializer must consume
this private directory and retain platform/ELF/probe gates.
"""
import hashlib
import json
import os
from pathlib import Path

from .runtime_install_descriptor import DescriptorError, plan_install
from .runtime_wheel_verification import verify_wheel_closure


def prepare_wheelhouse(document: dict, profiles: list[str], sources: dict[str, Path],
                       destination: Path, *, marker_environment: dict[str, str]) -> dict:
    """Copy exact selected bytes into a new private directory and revalidate.

    Never modify inputs or reuse a failed/active directory. The on-disk receipt
    records failures; a ready-input receipt is not an environment-ready record.
    """
    plan = plan_install(document, profiles, target=document['target'])
    if set(sources) != set(plan.artifacts):
        raise DescriptorError('source set differs from selected closure')
    destination = Path(destination)
    destination.mkdir(mode=0o700, parents=False, exist_ok=False)
    receipt = {'status': 'copying', 'environment_digest': plan.environment_digest,
               'descriptor_digest': plan.descriptor_digest, 'artifacts': list(plan.artifacts)}

    def save():
        temporary = destination / 'receipt.tmp'
        with temporary.open('w', encoding='utf-8') as stream:
            json.dump(receipt, stream, indent=2); stream.write('\n')
            stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, destination / 'receipt.json')
        fd = os.open(destination, os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)

    save()
    try:
        wheels = destination / 'wheels'; wheels.mkdir(mode=0o700)
        copied = {}; filenames = set()
        for key in plan.artifacts:
            artifact = document['artifacts'][key]
            filename = artifact['filename']
            if filename in filenames:
                raise DescriptorError('duplicate wheel filename')
            filenames.add(filename)
            target = wheels / filename
            size = 0; sha = hashlib.sha256()
            with Path(sources[key]).open('rb') as source, target.open('xb') as output:
                while block := source.read(1024 * 1024):
                    size += len(block)
                    if size > artifact['bytes']:
                        raise DescriptorError(f'{key}: input grew beyond locked size')
                    sha.update(block);output.write(block)
                output.flush();os.fsync(output.fileno())
            if size != artifact['bytes'] or sha.hexdigest() != artifact['sha256']:
                raise DescriptorError(f'{key}: copied input hash mismatch')
            target.chmod(0o400)
            copied[key] = target
        receipt['verification'] = verify_wheel_closure(document, profiles, copied, marker_environment=marker_environment)
        requirements = destination / 'requirements.txt'
        # Direct local files avoid index/name resolution. URI encoding handles
        # spaces safely; subprocess command arguments never pass through a shell.
        lines = [f"{copied[key].resolve().as_uri()} --hash=sha256:{document['artifacts'][key]['sha256']}" for key in plan.artifacts]
        with requirements.open('x',encoding='utf-8') as stream:
            stream.write('\n'.join(lines)+'\n');stream.flush();os.fsync(stream.fileno())
        requirements.chmod(0o400)
        receipt['requirements_sha256'] = hashlib.sha256(requirements.read_bytes()).hexdigest()
        receipt['status'] = 'verified_offline_input'
        receipt['scope'] = 'verified copied wheelhouse, not installed environment'
        save()
        return receipt
    except Exception as error:
        receipt.update(status='failed',error=str(error))
        save()
        raise


def offline_pip_arguments(python: Path, wheelhouse: Path) -> tuple[str, ...]:
    """Host-owned invocation; caller provides sandbox and clean environment.

    --no-deps is safe only following actual METADATA closure verification. No
    network namespace or environment-ready claim is supplied by these flags.
    """
    return (str(python), '-I', '-m', 'pip', '--isolated', '--disable-pip-version-check',
            'install', '--no-index', '--no-cache-dir', '--no-deps',
            '--only-binary=:all:', '--require-hashes',
            '-r', str(Path(wheelhouse) / 'requirements.txt'))
