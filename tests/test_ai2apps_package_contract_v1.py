from __future__ import annotations

import hashlib
import json
import zipfile

import pytest

from ai2apps.packages.contract_v1 import (
    PackageContractError,
    build_package,
    create_signature_envelope,
    generate_publisher_key,
    inspect_package,
    jcs,
    verify_signed_package,
)


def _source(tmp_path):
    source = tmp_path / "hello-app"
    source.mkdir()
    (source / "main.js").write_text("document.body.textContent = 'hello';\n", encoding="utf-8")
    (source / "ai2apps.json").write_text(
        json.dumps(
            {
                "schemaVersion": "ai2apps.package-manifest.v1",
                "package": {
                    "id": "example/hello-world",
                    "type": "app",
                    "version": "1.0.0",
                    "displayName": "Hello World",
                    "description": "Contract fixture",
                    "localizations": {
                        "zh-CN": {
                            "displayName": "你好世界",
                            "description": "合约测试包",
                        }
                    },
                },
                "compatibility": {
                    "ai2apps": ">=0.1.0 <2.0.0",
                    "platforms": ["darwin", "linux", "win32"],
                    "architectures": ["arm64", "x64"],
                },
                "entrypoints": [{"name": "main", "kind": "app", "path": "main.js"}],
                "permissions": [],
                "dependencies": [],
                "files": [],
            }
        ),
        encoding="utf-8",
    )
    return source


def test_jcs_matches_cloud_contract_object_order():
    assert jcs({"z": 1, "a": [True, None, "雪"]}) == '{"a":[true,null,"雪"],"z":1}'
    with pytest.raises(PackageContractError, match="Floating-point"):
        jcs({"unsafe": 1.5})


def test_build_inspect_sign_and_verify(tmp_path):
    archive = tmp_path / "hello.ai2app"
    inspected = build_package(_source(tmp_path), archive)
    assert inspected.manifest["files"][0]["path"] == "main.js"
    assert inspected.manifest["package"]["localizations"]["zh-CN"] == {
        "displayName": "你好世界",
        "description": "合约测试包",
    }
    assert inspected.sha256 == hashlib.sha256(archive.read_bytes()).hexdigest()
    private_pem, public_pem, _fingerprint = generate_publisher_key()
    envelope = create_signature_envelope(
        inspected,
        private_pem,
        publisher_id="147a1705-6d31-4790-9649-e0a57cadbe19",
        publisher_key_id="dfdc93a6-c46a-4b53-b218-6cac99d4e44c",
    )
    verified = verify_signed_package(archive, envelope, public_pem)
    assert verified.manifest["package"]["id"] == "example/hello-world"


def test_invalid_package_localization_is_rejected(tmp_path):
    source = _source(tmp_path)
    manifest_path = source / "ai2apps.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["package"]["localizations"] = {
        "not_a_locale": {"displayName": "Invalid"}
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(PackageContractError) as error:
        build_package(source, tmp_path / "invalid.ai2app")
    assert error.value.code == "manifest_invalid"


def test_os_version_constraints_require_one_platform_and_valid_range(tmp_path):
    source = _source(tmp_path)
    manifest_path = source / "ai2apps.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["compatibility"].update(
        {
            "platforms": ["darwin"],
            "minimumOsVersion": "26.2",
            "maximumOsVersionExclusive": "27.0",
        }
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    inspected = build_package(source, tmp_path / "compatible.ai2app")
    assert inspected.manifest["compatibility"]["minimumOsVersion"] == "26.2"

    manifest["compatibility"]["platforms"] = ["darwin", "linux"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(PackageContractError) as error:
        build_package(source, tmp_path / "ambiguous.ai2app")
    assert error.value.code == "manifest_invalid"


def test_raw_artifact_tamper_is_rejected_before_zip_parse(tmp_path):
    archive = tmp_path / "hello.ai2app"
    inspected = build_package(_source(tmp_path), archive)
    private_pem, public_pem, _fingerprint = generate_publisher_key()
    envelope = create_signature_envelope(
        inspected,
        private_pem,
        publisher_id="147a1705-6d31-4790-9649-e0a57cadbe19",
        publisher_key_id="dfdc93a6-c46a-4b53-b218-6cac99d4e44c",
    )
    archive.write_bytes(archive.read_bytes() + b"tamper")
    with pytest.raises(PackageContractError) as error:
        verify_signed_package(archive, envelope, public_pem)
    assert error.value.code == "artifact_digest_mismatch"


def test_incomplete_index_and_unsafe_zip_are_rejected(tmp_path):
    archive = tmp_path / "broken.ai2app"
    manifest = json.loads((_source(tmp_path) / "ai2apps.json").read_text())
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("ai2apps.json", json.dumps(manifest))
        bundle.writestr("main.js", "ok")
        bundle.writestr("../escape.js", "no")
    with pytest.raises(PackageContractError) as error:
        inspect_package(archive)
    assert error.value.code == "unsafe_archive_path"
