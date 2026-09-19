import asyncio
import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from fastapi import HTTPException
from ai2apps.model_providers import _effective_image_declaration, proxy_package_json
from ai2apps.model_worker import ModelWorkerRequest
from ai2apps.model_worker.image_capabilities import default_image_capabilities, validate_image_capabilities, ImageCapabilitiesError

ROOT = Path(__file__).resolve().parents[1]

@pytest.mark.parametrize("family", ["z-image", "ideogram4", "qwen-image", "flux2-klein"])
def test_compatibility_build_uses_bounded_install_map(tmp_path, family):
    import json
    from ai2apps.packages.contract_v1 import build_package, validate_manifest, PackageContractError
    source = ROOT / f"packages/ai2apps-model-{family}-mlx"
    built = build_package(source, tmp_path / "candidate.ai2service", include_model_install_catalog=False)
    assert "modelInstall" not in built.manifest
    assert "discovery" in built.manifest
    invalid = copy.deepcopy(built.manifest)
    invalid["package"]["version"] = "99.0.0"
    with pytest.raises(PackageContractError, match="modelInstall"):
        validate_manifest(invalid)

@pytest.mark.parametrize("operations,minimum,maximum", [(["image_generation"],0,0),(["image_edit"],1,3),(["image_generation","image_edit"],1,4)])
def test_valid_operation_and_reference_contract(operations,minimum,maximum):
    value=default_image_capabilities()
    value.update(operations=operations,inputs={"reference_images":{"minimum":minimum,"maximum":maximum}})
    assert validate_image_capabilities(value)["inputs"] == value["inputs"]

@pytest.mark.parametrize("minimum,maximum", [(0,3),(2,1),(1,17),(True,3)])
def test_invalid_edit_reference_contract(minimum,maximum):
    value=default_image_capabilities()
    value.update(operations=["image_edit"],inputs={"reference_images":{"minimum":minimum,"maximum":maximum}})
    with pytest.raises(ImageCapabilitiesError): validate_image_capabilities(value)

@pytest.mark.parametrize("family,expected", [("z-image",[["image_generation"]]),("ideogram4",[["image_generation"]]),("qwen-image",[["image_generation"],["image_edit"]]),("flux2-klein",[["image_generation","image_edit"]])])
def test_package_operations_match_model_declarations(family,expected):
    manifest=yaml.safe_load((ROOT/f"packages/ai2apps-model-{family}-mlx/service.yaml").read_text())
    assert [m["image_capabilities"]["operations"] for m in manifest["models"]] == expected
    for model in manifest["models"]:
        image=validate_image_capabilities(model["image_capabilities"])
        assert set(image["operations"]) == set(model["capabilities"]) & {"image_generation","image_edit"}

@pytest.mark.parametrize("family,class_name", [("z-image","ZImageAdapter"),("ideogram4","Ideogram4Adapter")])
def test_unaccepted_edit_rejected_before_model_loading(tmp_path,family,class_name):
    path=ROOT/f"packages/ai2apps-model-{family}-mlx/src/worker_adapter.py"
    spec=importlib.util.spec_from_file_location(f"reject_{family}",path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    adapter=getattr(module,class_name)(SimpleNamespace(),pipeline_factory=lambda **kwargs: pytest.fail("must not load"))
    with pytest.raises(Exception) as error:
        asyncio.run(adapter.invoke(ModelWorkerRequest("image_edit",{"prompt":"edit","imageDataUrls":["data:image/png;base64,AAAA"]},"test",output_root=tmp_path)))
    assert error.value.code == "operation_not_supported"

def test_old_qwen_contract_narrowed_without_mutating_signed_data():
    raw={"id":"ai2apps.model.qwen-image-mlx/edit-2511","capabilities":["image_edit"],"image_capabilities":{"operations":["image_generation","image_edit"]}}
    original=copy.deepcopy(raw)
    effective=_effective_image_declaration(raw)
    assert raw == original
    assert effective["image_capabilities"]["operations"] == ["image_edit"]
    assert effective["image_capabilities"]["inputs"]["reference_images"]["maximum"] == 3

@pytest.mark.parametrize("operation,count", [("image_generation",0),("image_edit",4)])
def test_host_rejects_invalid_operation_or_count_before_scheduler(operation,count):
    model=SimpleNamespace(runtime=None,model_type="image_generation",image_capabilities={"operations":["image_edit"],"inputs":{"reference_images":{"minimum":1,"maximum":3}}},capabilities=["image_edit"])
    with pytest.raises(HTTPException) as error:
        asyncio.run(proxy_package_json(model,operation,{"imageDataUrls":["x"]*count}))
    assert error.value.status_code == 400
