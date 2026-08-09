from omlx.request import Request, SamplingParams


def _request(**kwargs):
    return Request("r", [1, 2, 3], SamplingParams(), **kwargs)


def test_runtime_cache_namespace_is_exposed():
    request = _request(cache_extra_keys=("flesh", "coding", "head2"))
    assert request.extra_keys_for_cache == ("flesh", "coding", "head2")


def test_runtime_and_vlm_cache_namespaces_compose():
    request = _request(cache_extra_keys=("variant",), vlm_image_hash="image")
    assert request.extra_keys_for_cache == ("variant", "image")


def test_empty_cache_namespace_stays_none():
    assert _request().extra_keys_for_cache is None
