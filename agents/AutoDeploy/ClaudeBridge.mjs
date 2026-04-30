// ClaudeBridge — spawns claude-code with MCP terminal_bash tool.
// Built-in Bash disabled via --disallowedTools. MCP server relays commands
// via HTTP to a local bridge server, which executes via AI2Apps PTY terminal.

import { spawn } from 'child_process';
import { writeFile, unlink } from 'fs/promises';
import { join } from 'path';
import { fileURLToPath } from 'url';
import { tmpdir } from 'os';
import { createServer } from 'http';

export async function runClaudeWithSession({
  session,
  prompt,
  systemPrompt,
  cwd,
  onProgress,
}) {
  const globalContext = session.globalContext;
  if (!globalContext) throw new Error('session.globalContext is required');

  // 1) Ensure a PTY bash terminal exists
  const bashId = await ensureBash(session, globalContext);

  // 2) Start local HTTP bridge server (receives bash commands from MCP relay)
  const bridgeServer = createServer(async (req, res) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    if (req.method === 'OPTIONS') return res.end();

    if (req.method === 'POST' && req.url === '/bash') {
      let body = '';
      req.on('data', c => body += c);
      req.on('end', async () => {
        try {
          const { command } = JSON.parse(body);
          const output = await runBashViaPTY(session, bashId, globalContext, command);
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ output }));
        } catch (e) {
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: String(e) }));
        }
      });
      return;
    }

    res.writeHead(404); res.end();
  });

  await new Promise(resolve => bridgeServer.listen(0, '127.0.0.1', resolve));
  const bridgePort = bridgeServer.address()?.port;

  // 3) Write MCP config pointing to McpBashServer (with bridge URL in env)
  const mcpConfigPath = join(tmpdir(), `ai2apps-mcp-${Date.now()}.json`);
  const serverPath = join(
    fileURLToPath(new URL('.', import.meta.url)),
    'McpBashServer.mjs',
  );

  await writeFile(mcpConfigPath, JSON.stringify({
    mcpServers: {
      'ai2apps-terminal': {
        type: 'stdio',
        command: 'node',
        args: [serverPath],
        env: {
          AI2APPS_BRIDGE_URL: `http://127.0.0.1:${bridgePort}`,
          HOME: process.env.HOME || '/tmp',
          PATH: process.env.PATH || '',
        },
      },
    },
  }));

  // 4) Spawn claude-code
  const args = [
    '--print',
    '--verbose',
    '--input-format',  'stream-json',
    '--output-format', 'stream-json',
    '--dangerously-skip-permissions',
    '--mcp-config', mcpConfigPath,
    '--disallowedTools', 'Bash',
  ];
  // System prompt tells Claude Code about terminal_bash (MCP tool)
  const defaultSystemPrompt = [
    'You have access to a "terminal_bash" MCP tool for ALL shell commands. Always use terminal_bash instead of Bash.',
    'Terminal state (cwd, env vars, conda) persists between commands.',
    'IMPORTANT: Do NOT use "conda run -n". Instead, run "conda activate ENV_NAME" once, then run commands directly (e.g. "pip install", "python script.py"). The activated conda environment stays active for all subsequent commands.',
  ].join('\n');
  args.push('--system-prompt', systemPrompt
    ? `${defaultSystemPrompt}\n\n${systemPrompt}`
    : defaultSystemPrompt);

  const child = spawn('claude', args, {
    cwd: cwd || process.env.HOME || '/tmp',
    env: { ...process.env },
    stdio: ['pipe', 'pipe', 'pipe'],
  });

  // 5) Display-only loop (no tool interception)
  return new Promise((resolve) => {
    let assistantText = '';
    let resolved = false;

    async function cleanup() {
      bridgeServer.close();
      try { await unlink(mcpConfigPath); } catch {}
    }

    function finish(success, error) {
      if (resolved) return;
      resolved = true;
      child.kill('SIGTERM');
      setTimeout(() => { if (!child.killed) child.kill('SIGKILL'); }, 5000);
      resolve({ success, output: assistantText, error });
    }

    let buf = '';
    const msgQueue = [];
    let draining = false;

    function enqueue(line) {
      if (!line.trim()) return;
      try { msgQueue.push(JSON.parse(line)); }
      catch {}
    }
    async function drainQueue() {
      if (draining) return;
      draining = true;
      while (msgQueue.length > 0) {
        await handleMessage(msgQueue.shift());
      }
      draining = false;
    }

    child.stdout.on('data', (chunk) => {
      buf += chunk.toString();
      const lines = buf.split('\n');
      buf = lines.pop();
      for (const line of lines) enqueue(line);
      drainQueue();
    });

    function isBashTool(name) {
      return name === 'terminal_bash' || (name && name.includes('terminal_bash'));
    }

    function extractText(content) {
      if (!content) return '';
      if (typeof content === 'string') return content;
      if (Array.isArray(content)) return content.map(b => b.text || '').join('\n');
      return String(content);
    }

    async function handleMessage(msg) {
      switch (msg.type) {
        case 'assistant': {
          const content = msg.message?.content;
          if (Array.isArray(content)) {
            for (const block of content) {
              if (block.type === 'text' && block.text) {
                assistantText += block.text + '\n';
                if (onProgress) onProgress(block.text.trim());
              } else if (block.type === 'tool_use') {
                const name = block.name || '';
                // Skip internal tools
                if (name === 'TodoWrite' || name === 'TaskCreate' || name === 'TaskUpdate') continue;
                if (isBashTool(name)) {
                  if (onProgress) onProgress(`$ ${(block.input?.command || '').slice(0, 120)}`);
                } else if (name === 'Read') {
                  if (onProgress) onProgress(`Read: ${(block.input?.file_path || '').slice(-60)}`);
                } else if (name === 'Write') {
                  if (onProgress) onProgress(`Write: ${(block.input?.file_path || '').slice(-60)}`);
                } else {
                  const label = `${name}: ${JSON.stringify(block.input || {}).slice(0, 120)}`;
                  if (onProgress) onProgress(`[running] ${label}`);
                }
              }
            }
          }
          break;
        }
        case 'user': {
          const content = msg.message?.content;
          if (Array.isArray(content)) {
            for (const block of content) {
              if (block.type !== 'tool_result') continue;
              const text = extractText(block.content);
              if (!text || text.includes('Todos have been modified')) continue;
              // Skip Read results (file content already shown in assistant text)
              // Show bash output compactly
              if (onProgress) onProgress(text.slice(0, 300));
            }
          }
          break;
        }
        case 'result':
          if (onProgress) onProgress(`[done] ${msg.result || msg.subtype || 'done'}`);
          finish(true);
          break;
        case 'system':
          if (msg.subtype === 'init' && onProgress) {
            const mcpCount = msg.mcp_servers?.length || 0;
            onProgress(`[init] ${msg.model || ''} (mcp:${mcpCount})`);
          }
          break;
        case 'control_request':
          child.stdin.write(JSON.stringify({
            type: 'control_response',
            response: { requestId: msg.request?.requestId || msg.requestId || '', allowed: true },
          }) + '\n');
          break;
      }
    }

    child.stderr.on('data', (chunk) => {
      const text = chunk.toString().trim();
      if (text && onProgress) onProgress(`[stderr] ${text}`);
    });

    child.on('error', (err) => { cleanup(); finish(false, `spawn: ${err.message}`); });
    child.on('close', (code) => { cleanup(); finish(code === 0, code === 0 ? undefined : `exited ${code}`); });

    child.stdin.write(JSON.stringify({ type: 'user', message: { role: 'user', content: prompt } }) + '\n');
  });
}

