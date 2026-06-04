// ToolScheduler.mjs — Tool execution batching for NativeAgenticLoop.
// Ported from Claude Code's src/services/tools/toolOrchestration.ts.
// Read-only tools run concurrently within a batch; write tools run serially.

/**
 * Format tool arguments into a readable one-line summary.
 * e.g. Bash: "pip install torch", Read: "~/file.txt", Write: "~/out.txt"
 */
function formatToolArgs(name, rawArgs) {
	try {
		const args = typeof rawArgs === 'string' ? JSON.parse(rawArgs) : (rawArgs || {});
		switch (name) {
			case 'Bash': {
				if (args.purpose) return String(args.purpose);
				const cmd = String(args.command || '');
				return cmd.length > 120 ? `$ ${cmd.slice(0, 120)}...` : `$ ${cmd}`;
			}
			case 'Read': {
				const p = String(args.file_path || '');
				return p.length > 80 ? `...${p.slice(-80)}` : p;
			}
			case 'Write': {
				const p = String(args.file_path || '');
				const size = String(args.content || '').length;
				return `${p} (${size} 字符)`;
			}
			case 'Edit': {
				const p = String(args.file_path || '');
				const old = String(args.old_string || '').slice(0, 40);
				return `${p}: "${old}${old.length >= 40 ? '...' : ''}"`;
			}
			case 'Grep': {
				const pattern = String(args.pattern || '');
				const path = String(args.path || '');
				return path ? `${pattern} 在 ${path}` : pattern;
			}
			case 'Glob': {
				return String(args.pattern || '');
			}
			case 'TodoWrite': {
				const todos = args.todos || [];
				const done = todos.filter(t => t.status === 'completed').length;
				return `${done}/${todos.length} tasks done`;
			}
			case 'Finish': {
				return `Status: ${args.status || '?'}`;
			}
			case 'AskUser': {
				return `Ask: ${(args.question || '').slice(0, 60)}`;
			}
			case 'ShowText': {
				return `Display: ${(args.text || '').slice(0, 60)}`;
			}
			case 'ShowFile': {
				return `Show ${args.type || 'file'}: ${(args.file_path || '').slice(-40)}`;
			}
			default:
				return JSON.stringify(args).slice(0, 100);
		}
	} catch {
		return String(rawArgs || '').slice(0, 100);
	}
}

/**
 * Partition tool calls into batches.
 * Consecutive concurrency-safe (read-only) tools share a batch and run concurrently.
 * Each non-concurrency-safe tool gets its own batch (serial execution).
 *
 * Returns an array of { isReadOnly: boolean, tools: ToolCall[] } batches.
 */
export function partitionTools(toolCalls, toolDefinitions) {
	const batches = [];
	const toolMap = new Map();
	for (const t of toolDefinitions) {
		toolMap.set(t.name, t);
	}

	for (const tc of toolCalls) {
		const toolName = tc.function?.name || tc.name || '';
		const tool = toolMap.get(toolName);
		const isSafe = tool?.isConcurrencySafe ?? false;

		if (isSafe && batches.length > 0 && batches[batches.length - 1].isReadOnly) {
			batches[batches.length - 1].tools.push(tc);
		} else {
			batches.push({ isReadOnly: isSafe, tools: [tc] });
		}
	}
	return batches;
}

/**
 * Execute a single tool call.
 */
export async function executeTool(toolCall, toolDefinitions, session, globalContext) {
	const toolName = toolCall.function?.name || toolCall.name || '';
	const toolCallId = toolCall.id || '';

	const tool = toolDefinitions.find(t => t.name === toolName);
	if (!tool) {
		return {
			name: toolName,
			toolCallId,
			output: `Error: Unknown tool "${toolName}". Available tools: ${toolDefinitions.map(t => t.name).join(', ')}`,
			isError: true,
		};
	}

	let input;
	try {
		const rawArgs = toolCall.function?.arguments || toolCall.arguments || '{}';
		input = typeof rawArgs === 'string' ? JSON.parse(rawArgs) : rawArgs;
	} catch {
		return {
			name: toolName,
			toolCallId,
			output: `Error: Invalid JSON arguments for tool "${toolName}".`,
			isError: true,
		};
	}

	try {
		const result = await tool.call(input, { session, globalContext });
		const output = result.output ?? JSON.stringify(result);
		return {
			name: toolName,
			toolCallId,
			output,
			isError: !!result.error,
			_finished: result._finished,
			_status: result._status,
			_purpose: result._purpose,
			_filePath: input.file_path || null,
		};
	} catch (e) {
		return {
			name: toolName,
			toolCallId,
			output: `Tool execution error: ${e.message}`,
			isError: true,
		};
	}
}

/**
 * Run a batch of tool calls and yield progress/results.
 */
export async function* runTools(toolCalls, toolDefinitions, session, globalContext) {
	if (!toolCalls || toolCalls.length === 0) return;

	const batches = partitionTools(toolCalls, toolDefinitions);

	for (const batch of batches) {
		if (batch.isReadOnly) {
			for (const tc of batch.tools) {
				const name = tc.function?.name || tc.name || '?';
				const argsSummary = formatToolArgs(name, tc.function?.arguments || tc.arguments);
				yield { type: 'tool_progress', name, text: argsSummary };
			}
			const results = await Promise.all(
				batch.tools.map(tc => executeTool(tc, toolDefinitions, session, globalContext)),
			);
			for (const result of results) {
				yield { type: 'tool_result', toolResult: result };
			}
		} else {
			for (const tc of batch.tools) {
				const name = tc.function?.name || tc.name || '?';
				const argsSummary = formatToolArgs(name, tc.function?.arguments || tc.arguments);
				yield { type: 'tool_progress', name, text: argsSummary };
				const result = await executeTool(tc, toolDefinitions, session, globalContext);
				yield { type: 'tool_result', toolResult: result };
			}
		}
	}
}

export default { partitionTools, executeTool, runTools };
