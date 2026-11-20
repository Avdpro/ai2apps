"""Harness-owned file operations within a user-named directory.

All host paths are resolved by LocalDirectories, never by model-supplied authority.
Regular files only; no recursive delete or implicit overwrite.
"""
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import stat
import subprocess
import sys
from uuid import uuid4

from .local_directories import open_directory, descend, relative, MAX_FILES

TOOLS = ('host.directory.inspect', 'host.directory.mkdir', 'host.directory.export',
         'host.directory.copy', 'host.directory.move', 'host.directory.reveal')
MAX_EXPORT = 1024 * 1024 * 1024


@contextmanager
def regular_file(fd, name):
    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    with os.fdopen(descriptor, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('Only regular files are supported')
        yield stream


def digest(stream):
    h = hashlib.sha256()
    size = 0
    while chunk := stream.read(1024 * 1024):
        size += len(chunk)
        if size > MAX_EXPORT:
            raise ValueError('File exceeds the 1 GiB operation limit')
        h.update(chunk)
    return size, h.hexdigest()


def identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def publish(source, fd, name, *, collision='rename', expected_sha256=None, source_sha256=None):
    """Stage and verify bytes before publishing. Never follow a destination link."""
    if collision not in ('rename', 'skip', 'replace'):
        raise ValueError('Unsupported collision policy')
    temp = '.ai2apps-' + uuid4().hex
    committed = False
    try:
        before = os.fstat(source.fileno())
        source.seek(0)
        with os.fdopen(os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=fd), 'wb') as out:
            h = hashlib.sha256(); size = 0
            while chunk := source.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_EXPORT: raise ValueError('File exceeds the 1 GiB operation limit')
                out.write(chunk); h.update(chunk)
            out.flush(); os.fsync(out.fileno())
        if identity(before) != identity(os.fstat(source.fileno())):
            raise ValueError('Source changed during copy')
        with regular_file(fd, temp) as check:
            verified_size, verified_hash = digest(check)
        if source_sha256 and h.hexdigest() != source_sha256:
            raise ValueError('Artifact content hash mismatch')
        if (size, h.hexdigest()) != (verified_size, verified_hash):
            raise ValueError('Saved file verification failed')
        if collision == 'replace':
            if not expected_sha256: raise ValueError('Replacement requires the observed destination SHA-256')
            with regular_file(fd, name) as existing:
                existing_info = os.fstat(existing.fileno())
                if digest(existing)[1] != expected_sha256: raise ValueError('Destination changed; inspect again')
            if identity(os.stat(name, dir_fd=fd, follow_symlinks=False)) != identity(existing_info):
                raise ValueError('Destination changed; inspect again')
            os.replace(temp, name, src_dir_fd=fd, dst_dir_fd=fd)
        else:
            original = Path(name)
            for suffix in range(1000):
                candidate = name if suffix == 0 else f'{original.stem} ({suffix}){original.suffix}'
                try:
                    os.link(temp, candidate, src_dir_fd=fd, dst_dir_fd=fd, follow_symlinks=False)
                    name = candidate
                    break
                except FileExistsError:
                    if collision == 'skip': return {'status': 'skipped', 'name': name}
            else: raise ValueError('Too many name collisions')
            os.unlink(temp, dir_fd=fd)
        committed = True
        receipt = {'status': 'saved', 'name': name, 'size_bytes': size, 'sha256': verified_hash, 'verified': True}
        try: os.fsync(fd)
        except OSError as error: receipt['durability_warning'] = str(error)
        return receipt
    finally:
        if not committed:
            try: os.unlink(temp, dir_fd=fd)
            except FileNotFoundError: pass


