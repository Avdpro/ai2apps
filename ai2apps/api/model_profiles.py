"""Independent model routing profiles; privacy never inherits normal routes."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from ai2apps.api.identity import require_app_capability
from ai2apps.apps.access import APP_SYSTEM_MANAGE

class RoutesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    routes: dict[str, str | None]


def create_model_profiles_router(runtime_provider, principal_provider):
    router = APIRouter(prefix="/model-profiles", dependencies=[
        Depends(require_app_capability(principal_provider, APP_SYSTEM_MANAGE))])

    @router.get("")
    def profiles():
        manager = runtime_provider().model_manager
        return {"profiles": {key: manager.default_models(key) for key in ("normal", "privacy")}}

    @router.put("/privacy")
    async def save(request: RoutesRequest, http_request: Request):
        runtime = runtime_provider()
        # Use the same live catalog and compatibility checks as Normal settings,
        # including local, Fusion and enabled personal/AI2Apps Cloud models.
        catalog = await model_catalog(http_request)
        from omlx.admin.routes import _supports_default_model_purpose
        for purpose, selected in request.routes.items():
            model_id = str(selected or "").strip()
            if not model_id:
                continue
            model = catalog.get(model_id)
            if model is None:
                raise HTTPException(422, "Model is not available: " + model_id)
            if not _supports_default_model_purpose(model, purpose):
                raise HTTPException(422, "Model is not compatible with " + purpose)
        try:
            routes = runtime.model_manager.put_default_models(request.routes, profile="privacy", available_model_ids=set(catalog))
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        return {"defaults": routes, "profile": "privacy"}
    return router


async def model_catalog(request):
    from omlx.admin.routes import list_models
    result = await list_models(request=request, is_admin=True)
    return {str(model['id']): model for model in result['models']}
