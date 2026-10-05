"""Opt-in loopback bridge. A revocable credential is scoped to one Todo owner.

This is deliberately not a general runtime API or an execution entry point.
The stdio MCP adapter speaks one bounded JSON line per TCP connection.
"""
import asyncio
import hashlib
import json
import os
import secrets
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from .models import TaskInput, CodexBinding
from .store import now_text

MAX_MESSAGE = 1024 * 1024


class Operation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    arguments: dict = Field(default_factory=dict)
    token: str = Field(min_length=32, max_length=256)


class CodexBridge:
    def __init__(self, store, authorize=None):
        self.store = store
        self.authorize = authorize
        self.root = store.root / "codex-connections"
        self.server = None
        self.credentials = {}
        self.clients = set()
        self.start_lock = asyncio.Lock()

    def config_path(self, owner):
        return self.root / (hashlib.sha256(owner.encode()).hexdigest() + '.json')

    @staticmethod
    def write_config(path, data):
        temp = path.with_suffix('.tmp')
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f)
        os.chmod(temp, 0o600)
        os.replace(temp, path)

    async def start(self):
        async with self.start_lock:
            await self._start()

    async def _start(self):
        if self.server:
            return
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)
        self.server = await asyncio.start_server(self.handle, '127.0.0.1', 0, limit=MAX_MESSAGE)
        port = self.server.sockets[0].getsockname()[1]
        for path in self.root.glob('*.json'):
            try:
                data = json.loads(path.read_text())
                if path != self.config_path(data['owner']) or len(data['token']) < 32:
                    continue
                self.credentials[hashlib.sha256(data['token'].encode()).hexdigest()] = data['owner']
                data['port'] = port
                self.write_config(path, data)
            except (ValueError, KeyError, TypeError):
                continue

    async def connect(self, owner):
        await self.start()
        self.revoke(owner)
        token = secrets.token_urlsafe(48)
        data = {'version': 1, 'host': '127.0.0.1', 'port': self.server.sockets[0].getsockname()[1], 'owner': owner, 'token': token}
        self.write_config(self.config_path(owner), data)
        self.credentials[hashlib.sha256(token.encode()).hexdigest()] = owner
        return self.status(owner)

    def status(self, owner):
        return {'connected': owner in self.credentials.values(), 'config_path': str(self.config_path(owner))}

    def revoke(self, owner):
        self.credentials = {k: v for k, v in self.credentials.items() if v != owner}
        self.config_path(owner).unlink(missing_ok=True)

    async def close(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.server = None
        for client in list(self.clients):
            client.close()
        self.credentials.clear()

    async def handle(self, reader, writer):
        if len(self.clients) >= 32:
            writer.close()
            return
        self.clients.add(writer)
        try:
            raw = await asyncio.wait_for(reader.readline(), 10)
            request = Operation.model_validate_json(raw)
            owner = self.credentials.get(hashlib.sha256(request.token.encode()).hexdigest())
            if owner is None:
                raise ValueError('Connection revoked or invalid; reconnect in Todo')
            if self.authorize:
                self.authorize(owner)
            result = self.call(owner, request.name, request.arguments)
            response = {'result': result}
        except (ValueError, KeyError, TypeError) as e:
            # Do not serialize validation input: it contains the credential.
            response = {'error': str(e) if not isinstance(e, ValueError) or type(e) is ValueError else 'Invalid request'}
        except Exception:
            response = {'error': 'Todo connection unavailable'}
        try:
            writer.write((json.dumps(response, ensure_ascii=False)+'\n').encode())
            await asyncio.wait_for(writer.drain(), 10)
        finally:
            writer.close()
            self.clients.discard(writer)

    def call(self, owner, name, args):
        allowed = {
            'todo_list': {'query','directory_id','priority','thread_id','project_id','offset','limit'},
            'todo_read': {'task_id'},
            'todo_create': {'title','directory_id','parent_id','description','priority'},
            'todo_bind': {'task_id','revision','binding'},
            'todo_update': {'task_id','revision','status','progress','priority','summary'},
        }
        if name not in allowed or set(args) - allowed[name]:
            raise ValueError('Unsupported operation or arguments')
        if name == 'todo_list':
            snapshot = self.store.snapshot(owner)
            tasks = [t for t in snapshot['tasks'] if not t.get('deleted_at') and not t.get('archived_at')]
            by_id = {t['id']: t for t in tasks}
            query = str(args.get('query','')).casefold()
            results = []
            for t in tasks:
                if args.get('directory_id') and t['directory_id'] != args['directory_id']: continue
                if args.get('priority') and t['priority'] != args['priority']: continue
                if query and query not in (t['title']+' '+t['description']).casefold(): continue
                binding, inherited = self.effective_binding(t, by_id)
                if args.get('thread_id') and binding.get('thread_id') != args['thread_id']: continue
                if args.get('project_id') and binding.get('project_id') != args['project_id']: continue
                results.append({k: t.get(k) for k in ('id','title','directory_id','parent_id','status','progress','priority','revision') } | {'codex': binding, 'project_inherited': inherited})
            offset = max(0, int(args.get('offset',0))); limit = max(1,min(100,int(args.get('limit',50))))
            return {'directories': snapshot['directories'], 'tasks': results[offset:offset+limit], 'total': len(results), 'next_offset': offset+limit if offset+limit<len(results) else None}
        if name == 'todo_create':
            values = dict(args)
            if values.get('parent_id'):
                parent = self.store.get(owner, values['parent_id'])
                values['directory_id'] = parent['directory_id']
            if not values.get('directory_id'):
                raise ValueError('Select a directory or parent task first')
            return self.store.save(owner, values)
        task = self.store.get(owner, args['task_id'])
        if name == 'todo_read':
            snap = self.store.snapshot(owner)
            binding, inherited = self.effective_binding(task, {t['id']:t for t in snap['tasks']})
            return {'task': task, 'effective_codex': binding, 'project_inherited': inherited,
                    'attachments': [a for a in snap['attachments'] if a['task_id']==task['id']]}
        if task['revision'] != args.get('revision'):
            raise ValueError('Project changed; read it again before updating')
        data = {k: task[k] for k in TaskInput.model_fields if k in task}
        if name == 'todo_bind':
            data['codex'] = CodexBinding.model_validate(args['binding']).model_dump()
        else:
            for k in ('status','progress','priority'):
                if k in args: data[k] = args[k]
            if 'summary' in args:
                summary = str(args['summary']).strip()
                if not summary or len(summary)>8000: raise ValueError('Summary must be 1–8000 characters')
                data['codex_updates'] = (task.get('codex_updates',[])+[{'at':now_text(),'summary':summary}])[-30:]
        return self.store.save(owner, data, task['id'], task['revision'])

    @staticmethod
    def effective_binding(task, by_id):
        binding = dict(task.get('codex') or {})
        if binding.get('project_id') or binding.get('project_path') or not binding.get('inherit_project',True):
            return binding, False
        seen = {task['id']}; parent = task.get('parent_id')
        while parent and parent not in seen and parent in by_id:
            seen.add(parent); ancestor = by_id[parent]; other = ancestor.get('codex') or {}
            if other.get('project_id') or other.get('project_path'):
                for key in ('project_id','project_name','project_path','host_id'):
                    binding[key] = other.get(key,'')
                return binding, True
            if not other.get('inherit_project',True): break
            parent = ancestor.get('parent_id')
        return binding, False