class LocalFiles:
    def __init__(self, runtime, directories):
        self.runtime, self.directories = runtime, directories

    async def prepare(self, args, context):
        await self.directories.prepare({'root': args['root']}, context)
        for key in ('path', 'source', 'destination'):
            if key in args: relative(args[key])
        for item in args.get('files', []): relative(item['path'])
        if args.get('collision') == 'replace':
            # A save request alone is not permission to destroy an existing file.
            requests = self.runtime.app_chat.source_user_requests(context.trace_id, context.session_id)
            import re
            if not any(re.search(r'覆盖|替换|\boverwrite\b|\breplace\b', text, re.I) for text in requests):
                raise PermissionError('Overwrite needs an explicit user request; use rename or skip')
        return args

    def inspect(self, args, context):
        root = self.directories.root(args, context)
        parts = relative(args.get('path', '.'))
        with open_directory(root) as root_fd, descend(root_fd, parts[:-1] if parts else ()) as fd:
            info = os.stat(parts[-1], dir_fd=fd, follow_symlinks=False) if parts else os.fstat(fd)
            if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
                raise ValueError('Only regular files and directories can be inspected')
            if parts and stat.S_ISDIR(info.st_mode):
                with descend(fd, (parts[-1],)) as target_fd:
                    space = os.fstatvfs(target_fd)
            else:
                space = os.fstatvfs(fd)
            result = {'root': str(root), 'path': args.get('path', '.'),
                      'kind': 'directory' if stat.S_ISDIR(info.st_mode) else 'file',
                      'size_bytes': info.st_size, 'free_bytes': space.f_bavail * space.f_frsize,
                      'writable': bool(info.st_mode & 0o222)}
            if stat.S_ISREG(info.st_mode):
                with regular_file(fd, parts[-1]) as stream:
                    result['size_bytes'], result['sha256'] = digest(stream)
            return result

    def mkdir(self, args, context):
        root = self.directories.root(args, context)
        parts = relative(args['path'])
        with open_directory(root) as root_fd:
            fd = os.dup(root_fd)
            try:
                for part in parts:
                    try: os.mkdir(part, mode=0o700, dir_fd=fd)
                    except FileExistsError: pass
                    nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                    os.close(fd); fd = nxt
            finally: os.close(fd)
        return {'status': 'completed', 'path': str(root.joinpath(*parts))}

    def export(self, args, context):
        root = self.directories.root(args, context)
        files = args['files']
        if not 1 <= len(files) <= MAX_FILES: raise ValueError('Export supports 1–64 files')
        # Preflight all ownership and paths before writing any output.
        artifacts = []
        for item in files:
            parts = relative(item['path'])
            if not parts: raise ValueError('Output must be a file path')
            artifact = self.runtime.workspace.get_artifact(context.session_id, item['artifact_id'])
            artifacts.append(artifact)
        if sum(a.size_bytes for a in artifacts) > MAX_EXPORT: raise ValueError('Batch exceeds 1 GiB')
        results = []
        with open_directory(root) as root_fd:
            for item, artifact in zip(files, artifacts):
                parts = relative(item['path'])
                try:
                    with descend(root_fd, parts[:-1]) as fd:
                        if os.fstatvfs(fd).f_bavail * os.fstatvfs(fd).f_frsize < artifact.size_bytes:
                            raise ValueError('Insufficient destination space')
                        with self.runtime.workspace.artifact_path(artifact).open('rb') as source:
                            result = publish(source, fd, parts[-1], collision=args.get('collision', 'rename'),
                                             expected_sha256=item.get('expected_sha256'),
                                             source_sha256=artifact.content_hash.removeprefix('sha256:'))
                    result.update(artifact_id=artifact.id, path=str(root.joinpath(*parts[:-1], result['name'])))
                except (OSError, ValueError) as error:
                    result = {'artifact_id': artifact.id, 'path': item['path'], 'status': 'failed', 'error': str(error)}
                results.append(result)
        return {'status': 'partial' if any(x['status']=='failed' for x in results) else 'completed', 'files': results,
                'saved': sum(x['status']=='saved' for x in results), 'failed': sum(x['status']=='failed' for x in results)}

    def transfer(self, args, context, *, move=False):
        root = self.directories.root(args, context)
        src, dst = relative(args['source']), relative(args['destination'])
        if not src or not dst or src == dst: raise ValueError('Choose two different file paths')
        with open_directory(root) as root_fd, descend(root_fd, src[:-1]) as sf, descend(root_fd, dst[:-1]) as df:
            with regular_file(sf, src[-1]) as stream:
                before = os.fstat(stream.fileno())
                result = publish(stream, df, dst[-1], collision=args.get('collision', 'rename'),
                                 expected_sha256=args.get('expected_sha256'))
            if move and result['status'] == 'saved':
                # A failed source removal must not obscure the successfully saved destination.
                try:
                    if identity(os.stat(src[-1], dir_fd=sf, follow_symlinks=False)) != identity(before):
                        raise ValueError('Source changed; copied destination retained, source not removed')
                    os.unlink(src[-1], dir_fd=sf); os.fsync(sf)
                    result['source_removed'] = True
                except (OSError, ValueError) as error:
                    result.update(status='partial', source_removed=False, error=str(error))
            result['path'] = str(root.joinpath(*dst[:-1], result['name']))
        return result

    def reveal(self, args, context):
        root = self.directories.root(args, context)
        parts = relative(args.get('path', '.'))
        # Validate every component, including the leaf, before invoking a fixed executable.
        with open_directory(root) as root_fd, descend(root_fd, parts[:-1]) as fd:
            if parts:
                mode = os.stat(parts[-1], dir_fd=fd, follow_symlinks=False).st_mode
                if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)): raise ValueError('Cannot reveal a link or special file')
        if sys.platform != 'darwin': raise ValueError('Finder reveal is supported only on macOS')
        path = str(root.joinpath(*parts))
        subprocess.run(['/usr/bin/open', '-R', path], check=True, timeout=10, capture_output=True)
        return {'status': 'requested', 'path': path, 'note': 'Finder reveal requested; this does not verify a visible window'}


