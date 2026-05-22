// NativeAgenticLoop.mjs — Core agentic loop for AI2Apps.
// Extracted from Claude Code's query.ts architecture and reimplemented natively.
//
// Pattern: async generator that iterates "call model → receive response → execute tools → loop"
// until the model stops calling tools or maxTurns is reached.
//
// Two APIs:
//   nativeAgenticLoop()  — low-level async generator, full control over events
//   runAgenticTask()     — high-level wrapper: terminal setup + loop + output display + cleanup

import { assembleSystemPrompt, buildMessagesForQuery } from './LoopContext.mjs';
import { runTools } from './ToolScheduler.mjs';

// ---- Helpers ----

async function sleep(ms) {
	return new Promise(r => setTimeout(r, ms));
}

function isRetryableError(err) {
	const msg = (err.message || '').toLowerCase();
	if (msg.includes('rate') && msg.includes('limit')) return true;
	if (msg.includes('network')) return true;
	if (msg.includes('timeout')) return true;
	if (msg.includes('econnrefused')) return true;
	if (msg.includes('econnreset')) return true;
	if (msg.includes('429')) return true;
	if (msg.includes('500')) return true;
	if (msg.includes('502')) return true;
	if (msg.includes('503')) return true;
	if (msg.includes('overloaded')) return true;
	if (msg.includes('capacity')) return true;
	return false;
}

// ---- Per-model defaults (tuned for tool-calling accuracy) ----

/**
 * Apply model-specific parameter overrides.
 * Different models need different temp, parallel, and token settings for reliable tool calling.
 */
function applyModelDefaults(model, platform, params) {
	const m = model.toLowerCase();

	// Detect model family
	if (m.includes('deepseek') || m.includes('deep-seek')) {
		params.temperature = Math.min(params.temperature, 0.3);
		params.enable_thinking = false;
	} else if (m.includes('gpt-4o') || m.includes('gpt-4.1')) {
		// defaults are fine
	} else if (m.includes('gpt-4')) {
		params.temperature = Math.min(params.temperature, 0.7);
	} else if (m.includes('gpt-3.5')) {
		params.temperature = Math.min(params.temperature, 0.3);
	} else if (m.includes('claude') || m.includes('opus') || m.includes('sonnet') || m.includes('haiku')) {
		// defaults are fine
	} else if (m.includes('qwen') || m.includes('llama')) {
		params.temperature = Math.min(params.temperature, 0.3);
	}

	// Cap maxTokens for models with smaller context or thinking overhead
	if (m.includes('deepseek') || m.includes('qwen')) {
		params.maxTokens = Math.min(params.maxTokens, 2048);
	}
}

// ---- Low-level: Async Generator Loop ----

/**
 * Native agentic loop — async generator, one event per iteration step.
 *
 * The loop terminates by returning { reason, messages, text? }:
 *   - 'completed': model finished without tool calls
 *   - 'max_turns': exceeded maxTurns
 *   - 'aborted':   abortController was signaled
 *   - 'error':     unrecoverable API error
 */
