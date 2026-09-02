from pathlib import Path

from ai2apps.apps.system import SYSTEM_APP_MANIFESTS
from omlx.admin.routes import _HOST_APP_ENTRIES, _shell_mount_payload

ROOT = Path(__file__).parents[1]


def test_agents_exposes_browser_sidebar_mini_entry():
    manifest = next(
        item for item in SYSTEM_APP_MANIFESTS if item["id"] == "ai2apps.agents"
    )
    assert manifest["mini_entry"] == {
        "kind": "host",
        "resource": "ai2apps:system/agent-mini",
        "placements": ["sidebar"],
    }
    assert _HOST_APP_ENTRIES["ai2apps:system/agent-mini"] == "/admin/agent-mini"
    payload = _shell_mount_payload(
        None,
        {
            "id": "mount_agent_mini",
            "app_instance_id": "appi_agents",
            "renderer": "host",
            "resource": "ai2apps:system/agent-mini",
            "placement": "sidebar",
            "source": "builtin",
        },
    )
    assert payload["content_url"] == "/admin/agent-mini"


def test_agent_mini_uses_transparent_bidi_and_durable_agent_runs():
    template = (
        ROOT / "ai2apps/web/templates/system_apps/agent_mini.html"
    ).read_text()
    client = (ROOT / "ai2apps/web/static/js/browser_bidi_client.js").read_text()
    mini = (ROOT / "ai2apps/web/static/js/agent_mini.js").read_text()

    assert "agent.mini.run_mode" in template
    assert "agent.mini.build_mode" in template
    assert "agent-page-title" not in template
    assert "agent-page-domain" not in template
    assert "agent.mini.pick" in mini
    assert "/agent-drafts/" in mini
    assert "/agent-draft-runs/" in mini
    assert "/chat-context" in mini
    assert "/knowledge" in mini
    assert "agent-knowledge-bucket" in template
    assert "input.performActions" in client
    assert "script.callFunction" in client
    assert "browsingContext.captureScreenshot" not in client
    assert "AI2AppsRequestBrowserContext" not in client
    assert "image_url:imageUrl" in client
    assert "data-srcset" in client
    assert "agent_confirmation" in mini
    assert "step?.ai && typeof step.ai === 'object'" in mini


def test_agent_mini_rebinds_when_the_sidebar_browser_context_changes():
    client = (ROOT / "ai2apps/web/static/js/browser_bidi_client.js").read_text()
    mini = (ROOT / "ai2apps/web/static/js/agent_mini.js").read_text()

    assert "payload?.type !== 'ai2apps:browser-context'" in client
    assert "applyBrowserContext(event.detail || {})" in mini
    assert "revision !== state.contextRevision" in mini
    assert "await previousClient?.connection?.close()" in mini
    assert "contextIsWebPage" in mini


def test_agent_mini_checks_explicit_interaction_policy_before_target_lookup():
    mini = (ROOT / "ai2apps/web/static/js/agent_mini.js").read_text()

    policy_check = "const requestedPolicy = interactionPolicy(step, null);"
    target_lookup = "const target = await bidi.findTarget(intent(step));"
    interaction_branch = mini.index(
        "} else if (['click', 'delete', 'hover', 'input'].includes(op)) {"
    )
    assert mini.index(policy_check, interaction_branch) < mini.index(
        target_lookup, interaction_branch
    )


def test_agent_mini_keeps_new_and_previewed_drafts_out_of_the_saved_menu():
    mini = (ROOT / "ai2apps/web/static/js/agent_mini.js").read_text()

    create_start = mini.index("async function createDraft(")
    create_end = mini.index("async function openDraft", create_start)
    create_body = mini[create_start:create_end]

    assert "source.authoring = {saved: false}" in create_body
    assert "api('/agent-drafts'" not in create_body
    assert ".filter(savedForMenu)" in mini
    assert "await persistDraft();" in mini
    assert "return persistDraft({explicit: true});" in mini


def test_agent_mini_can_archive_the_current_agent_after_confirmation():
    template = (
        ROOT / "ai2apps/web/templates/system_apps/agent_mini.html"
    ).read_text()
    mini = (ROOT / "ai2apps/web/static/js/agent_mini.js").read_text()

    assert 'id="agent-delete"' in template
    assert "window.confirm(tr('agent.mini.delete_confirm'" in mini
    assert "'/archive'" in mini
    assert "expected_revision: state.draft.revision" in mini
    assert "$('#agent-delete').onclick" in mini
    assert "translationFallbacks" in mini
    assert "$('#agent-delete').textContent = tr('agent.mini.delete')" in mini


def test_agent_mini_notices_are_dismissible_and_expire_by_tone():
    template = (
        ROOT / "ai2apps/web/templates/system_apps/agent_mini.html"
    ).read_text()
    mini = (ROOT / "ai2apps/web/static/js/agent_mini.js").read_text()

    assert 'id="agent-notice-close"' in template
    assert "$('#agent-notice-close').onclick = () => notice('')" in mini
    assert "success: 4000" in mini
    assert "warning: 8000" in mini
    assert "error: 12000" in mini
    assert "window.clearTimeout(noticeTimer)" in mini


def test_agent_mini_hydrates_recipe_run_receipts_before_polling():
    mini = (ROOT / "ai2apps/web/static/js/agent_mini.js").read_text()

    assert "const runId = created.id || created.run_id;" in mini
    assert "await api('/agent-draft-runs/' + encodeURIComponent(runId))" in mini
    assert "renderRun(run);" in mini


