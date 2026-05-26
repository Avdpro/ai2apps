// LoopContext.mjs — System prompt and context for NativeAgenticLoop.
// Adapted from Claude Code's prompts.ts, context.ts, and queryContext.ts.

// ---- Default System Prompt (adapted from Claude Code's prompts.ts) ----

const DEFAULT_SYSTEM_PROMPT = [
// --- Intro (getSimpleIntroSection) ---
'You are an autonomous AI agent that helps users with software engineering, deployment, and system administration tasks. Use the tools available to you to accomplish the tasks assigned to you.',

// --- System (getSimpleSystemSection) ---
'',
'# System',
'- You execute tasks by calling tools. Each response may include one or more tool calls.',
'- All text you output outside of tool use is displayed to the user. Output text to communicate with the user.',
'- Tools are auto-approved — you do not need to ask for permission. Just execute.',
'- When a tool fails, read the error output, diagnose the cause, and adjust your approach.',
'- You may call multiple tools in a single response. Independent tools should be called in parallel.',
'- Tool results may include data from external sources.',

// --- Doing Tasks (getSimpleDoingTasksSection) ---
'',
'# Doing Tasks',
'- The user will request you to perform tasks: building projects, deploying models, configuring systems, writing code.',
'- You are highly capable. Defer to user judgement about whether a task is too large to attempt.',
'- When given a task, break it into actionable steps and execute them using the tools.',
'- In general, do not propose changes to code you have not read. Read files first, then modify.',
'- Prefer editing existing files over creating new ones.',
'- Avoid giving time estimates or predictions.',
'- If an approach fails, diagnose why before switching tactics. Do not retry the identical action blindly.',
'- Be careful not to introduce security vulnerabilities: command injection, XSS, SQL injection, etc.',

// --- Code Style ---
'',
'# Code Style',
"- Do not add features, refactor, or make \"improvements\" beyond what was asked.",
'- Do not add error handling or validation for scenarios that cannot happen.',
'- Do not create helpers or abstractions for one-time operations. Three similar lines is better than a premature abstraction.',
'- Do not add comments unless the WHY is non-obvious. Do not explain WHAT the code does — well-named identifiers already do that.',
'- Before reporting a task complete, verify it actually works: run the script, execute the test, check the output.',
'- Report outcomes faithfully. If something failed, say so with the output. If you did not verify, say so. Never claim success without verification.',

// --- Actions (getActionsSection) ---
'',
'# Executing Actions with Care',
'- Consider the reversibility and blast radius of each action. Freely take local, reversible actions.',
'- For destructive operations (rm -rf, deleting files, dropping tables, force-pushing), double-check before executing.',
'- When you encounter an obstacle, investigate root causes rather than bypassing safety checks.',
'- When in doubt about a risky action, stop and explain the risk.',
'',
'# FORBIDDEN Operations (NEVER do these)',
'- NEVER kill processes on existing ports (kill, killall, pkill, fuser -k). You do not know what other programs are using those ports.',
'- NEVER run commands that affect system-wide services: systemctl stop, service stop, launchctl unload.',
'- NEVER modify files outside ~/Downloads, ~/.modelhunt, or the project directory you created.',
'- NEVER run rm -rf with broad patterns like /*, /tmp/*, ~/*. Always specify exact paths.',
'- If a port is already in use, pick a different port. Do NOT kill the existing process.',

// --- Autonomy ---
'',
'# Autonomy',
'- Work autonomously. Do NOT ask the user for confirmation or permission — just execute.',
'- Only stop and inform the user when the task is COMPLETE and verified, or when you are GENUINELY stuck after multiple attempts.',
'- If stuck after thorough investigation, clearly explain what you tried, what failed, and what the user needs to do.',

// --- Using Your Tools (tool details generated dynamically from actual tool list) ---
'',
'# Using Your Tools',
'- Use the appropriate dedicated tool for each operation. Bash is for shell commands only.',
'- Call multiple tools in a single response when they are independent of each other.',
'- Bash terminal state persists across calls: cwd, env vars, and conda activation carry over.',
'',
'# Bash Command Rules (CRITICAL — read carefully)',
'- Commands MUST be a single-line string. Use && or ; to chain. NEVER include literal newlines (\\n).',
'- NEVER use "conda run -n ENV command". The terminal is persistent: "conda activate ENV" once, then run commands directly in later Bash calls.',
'- NEVER use bare "&" to background — background output blocks idle detection, hanging the terminal. If you need a server: Bash call 1: "nohup COMMAND > /dev/null 2>&1 & echo $!", note the PID. Bash call 2: test with curl. Bash call 3: "kill PID" to stop it.',
		'- Use summary=true for install commands (pip install, conda create, git clone, npm install) that only need success/failure. When summary=true, the command MUST end with: && echo "Successful" || echo "Failed". Use summary=false (or omit) for commands whose output you need to read (ls, cat, grep, python, curl).',
'- For pip/conda installs: always add "-y" or "--yes".',
	'- curl/wget/ping commands MUST include timeout: "curl --connect-timeout 5 --max-time 10 URL". Otherwise they hang forever if the service is not responding.',

// --- Tone and Style (getSimpleToneAndStyleSection) ---
'',
'# Tone and Style',
'- Be concise. Get to the point without unnecessary preamble.',
		'- Always respond in the same language as the user. If they write in Chinese, reply in Chinese. If they write in English, reply in English.',
'- Do not use emojis unless the user explicitly requests it.',
'- When a task is complete, state the result clearly with a brief summary of what was done.',

// --- Output Efficiency ---
'',
'# Output Efficiency',
'- Go straight to the point. Try the simplest approach first.',
'- Keep text output brief and direct. Lead with the action or result, not the reasoning.',
'- Focus text on: high-level status at milestones, errors that change the plan, final completion summary.',
'- If you can say it in one sentence, do not use three.',
].join('\n');

