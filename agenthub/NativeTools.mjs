// NativeTools.mjs — Tool definitions for NativeAgenticLoop.
// Ported from Claude Code's tool system (src/Tool.ts, src/tools.ts), implemented on AI2Apps infrastructure.

import { promises as fsp } from 'fs';
import pathLib from 'path';
import { exec } from 'child_process';
import { promisify } from 'util';

const execPromise = promisify(exec);

// ---- Quote normalization (ported from Claude Code FileEditTool/utils.ts) ----

const LEFT_SINGLE = '‘';
const RIGHT_SINGLE = '’';
const LEFT_DOUBLE = '“';
const RIGHT_DOUBLE = '”';

function normalizeQuotes(str) {
	return str
		.replaceAll(LEFT_SINGLE, "'").replaceAll(RIGHT_SINGLE, "'")
		.replaceAll(LEFT_DOUBLE, '"').replaceAll(RIGHT_DOUBLE, '"');
}

function findActualString(fileContent, searchString) {
	if (fileContent.includes(searchString)) return searchString;
	const ns = normalizeQuotes(searchString);
	const nf = normalizeQuotes(fileContent);
	const idx = nf.indexOf(ns);
	if (idx !== -1) return fileContent.substring(idx, idx + searchString.length);
	return null;
}

function preserveQuoteStyle(oldStr, actualOldStr, newStr) {
	if (oldStr === actualOldStr) return newStr;
	let r = newStr;
	if (actualOldStr.includes(LEFT_DOUBLE) || actualOldStr.includes(RIGHT_DOUBLE))
		r = applyCurlyDoubleQuotes(r);
	if (actualOldStr.includes(LEFT_SINGLE) || actualOldStr.includes(RIGHT_SINGLE))
		r = applyCurlySingleQuotes(r);
	return r;
}

function applyCurlyDoubleQuotes(str) {
	let out = '', open = true;
	for (const ch of str) {
		if (ch === '"') { out += open ? LEFT_DOUBLE : RIGHT_DOUBLE; open = !open; }
		else { out += ch; if (ch === '\n') open = true; }
	}
	return out;
}

function applyCurlySingleQuotes(str) {
	let out = '', open = true;
	for (let i = 0; i < str.length; i++) {
		const ch = str[i];
		if (ch === "'") {
			const prev = i > 0 ? str[i-1] : '';
			const next = i < str.length - 1 ? str[i+1] : '';
			if (/\p{L}/u.test(prev) && /\p{L}/u.test(next)) { out += RIGHT_SINGLE; }
			else { out += open ? LEFT_SINGLE : RIGHT_SINGLE; open = !open; }
		} else { out += ch; if (ch === '\n') open = true; }
	}
	return out;
}

// ---- Bash via Bash.js (uses splitShellCommands, idle detection, password handling) ----

async function ensureBashId(session, globalContext) {
	if (globalContext.nativeLoopBashId) return globalContext.nativeLoopBashId;
	try {
		const args = { bashId: '', action: 'Create', commands: '', options: { client: true, initConda: true } };
		const result = await session.pipeChat('/@AgentBuilder/Bash.js', args, false);
		globalContext.nativeLoopBashId = String(result || '');
		return globalContext.nativeLoopBashId || null;
	} catch (e) {
		return null;
	}
}

function truncateOutput(output, maxChars) {
	if (!output || output.length <= maxChars) return output;
	const half = Math.floor(maxChars / 2);
	return output.slice(0, half) + `\n\n... (truncated, ${output.length - maxChars} more chars) ...\n\n` + output.slice(-half);
}

// ---- Tool Definitions ----

