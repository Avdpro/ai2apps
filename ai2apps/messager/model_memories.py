"""Bot-owned model memory snapshots. Only model preferences cross delegation."""
import logging
import asyncio
import time
import hashlib
import json
from copy import deepcopy

from ai2apps.model_manager import DEFAULT_MODEL_PURPOSES
from ai2apps.model_preferences import validate


def model_value(value):
    if not isinstance(value, dict) or set(value) != {'purpose', 'profile', 'model'}:
        raise ValueError('Select a model purpose, profile and model')
    if value['purpose'] not in DEFAULT_MODEL_PURPOSES or value['profile'] not in ('normal', 'privacy'):
        raise ValueError('Unknown model purpose or profile')
    if not isinstance(value['model'], str) or not 1 <= len(value['model']) <= 512:
        raise ValueError('Invalid model identifier')
    return dict(value)


class ModelMemories:
    def __init__(self, runtime, directory):
        self.runtime, self.directory = runtime, directory
        self._catalog_lock = asyncio.Lock()
        self._catalog_cache = None

    def catalog_generation(self):
        """Cheap local invalidation; never repeats remote discovery per Tool hop."""
        manager = self.runtime.model_manager
        files = []
        for key in ('cloud_path','defaults_path'):
            path = getattr(manager, key, None)
            try: files.append((key, path.stat().st_mtime_ns))
            except (OSError, AttributeError): files.append((key, None))
        # Registration data is cheap; enumerating resolved package models here
        # would also resolve unrelated worker credentials/checkpoint dependencies.
        packages = tuple(sorted((s.id, str(s.status), hashlib.sha256(json.dumps(
            s.config,sort_keys=True,default=str).encode()).hexdigest())
            for s in self.runtime.services.list_services()
            if s.source == 'installed' and s.config.get('models')))
        policy = json.dumps(manager.cloud_default_policy(),sort_keys=True)
        return (tuple(files), packages, policy)

    async def current_catalog(self):
        from ai2apps.api.model_profiles import model_catalog
        generation = self.catalog_generation()
        async with self._catalog_lock:
            cached = self._catalog_cache
            if cached and cached[0] == generation and time.monotonic() - cached[1] < 120:
                return cached[2]
            models = await model_catalog(None)
            self._catalog_cache = (generation, time.monotonic(), deepcopy(models))
            return models

    def snapshot(self, actor, bot, inherited=None):
        self.directory.scope(actor, {'bot_id': bot})
        routes = []
        for note in self.directory.memory.list(actor, bot)['items']:
            metadata = note.get('metadata') or {}
            if note['deleted'] or metadata.get('kind') != 'model':
                continue
            if getattr(self.directory, 'memory_returns', None) and not self.directory.memory_returns.usable(actor, bot, note['id']):
                continue
            routes.append({**model_value(metadata['value']), 'memory_id': note['id'],
                           'revision': note['revision'], 'bot_id': bot})
        seen = {(r['purpose'], r['profile']) for r in routes}
        for route in (validate(inherited) or {}).get('routes', []):
            if (route['purpose'], route['profile']) not in seen:
                routes.append(route)
                seen.add((route['purpose'], route['profile']))
        return validate({'schema': 'ai2apps.model-preferences/v1', 'routes': routes})

    def capture(self, actor, scope):
        self.directory.scope(actor, {'bot_id': scope['bot_id']})
        if scope.get('dialogue_job'):
            dialogue = self.runtime.messager_dialogue
            job = dialogue.row(dialogue.admissions.get(scope['dialogue_job'], scope['dialogue_job']))
            if job['actor'] != actor or job['bot_id'] != scope['bot_id']:
                raise PermissionError('Model memory task owner changed')
            logical = dialogue.sessions.for_job(job['id'])
            if logical:
                root = dialogue.row(logical['id'])
                if root['actor'] != actor or root['bot_id'] != scope['bot_id']:
                    raise PermissionError('Model memory chain owner changed')
                job = root
            return validate(self.runtime.agents.get_run(job['source_run']).input.get('model_preferences'))
        if scope.get('todo_run_id'):
            context = self.runtime.messager_task_execution.task_context(actor, scope)
            return validate(context['bot_identity'].get('model_preferences'))
        return self.snapshot(actor, scope['bot_id'])

    async def select_model(self, actor, scope, snapshot, purpose, fallback):
        from ai2apps.model_preferences import choose, scope as preference_scope
        from ai2apps.task_llm import effective_profile
        profile = effective_profile(self.runtime)
        if profile == 'privacy':
            fallback = self.runtime.model_manager.resolve_default_model(purpose, profile='privacy')
            if not fallback and not any(r['purpose']==purpose and r['profile']=='privacy'
                                       for r in (snapshot or {}).get('routes', [])):
                raise ValueError('Configure a model for the privacy profile before execution')
        route = next((r for r in (snapshot or {}).get('routes', [])
                      if r['purpose'] == purpose and r['profile'] == profile), None)
        if not route:
            return fallback
        # Model-App remains the source of availability and suitability.
        try:
            choices = catalog_rows(await self.current_catalog(), purpose)
        except Exception:
            logging.getLogger(__name__).warning('Model preference validation unavailable; using profile default', exc_info=True)
            choices = []
        with preference_scope(snapshot):
            model, _ = choose(self.runtime, purpose, fallback, choices=choices, profile=profile)
        if not model and profile == 'privacy':
            raise ValueError('Configure an available model for the privacy profile before execution')
        return model

    async def resolve(self, snapshot):
        snapshot = validate(snapshot)
        if not snapshot or not snapshot['routes']:
            return snapshot
        try:
            models = await self.current_catalog()
        except Exception:
            logging.getLogger(__name__).warning('Model catalog unavailable; using profile defaults', exc_info=True)
            models = {}
        for route in snapshot['routes']:
            model = models.get(route['model'])
            route['available'] = bool(model and compatible(model, route['purpose'])
                and model.get('checkpoint_ready', True) is not False and not model.get('load_failed'))
        return snapshot


def compatible(model, purpose):
    # Same catalog classifier and Agent suitability rule as Model-App defaults.
    from omlx.admin.routes import _supports_default_model_purpose
    from ai2apps.model_capabilities import agent_model_selectable
    return (agent_model_selectable(model) if purpose == 'work_agent'
            else _supports_default_model_purpose(model, purpose))


async def catalog(request, purpose, profile):
    if purpose not in DEFAULT_MODEL_PURPOSES or profile not in ('normal', 'privacy'):
        raise ValueError('Unknown model purpose or profile')
    from ai2apps.api.model_profiles import model_catalog
    models = await model_catalog(request)
    return catalog_rows(models, purpose)


def catalog_rows(models, purpose):
    return [{'id': key, 'label': m.get('name') or m.get('display_name') or key,
             'ready': m.get('checkpoint_ready', True) is not False and not m.get('load_failed')}
            for key, m in models.items() if compatible(m, purpose) and m.get('source_type') != 'hf_cache']
