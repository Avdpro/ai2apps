"""Intel Center owns its handoff declaration."""
from ai2apps.agents.app_interactions import InteractionCapability
DECLARATIONS = {
    'intelligence.create_channel': InteractionCapability(
        'intelligence.create_channel', 'ai2apps.intelligence', {
            'type': 'object', 'properties': {
                'name': {'type': 'string', 'maxLength': 80},
                'interests': {'type': 'string', 'maxLength': 3000},
                'excluded': {'type': 'string', 'maxLength': 1000},
            }, 'additionalProperties': False,
        }),
}
