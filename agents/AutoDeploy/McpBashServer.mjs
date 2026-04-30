// McpBashServer — MCP stdio → HTTP relay
// Started by Claude Code. Receives JSON-RPC on stdin, forwards bash commands
// via HTTP to the bridge's local server (which has session.pipeChat access).

import { createInterface } from 'readline';

const BRIDGE_URL = process.env.AI2APPS_BRIDGE_URL || 'http://localhost:19999';
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
      try {
        const resp = await fetch(`${BRIDGE_URL}/bash`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ command }),
        });
        const data = await resp.json();
        const text = data.output || data.error || '(no output)';
        return {
          jsonrpc: '2.0', id,
          result: { content: [{ type: 'text', text }], isError: !!data.error },
        };
      } catch (e) {
        return {
          jsonrpc: '2.0', id,
          result: { content: [{ type: 'text', text: `Error: ${e.message}` }], isError: true },
        };
      }
    }

    default:
      return { jsonrpc: '2.0', id, error: { code: -32601, message: `Unknown method: ${method}` } };
  }
}
