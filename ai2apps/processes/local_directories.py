"""Harness-owned, user-request-scoped host directory reads and material imports.

The App grant permits this operation; the trusted owner request fixes its path.
No model argument, file content, symlink or assistant history can widen that root.
"""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
import mimetypes
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tempfile

from ai2apps.api.ownership import authorize_session
from ai2apps.services import (ServiceInstanceStatus, ServiceRuntimeMode, ToolProviderError)
from ai2apps.services.aaat import principal_for
from ai2apps.services.capability_routing import CapabilityInvocationError

TOOLS = ('host.directory.list', 'host.directory.import')
MAX_FILE = 64 * 1024 * 1024
MAX_BATCH = 256 * 1024 * 1024
MAX_FILES = 64
DESCRIPTION = (
    'Read a local directory explicitly named by the user in this task. '
    'Use root="~/Desktop/Comic" for a user who names Comic on their Desktop, or the exact requested '
    'absolute/home-relative path. Only this root and its descendants are accessible; no symlinks. '
    'List files first, then import selected relative file paths into this task as artifacts. '
    'The source is read-only. Imported artifact IDs can be passed directly to compatible Mini-Apps. '
    'An empty Session workspace says nothing about a user-named host directory. '
    'Do not ask the user to upload files again when this capability can read the specified directory.'
)


def requested_roots(requests, home):
    """Resolve literal paths and named standard-location children, without scanning disk."""
    roots = set()
    locations = {'桌面': 'Desktop', 'desktop': 'Desktop', '文稿': 'Documents',
                 '文档': 'Documents', 'documents': 'Documents', '下载': 'Downloads', 'downloads': 'Downloads'}
    for text in requests:
        # Quoted paths may contain spaces. Unquoted paths end at natural separators.
        paths = re.findall(r'''["'「`]((?:/|~/)[^"'」`\n]+)["'」`]|((?:~/|/Users/|/Volumes/|/tmp/)[^\s，。！？；：<>"'`]+)''', text)
        for quoted, plain in paths:
            value = (quoted or plain).rstrip('.,;:!?）)')
            path = home / value[2:] if value.startswith('~/') else Path(value)
            if '..' not in path.parts and path != Path('/') and path != home:
                roots.add(str(path))
        for name, directory in locations.items():
            # Explicitly named child, e.g. 桌面有个Comic目录, Desktop/Comic,
            # or the Comic folder on my Desktop. Never infer an entire home root.
            patterns = [
                re.escape(name) + r'(?:上面|下面|上方|下方|上边|下边|上|下|里|中|的|有|一个|个|叫|名为|named|called|\s|[/:：]){0,18}[「"\']?([\w.\- ]{1,120}?)[」"\']?(?:目录|文件夹|\s+folder|\s+directory)',
                r'[「"\']?([\w.\-]{1,120})[」"\']?\s+(?:folder|directory)\s+(?:on|in)\s+(?:my\s+|the\s+)?' + re.escape(name),
                re.escape(name) + r'/([\w.\-]{1,120})(?=$|[\s，。！？；])',
            ]
            for pattern in patterns:
                for child in re.findall(pattern, text, re.I):
                    child = child.strip()
                    if child not in ('.', '..') and '/' not in child:
                        roots.add(str(home / directory / child))
    return roots


def relative(value):
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or '\\' in value or '\x00' in value:
        raise PermissionError('Only relative paths inside the requested directory are allowed')
    return path.parts


@contextmanager
def open_directory(path):
    # Component-wise O_NOFOLLOW closes ancestor/root symlink and replacement races.
    if sys.platform == 'darwin':
        # Darwin can reject links in every component of an absolute path
        # atomically with O_NOFOLLOW_ANY (Darwin sys/fcntl.h).
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | 0x20000000)
        try:
            yield fd
        finally:
            os.close(fd)
        return
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = nxt
        yield fd
    finally:
        os.close(fd)


@contextmanager
def descend(root_fd, parts):
    fd = os.dup(root_fd)
    try:
        for part in parts:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = nxt
        yield fd
    finally:
        os.close(fd)


