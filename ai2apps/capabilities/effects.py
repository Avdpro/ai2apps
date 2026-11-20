"""Platform vocabulary for declared tool effects. Effects never grant authority."""

from dataclasses import dataclass
from collections.abc import Iterable


def has_mutating_effects(effects: Iterable[str]) -> bool:
    """Treat a network action as read-only only with an explicit read declaration."""
    values = set(effects)
    if values <= {"read"}:
        return False
    return not ("external_read" in values and values <= {"read", "external_read", "network"})


@dataclass(frozen=True)
class Effect:
    operation: str
    risk: str
    bot_mode: str = 'write'
    special: bool = False
    confirm_once: bool = False
    countdown: bool = False


_READ = Effect('read', 'low', 'read')
_TIMED_READ = Effect('read', 'low', 'read', countdown=True)
_WRITE = Effect('write', 'medium')
_EXTERNAL = Effect('external', 'medium')
_HOST = Effect('write', 'high', special=True)
_CONFIRM_EXTERNAL = Effect('external', 'high', special=True, confirm_once=True)
_CONFIRM_SENSITIVE = Effect('read', 'critical', special=True, confirm_once=True)
_UNKNOWN = Effect('unknown', 'high', special=True, confirm_once=True)

EFFECTS = {
    'read': _TIMED_READ,
    'read-host': Effect('read', 'low', 'read', special=True, countdown=True),
    'workspace.read': _READ,
    'artifact.read': _TIMED_READ,
    'filesystem.read': _READ,
    'external_read': Effect('external', 'medium', 'read', countdown=True),
    'network': Effect('external', 'high', 'read'),
    'write': _WRITE,
    'workspace.write': _WRITE,
    'artifact.write': _WRITE,
    'artifact.create': Effect('write', 'medium', countdown=True),
    'ai.usage': _WRITE,
    'external': Effect('external', 'medium', special=True),
    'export': Effect('external', 'medium', special=True),
    'upload': _EXTERNAL,
    'publish': _CONFIRM_EXTERNAL,
    'send': _CONFIRM_EXTERNAL,
    'delete': Effect('destructive', 'critical', special=True),
    'destructive': Effect('destructive', 'critical', special=True),
    'purchase': Effect('destructive', 'critical', special=True, confirm_once=True),
    'payment': Effect('destructive', 'critical', special=True, confirm_once=True),
    'billing': Effect('external', 'critical', special=True, confirm_once=True),
    'credential': Effect('write', 'critical', special=True, confirm_once=True),
    'credential.read': _CONFIRM_SENSITIVE,
    'settings.network.read': _READ,
    'settings.network.write': Effect('write', 'critical', special=True, confirm_once=True),
    'privileged': Effect('write', 'critical', special=True, confirm_once=True),
    'write-host': _HOST,
    'host-control': _HOST,
    'execute': _HOST,
    'process': _HOST,
    'clipboard': _HOST,
    'browser.interact': Effect('external', 'high', special=True),
    'model.lifecycle': _HOST,
    'task.cancel': _HOST,
    'interact': Effect('external', 'high', special=True),
    'transfer': Effect('external', 'high', special=True),
    'commit': _CONFIRM_EXTERNAL,
    'restricted': Effect('unknown', 'high', special=True, confirm_once=True),
    'unclassified': _UNKNOWN,
}

# Signed and persisted declarations retain conservative behavior until the
# owner maps each operation to an exact effect. These names are not authorable.
LEGACY_EFFECTS = {
    'gallery.write': Effect('write', 'medium', special=True),
    'local_write': _HOST,
    'external_write': Effect('external', 'high', special=True),
    'memory': _HOST,
}

EXACT_EFFECT_CONFIRMATION = 'effect.confirm'


def unknown_effects(effects) -> tuple[str, ...]:
    return tuple(value for value in effects
                 if value == 'unclassified' or (value not in EFFECTS and value not in LEGACY_EFFECTS))


def can_remember_unknown_risk(effects) -> bool:
    unknown = set(unknown_effects(effects))
    return bool(unknown) and not any(effect_profile(value).special for value in effects if value not in unknown)


def effect_profile(effect: str) -> Effect:
    return EFFECTS.get(effect) or LEGACY_EFFECTS.get(effect) or _UNKNOWN


def requires_exact_confirmation(effects) -> bool:
    return any(effect_profile(value).confirm_once for value in effects)


def validate_effect_names(values, *, existing=()) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError('effects must be an array of effect names')
    names = tuple(values)
    if any(not isinstance(value, str) or not value for value in names):
        raise ValueError('effects must contain non-empty strings')
    invalid = set(names) - EFFECTS.keys() - set(existing)
    if invalid:
        raise ValueError(f'Unknown or retired AaAT effects: {sorted(invalid)!r}. '
                         f'Use registered effects: {", ".join(sorted(EFFECTS))}.')
    return tuple(sorted(set(names)))
