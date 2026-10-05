#!/usr/bin/env python3
"""Prepare a dedicated local marketplace and install via Codex's supported CLI."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--connection', required=True, help='Private config path displayed by Todo; do not paste its contents')
    parser.add_argument('--destination', type=Path, default=Path.home()/'.codex/ai2apps-todo-local')
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    connection = Path(args.connection).expanduser().resolve()
    if not connection.is_absolute(): parser.error('Connection path must be absolute')
    root = args.destination.expanduser().resolve()
    plugin = root/'plugins/ai2apps-todo'
    source = Path(__file__).resolve().parent
    plugin.mkdir(parents=True,exist_ok=True)
    for name in ('scripts','skills'):
        shutil.copytree(source/name,plugin/name,dirs_exist_ok=True)
    shutil.copy2(source/'plugin.json',plugin/'plugin.json')
    # Use compatibility manifest as well for existing Codex Desktop versions.
    (plugin/'.codex-plugin').mkdir(exist_ok=True)
    (plugin/'.codex-plugin/plugin.json').write_text(json.dumps({'name':'ai2apps-todo','version':'0.1.0','description':'AI2Apps Todo local integration','skills':'./skills/','mcpServers':'./.mcp.json'},indent=2))
    server = {'command':sys.executable,'args':[str(plugin/'scripts/server.py'),'--config',str(connection)]}
    (plugin/'.mcp.json').write_text(json.dumps({'mcpServers':{'todo':server}},indent=2))
    (plugin/'mcp.json').write_text(json.dumps({'$schema':'https://agent-plugins.org/schemas/1.0.0/mcp.schema.json','mcpServers':{'todo':{'type':'stdio',**server}}},indent=2))
    catalog = root/'.agents/plugins'; catalog.mkdir(parents=True,exist_ok=True)
    (catalog/'marketplace.json').write_text(json.dumps({'name':'ai2apps-local','interface':{'displayName':'AI2Apps Local'},'plugins':[{'name':'ai2apps-todo','source':{'source':'local','path':'./plugins/ai2apps-todo'},'policy':{'installation':'AVAILABLE','authentication':'ON_INSTALL'},'category':'Productivity'}]},indent=2))
    if not args.prepare_only:
        subprocess.run(['codex','plugin','marketplace','add',str(root)],check=True)
        subprocess.run(['codex','plugin','add','ai2apps-todo@ai2apps-local'],check=True)
    print('AI2Apps Todo plugin prepared at '+str(root))
    print('Open a new Codex chat to load the plugin; restart Desktop if its plugin list has not refreshed.')


if __name__ == '__main__': main()