export const BashTool = {
	name: 'Bash',
	description: 'Execute a bash command in a persistent terminal. The shell state (cwd, env vars, conda activation) persists between calls. Use for ALL system operations: installing packages, running scripts, managing files, checking system state.',
	inputSchema: {
		type: 'object',
		properties: {
			command: { type: 'string', description: 'The bash command to execute.' },
			purpose: { type: 'string', description: 'What this command does, in natural conversational language. Use the same language as the user (Chinese for Chinese users, English for English users). For example: "正在安装 Flask 和 SQLAlchemy 依赖进行测试" or "Installing Flask and SQLAlchemy dependencies for testing"' },
		},
		required: ['command'],
	},
	isReadOnly: false,
	isConcurrencySafe: false,
	maxResultSizeChars: 30000,

	async call(input, context) {
		const { session, globalContext } = context;
		const bashId = await ensureBashId(session, globalContext);
		if (!bashId) {
			return { output: 'Terminal not available — cannot run bash commands.' };
		}
		// Reject commands with literal newlines — they get split into separate commands
		const command = String(input.command || '');
		if (command.includes('\n')) {
			return { output: 'ERROR: Command contains literal newlines. Each newline creates a separate command that runs independently, breaking the sequence. Use && or ; to chain commands in a SINGLE line instead.', error: 'newlines in command' };
		}
		try {
			const result = await session.pipeChat('/@AgentBuilder/Bash.js', {
				bashId,
				action: 'Command',
				commands: command,
				options: { idleTime: 600000 },
			}, false);
			const output = typeof result === 'string' ? result
				: result?.content ? result.content
				: JSON.stringify(result || '(no output)');
			return { output: truncateOutput(output, this.maxResultSizeChars) };
		} catch (e) {
			return { output: `Bash error: ${e.message}` };
		}
	},
};

export const ReadFileTool = {
	name: 'Read',
	description: 'Read the contents of a file from the filesystem. Returns the file content as text.',
	inputSchema: {
		type: 'object',
		properties: {
			file_path: { type: 'string', description: 'The absolute path to the file to read' },
			offset: { type: 'number', description: 'Optional line number to start reading from' },
			limit: { type: 'number', description: 'Optional max number of lines to read' },
		},
		required: ['file_path'],
	},
	isReadOnly: true,
	isConcurrencySafe: true,
	maxResultSizeChars: 50000,

	async call(input) {
		try {
			let content = await fsp.readFile(input.file_path, 'utf8');
			const lines = content.split('\n');
			if (input.offset && input.limit) content = lines.slice(Math.max(0, input.offset), input.offset + input.limit).join('\n');
			else if (input.offset) content = lines.slice(Math.max(0, input.offset)).join('\n');
			else if (input.limit) content = lines.slice(0, input.limit).join('\n');
			return { output: truncateOutput(content, this.maxResultSizeChars) };
		} catch (e) {
			return { output: `Error reading file: ${e.message}`, error: e.message };
		}
	},
};

export const WriteFileTool = {
	name: 'Write',
	description: 'Write content to a file. Creates parent directories if they do not exist. Overwrites existing files.',
	inputSchema: {
		type: 'object',
		properties: {
			file_path: { type: 'string', description: 'The absolute path to the file to write' },
			content: { type: 'string', description: 'The content to write to the file' },
		},
		required: ['file_path', 'content'],
	},
	isReadOnly: false,
	isConcurrencySafe: false,
	maxResultSizeChars: 2000,

	async call(input) {
		const filePath = input.file_path;
		const content = input.content;
		try {
			await fsp.mkdir(pathLib.dirname(filePath), { recursive: true });
			let oldContent = null;
			let isCreate = false;
			try {
				oldContent = await fsp.readFile(filePath, 'utf8');
				oldContent = oldContent.replaceAll('\r\n', '\n');
			} catch (e) {
				if (e.code === 'ENOENT') { isCreate = true; }
				else { throw e; }
			}
			if (!isCreate && oldContent === content.replaceAll('\r\n', '\n')) {
				return { output: `The file ${filePath} has not been changed.` };
			}
			await fsp.writeFile(filePath, content, 'utf8');
			if (isCreate) {
				return { output: `File created successfully at: ${filePath}` };
			}
			return { output: `The file ${filePath} has been updated successfully.` };
		} catch (e) {
			return { output: `Error writing file: ${e.message}`, error: e.message };
		}
	},
};

