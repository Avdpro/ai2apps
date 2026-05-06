// McpBashServer — MCP stdio server. Tries HTTP relay to bridge (PTY),
// falls back to child_process.exec if bridge is unreachable.

import { createInterface } from 'readline';
import { exec } from 'child_process';
import { request } from 'http';
import { promisify } from 'util';

const execP = promisify(exec);
const BRIDGE_URL = process.env.AI2APPS_BRIDGE_URL || 'http://127.0.0.1:19999';
const { hostname, port } = new URL(BRIDGE_URL);

const rl = createInterface({ input: process.stdin });

rl.on('line', async (line) => {
  if (!line.trim()) return;
  let msg;
  try { msg = JSON.parse(line); }
  catch { return; }

  const response = await handle(msg);
  if (response) {
    process.stdout.write(JSON.stringify(response) + '\n');
  }
});

async function handle(msg) {
  const { id, method, params } = msg;

  switch (method) {
    case 'initialize':
      return {
        jsonrpc: '2.0', id,
        result: {
          protocolVersion: '2024-11-05',
          capabilities: { tools: {} },
          serverInfo: { name: 'ai2apps-terminal', version: '1.0.0' },
        },
      };

    case 'notifications/initialized':
      return null;

    case 'tools/list':
      return {
        jsonrpc: '2.0', id,
        result: {
          tools: [{
            name: 'terminal_bash',
            description: 'Execute a shell command in the AI2Apps persistent terminal. Terminal state (cwd, env vars, conda) persists between calls. Use this for ALL shell commands.',
            inputSchema: {
              type: 'object',
              properties: {
                command: { type: 'string', description: 'The shell command to execute.' },
              },
              required: ['command'],
            },
          }],
        },
      };

    case 'tools/call': {
      if (params.name !== 'terminal_bash') {
        return { jsonrpc: '2.0', id, error: { code: -32601, message: `Unknown tool: ${params.name}` } };
      }

      const command = params.arguments?.command || '';

      // 1) Try bridge HTTP relay (PTY terminal with conda persistence)
      try {
        const text = await httpPost('/bash', { command });
        return { jsonrpc: '2.0', id, result: { content: [{ type: 'text', text }] } };
      } catch {}

      // 2) Fallback: direct exec
      try {
        const { stdout, stderr } = await execP(command, {
          timeout: 0, maxBuffer: 10 * 1024 * 1024,
          shell: true, cwd: process.env.HOME || '/tmp',
        });
        const text = ((stdout || '') + (stderr || '')).trim() || '(no output)';
        return { jsonrpc: '2.0', id, result: { content: [{ type: 'text', text }] } };
      } catch (e) {
        const text = ((e.stdout || '') + (e.stderr || '') + `\n[exit ${e.code || '?'}] ${e.message || ''}`).trim();
        return { jsonrpc: '2.0', id, result: { content: [{ type: 'text', text }], isError: true } };
      }
    }

    default:
      return { jsonrpc: '2.0', id, error: { code: -32601, message: `Unknown method: ${method}` } };
  }
}

// ---- raw HTTP POST, no timeout ----
function httpPost(path, data) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify(data);
    const req = request({
      hostname, port: Number(port),
      path, method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) },
      timeout: 0, // socket timeout disabled
    }, (res) => {
      let buf = '';
      res.on('data', c => buf += c);
      res.on('end', () => {
        try {
          const json = JSON.parse(buf);
          resolve(json.output || json.error || '(no output)');
        } catch {
          resolve(buf || '(no output)');
        }
      });
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('request timeout')); });
    req.write(body);
    req.end();
  });
}