// ---- PTY bash execution (runs inside bridge, has session access) ----

async function runBashViaPTY(session, bashId, globalContext, command) {
  const cmd = String(command).trim();
  if (!cmd.includes('echo "Successful"') && !cmd.includes("echo 'Successful'")) {
    return await runBashViaExec(cmd);
  }

  if (bashId) {
    try {
      const args = { bashId, action: 'Command', commands: cmd, options: { idleTime: 600000 } };
      const result = await session.pipeChat('/@AgentBuilder/Bash.js', args, false);
      if (result) {
        if (typeof result === 'string') return result;
        if (result.content) return result.content;
        try { return JSON.stringify(result); } catch { return String(result); }
      }
    } catch {}
  }

  return await runBashViaExec(cmd);
}

async function runBashViaExec(cmd) {
  try {
    const { exec } = await import('child_process');
    const { promisify } = await import('util');
    const { stdout, stderr } = await promisify(exec)(cmd, {
      timeout: 0, maxBuffer: 10 * 1024 * 1024, // 0 = no timeout
      shell: true, cwd: process.env.HOME || '/tmp',
    });
    return ((stdout || '') + (stderr || '')).trim() || '(no output)';
  } catch (e) {
    return ((e.stdout || '') + (e.stderr || '') + `\n[exit ${e.code || '?'}] ${e.message || ''}`).trim();
  }
}

