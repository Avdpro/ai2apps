"""CPU-only checks for executor selection and subprocess argument translation."""
import argparse,unittest
from types import SimpleNamespace
from unittest.mock import patch
from inference_mode import select,launch


def config(**updates):
    values=dict(inference_mode='auto',image=None,messages_json=None,trace=False,
                layer_progress=False,collect_routes=False,static_l1=False,l1_policy='eviction_dual',
                l1_shape=None,main_slots=40,burst_tail='zero',block_layers=1,prefill_top=None,
                shared_dispatch=False,fused_gate_up=False,decode_dispatch='legacy',attention_chunk=64,
                resume_block=4,burst_top=None)
    values.update(updates);return SimpleNamespace(**values)


class DefaultEntry(unittest.TestCase):
    def test_text_defaults_and_legacy(self):
        choice=select(config())
        self.assertEqual(choice['requested'],'auto')
        self.assertEqual(choice['selected'],'packet')
        self.assertIn('L1=40/L0=8',choice['reason'])
        self.assertEqual(select(config(inference_mode='packet'))['selected'],'packet')
        self.assertEqual(select(config(inference_mode='legacy'))['selected'],'legacy')
    def test_unsupported_modes_remain_explicit(self):
        for changed in [dict(image=['x.png']),dict(trace=True),dict(burst_tail='renorm'),dict(l1_shape='shape.json'),dict(l1_policy='baseline')]:
            with self.subTest(changed=changed):
                self.assertEqual(select(config(**changed))['selected'],'packet')
                self.assertEqual(select(config(inference_mode='packet',**changed))['selected'],'packet')
                with self.assertRaises(ValueError):select(config(inference_mode='guarded',**changed))
    def test_burst_translation_and_user_arguments(self):
        argv=['--burst-top=2','--resume-block','2','--inference-mode=auto','--output','a b','--prompt','hello world','--block-layers','1']
        with patch('inference_mode.Path.is_file',return_value=True),patch('inference_mode.Path.glob',return_value=iter(['bridge.so'])),patch('inference_mode.os.execve') as execute:
            launch(config(burst_top=2,resume_block=2),argv,argparse.ArgumentParser())
        cmd=execute.call_args.args[1]
        self.assertIn('--burst-top=2',cmd)
        self.assertNotIn('--inference-mode=auto',cmd);self.assertIn('--block-layers',cmd)
        self.assertEqual(cmd[cmd.index('--resume-mode')+1],'packet')
        self.assertEqual(cmd[cmd.index('--resume-block')+1],'2')
        self.assertEqual(cmd[cmd.index('--prompt')+1],'hello world')
        self.assertEqual(cmd[cmd.index('--output')+1],'a b')
    def test_native_windows_require_burst_and_preserve_scope(self):
        with self.assertRaises(ValueError):select(config(inference_mode='window'))
        self.assertEqual(select(config(inference_mode='window',burst_top=2))['selected'],'window')
        with self.assertRaises(ValueError):select(config(inference_mode='window',burst_top=2,image=['x.png']))

    def test_missing_backend_does_not_silently_change_model(self):
        with patch('inference_mode.Path.is_file',return_value=False),patch('inference_mode.os.execve') as execute:
            with self.assertRaises(SystemExit):launch(config(),[],argparse.ArgumentParser())
            execute.assert_not_called()

if __name__=='__main__':unittest.main()
