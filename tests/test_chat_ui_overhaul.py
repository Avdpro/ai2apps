"""Regression guards for the chat UI overhaul follow-up."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHAT_TEMPLATE = ROOT / "ai2apps/web/templates/chat.html"


def test_chat_merges_managed_models_from_admin_catalog():
    chat = CHAT_TEMPLATE.read_text(encoding="utf-8")

    assert "const catalogIds = new Set(catalogModels.map(model => model.id));" in chat
    assert "['cloud', 'fusion'].includes(model.source_type)" in chat
    assert "const allModels = [...catalogModels, ...managedModels];" in chat
I18N_DIR = ROOT / "ai2apps/web/i18n"
TAILWIND_CSS = ROOT / "ai2apps/web/static/css/tailwind.css"

NEW_I18N_KEYS = {
    "chat.clear_search",
    "chat.no_chats_match",
    "chat.pin_chat",
    "chat.unpin_chat",
    "chat.regenerate_creative",
    "chat.regenerate_with",
    "chat.chat_tab",
}


def _template() -> str:
    return CHAT_TEMPLATE.read_text()


def _section(source: str, start: str, end: str) -> str:
    return source.split(start, 1)[1].split(end, 1)[0]


def test_model_markdown_never_mounts_raw_html_in_chat_document():
    html = _template()

    assert "function escapeRawMarkdownHtml(value)" in html
    assert "html(token)" in html
    assert "return escapeRawMarkdownHtml(rawHtml);" in html
    assert ".replace(/</g, '&lt;')" in html
    assert "markedHighlight.markedHighlight" in html


def test_regeneration_overrides_survive_stream_context():
    stream = _section(
        _template(),
        "async streamResponse(streamContext = null, depth = 0)",
        "stopStreaming()",
    )

    assert "_modelOverride: streamContext?._modelOverride ?? null" in stream
    assert "_generationOverride: streamContext?._generationOverride ?? null" in stream
    assert "context._modelOverride || context.model" in stream
    assert "context._generationOverride" in stream


def test_one_off_regeneration_does_not_replace_session_model():
    html = _template()
    stream = _section(
        html,
        "async streamResponse(streamContext = null, depth = 0)",
        "stopStreaming()",
    )
    regenerate = _section(
        html,
        "async regenerateMessage(index, opts = {})",
        "_copyFallback(text)",
    )

    assert "if (!context._modelOverride)" in stream
    assert "model: this.currentModel" in regenerate
    assert "_modelOverride: opts.model || null" in regenerate
    assert "chatSession.messages, context.model" not in stream
    assert "chatSession.messages, chatSession.model" in stream


def test_wheel_listener_is_registered_only_during_scroll_setup():
    html = _template()
    setup = _section(html, "    setupScrollListener() {", "    async downloadChats()")
    scroll = _section(
        html,
        "    scrollToBottom(force = false) {",
        "    forceScrollToBottom() {",
    )

    assert "addEventListener('wheel'" in setup
    assert "addEventListener('wheel'" not in scroll


def test_live_generator_draft_follows_only_when_near_tail():
    html = _template()
    setup = _section(html, "    setupScrollListener() {", "    async downloadChats()")
    stream = _section(
        html,
        "async streamResponse(streamContext = null, depth = 0)",
        "stopStreaming()",
    )

    assert "const threshold = 160" in setup
    reasoning = stream.index("stream.streamingThinking += delta.reasoning_content")
    follow = stream.index("this.scrollToBottom();", reasoning)
    content = stream.index("if (delta?.content)", reasoning)
    assert reasoning < follow < content


def test_chat_history_is_sorted_before_it_is_trimmed():
    save = _section(
        _template(),
        "    saveCurrentChat(",
        "    startRenamingChat(chat)",
    )

    assert save.index("this.sortChatHistory()") < save.index(
        "this.chatHistory.slice(0, MAX_CHAT_HISTORY_SIZE)"
    )
    assert "this.saveChatHistory()" in save


def test_chat_backend_migration_is_idempotent_and_keeps_local_backup():
    html = _template()
    initialize = _section(
        html,
        "    async initializeBackendChat()",
        "    scheduleBackendChatSync(",
    )

    assert "legacy_thread_id: legacy.id" in initialize
    assert "pendingLegacy" in initialize
    assert "CHAT_BACKEND_MIGRATION_KEY" in initialize
    assert "localStorage.removeItem(CHAT_HISTORY_STORAGE_KEY)" not in html
    assert "await this.initializeBackendChat()" in html


def test_chat_browser_state_is_scoped_to_principal_and_member_cannot_claim_legacy():
    html = _template()
    initialize = _section(
        html,
        "    async initializeBackendChat()",
        "    scheduleBackendChatSync(",
    )

    assert "ai2apps_chat_history_v2:${CHAT_PRINCIPAL_ACTOR_ID}" in html
    assert "ai2apps_chat_backend_migrated_v2:${CHAT_PRINCIPAL_ACTOR_ID" in html
    assert "(CHAT_PRINCIPAL_IS_CORE ? localBackup : [])" in initialize
    assert "localStorage.removeItem(LEGACY_API_KEY_STORAGE_KEY)" in html
    assert "localStorage.setItem(API_KEY_STORAGE_KEY" not in html


def test_chat_backend_is_authoritative_with_revisioned_snapshot_sync():
    html = _template()
    sync = _section(
        html,
        "    async performBackendChatSync(chatId)",
        "    loadChatHistory()",
    )

    assert "expected_revision: chat.backendRevision" in sync
    assert "method: 'PUT'" in sync
    assert "messages: (session.messages || []).map" in sync
    assert "this.scheduleBackendChatSync(chatId)" in html
    assert "backendChatSyncState = error?.status === 409 ? 'conflict'" in sync


def test_chat_lifecycle_actions_call_backend_before_local_commit():
    html = _template()
    delete_chat = _section(html, "    async deleteChat(", "    // Clear all history")
    pin_chat = _section(
        html, "    async togglePinChat(chatId)", "    imageLimitReached()"
    )

    assert "await this.flushBackendChatSync(chatId)" in delete_chat
    assert "method: 'DELETE'" in delete_chat
    assert "method: 'PATCH'" in pin_chat
    assert "expected_revision: chat.backendRevision" in pin_chat


def test_chat_navigation_preserves_the_previous_chat_timestamp():
    html = _template()
    start_new = _section(html, "    async startNewChat()", "    async loadChat(chatId)")
    load = _section(
        html,
        "    async loadChat(chatId, { skipBackendSelect = false } = {})",
        "    saveCurrentChat(",
    )
    save = _section(
        html,
        "    saveCurrentChat(",
        "    startRenamingChat(chat)",
    )

    assert "{ touchUpdatedAt: false }" in start_new
    assert "{ touchUpdatedAt: false }" in load
    assert "options.touchUpdatedAt === false && existingChat?.updatedAt" in save
    assert "? existingChat.updatedAt" in save


def test_new_chat_strings_exist_in_every_locale():
    for locale_path in I18N_DIR.glob("*.json"):
        translations = json.loads(locale_path.read_text())
        missing = NEW_I18N_KEYS - translations.keys()
        assert not missing, f"{locale_path.name} is missing {sorted(missing)}"
        assert "{max}" in translations["chat.error.image_too_large"]


def test_tailwind_contains_new_chat_ui_utilities():
    css = TAILWIND_CSS.read_text()

    assert ".max-h-40{" in css
    assert ".z-\\[200\\]{" in css


def test_agent_status_renderer_is_extensible_but_rich_html_fails_to_text():
    html = _template()
    registry = _section(
        html, "class StatusRendererRegistry", "function resolveChatUntitledLabel"
    )
    card = _section(
        html,
        "<!-- AgentRun card anchored beneath its invoking User Message. -->",
        "<!-- Assistant Message -->",
    )

    assert "agentStatusRenderers.register('status-v1'" in registry
    assert "safe-html-v1" in registry
    assert "sandbox-html-v1" in registry
    assert "Rich status content is disabled" in html
    assert "x-html" not in card
    assert "agentStatusView(run).tone" in card
    assert "agentStatusView(run).effect" in card
    assert "prefers-reduced-motion: reduce" in html


def test_agent_run_uses_authenticated_replayable_sse_and_snapshot_convergence():
    html = _template()
    stream = _section(
        html,
        "async connectAgentRunStream(runId)",
        "async cancelAgentRun(runId)",
    )

    assert "Authorization: `Bearer ${apiKey}`" in stream
    assert "?after=${encodeURIComponent(run.lastEventSequence || 0)}" in stream
    assert "this.scheduleAgentRunRefresh" in stream
    assert "this.refreshAgentRun(runId)" in html
    assert "ACTIVE_AGENT_RUNS_STORAGE_KEY" in html
    assert "restoreAgentRunsForChat" in html


def test_chat_turn_supports_direct_model_and_general_agent_modes():
    html = _template()
    send = _section(html, "async sendMessage()", "async streamResponse(")
    agent_start = _section(html, "async startAgentRun(", "async finalizeAgentRun(")

    assert "const useAgent = CHAT_PRINCIPAL_IS_CORE && this.agentMode" in send
    assert "execution_mode: useAgent ? 'agent' : 'chat'" in send
    assert "await this.streamResponse" in send
    assert "_directModelOnly: true" in send
    assert "await this.startAgentRun" in send
    assert "/sessions/${chatId}/agent-runs" in agent_start
    assert "Idempotency-Key" in agent_start
    assert "agent: agentKey || 'ai2apps.general-agent'" in agent_start
    assert "instructions: sourceSystemPrompt" in send
    assert "fetch('/v1/chat/completions'" in html


def test_agent_mode_is_session_scoped_and_exposes_run_controls():
    html = _template()
    metadata = _section(
        html,
        "backendSessionMetadata(chat, session = null)",
        "backendMessagePayload(message)",
    )

    assert "setConversationMode('chat')" in html
    assert "setConversationMode('agent')" in html
    assert "agentMode: source.agentMode ?? chat?.agentMode ?? false" in metadata
    assert "agentKey: source.agentKey ?? chat?.agentKey ?? 'ai2apps.general-agent'" in metadata
    assert "await this.loadAgents()" in html
    assert "setConversationAgent($event.target.value)" in html
    assert "execution_agent: sourceAgentKey" in html
    assert "agentRunName(run)" in html


def test_agent_invocation_ui_is_schema_driven_and_mentions_are_explicit():
    html = _template()
    send = _section(html, "async sendMessage()", "async streamResponse(")

    assert "agent.discoverable !== false" in html
    assert "agentParameterFields(currentAgentKey)" in html
    assert "agent?.invocation_schema" in html
    assert "resolveAgentInvocation(userText)" in send
    assert "source: 'mention'" in html
    assert "agent_invocation_source: invocation.source" in send
    assert "agent_parameters: this.cloneData(agentParameters)" in send
    assert "validateAgentParameters(sourceAgentKey, agentParameters)" in send
    assert "x-html" not in _section(
        html,
        "<details x-show=\"agentMode && agentParameterFields(currentAgentKey).length\"",
        "<!-- Many-images context warning",
    )
    assert "async pauseAgentRun(runId)" in html
    assert "async resumeAgentRun(runId, uncertainResolution = null)" in html
    assert "agentRunCanPause(run)" in html
    assert "agentRunHasUncertainStep(run)" in html


def test_direct_chat_completion_does_not_offer_mcp_tools():
    html = _template()
    body = _section(
        html,
        "buildChatCompletionBody(messages, context, depth = 0)",
        "createThinkingState()",
    )
    stream = _section(html, "async streamResponse(", "async executeToolCalls(")

    assert "!context._directModelOnly" in body
    assert "_directModelOnly: streamContext?._directModelOnly ?? false" in stream


def test_direct_chat_completion_uses_the_currently_selected_model():
    html = _template()
    body = _section(
        html,
        "buildChatCompletionBody(messages, context, depth = 0)",
        "createThinkingState()",
    )

    assert "context._directModelOnly" in body
    assert "this.resolveGatewayModelId(context.model)" in body
    assert "this.resolveApiModel(messages, context.model, variantUserIndex)" in body


def test_agent_interactions_are_schema_driven_and_file_waits_for_resource_handle():
    html = _template()
    card = _section(
        html,
        "<!-- AgentRun card anchored beneath its invoking User Message. -->",
        "<!-- Assistant Message -->",
    )

    assert "agentMenuOptions(interaction)" in card
    assert "submitAgentText(run, interaction)" in card
    assert "decideAgentInteraction(run, interaction, 'approve', 'run')" in card
    assert "decideAgentInteraction(run, interaction, 'approve', 'session')" in card
    assert "decideAgentInteraction(run, interaction, 'approve', 'agent')" in card
    assert "Allow once" in card
    assert "decideAgentInteraction(run, interaction, 'deny')" in card
    assert "submitAgentFile(run, interaction, $event)" in card
    assert "Copied into this Session workspace" in card


def test_parent_agent_card_projects_recursive_child_runs_and_interactions():
    html = _template()
    card = _section(
        html,
        "<!-- AgentRun card anchored beneath its invoking User Message. -->",
        "<!-- Mini-Entries stay anchored",
    )

    assert 'x-for="child in agentRunDescendants(run)"' in card
    assert "pendingAgentInteractions(child)" in card
    assert "pauseAgentRun(child.id)" in card
    assert "cancelAgentRun(child.id)" in card
    assert "agentRunDescendants(run)" in html
    assert "for (const childId of (run.child_run_ids || []))" in html
    assert "if (run.parent_run_id)" in html


def test_empty_thinking_content_is_not_rendered_or_replayed():
    html = _template()
    helper = _section(
        html,
        "            hasVisibleThinking(thinking) {",
        "            snapshotGenerationSettings()",
    )
    message_builder = _section(
        html,
        "            buildMessagesForApi(messages, systemPrompt, opts = {})",
        "            buildChatCompletionBody(messages, context, depth)",
    )
    renderer = _section(
        html,
        "    extractThinking(text) {",
        "    // Efficiently update streaming DOM",
    )
    stream = _section(
        html,
        "async streamResponse(streamContext = null, depth = 0)",
        "stopStreaming()",
    )

    assert "thinking.trim().length > 0" in helper
    assert "this.hasVisibleThinking(thinking) ? thinking : null" in helper
    assert "this.hasVisibleThinking(msg.reasoning_content)" in message_builder
    assert "this.hasVisibleThinking(msg._thinking)" in message_builder
    assert "if (content)" in renderer
    assert "if (!this.hasVisibleThinking(content)) return '';" in renderer
    assert "if (this.hasVisibleThinking(thinkingContent))" in renderer
    assert "&& this.hasVisibleThinking(stream.streamingThinking)" in stream
    assert (
        "reasoning_content: this.hasVisibleThinking(stream.streamingThinking)" in stream
    )
    assert 'x-if="hasVisibleThinking(msg._thinking)"' in html
    assert 'x-show="hasVisibleThinking(currentStream()?.streamingThinking)"' in html


def test_external_review_waits_for_explicit_confirmation_before_replacing_answer():
    html = _template()
    review = _section(
        html,
        "    async externalReviewMessage(index, externalModel)",
        "    _copyFallback(text)",
    )

    assert "External Review in progress" in html
    assert 'class="external-review-dialog fixed inset-0' in html
    assert "z-index: 2147483000" in html
    assert 'class="external-review-dialog__panel rounded-2xl' in html
    assert "width: min(35rem, calc(100vw - 2rem))" in html
    assert "max-height: min(80vh, 48rem)" in html
    assert 'class="external-review-dialog__body custom-scrollbar' in html
    assert "max-h-[40vh] overflow-y-auto" in html
    assert "flex-shrink-0 justify-end" in html
    assert "the answer will not be changed automatically" in html
    assert "status: proposesChange ? 'needs_confirmation' : 'passed'" in review
    assert "msg.content = result.answer" not in review
    assert "applyExternalReviewChange()" in review
    assert "msg.content = review.proposedAnswer" in review
    assert "rejectExternalReviewChange()" in review
    assert "View details" in html
    assert "externalReviewDialog.prompt" in html
    assert "externalReviewDialog.response" in html
    assert "JSON.stringify(result.prompt || [], null, 2)" in review
    assert "Issues found" in html
    assert "externalReviewDialog.explanation" in html
    assert "externalReviewExplanation(result)" in review
    assert "parsed?.explanation" in review
    assert "Add feedback to chat" in html
    assert "addExternalReviewFeedbackToChat()" in review
    assert "_externalReviewFeedback: true" in review


def test_chat_routes_image_models_and_renders_image_output_parts():
    html = _template()
    send = _section(html, "    async sendMessage()", "    async persistGeneratedImage")
    stream = _section(
        html,
        "async streamResponse(streamContext = null, depth = 0)",
        "stopStreaming()",
    )

    assert "imageGenerationModel(sourceModel)" in send
    assert "generateImageResponse" in send
    assert "`/v1/images/${editing ? 'edits' : 'generations'}`" in html
    assert "imageUrlsFromResponseDelta(data, delta)" in stream
    assert "textFromResponseDelta(delta)" in stream
    assert "assistantContentWithImages" in stream
    assert "stream.streamingImages" in stream
    assert "ai2apps_idempotency_key" in html
    assert "ensureCloudRequestKey" in html
    assert "applyCloudLifecycle" in stream
    assert "recoverCloudRequest(stream)" in stream
    assert "/cancel`" in html
    assert "notifyCloudAccountChanged" in html
    assert 'x-init="loadImageElement($el, imgUrl)"' in html
    assert "headers: { 'Authorization': `Bearer ${this.getApiKey()}` }" in html
    assert 'x-html="renderMarkdown(getTextContent(msg.content))"' in html
    assert 'class="max-w-full max-h-[32rem] object-contain rounded-lg cursor-pointer"' in html


def test_image_regeneration_uses_the_image_endpoint():
    regenerate = _section(
        _template(),
        "async regenerateMessage(index, opts = {})",
        "_copyFallback(text)",
    )

    assert "origMsg.meta?.image_generation" in regenerate
    assert "await this.generateImageResponse" in regenerate
    assert "model: opts.model || origMsg.model || this.currentModel" in regenerate
