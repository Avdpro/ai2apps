from types import SimpleNamespace

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from ai2apps.api.imagine_studio import create_imagine_studio_router


def test_catalog_preserves_readiness_and_geometry_without_worker_secrets(monkeypatch):
    def model(name, ready=True, internal=False, kind='image_generation'):
        return SimpleNamespace(
            id=name, display_name=name, model_type=kind,
            metadata={'internal': internal}, checkpoint_ready=ready,
            capabilities=['image_generation', 'image_edit'],
            image_capabilities={'geometry': {'multiple_of': 32}},
            internal_headers={'Authorization': 'private'}, endpoint='private',
        )
    monkeypatch.setattr('ai2apps.api.imagine_studio.list_package_models', lambda _: [
        model('z-image'), model('not-downloaded', False),
        model('internal', internal=True), model('chat', kind='llm'),
    ])
    app = FastAPI()
    app.include_router(create_imagine_studio_router(lambda: None, lambda: object()))
    response = TestClient(app).get('/imagine-studio/models')
    assert response.status_code == 200
    ready, pending = response.json()['data']
    assert ready['id'] == 'z-image'
    assert ready['source_type'] == 'package' and ready['checkpoint_ready']
    assert ready['image_capabilities']['geometry']['multiple_of'] == 32
    assert pending['is_hidden'] and not pending['checkpoint_ready']
    assert 'private' not in response.text


def test_catalog_requires_principal():
    def denied():
        raise HTTPException(status_code=401)
    app = FastAPI()
    app.include_router(create_imagine_studio_router(lambda: None, denied))
    assert TestClient(app).get('/imagine-studio/models').status_code == 401
