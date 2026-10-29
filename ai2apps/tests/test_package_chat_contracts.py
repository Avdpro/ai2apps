"""All first-party Package Mini-Apps use the canonical non-executing UI bridge."""
from pathlib import Path
import json
import yaml
from ai2apps.studio.mini_app_chat import validate_chat_declaration
ROOT=Path(__file__).resolve().parents[2]

def test_all_thirteen_package_chat_interfaces_are_closed_and_bundled():
 count=0
 for p in (ROOT/'packages').glob('*/app.yaml'):
  app=yaml.safe_load(p.read_text())
  for mini in app.get('mini_apps',[]):
   count+=1;chat=mini['chat'];validate_chat_declaration(chat)
   assert chat['tools'][0]['name']=='update_current_draft'
   assert chat['tools'][0]['input_schema']['additionalProperties'] is False
   fields=chat['tools'][0]['input_schema']['properties']
   assert not any(any(s in key.lower() for s in ('secret','token','consent','rights')) for key in fields)
   html=p.parent/mini['entry']['resource'];assert html.with_suffix('.chat.js').is_file()
   assert 'package_mini_chat.js' in html.read_text()
   assert (p.parent/'web/package_mini_chat.js').read_bytes()==(ROOT/'ai2apps/web/static/js/package_mini_chat.js').read_bytes()
   assert (p.parent/chat['help']['resource']).is_file()
 # SearchAll and WebReader are now product built-ins, not independent Packages.
 assert count==13