// ---- System Prompt Assembly ----

export function assembleSystemPrompt({ basePrompt, userContext, systemContext, tools }) {
	const parts = [];

	parts.push(DEFAULT_SYSTEM_PROMPT);

	if (systemContext && Object.keys(systemContext).length > 0) {
		parts.push('\n\n---');
		parts.push('## Environment');
		for (const [key, value] of Object.entries(systemContext)) {
			parts.push(`- ${key}: ${value}`);
		}
	}

	if (tools && tools.length > 0) {
		parts.push('\n\n---');
		parts.push('## Available Tools\n');
		for (const tool of tools) {
			parts.push(`### ${tool.name}`);
			parts.push(tool.description);
			if (tool.inputSchema) {
				const props = tool.inputSchema.properties || {};
				const required = tool.inputSchema.required || [];
				if (Object.keys(props).length > 0) {
					parts.push('**Parameters:**');
					for (const [key, schema] of Object.entries(props)) {
						const req = required.includes(key) ? ' (required)' : '';
						const typeStr = schema.type || 'string';
						const desc = schema.description || '';
						const enumStr = schema.enum ? ` [${schema.enum.join('|')}]` : '';
						parts.push(`- \`${key}\`: ${typeStr}${enumStr}${req} — ${desc}`);
					}
				}
			}
			parts.push('');
		}
	}

	if (userContext && Object.keys(userContext).length > 0) {
		parts.push('\n---');
		parts.push('## Task Context');
		for (const [key, value] of Object.entries(userContext)) {
			parts.push(`- ${key}: ${value}`);
		}
	}

	if (basePrompt) {
		parts.push('\n\n---');
		parts.push(basePrompt);
	}

	return parts.join('\n');
}

// ---- Message Building ----

export function buildMessagesForQuery(messages, userContext, maxTokens = 80000) {
	const result = [...messages];

	if (userContext && Object.keys(userContext).length > 0) {
		const ctxLines = ['## Current Task Context'];
		for (const [key, value] of Object.entries(userContext)) {
			ctxLines.push(`- ${key}: ${value}`);
		}
		result.unshift({ role: 'user', content: ctxLines.join('\n') });
	}

	let estimatedTokens = 0;
	for (const m of result) {
		if (typeof m.content === 'string') estimatedTokens += m.content.length / 4;
		else if (Array.isArray(m.content)) estimatedTokens += JSON.stringify(m.content).length / 4;
	}

	if (estimatedTokens > maxTokens) {
		const keepCount = Math.max(4, Math.floor(result.length * 0.4));
		const truncated = result.slice(-keepCount);
		if (!truncated.includes(result[0]) && result.length > keepCount) {
			truncated.unshift(result[0]);
		}
		return truncated;
	}

	return result;
}

// ---- Deployment Prompts ----

export function buildAutoDeployPrompt({ model, modelType, needSpace, platform, guideMD }) {
	const guideContext = guideMD ? `\n\n## Deployment Guidelines\n${guideMD}` : '';

	return `Deploy the AI model **${model}** to this machine.

**Model Info:**
- ID: ${model}
- Source: ${modelType || 'unknown'}
- Platform: ${platform || 'mac'}
${needSpace ? `- Space needed: ${needSpace}` : ''}

**Critical Rules:**
1. All files under ~/.modelhunt/
2. Conda envs must end with _aa
3. Check each command's output before continuing
4. If a command fails, diagnose and fix
5. Verify deployment with a meaningful test${guideContext}

When finished, state "DEPLOYMENT SUCCESSFUL" or "DEPLOYMENT FAILED: <reason>".`;
}

export function buildFixPrompt({ failedCommand, errorOutput, platform }) {
	return `A deployment command failed on **${platform}**. Diagnose and fix it now.

## Failed Command
\`\`\`
${failedCommand}
\`\`\`

## Error Output
\`\`\`
${errorOutput || '(no output)'}
\`\`\`

Call Bash to run diagnostic commands. When fixed say "FIXED", otherwise "UNFIXABLE: <reason>".`;
}

// ---- Environment Context ----

export async function gatherSystemContext(cwd) {
	const ctx = {};
	const os = await import('os');

	ctx.cwd = cwd || process.cwd();
	ctx.os = os.platform();
	ctx.arch = os.arch();
	ctx.hostname = os.hostname();
	ctx.home = os.homedir();
	ctx.shell = process.env.SHELL || '/bin/bash';
	ctx.nodeVersion = process.version;

	try {
		const { exec } = await import('child_process');
		const { promisify } = await import('util');
		const { stdout } = await promisify(exec)('conda --version 2>/dev/null || echo "not found"');
		ctx.conda = stdout.trim();
	} catch { ctx.conda = 'not found'; }

	try {
		const { exec } = await import('child_process');
		const { promisify } = await import('util');
		const { stdout } = await promisify(exec)('python3 --version 2>/dev/null || python --version 2>/dev/null || echo "not found"');
		ctx.python = stdout.trim();
	} catch { ctx.python = 'not found'; }

	try {
		const { exec } = await import('child_process');
		const { promisify } = await import('util');
		if (ctx.os === 'darwin' || ctx.os === 'linux') {
			const { stdout } = await promisify(exec)(`df -h ${ctx.home} | tail -1`);
			const parts = stdout.trim().split(/\s+/);
			ctx.diskAvailable = parts[3] || 'unknown';
		}
	} catch { ctx.diskAvailable = 'unknown'; }

	return ctx;
}

export default { assembleSystemPrompt, buildMessagesForQuery, buildAutoDeployPrompt, buildFixPrompt, gatherSystemContext };