export const EditFileTool = {
	name: 'Edit',
	description: 'Perform exact string replacements in an existing file. The edit will FAIL if old_string is not unique — provide more surrounding context to make it unique. Handles curly/straight quote differences automatically.',
	inputSchema: {
		type: 'object',
		properties: {
			file_path: { type: 'string', description: 'The absolute path to the file to modify' },
			old_string: { type: 'string', description: 'The exact text to find and replace' },
			new_string: { type: 'string', description: 'The text to replace it with (must be different from old_string)' },
			replace_all: { type: 'boolean', description: 'Replace all occurrences (default false)' },
		},
		required: ['file_path', 'old_string', 'new_string'],
	},
	isReadOnly: false,
	isConcurrencySafe: false,
	maxResultSizeChars: 2000,

	async call(input) {
		const filePath = input.file_path;
		const oldStr = input.old_string;
		const newStr = input.new_string;
		const replaceAll = input.replace_all || false;

		if (oldStr === newStr) {
			return { output: 'No changes to make: old_string and new_string are exactly the same.', error: 'same strings' };
		}

		try {
			// 1. Read current file
			let fileContent;
			try {
				fileContent = await fsp.readFile(filePath, 'utf8');
				fileContent = fileContent.replaceAll('\r\n', '\n');
			} catch (e) {
				if (e.code === 'ENOENT') {
					if (oldStr === '') {
						await fsp.mkdir(pathLib.dirname(filePath), { recursive: true });
						await fsp.writeFile(filePath, newStr, 'utf8');
						return { output: `File created: ${filePath}` };
					}
					return { output: `File does not exist: ${filePath}`, error: 'not found' };
				}
				throw e;
			}

			// 2. Find actual match (handles curly/straight quote differences)
			const actualOldStr = findActualString(fileContent, oldStr);
			if (!actualOldStr) {
				return { output: `String to replace not found in file (even after quote normalization).\nString: ${oldStr}`, error: 'not found' };
			}

			// 3. Check uniqueness
			const matchCount = fileContent.split(actualOldStr).length - 1;
			if (matchCount > 1 && !replaceAll) {
				return { output: `Found ${matchCount} matches of the string to replace, but replace_all is false. To replace all, set replace_all to true. To replace one, provide more surrounding context.\nString: ${oldStr}`, error: 'not unique' };
			}

			// 4. Preserve quote style from the file
			const actualNewStr = preserveQuoteStyle(oldStr, actualOldStr, newStr);

			// 5. Re-read before writing (staleness guard)
			let currentContent;
			try {
				currentContent = await fsp.readFile(filePath, 'utf8');
				currentContent = currentContent.replaceAll('\r\n', '\n');
			} catch (e) {
				return { output: 'File has been modified since read. Read it again before editing.', error: 'stale' };
			}

			const recheck = findActualString(currentContent, oldStr);
			if (!recheck) {
				return { output: 'File has been modified since read, either by the user or by a linter. Read it again before attempting to write it.', error: 'stale' };
			}

			// 6. Apply edit
			const updated = replaceAll
				? currentContent.replaceAll(recheck, actualNewStr)
				: currentContent.replace(recheck, actualNewStr);

			if (updated === currentContent) {
				return { output: 'Original and edited file match exactly. Failed to apply edit.', error: 'no change' };
			}

			// 7. Write
			await fsp.mkdir(pathLib.dirname(filePath), { recursive: true });
			await fsp.writeFile(filePath, updated, 'utf8');

			if (replaceAll) {
				return { output: `The file ${filePath} has been updated. All ${matchCount} occurrences were replaced.` };
			}
			return { output: `The file ${filePath} has been updated successfully.` };
		} catch (e) {
			return { output: `Error editing file: ${e.message}`, error: e.message };
		}
	},
};

export const GrepTool = {
	name: 'Grep',
	description: 'Search for a pattern (regex) in files under a directory. Returns matching lines with file paths and line numbers.',
	inputSchema: {
		type: 'object',
		properties: {
			pattern: { type: 'string', description: 'The regex pattern to search for' },
			path: { type: 'string', description: 'Directory to search in. Defaults to current working directory.' },
			include: { type: 'string', description: 'Optional file pattern to include (e.g. "*.js")' },
		},
		required: ['pattern'],
	},
	isReadOnly: true,
	isConcurrencySafe: true,
	maxResultSizeChars: 10000,

	async call(input) {
		try {
			const dirPath = input.path || process.cwd();
			const inc = input.include ? ` --include="${input.include}"` : '';
			const cmd = `grep -rn${inc} --color=never "${input.pattern.replace(/"/g, '\\"')}" "${dirPath}" 2>&1 | head -100`;
			const { stdout } = await execPromise(cmd, { timeout: 30000, maxBuffer: 1024 * 1024 });
			return { output: truncateOutput(stdout.trim() || '(no matches)', this.maxResultSizeChars) };
		} catch (e) {
			if (e.code === 1 && !e.stdout) return { output: '(no matches)' };
			return { output: truncateOutput(`${e.stdout || ''}\n${e.stderr || ''}`.trim(), this.maxResultSizeChars) };
		}
	},
};

