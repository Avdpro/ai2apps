"""Actor-scoped business projections; no raw event or publisher credentials."""
from fastapi import APIRouter, Depends, HTTPException, Query
from ai2apps.api.identity import require_app_capability


def create_business_event_router(runtime_provider, principal_provider):
    router=APIRouter(prefix='/business-events',dependencies=[Depends(require_app_capability(principal_provider,'app.use'))])
    def service():
        selected=getattr(runtime_provider(),'business_events',None)
        if selected is None:
            raise HTTPException(503,'Business event service unavailable')
        return selected
    @router.get('/catalog')
    def catalog():
        return {'items':service().catalog()}
    @router.get('')
    def list_events(after:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=100),event_type:str|None=None,
                    principal=Depends(principal_provider)):
        try:
            return service().list(principal.actor_user_id,after=after,limit=limit,event_type=event_type)
        except ValueError as e:
            raise HTTPException(422,str(e)) from e
    @router.get('/{event_id}')
    def read(event_id:str,principal=Depends(principal_provider)):
        try:
            return service().read(principal.actor_user_id,event_id)
        except (KeyError,PermissionError) as e:
            raise HTTPException(404,'Business event unavailable') from e
    return router
