"""Independent Worker Runtime must not import another backend eagerly."""
import subprocess
import sys
from pathlib import Path


def test_worker_protocol_and_server_without_omlx():
    root = Path(__file__).resolve().parents[1]
    script = '''
import importlib.abc
import sys
sys.path.insert(0, sys.argv[1])
class NoOmlx(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'omlx', 'mlx'}:
            raise AssertionError('Unexpected backend import: ' + fullname)
sys.meta_path.insert(0, NoOmlx())
from ai2apps.model_worker import ModelWorkerRequest
from ai2apps.model_worker.server import create_app
assert callable(create_app)
assert ModelWorkerRequest('chat_completions', {}, 'test').operation == 'chat_completions'
'''
    subprocess.run([sys.executable, "-I", "-c", script, str(root)], check=True)


def test_existing_omlx_adapter_exports_remain_available():
    from ai2apps.model_worker import OmlxChatAdapter, OmlxSTTAdapter, OmlxTTSAdapter
    from ai2apps.model_worker.omlx_chat import OmlxChatAdapter as Chat
    from ai2apps.model_worker.omlx_audio import OmlxSTTAdapter as STT, OmlxTTSAdapter as TTS
    assert (OmlxChatAdapter, OmlxSTTAdapter, OmlxTTSAdapter) == (Chat, STT, TTS)