export async function* nativeAgenticLoop(session, params) {
	const {
		initialMessages = [],
		basePrompt = '',
		userContext = {},
		systemContext = {},
		tools = [],
		model = 'gpt-4o',
		platform = 'OpenRouter',
		maxTurns = 30,
		temperature = 0.7,
		maxTokens = 4096,
		thinkingEnabled = true,
		abortController = null,
		globalContext = {},
	} = params;


	let messages = initialMessages; // direct reference — session persistence depends on this
	let turnCount = 0;
	let totalInputTokens = 0;
	let totalOutputTokens = 0;

	const functionDefs = tools.map(t => ({
		name: t.name,
		description: t.description,
		parameters: t.inputSchema,
	}));
	const stubs = {};
	for (const t of tools) {
		stubs[t.name] = { def: { name: t.name, description: t.description, parameters: t.inputSchema }, func: null };
	}

	const fullSystemPrompt = assembleSystemPrompt({ basePrompt, userContext, systemContext, tools });

	while (turnCount < maxTurns) {
		if (abortController?.signal?.aborted) {
			yield { type: 'progress', text: '任务已取消.' };
			return { reason: 'aborted', messages };
		}

		turnCount++;
		yield { type: 'progress', text: `第 ${turnCount}/${maxTurns} 轮...` };

		let messagesForAPI = [{ role: 'system', content: fullSystemPrompt }];
		messagesForAPI = messagesForAPI.concat(buildMessagesForQuery(messages, {}));

		// Apply model-specific tuning each turn (in case model changes)
		const tuned = { temperature, enable_thinking: thinkingEnabled, maxTokens };
		applyModelDefaults(model, platform, tuned);

		const opts = {
			platform, model,
			temperature: tuned.temperature,
			maxToken: tuned.maxTokens,
			apis: { functions: functionDefs, stubs },
			parallelFunction: true,  // always use tools format (OpenRouter + all models support it)
			enable_thinking: tuned.enable_thinking,
		};

		let response;
		const maxRetries = 3;
		let lastError = null;

		for (let attempt = 0; attempt < maxRetries; attempt++) {
			if (abortController?.signal?.aborted) {
				yield { type: 'progress', text: '任务已取消.' };
				return { reason: 'aborted', messages };
			}
			try {
				response = await session.callHubLLMRaw(opts, messagesForAPI);
				if (response) break;
			} catch (err) {
				lastError = err;
				if (isRetryableError(err) && attempt < maxRetries - 1) {
					const delay = Math.pow(2, attempt) * 1000;
					yield { type: 'progress', text: `API 调用失败，${delay / 1000} 秒后重试 (${attempt + 1}/${maxRetries})...` };
					await sleep(delay);
					continue;
				}
				yield { type: 'error', error: `API 调用失败: ${err.message}` };
				return { reason: 'error', messages, error: err.message };
			}
		}

		if (!response) {
			yield { type: 'error', error: `API 调用失败（已重试 ${maxRetries} 次）: ${lastError?.message || 'unknown'}` };
			return { reason: 'error', messages, error: lastError?.message || 'API call failed' };
		}

		totalInputTokens += response.inputTokens || 0;
		totalOutputTokens += response.outputTokens || 0;

		const assistantText = response.content || '';
		if (assistantText.trim()) {
			yield { type: 'assistant', text: assistantText, tokens: { input: totalInputTokens, output: totalOutputTokens } };
		}

		// Normalize function_call → toolCalls
		if (response.functionCall && !response.toolCalls) {
			const fc = response.functionCall;
			const args = typeof fc.arguments === 'string' ? JSON.parse(fc.arguments) : fc.arguments;
			response.toolCalls = [{ id: `func_${turnCount}`, function: { name: fc.name, arguments: args } }];
		}

		if (!response.toolCalls || response.toolCalls.length === 0) {
			// Like Claude Code: no tool calls = done.
			if (assistantText.trim()) {
				messages.push({ role: 'assistant', content: assistantText });
			}
			return { reason: 'completed', messages, text: assistantText, tokens: { input: totalInputTokens, output: totalOutputTokens } };
		}

		messages.push({ role: 'assistant', content: assistantText, tool_calls: response.toolCalls });

		const toolResultMap = new Map();
		for await (const event of runTools(response.toolCalls, tools, session, globalContext)) {
			yield event;
			if (event.type === 'tool_result' && event.toolResult) {
				toolResultMap.set(event.toolResult.toolCallId, event.toolResult);
			}
		}

		let finished = false;
		let finishStatus = 'success';
		for (const tc of response.toolCalls) {
			const result = toolResultMap.get(tc.id);
			if (result) {
				if (result._finished) {
					finished = true;
					finishStatus = result._status || 'success';
				}
				messages.push({ role: 'tool', tool_call_id: tc.id, name: result.name, content: result.output });
			}
		}
		if (finished) {
			return { reason: 'finished', messages, text: assistantText, finishStatus, tokens: { input: totalInputTokens, output: totalOutputTokens } };
		}
	}

	yield { type: 'progress', text: `达到最大轮次限制 (${maxTurns}).` };
	return { reason: 'max_turns', messages };
}

// ---- High-level: runAgenticTask() ----

