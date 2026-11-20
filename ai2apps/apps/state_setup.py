"""Composition root for trusted App-State owners; no user registration endpoint."""
from threading import RLock
from .app_state import AppStateService

_lock=RLock()


def get_app_state(runtime):
    with _lock:
        if getattr(runtime,'app_state',None) is None:
            service=AppStateService(runtime)
            from ai2apps.studio.app_state import register
            register(service)
            from ai2apps.intelligence.app_state import register as intelligence
            from ai2apps.todo.app_state import register as todo
            from ai2apps.gallery.app_state import register as gallery
            from ai2apps.knowledge.app_state import register as knowledge
            from ai2apps.doc_studio.app_state import register as doc_studio
            for owner in (intelligence,todo,gallery,knowledge,doc_studio):owner(service)
            runtime.app_state=service
        return runtime.app_state