class LocalDirectories:
    def __init__(self, runtime, *, home=None):
        self.runtime = runtime
        self.home = Path(home) if home else Path.home()

    def root(self, arguments, context):
        if not context.session_id or not context.trace_id:
            raise PermissionError('Local directory access requires an owned task')
        authorize_session(self.runtime, principal_for(self.runtime, context), context.session_id)
        requests = self.runtime.app_chat.source_user_requests(context.trace_id, context.session_id)
        value = arguments['root']
        root = self.home / value[2:] if value.startswith('~/') else Path(value)
        if not root.is_absolute() or '..' in root.parts or str(root) not in requested_roots(requests, self.home):
            raise PermissionError('Directory is outside the paths explicitly named by the user in this task')
        return root

    async def prepare(self, arguments, context):
        try:
            self.root(arguments, context)
            for path in arguments.get('files', [arguments.get('path', '.')]):
                relative(path)
        except (PermissionError, ValueError, KeyError) as error:
            raise CapabilityInvocationError('local_directory_scope_denied', str(error), {'phase': 'prepare'}) from error
        return arguments

    def list(self, arguments, context):
        root = self.root(arguments, context)
        with open_directory(root) as parent, descend(parent, relative(arguments.get('path', '.'))) as fd:
            names = sorted(os.listdir(fd), key=lambda name: (name.casefold(), name))
            start, limit = arguments.get('offset', 0), arguments.get('limit', 200)
            items = []
            for name in names[start:start + limit]:
                info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                kind = 'symlink' if stat.S_ISLNK(info.st_mode) else 'directory' if stat.S_ISDIR(info.st_mode) else 'file' if stat.S_ISREG(info.st_mode) else 'special'
                items.append({'name': name, 'path': str(PurePosixPath(arguments.get('path', '.')) / name),
                              'kind': kind, 'size_bytes': info.st_size,
                              'media_type': mimetypes.guess_type(name)[0] if kind == 'file' else None,
                              'readable': kind in ('file', 'directory')})
        return {'root': str(root), 'path': arguments.get('path', '.'), 'items': items,
                'offset': start, 'has_more': start + len(items) < len(names),
                'scope': 'user_requested_directory', 'source_read_only': True}

    def import_files(self, arguments, context):
        root = self.root(arguments, context)
        outputs, total = [], 0
        with open_directory(root) as root_fd, tempfile.TemporaryDirectory(prefix='harness-import-') as temp:
            # Snapshot every source before publishing any input, with bounded reads.
            snapshots = []
            for index, value in enumerate(arguments['files']):
                parts = relative(value)
                if not parts:
                    raise ValueError('Choose a file, not the root directory')
                with descend(root_fd, parts[:-1]) as fd:
                    file_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
                    with os.fdopen(file_fd, 'rb') as source:
                        before = os.fstat(source.fileno())
                        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_FILE:
                            raise ValueError('Only regular files up to 64 MiB can be imported')
                        snapshot = Path(temp) / str(index)
                        size = 0
                        with snapshot.open('wb') as target:
                            while chunk := source.read(min(1024 * 1024, MAX_FILE - size + 1)):
                                size += len(chunk)
                                total += len(chunk)
                                if size > MAX_FILE or total > MAX_BATCH:
                                    raise ValueError('Directory import exceeds its bounded size limit')
                                target.write(chunk)
                        after = os.fstat(source.fileno())
                        if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
                            raise ValueError('Source file changed during import; list and read it again')
                snapshots.append((value, snapshot))
            for value, snapshot in snapshots:
                artifact = self.runtime.workspace.import_artifact(context.session_id, snapshot,
                    name=PurePosixPath(value).name, run_id=context.trace_id,
                    media_type=mimetypes.guess_type(value)[0] or 'application/octet-stream',
                    metadata={'input': True, 'host_directory': str(root), 'relative_path': value})
                outputs.append({'path': value, 'artifact_id': artifact.id, 'filename': artifact.name,
                                'media_type': artifact.media_type, 'size_bytes': artifact.size_bytes,
                                'url': f'/v1/platform/sessions/{context.session_id}/artifacts/{artifact.id}/download'})
        return {'root': str(root), 'status': 'completed', 'files': outputs, 'source_read_only': True}


def install(runtime):
    service = runtime.services.ensure_service(service_key='ai2apps.harness.local-directories',
        package_id='ai2apps.core', package_version='1', display_name='Harness local directories',
        runtime_mode=ServiceRuntimeMode.IN_PROCESS, capabilities=('filesystem.read',))
    instance = runtime.services.ensure_instance(service_id=service.id, provider_key='builtin:local-directories',
        status=ServiceInstanceStatus.RUNNING, endpoint=None, health={'status': 'ok'})
    owner = LocalDirectories(runtime)
    for name in TOOLS:
        importing = name.endswith('import')
        schema = {'type': 'object', 'properties': {'root': {'type': 'string', 'minLength': 1, 'maxLength': 4096}},
                  'required': ['root'], 'additionalProperties': False}
        if importing:
            schema['properties']['files'] = {'type': 'array', 'minItems': 1, 'maxItems': MAX_FILES,
                'uniqueItems': True, 'items': {'type': 'string', 'minLength': 1, 'maxLength': 4096}}
            schema['required'].append('files')
        else:
            schema['properties'].update(path={'type': 'string', 'maxLength': 4096},
                offset={'type': 'integer', 'minimum': 0}, limit={'type': 'integer', 'minimum': 1, 'maximum': 200})
        runtime.services.ensure_tool(service_id=service.id, qualified_name=name,
            display_name='Import local directory files' if importing else 'List local directory',
            description=DESCRIPTION, input_schema=schema, output_schema={'type': 'object'},
            effects=('filesystem.read', 'artifact.create') if importing else ('read',), timeout_ms=120000)
        async def handler(arguments, context, action=owner.import_files if importing else owner.list):
            try:
                return await asyncio.to_thread(action, arguments, context)
            except (OSError, ValueError, PermissionError) as error:
                raise ToolProviderError(str(error)) from error
        runtime.service_registry.bind_tool(name, provider_key=instance.provider_key, handler=handler)
    return owner