def test_agent_mini_renders_completed_run_results_and_restores_the_latest_run():
    template = (
        ROOT / "ai2apps/web/templates/system_apps/agent_mini.html"
    ).read_text()
    mini = (ROOT / "ai2apps/web/static/js/agent_mini.js").read_text()

    assert 'id="agent-run-result"' in template
    assert "function resultFromRun(run)" in mini
    assert "function renderRunResult(run)" in mini
    assert "Array.isArray(result?.items)" in mini
    assert "renderRun(runs.items[0]);" in mini


def test_exploration_clears_a_restored_stale_run_card():
    mini = (ROOT / "ai2apps/web/static/js/agent_mini.js").read_text()

    start = mini.index("async function startExploration(goal)")
    reset = mini.index("renderRun(null);", start)
    exploration_state = mini.index("state.exploration = {", start)

    assert reset < exploration_state
    assert "$('#agent-run-handoff').hidden = true;" in mini


def test_agent_review_uses_stacked_comparison_and_readable_type():
    css = (ROOT / "ai2apps/web/static/css/agent_mini_p0.css").read_text()

    assert ".agent-review-compare {\n    display: grid;\n    grid-template-columns: minmax(0, 1fr);" in css
    assert ".agent-mini {\n    font-size: 14px;" in css
    assert ".agent-review-compare pre," in css
    assert "font-size: 12px;" in css


def test_agent_mini_defaults_to_json_and_only_ai_renders_a_validated_spec():
    template = (
        ROOT / "ai2apps/web/templates/system_apps/agent_mini.html"
    ).read_text()
    mini = (ROOT / "ai2apps/web/static/js/agent_mini.js").read_text()

    assert 'id="agent-result-json"' in template
    assert 'id="agent-result-ai"' in template
    assert "resultMode: 'json'" in mini
    assert "JSON.stringify(result, null, 2)" in mini
    assert "'/presentation'" in mini
    assert "function renderPresentation(result, spec, content)" in mini
    assert "['http:', 'https:'].includes(url.protocol)" in mini
    assert "state.resultMode = 'json'" in mini
    assert "state.run.ephemeral && state.recipe?.id" in mini
    assert "'/agent-recipes/' + encodeURIComponent(state.recipe.id) + '/presentation'" in mini


def test_agent_mini_presentation_images_allow_https_without_referrer():
    routes = (ROOT / "omlx/admin/routes.py").read_text()
    mini = (ROOT / "ai2apps/web/static/js/agent_mini.js").read_text()

    agent_mini_route = routes.split(
        '@router.get("/agent-mini", response_class=HTMLResponse)', 1
    )[1].split('@router.get("/static/{path:path}")', 1)[0]
    assert '"img-src \'self\' data: blob: https:; "' in agent_mini_route
    assert "image.referrerPolicy = 'no-referrer';" in mini


def test_agent_mini_reviews_source_and_ir_before_recipe_commit():
    template = (
        ROOT / "ai2apps/web/templates/system_apps/agent_mini.html"
    ).read_text()
    mini = (ROOT / "ai2apps/web/static/js/agent_mini.js").read_text()

    assert 'id="agent-recipe-review"' in template
    assert 'id="agent-review-source"' in template
    assert 'id="agent-review-ir"' in template
    assert 'id="agent-review-feedback"' in template
    assert 'id="agent-review-approve"' in template
    assert 'id="agent-review-commit"' in template
    assert "function renderRecipeReview()" in mini
    assert "'/review/revisions'" in mini
    assert "'/review/approve'" in mini
    assert "$('#agent-review-commit').hidden = !approved" in mini
    assert "await loadRecipeReview();" in mini


def test_agent_mini_runs_a_bounded_one_step_exploration_timeline():
    template = (
        ROOT / "ai2apps/web/templates/system_apps/agent_mini.html"
    ).read_text()
    mini = (ROOT / "ai2apps/web/static/js/agent_mini.js").read_text()
    client = (ROOT / "ai2apps/web/static/js/browser_bidi_client.js").read_text()

    assert 'id="agent-exploration"' in template
    assert 'id="agent-exploration-timeline"' in template
    assert "async function startExploration(goal)" in mini
    assert "maxSteps: 12" in mini
    assert "'/agent-explorations/next'" in mini
    assert "'/agent-explorations/distill'" in mini
    assert "function explorationActionNeedsConfirmation" in mini
    assert "['open', 'page_access', 'click', 'input', 'hover', 'delete']" in mini
    assert "await execute(step, false" in mini
    assert "'agent.mini.exploration_model': 'Model'" in mini
    assert "'agent.mini.exploration_model': '模型'" in mini
    assert "status.textContent = statusText(exploration.status)" in mini
    assert "status.textContent = statusText(review.status)" in mini
    assert "successful steps`" not in mini
    assert "compiled steps`" not in mini
    assert "async explorationObservation()" in client


def test_agent_mini_pins_sidebar_context_during_browser_orchestration():
    mini = (ROOT / "ai2apps/web/static/js/agent_mini.js").read_text()

    assert "function setContextPinned(pinned)" in mini
    assert "fragment.set('agent_context_lock', '1')" in mini
    assert "fragment.delete('agent_context_lock')" in mini
    assert "async function startExploration(goal) {\n        setContextPinned(true);" in mini
    assert "async function driveRun() {" in mini
    assert "setContextPinned(false);\n        await refreshDrafts()" in mini