export const GlobTool = {
	name: 'Glob',
	description: 'Find files matching a glob pattern. Returns a list of matching file paths.',
	inputSchema: {
		type: 'object',
		properties: {
			pattern: { type: 'string', description: 'The glob pattern (e.g. "**/*.js")' },
			path: { type: 'string', description: 'Directory to search in. Defaults to cwd.' },
		},
		required: ['pattern'],
	},
	isReadOnly: true,
	isConcurrencySafe: true,
	maxResultSizeChars: 10000,

	async call(input) {
		try {
			const dirPath = input.path || process.cwd();
			const pattern = input.pattern.replace(/\*\*\//g, '');
			const cmd = `find "${dirPath}" -type f -path "*/${pattern}" 2>&1 | head -100`;
			const { stdout } = await execPromise(cmd, { timeout: 15000, maxBuffer: 1024 * 1024 });
			const files = stdout.trim().split('\n').filter(Boolean);
			return { output: files.length > 0 ? files.join('\n') : '(no files found)' };
		} catch (e) {
			return { output: `Glob error: ${e.message}` };
		}
	},
};

export const TodoWriteTool = {
	name: 'TodoWrite',
	description: 'Use this tool to create and manage a structured task list for your current session. This helps track progress through complex multi-step tasks. Mark each task as completed as soon as it is done. Only ONE task in_progress at a time.',
	inputSchema: {
		type: 'object',
		properties: {
			todos: {
				type: 'array',
				description: 'The full updated todo list',
				items: {
					type: 'object',
					properties: {
						content: { type: 'string', description: 'What needs to be done (imperative form, e.g. "Install dependencies")' },
						status: { type: 'string', enum: ['pending', 'in_progress', 'completed'], description: 'Current status' },
						activeForm: { type: 'string', description: 'Present continuous form shown during execution (e.g. "Installing dependencies")' },
					},
					required: ['content', 'status', 'activeForm'],
				},
			},
		},
		required: ['todos'],
	},
	isReadOnly: true,
	isConcurrencySafe: true,
	maxResultSizeChars: 5000,

	async call(input, context) {
		const { todos } = input;
		const globalContext = context.globalContext || {};
		// Store todos so they persist across turns
		globalContext.todos = todos;

		const pending = todos.filter(t => t.status === 'pending').length;
		const inProgress = todos.filter(t => t.status === 'in_progress').length;
		const completed = todos.filter(t => t.status === 'completed').length;

		let output = `Todo list updated. ${completed} done`;
		if (inProgress > 0) output += `, ${inProgress} in progress`;
		if (pending > 0) output += `, ${pending} pending`;
		output += '.';
		return { output };
	},
};

export const AskUserTool = {
	name: 'AskUser',
	description: 'Ask the user a question and wait for their response. Use this when you are stuck or need clarification. The user\'s reply will be returned as the tool result so you can continue.',
	inputSchema: {
		type: 'object',
		properties: {
			question: { type: 'string', description: 'The question to ask the user.' },
		},
		required: ['question'],
	},
	isReadOnly: true,
	isConcurrencySafe: false,
	maxResultSizeChars: 5000,

	async call(input, context) {
		try {
			const { session } = context;
			session.addChatText?.('assistant', input.question, { channel: 'Chat' });
			const result = await session.askChatInput({ type: 'input', placeholder: '', text: '', allowFile: false, allowEmpty: false });
			const reply = typeof result === 'string' ? result : (result.text || result.prompt || JSON.stringify(result));
			session.addChatText?.('user', reply);
			return { output: reply };
		} catch (e) {
			return { output: `无法获取用户输入: ${e.message}`, error: e.message };
		}
	},
};

export const FinishTool = {
	name: 'Finish',
	description: 'Call this tool when the entire task is COMPLETE and verified, or when you are GENUINELY stuck and cannot proceed. This ends the session and reports the final result to the user.',
	inputSchema: {
		type: 'object',
		properties: {
			result: { type: 'string', description: 'Brief summary of what was accomplished (if successful) or what went wrong (if failed). Include key file paths, commands run, or error details.' },
			status: { type: 'string', enum: ['success', 'failure'], description: 'Whether the task succeeded or failed.' },
		},
		required: ['result', 'status'],
	},
	isReadOnly: true,
	isConcurrencySafe: true,
	maxResultSizeChars: 2000,

	async call(input) {
		return { output: `Task finished. Status: ${input.status}. ${input.result}`, _finished: true, _status: input.status };
	},
};

export const ShowTextTool = {
	name: 'ShowText',
	description: 'Display text or a final result to the user. Use this to show output, summaries, or results of the task. NOT for short status updates — use the assistant text for that.',
	inputSchema: {
		type: 'object',
		properties: {
			text: { type: 'string', description: 'The text to display to the user.' },
		},
		required: ['text'],
	},
	isReadOnly: true,
	isConcurrencySafe: true,
	maxResultSizeChars: 2000,

	async call(input, context) {
		try { context.session.addChatText?.('assistant', input.text, { channel: 'Chat' }); } catch {}
		return { output: `Displayed to user.` };
	},
};

export const ShowFileTool = {
	name: 'ShowFile',
	description: 'Display a file (image, audio, text) to the user. Reads the file and shows it in the chat.',
	inputSchema: {
		type: 'object',
		properties: {
			file_path: { type: 'string', description: 'Absolute path to the file to display.' },
			type: { type: 'string', enum: ['image', 'audio', 'video', 'file'], description: 'Type of file to display.' },
		},
		required: ['file_path', 'type'],
	},
	isReadOnly: true,
	isConcurrencySafe: true,
	maxResultSizeChars: 2000,

	async call(input, context) {
		try {
			const { session } = context;
			const absPath = input.file_path;
			const basename = pathLib.basename(absPath);
			// Verify file exists
			try { await fsp.access(absPath); } catch (e) {
				return { output: `File not found: ${absPath}`, error: 'not found' };
			}
			const data = await fsp.readFile(absPath);
			const saveName = `output_${Date.now()}_${basename}`;
			const savedHubName = await session.saveHubFile(saveName, data);
			const hubUrl = 'hub://' + savedHubName;
			let opts = { channel: 'Chat' };
			let content = '';
			if (input.type === 'image') {
				opts.image = hubUrl;
				content = `Image: ${basename}`;
			} else if (input.type === 'audio') {
				opts.audio = hubUrl;
				content = `Audio: ${basename}`;
			} else if (input.type === 'video') {
				opts.video = hubUrl;
				content = `Video: ${basename}`;
			} else {
				opts.file = hubUrl;
				try {
					const text = data.toString('utf8');
					content = `**${basename}**\n\`\`\`\n${text.slice(0, 5000)}\n\`\`\``;
				} catch {
					content = `File: ${basename} (${data.length} bytes)`;
				}
			}
			session.addChatText?.('assistant', content, opts);
			return { output: `Displayed ${input.type}: ${basename}` };
		} catch (e) {
			return { output: `Error displaying file: ${e.message}`, error: e.message };
		}
	},
};

export function getDeployTools() {
	return [BashTool, ReadFileTool, WriteFileTool, EditFileTool, GrepTool, GlobTool, TodoWriteTool, FinishTool];
}

export function getFixTools() {
	return [BashTool, ReadFileTool, WriteFileTool, EditFileTool, GrepTool, TodoWriteTool, FinishTool];
}

export function getAllTools() {
	return [BashTool, ReadFileTool, WriteFileTool, EditFileTool, GrepTool, GlobTool, TodoWriteTool, ShowTextTool, ShowFileTool, AskUserTool, FinishTool];
}

export default { BashTool, ReadFileTool, WriteFileTool, EditFileTool, GrepTool, GlobTool, TodoWriteTool, ShowTextTool, ShowFileTool, AskUserTool, FinishTool, getDeployTools, getFixTools, getAllTools };
