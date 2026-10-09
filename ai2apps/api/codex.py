"""Shared authenticated Codex integration APIs; no Todo dependency."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from ai2apps.api.identity import require_app_capability
from ai2apps.apps.access import APP_CODER_USE
from ai2apps.codex.transport import CodexDesktop


class CodexReplyRequest(BaseModel):
    decision: str | None = None
    answers: dict[str, str] | None = None


def create_codex_router(runtime_provider, principal_provider):
    router = APIRouter(prefix='/codex', tags=['codex'], dependencies=[
        Depends(require_app_capability(principal_provider, APP_CODER_USE))])
    dep = Depends(principal_provider)

    def manager():
        value = getattr(runtime_provider(), 'codex', None)
        if value is None: raise HTTPException(503, 'Codex service is not ready')
        return value

    @router.get('/status')
    async def status(principal=dep):
        return {'available':bool(CodexDesktop.executable()), 'transport':'app-server',
                'project_source':'desktop_metadata_or_conversation_directories'}

    @router.get('/projects')
    async def projects(principal=dep):
        try: return await manager().projects()
        except (ValueError, OSError, TimeoutError) as error:
            raise HTTPException(503, str(error) or 'Codex connection timed out') from error

    @router.post('/threads/{thread_id}/open')
    async def open_thread(thread_id: str, request: Request, principal=dep):
        if not request.client or request.client.host not in ('127.0.0.1', '::1'):
            raise HTTPException(403, 'Open Codex Desktop from this Mac only')
        from ai2apps.codex.desktop_open import open_conversation
        try:
            return await open_conversation(thread_id)
        except (ValueError, OSError, TimeoutError) as error:
            raise HTTPException(422, str(error) or 'Opening Codex Desktop timed out') from error

    @router.get('/threads')
    async def threads(cwd: str | None = None, cursor: str | None = None, principal=dep):
        try: return await manager().threads(cwd, cursor)
        except (ValueError, OSError, TimeoutError) as error:
            raise HTTPException(503, str(error) or 'Codex connection timed out') from error

    @router.post('/requests/{token}')
    async def reply(token: str, body: CodexReplyRequest, principal=dep):
        try: return manager().reply(principal.actor_user_id, token, body.decision, body.answers)
        except ValueError as error: raise HTTPException(422, str(error)) from error

    return router
