"""First-run language follows the host OS; saved choices survive restarts."""

import json
import subprocess
from unittest.mock import patch

import pytest

from omlx.settings import GlobalSettings, UISettings, default_ui_language


@pytest.mark.parametrize("preferred, expected", [
    ('"zh-Hans-CN",\n    "en-US"', "zh"),
    ('"zh-Hant-TW"', "zh"),
    ('"en-US",\n    "zh-Hans"', "en"),
    ('"ja-JP",\n    "zh-Hans"', "en"),
])
def test_macos_primary_language_overrides_terminal_locale(preferred, expected):
    result = subprocess.CompletedProcess([], 0, f"(\n    {preferred}\n)\n")
    with patch("omlx.settings.sys.platform", "darwin"), patch(
        "omlx.settings.subprocess.run", return_value=result
    ), patch.dict("os.environ", {"LANG": "en_US.UTF-8"}, clear=True):
        assert default_ui_language() == expected


@pytest.mark.parametrize("environment, expected", [
    ({"LANG": "zh_CN.UTF-8"}, "zh"),
    ({"LC_ALL": "en_US.UTF-8", "LANG": "zh_CN.UTF-8"}, "en"),
    ({"LC_MESSAGES": "zh_TW.UTF-8", "LANG": "en_US.UTF-8"}, "zh"),
    ({"LANG": "C"}, "en"),
    ({}, "en"),
])
def test_unavailable_system_preferences_fall_back_safely(environment, expected):
    with patch("omlx.settings.sys.platform", "darwin"), patch(
        "omlx.settings.subprocess.run", side_effect=subprocess.TimeoutExpired("defaults", 2)
    ), patch.dict("os.environ", environment, clear=True), patch(
        "omlx.settings.locale.getlocale", return_value=(None, None)
    ):
        assert default_ui_language() == expected


def test_first_launch_saved_choice_and_data_reset(tmp_path):
    with patch("omlx.settings.sys.platform", "linux"), patch.dict(
        "os.environ", {"LANG": "zh_CN.UTF-8"}, clear=True
    ):
        assert GlobalSettings.load(tmp_path).ui.language == "zh"
        assert UISettings.from_dict({}).language == "zh"
        settings_file = tmp_path / "settings.json"
        settings_file.write_text(json.dumps({"ui": {"language": "en"}}))
        assert GlobalSettings.load(tmp_path).ui.language == "en"
        settings_file.unlink()
        assert GlobalSettings.load(tmp_path).ui.language == "zh"