async function ensureBash(session, globalContext) {
  if (globalContext.bash) return globalContext.bash;
  try {
    const args = { bashId: '', action: 'Create', commands: '', options: { client: true } };
    const result = await session.pipeChat('/@AgentBuilder/Bash.js', args, false);
    if (result && (typeof result === 'string' || typeof result === 'number')) {
      globalContext.bash = String(result);
    }
  } catch {}
  return globalContext.bash || null;
}

// ---- prompt builders ----

export function buildAutoDeployPrompt({ model, modelType, needSpace, platform, guideMD }) {
  const guideContext = guideMD ? `\n\n## Deployment Guidelines\n${guideMD}` : '';
  return `Deploy the AI model **${model}** to this machine.

**Model Info:**
- ID: ${model}
- Source: ${modelType || 'unknown'}
- Platform: ${platform || 'mac'}
${needSpace ? `- Space needed: ${needSpace}` : ''}

**Rules (CRITICAL):**
1. All files under ~/.modelhunt/
2. Conda envs must end with _aa
3. Read project docs before installing
4. Check each command's output before continuing
5. If a command fails, diagnose and fix — don't blindly retry
6. Verify deployment with a quick test when done
${guideContext}

**Steps:**
1. Search/read the model's documentation for setup instructions
2. Clone or download the project to ~/.modelhunt
3. Create a conda env (name ending _aa) with appropriate Python version
4. Install system deps (brew on macOS)
5. Install Python deps
6. Download model weights
7. **TEST (REQUIRED)**: Run the model with actual input to verify it works. For example:
   - Image models: process a real image, check output file exists and has content
   - TTS models: generate audio, verify the file plays
   - LLM models: run inference, check output is sensible
   - If the test fails, diagnose and fix before reporting success
   - Show the test command AND its output in your final report

When finished, clearly state "DEPLOYMENT SUCCESSFUL" or "DEPLOYMENT FAILED: <reason>".
Do NOT claim success without a passing test.`;
}

export function buildFixPrompt({ failedCommand, errorOutput, platform, model, completedSteps }) {
  const stepsCtx = completedSteps?.length
    ? `\n## Completed Steps\n${completedSteps.map((s, i) => `${i + 1}. ${s.tip?.en || s.action || 'unknown'}`).join('\n')}`
    : '';
  return `A deployment step failed for model **${model}** on **${platform}**. Diagnose and fix.

## Failed Command
\`\`\`bash
${failedCommand}
\`\`\`

## Error
\`\`\`
${errorOutput || '(no output)'}
\`\`\`
${stepsCtx}

## Task
1. Analyze the error
2. Output the fix as JSON:
\`\`\`json
{ "diagnosis": "root cause", "fixedCommand": "corrected command", "preCommands": ["setup if needed"] }
\`\`\`
If unfixable: \`{ "diagnosis": "explanation", "unfixable": true }\``;
}

export function isClaudeAvailable() {
  return new Promise((resolve) => {
    const child = spawn('claude', ['--version'], { stdio: 'pipe', timeout: 5000 });
    child.on('close', (code) => resolve(code === 0));
    child.on('error', () => resolve(false));
  });
}

// ---- agent wrapper ----
async function claudeBridgeAgent(session) {
  let prompt;
  return {
    isAIAgent: true, session, name: 'ClaudeBridge', url: import.meta.url, autoStart: true,
    execChat: async function (input) {
      if (typeof input === 'string') prompt = input;
      else { prompt = input.prompt; }
      const result = await runClaudeWithSession({
        session, prompt,
        cwd: process.env.HOME || '/tmp',
        onProgress: (text) => { if (text?.trim()) session.addChatText('assistant', text.trim(), { channel: 'Log' }); },
      });
      return { result: result.success ? 'Finish' : 'Failed', output: result.output, error: result.error };
    },
  };
}

export default { runClaudeWithSession, buildAutoDeployPrompt, buildFixPrompt, isClaudeAvailable, claudeBridgeAgent };

//#CodyExport>>>
let ChatAPI = [{
  def: {
    name: 'ClaudeBridge',
    description: '调用 Claude Code 自主执行任务。Bash 通过 MCP → HTTP → AI2Apps PTY 终端。',
    parameters: { type: 'object', properties: { prompt: { type: 'string' }, timeout: { type: 'number' } } },
  },
  agentNode: 'AgentBuilder', agentName: 'ClaudeBridge.mjs', isChatApi: true,
}];
//#CodyExport<<<
