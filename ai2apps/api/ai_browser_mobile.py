"""Curated owner Mobile AI Browser operations; no authoring or raw BiDi."""
from fastapi import APIRouter
from ai2apps.web.owner_studio_gateway import restrict_router


def create_ai_browser_mobile_router(runtime_provider, principal_provider):
    from .client import create_client_router
    from .agent_platform import create_agent_platform_router
    from .agent_builder import create_agent_builder_router
    from .studio_mini_apps import create_studio_mini_app_router
    import json
    from pathlib import Path
    rows = json.loads((Path(__file__).resolve().parents[1] / 'web/owner_studio_routes.json').read_text())
    router = APIRouter()
    for name, factory in [('client', create_client_router), ('agent_platform', create_agent_platform_router),
                          ('agent_builder', create_agent_builder_router), ('studio_mini_apps', create_studio_mini_app_router)]:
        child = factory(runtime_provider, principal_provider)
        allowed = {(row['method'], row['path']) for row in rows if row['module'] == name}
        if name == 'studio_mini_apps':
            allowed = {pair for pair in allowed if '/web-agent/' in pair[1] or '/draft' in pair[1]
                       or pair[1].endswith(('/mini-apps', '/mini-app-mounts'))
                       or pair == ('GET', '/v1/platform/studios/{studio_id}/mini-app-mounts/{mount_id}/capabilities')}
        restrict_router(child, allowed)
        router.include_router(child)
    return router
