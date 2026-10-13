"""Package iframe is the sole scroll owner, not its outer workspace."""
from pathlib import Path

def test_package_loading_placeholder_does_not_overlap_frame():
    template = (Path(__file__).resolve().parents[1]/'web/templates/system_apps/imagine_studio.html').read_text()
    # Once the frame owns startup feedback, the host must stop showing its own.
    assert 'x-show="packageMiniAppLoading&&!packageMiniAppUrl&&!packageMiniAppError"' in template
    assert 'x-show="packageMiniAppUrl&&!packageMiniAppError"' in template

def test_imagine_package_scroll_layout():
    css=(Path(__file__).resolve().parents[1]/'web/static/css/studio_mini_apps.css').read_text()
    assert '.vs-shell>.is-mini-app-workspace.package-active{overflow:hidden}' in css
    assert '.is-mini-app-workspace.package-active>.is-package-mini-app{display:flex;flex-direction:column;min-height:0;overflow:hidden}' in css
    assert '.is-mini-app-workspace.package-active .is-package-mini-app-frame{flex:1 1 auto;height:100%;min-height:0}' in css
    assert '.is-mini-app-workspace.package-active .is-package-mini-app-state{flex:1 1 auto;min-height:0}' in css
    assert css.index('.vs-shell>.is-mini-app-workspace.package-active{overflow:hidden}')>css.index('grid-row:1;overflow:auto')


def test_mobile_package_uses_bounded_iframe_not_content_height():
    css=(Path(__file__).resolve().parents[1]/'web/static/css/studio_mobile.css').read_text()
    rule='.sm-mobile[data-sm-page=create] [data-sm-panel=create].is-mini-app-workspace.package-active{display:flex!important;flex-direction:column;overflow:hidden}'
    assert rule in css
    assert css.index(rule)>css.index('[data-sm-panel=output]{display:block!important}')
    assert '.sm-mobile .is-mini-app-workspace.package-active>.is-package-mini-app{flex:1 1 0;min-height:0}' in css
    # !important beats the SDK's inline content-height notification; zero
    # flex-basis lets the frame fill the bounded remainder beneath the header.
    assert '.sm-mobile .is-mini-app-workspace.package-active .is-package-mini-app-frame{flex:1 1 0;height:0!important;min-height:0}' in css