def install(runtime, directories):
    import asyncio
    from ai2apps.services import ServiceInstanceStatus, ServiceRuntimeMode, ToolProviderError
    service = runtime.services.ensure_service(service_key='ai2apps.harness.local-files',
        package_id='ai2apps.harness.local-files', package_version='1', display_name='Harness local file operations',
        runtime_mode=ServiceRuntimeMode.IN_PROCESS, capabilities=('filesystem.read', 'filesystem.write'))
    instance = runtime.services.ensure_instance(service_id=service.id, provider_key='builtin:local-files',
        status=ServiceInstanceStatus.RUNNING, endpoint=None, health={'status':'ok'})
    owner = LocalFiles(runtime, directories)
    text = {'type':'string','minLength':1,'maxLength':4096}
    collision = {'enum':['rename','skip','replace'],'default':'rename'}
    base = {'root':text}
    specs = [
        ('inspect', {'path':text}, [], (), owner.inspect,
         'Inspect a file or directory in the user-named local root. Returns free space, permissions and file SHA-256; no file contents.'),
        ('mkdir', {'path':text}, ['path'], ('write-host',), owner.mkdir,
         'Create an output subdirectory within the user-named existing root. Existing directories are accepted; links are rejected.'),
        ('export', {'files':{'type':'array','minItems':1,'maxItems':64,'items':{'type':'object',
            'properties':{'artifact_id':text,'path':text,'expected_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'}},
            'required':['artifact_id','path'],'additionalProperties':False}},'collision':collision}, ['files'], ('export',), owner.export,
         'Save owned Session artifacts to the user-named local directory, singly or in a batch. Use existing artifact IDs; do not regenerate. Paths are relative, parent directories must exist (use host.directory.mkdir). Default rename avoids overwrite. Replace requires an explicit user overwrite request and an observed destination SHA-256. Returns verified per-file receipts; partial is not full success. Inspect failed destinations before retrying; never blindly replay a batch.'),
        ('copy', {'source':text,'destination':text,'collision':collision,'expected_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'}}, ['source','destination'], ('write-host',), owner.transfer,
         'Copy one regular file within the user-named root. No recursive copy. Default collision policy is rename; replace requires explicit user overwrite request and observed destination hash.'),
        ('move', {'source':text,'destination':text,'collision':collision,'expected_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'}}, ['source','destination'], ('write-host',), lambda a,c:owner.transfer(a,c,move=True),
         'Move or rename one regular file inside the user-named root. Destination bytes are verified before source removal; inspect partial receipts. No recursive move or deletion.'),
        ('reveal', {'path':text}, [], ('host-control',), owner.reveal,
         'Reveal a user-requested local output file or folder in macOS Finder. Only paths within the user-named root. Does not read or execute file contents; a requested reveal is not proof of a visible Finder window.'),
    ]
    for suffix, properties, required, effects, action, description in specs:
        name = 'host.directory.' + suffix
        runtime.services.ensure_tool(service_id=service.id, qualified_name=name, display_name=description.split('.')[0],
            description=description, input_schema={'type':'object','properties':{**base,**properties},
                'required':['root',*required],'additionalProperties':False}, output_schema={'type':'object'},
            effects=effects, timeout_ms=120000)
        async def handler(arguments, context, action=action):
            try:
                await owner.prepare(arguments, context)
                return await asyncio.to_thread(action, arguments, context)
            except (OSError, ValueError, PermissionError, subprocess.SubprocessError) as error:
                raise ToolProviderError(str(error)) from error
        runtime.service_registry.bind_tool(name, provider_key=instance.provider_key, handler=handler)
    return owner