/**
 * One-stop wrapper — call this from any agent segment.
 *
 * It handles:
 *   1. Creating a visible xterm terminal in the frontend (via Bash.js with client:true)
 *   2. Gathering system context (OS, conda, python, disk)
 *   3. Running the agentic loop
 *   4. Streaming all output to the appropriate channels:
 *        - Assistant text      → Chat channel (main message area)
 *        - Progress / tool info → Log channel
 *        - Bash commands       → frontend switches to show the xterm terminal
 *   5. Returning { text, reason } for the segment to route
 *
 * Usage in a segment:
 *   let result = await runAgenticTask(session, {
 *       prompt: 'Deploy model X to this machine',
 *       systemPrompt: 'You are a deployment engineer...',
 *       tools: getDeployTools(),
 *       maxTurns: 30,
 *   });
 *   if (result.reason === 'completed') { ... }
 *
 * @returns {{ text: string, reason: string, toolCount: number }}
 */
	export async function runAgenticTask(session, params) {
	const {
		prompt,
		sessionKey = null,
		systemPrompt = '',
		tools = [],
		model = 'gpt-4o',
		platform = 'OpenRouter',
		maxTurns = 20,
		temperature = 0.7,
		userContext = {},
		headerOpts = null,
		cwd = null,
			bashId = null,
	} = params;

	const globalContext = session.globalContext || {};
	const opts = headerOpts || { channel: 'Chat' };
	let finalText = '';
	let finalReason = 'completed';
	let toolCount = 0;

	// ---- Session: persist state across calls ----
	const storeKey = sessionKey ? 'nl_session_' + sessionKey : null;
	let stored;
	if (storeKey) {
		stored = globalContext[storeKey];
	}

	let messages, storedSystemContext;
	if (stored) {
		// Reuse existing session: append new user message
		messages = stored.messages;
		messages.push({ role: 'user', content: prompt });
		storedSystemContext = stored.systemContext;
	} else {
			// New session: use provided bashId or create one
			if (bashId) {
				globalContext.nativeLoopBashId = bashId;
			} else {
				try {
					const args = { bashId: '', action: 'Create', commands: '', options: { client: true, initConda: true } };
					const result = await session.pipeChat('/@AgentBuilder/Bash.js', args, false);
					globalContext.nativeLoopBashId = String(result || '');
				} catch (e) {}
			}

		storedSystemContext = {};
		try {
			const { gatherSystemContext } = await import('./LoopContext.mjs');
			storedSystemContext = await gatherSystemContext(cwd || process.cwd());
		} catch {}

		messages = [{ role: 'user', content: prompt }];
	}

	// ---- Run the loop ----
	for await (const event of nativeAgenticLoop(session, {
		initialMessages: messages,
		basePrompt: systemPrompt,
		userContext,
		systemContext: storedSystemContext,
		tools,
		model,
		platform,
		maxTurns,
		temperature,
		thinkingEnabled: true,
		globalContext,
	})) {
		switch (event.type) {
			case 'assistant':
				finalText += event.text + '\n';
				if (event.text.trim()) {
					try { session.addChatText?.('assistant', event.text.trim(), opts); } catch {}
				}
				break;
			case 'progress':
				// Skip round counts — pure noise for the user
				break;
			case 'tool_progress': {
				const toolName = event.name || '';
				if (toolName === 'Bash' && event.text) {
					try { session.addChatText?.('assistant', event.text, opts); } catch {}
				}
				break;
			}
			case 'tool_result': {
				toolCount++;
				const tr = event.toolResult;
				if (!tr) break;
				if (tr.name === 'TodoWrite' || tr.name === 'Finish' || tr.name === 'AskUser') break;
				if (tr.isError) {
					const preview = (tr.output || '').slice(0, 300);
					try { session.addChatText?.('assistant', '❌ **' + tr.name + '**\n' + preview, opts); } catch {}
				} else if (tr.name === 'Read') {
					// Don't show file content — only confirm what was read
					try { session.addChatText?.('assistant', '已读取文件.', opts); } catch {}
				} else if (tr.name === 'Write' || tr.name === 'Edit') {
					try { session.addChatText?.('assistant', tr.output, opts); } catch {}
				}
				break;
			}
			case 'error':
				try { session.addChatText?.('assistant', '❌ ' + event.error, opts); } catch {}
				break;
		}
	}

	// ---- Save session state ----
	if (storeKey) {
		globalContext[storeKey] = {
			messages,
			systemContext: storedSystemContext,
		};
	}

	return { text: finalText.trim(), reason: finalReason, toolCount };
}

export default { nativeAgenticLoop, runAgenticTask };
