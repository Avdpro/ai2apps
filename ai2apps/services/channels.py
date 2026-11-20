"""Versioned, read-only channel projection over trusted Provider registrations.

No model loop, content cache, permission grant, or alternative business handler.
The initial HTTP host is the authenticated system-management surface only.
"""
from copy import deepcopy
from dataclasses import dataclass, replace

from ai2apps.services.capability_routing import CapabilityInvocationError

PROTOCOL = 'ai2apps.channels/v1'
READ_ROLES = frozenset({'list', 'search', 'read', 'resolve'})


@dataclass(frozen=True)
class ChannelBinding:
    local_id: str
    name: str
    role: str
    content_types: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    interface_version: str = '1'

    def __post_init__(self):
        if (not self.local_id or not self.name or self.role not in READ_ROLES
                or self.interface_version != '1'):
            raise ValueError('Invalid read-only channel binding')


def fail(code, message):
    raise CapabilityInvocationError(code, message, {'phase': 'prepare', 'submitted': False})


@dataclass(frozen=True)
class RepairField:
    name: str
    aliases: tuple[str, ...] = ()
    ai: bool = False
    ai_maximum: int = 20


class ChannelDirectory:
    def __init__(self, runtime):
        self.runtime = runtime
        self.router = runtime.app_capability_router

    def visible(self, context):
        if not context.actor_user_id or not context.installation_id:
            fail('permission_denied', 'Authenticated actor and Installation required')
        # Only currently executable tools: discovery does not grant missing caps.
        tools = {t.qualified_name: t for t in self.runtime.tools.list_tools(context)}
        disabled = self.router.disabled(context.actor_user_id, context.installation_id)
        for provider in tuple(self.router.providers.values()):
            tool = tools.get(provider.capability)
            if (tool is None or provider.id in disabled or not provider.channels
                    or not set(tool.effects).issubset({'read', 'external_read'})
                    or provider.invocation_policy is not None):
                continue
            scope = self.router.execution_scope
            if scope and not scope.provider_visible(context.session_id, provider):
                continue
            for binding in provider.channels:
                yield provider, binding

    def catalog(self, context, *, query='', offset=0, limit=20):
        if offset < 0 or not 1 <= limit <= 100 or len(query) > 500:
            fail('invalid_tool_arguments', 'Invalid channel query or pagination')
        groups = {}
        for provider, binding in self.visible(context):
            key = (provider.app_id, binding.local_id, binding.interface_version)
            row = groups.setdefault(key, {
                'ref': {'owner': provider.app_id, 'local_id': binding.local_id,
                        'interface_version': binding.interface_version},
                'name': binding.name, 'aliases': list(binding.aliases),
                'content_types': list(binding.content_types), 'operations': []})
            row['operations'].append({'role': binding.role, 'provider': provider.id,
                                      'provider_version': provider.version,
                                      'capability': provider.capability})
        words = query.casefold().split()
        rows = [row for _, row in sorted(groups.items())
                if all(word in (' '.join([row['name'], *row['aliases'], *row['content_types']])).casefold()
                       for word in words)]
        page = rows[offset:offset + limit]
        return {'schema': PROTOCOL, 'items': page, 'total': len(rows),
                'next_offset': offset + len(page) if offset + len(page) < len(rows) else None,
                'scope': 'visible_registered_channels', 'coverage': 'static_bindings_only',
                'truncated': offset + len(page) < len(rows)}

    async def invoke(self, context, *, owner, local_id, interface_version,
                     provider_id, provider_version, role, arguments):
        # Identity and Session are supplied by the host, never by arguments.
        if role not in READ_ROLES or interface_version != '1':
            fail('version_conflict', 'Unsupported channel interface or operation')
        selected = [(p, b) for p, b in self.visible(context)
                    if p.id == provider_id and p.app_id == owner and b.local_id == local_id
                    and b.role == role and b.interface_version == interface_version]
        if len(selected) != 1:
            fail('channel_unavailable', 'Channel operation unavailable')
        provider, _ = selected[0]
        if provider.version != provider_version:
            fail('version_conflict', 'Provider version changed; rediscover channel')
        if not isinstance(arguments, dict) or {'provider', 'parameters'} & arguments.keys():
            fail('invalid_tool_arguments', 'Supply owner parameters only, without routing fields')
        pinned = replace(context, pinned_provider=(provider.capability, provider.id, provider.version))
        result = await self.runtime.tools.execute(provider.capability,
            {**deepcopy(arguments), 'provider': provider.id}, context=pinned)
        return {'schema': PROTOCOL, 'invocation_id': result.invocation_id,
                'provider': provider.id, 'provider_version': provider.version,
                'output': result.output}

    async def invoke_repaired(self, context, *, options, **request):
        # Lazy and new-entry-only: legacy routing never initializes a repair loop.
        from .parameter_repair import ReadParameterRepair
        return await ReadParameterRepair(self, context, options).invoke(**request)
