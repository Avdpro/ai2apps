from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "ai2apps"


def test_studios_load_shared_package_mini_app_client_and_resume_setup():
    helper = (ROOT / "web/static/js/studio_mini_apps.js").read_text()
    video = (ROOT / "web/static/js/video_studio.js").read_text()
    readaloud = (ROOT / "web/static/js/readaloud.js").read_text()
    imagine = (ROOT / "web/static/js/imagine_studio.js").read_text()
    video_template = (ROOT / "web/templates/system_apps/video_studio.html").read_text()
    readaloud_template = (ROOT / "web/templates/system_apps/readaloud.html").read_text()
    imagine_template = (ROOT / "web/templates/system_apps/imagine_studio.html").read_text()

    assert "/v1/platform/studios/${encodeURIComponent(studioId)}/mini-apps" in helper
    assert "/mini-app-mounts" in helper
    assert "/capabilities`" in helper
    assert "/mini-app-capabilities`" in helper
    assert "async probeAll(studioId)" in helper
    assert "async readiness(studioId)" in helper
    assert "X-AI2Apps-App-Instance" in helper
    assert "item.source === 'package'" in readaloud
    assert "miniApp.source === 'package'" in video
    assert "AI2AppsStudioMiniApps.mount" in video
    assert "AI2AppsStudioMiniApps.mount" in readaloud
    assert "AI2AppsStudioMiniApps.probe" in video
    assert "AI2AppsStudioMiniApps.probe" in readaloud
    assert "AI2AppsCapabilities.ensure" in helper
    assert "async setup(studioId, miniApp)" in helper
    assert "async resumeSetup(studioId, miniApps = [])" in helper
    assert "pendingSetup(studioId)" in helper
    assert "actionId: 'setup-mini-app'" in helper
    assert "setupCurrentMiniApp()" in video
    assert "setupCurrentMiniApp()" in readaloud
    assert "required.every" in video
    assert "required.every" in readaloud
    assert "if (item?.source === 'package') return true" not in readaloud
    assert "if (miniApp?.source === 'package') return true" not in video
    assert "this.currentMiniApp.source === 'package') return" in readaloud
    assert "item.id === miniAppId)?.source === 'package') return" in readaloud
    assert "AI2AppsStudioMiniApps.mount" in imagine
    assert "AI2AppsStudioMiniApps.probe" in imagine
    assert "setupCurrentMiniApp()" in imagine
    assert "required.every" in imagine
    assert "resumeSetup(APP_ID" in video
    assert "resumeSetup(APP_ID" in readaloud
    assert "resumeSetup(APP_ID" in imagine
    assert "pendingSetup(APP_ID)" in video
    assert "pendingSetup(APP_ID)" in readaloud
    assert "pendingSetup(APP_ID)" in imagine
    assert "studio_mini_apps.js" in video_template
    assert "studio_mini_apps.js" in readaloud_template
    assert "studio_mini_apps.js" in imagine_template
    assert "packageMiniAppUrl" in video_template
    assert "packageMiniAppUrl" in readaloud_template
    assert "packageMiniAppUrl" in imagine_template
    assert '<button x-show="!miniAppReady(currentMiniApp)" type="button" class="ra-pipeline-ready"' in readaloud_template
    assert '<button x-show="!miniAppReady(currentMiniApp)" type="button" class="vs-mini-app-ready"' in video_template
    assert "Setup required" in imagine_template
    assert "refreshAllPackageMiniAppReadiness()" in video
    assert "refreshAllPackageMiniAppReadiness()" in readaloud
    assert "refreshAllPackageMiniAppReadiness()" in imagine
    assert "AI2AppsStudioMiniApps?.readiness(APP_ID)" in video
    assert "AI2AppsStudioMiniApps?.readiness(APP_ID)" in readaloud
    assert "AI2AppsStudioMiniApps?.readiness(APP_ID)" in imagine
    assert "currentMiniAppReady?'Dependencies ready':'Setup required'" in imagine_template
    assert 'x-show="currentMiniApp.source===\'package\' && !miniAppReady(currentMiniApp)"' in imagine_template
    assert "function handlePackageMiniAppResize(event)" in helper
    assert "frame.contentWindow === source" in helper
    assert "message?.version !== 1" in helper
    assert "Math.min(20000, Math.max(620" in helper
    assert "frame.style.height = `${height}px`" in helper
    assert "package-auto-height-v1" in video_template
    assert "package-auto-height-v1" in readaloud_template
    assert "package-auto-height-v1" in imagine_template


def test_acpf_groups_repeated_steps_and_keeps_only_step_region_scrollable():
    client = (ROOT / "web/static/js/capability_provisioning.js").read_text()
    styles = (ROOT / "web/static/css/capability_provisioning.css").read_text()

    assert "function groupedSteps(session)" in client
    assert "groups.find(item => item.key === key)" in client
    assert "`×${group.steps.length}`" in client
    assert "stepStateLabels" in client
    assert "acpf-step-state" in client
    assert "acpf-run-header" in client
    assert "acpf-run-scroll" in client
    assert "acpf-run-footer" in client
    assert ".acpf-run-scroll{flex:1 1 auto;min-height:0;overflow-y:auto" in styles
    assert ".acpf-run-sheet{height:" in styles
    assert ".acpf-steps>li.active>i" in styles
    assert ".acpf-steps>li.failed>i" in styles
