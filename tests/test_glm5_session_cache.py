from types import SimpleNamespace

from omlx.patches.glm5_next_cache.session_cache import Glm5SessionCacheController


class _FakeCache:
    def __init__(self):
        self.value = "cold"
        self.restored = []

    def session_snapshot(self):
        return {"main": {3: (self.value,)}, "tail": {}}

    def restore_session(self, snapshot):
        self.value = snapshot["main"][3][0]
        self.restored.append(self.value)
        return {"experts_loaded": 7, "bytes_loaded": 70, "seconds": 0.25}


def _owner(cache):
    block = SimpleNamespace(dynamic_cache=cache)
    model = SimpleNamespace(layers=[SimpleNamespace(mlp=block)])
    return SimpleNamespace(_vlm_model=SimpleNamespace(language_model=SimpleNamespace(model=model)))


def test_session_l1_snapshots_and_physically_restores_returning_chat():
    cache = _FakeCache()
    controller = Glm5SessionCacheController(_owner(cache), max_sessions=2)

    controller.prepare("chat-a")
    cache.value = "a-hot"
    controller.finish("chat-a")

    controller.prepare("chat-b")
    cache.value = "b-hot"
    controller.finish("chat-b")

    result = controller.prepare("chat-a")

    assert cache.value == "a-hot"
    assert cache.restored == ["a-hot"]
    assert result["experts_loaded"] == 7
    assert controller.stats()["restores"] == 1


def test_session_l1_lru_bounds_saved_metadata():
    cache = _FakeCache()
    controller = Glm5SessionCacheController(_owner(cache), max_sessions=2)

    for session in ("a", "b", "c"):
        controller.prepare(session)
        cache.value = session
        controller.finish(session)

    assert len(controller.snapshots) == 2
    assert "a" not in controller.snapshots
