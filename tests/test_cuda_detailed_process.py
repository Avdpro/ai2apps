import importlib.util
from pathlib import Path
import sys
import threading
import time
import pytest

spec=importlib.util.spec_from_file_location('cuda_detailed_process',Path(__file__).parents[1]/'spark/cuda_detailed_process.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def test_result_and_cleanup(tmp_path):
    child=tmp_path/'child.py';marker=tmp_path/'directory'
    child.write_text('import argparse,json,pathlib\np=argparse.ArgumentParser();p.add_argument("--job");p.add_argument("--result");a=p.parse_args()\nj=json.loads(pathlib.Path(a.job).read_text());pathlib.Path(j["marker"]).write_text(str(pathlib.Path(a.job).parent));pathlib.Path(a.result).write_text(json.dumps({"ok":True}))\n')
    runner=m.DetailedStageProcess(Path(sys.executable),Path(sys.executable),script=child)
    assert runner.run({'stage':'qwen','marker':str(marker)},threading.Event())=={'ok':True}
    assert not Path(marker.read_text()).exists()


def test_cancel_live_child_and_cleanup(tmp_path):
    child=tmp_path/'child.py';marker=tmp_path/'pid'
    child.write_text('import argparse,json,pathlib,os,time\np=argparse.ArgumentParser();p.add_argument("--job");p.add_argument("--result");a=p.parse_args()\nj=json.loads(pathlib.Path(a.job).read_text());pathlib.Path(j["marker"]).write_text(str(os.getpid())+"\\n"+str(pathlib.Path(a.job).parent));time.sleep(60)\n')
    runner=m.DetailedStageProcess(Path(sys.executable),Path(sys.executable),script=child)
    event=threading.Event();errors=[]
    def work():
        try:runner.run({'stage':'sortformer','marker':str(marker)},event)
        except Exception as e:errors.append(e)
    thread=threading.Thread(target=work);thread.start()
    deadline=time.monotonic()+5
    while not marker.exists() and time.monotonic()<deadline:time.sleep(.01)
    assert marker.exists();pid,directory=marker.read_text().splitlines()
    event.set();thread.join(5);assert not thread.is_alive()
    assert len(errors)==1 and isinstance(errors[0],m.DetailedCancelled)
    import os
    with pytest.raises(ProcessLookupError):os.kill(int(pid),0)
    assert not Path(directory).exists()


def test_precancel_does_not_spawn(tmp_path):
    event=threading.Event();event.set()
    runner=m.DetailedStageProcess(tmp_path/'absent',tmp_path/'absent')
    with pytest.raises(m.DetailedCancelled):runner.run({'stage':'qwen'},event)


def test_failed_child_cleans_workspace_and_reports_error(tmp_path):
    child=tmp_path/'child.py';marker=tmp_path/'directory'
    child.write_text('import argparse,json,pathlib\np=argparse.ArgumentParser();p.add_argument("--job");p.add_argument("--result");a=p.parse_args()\nj=json.loads(pathlib.Path(a.job).read_text());pathlib.Path(j["marker"]).write_text(str(pathlib.Path(a.job).parent));raise RuntimeError("intentional inference failure")\n')
    runner=m.DetailedStageProcess(Path(sys.executable),Path(sys.executable),script=child)
    with pytest.raises(RuntimeError,match='intentional inference failure'):
        runner.run({'stage':'qwen','marker':str(marker)},threading.Event())
    assert not Path(marker.read_text()).exists()


def test_runtime_stage_factory_requires_both_declared_layers(tmp_path):
    import json
    root=tmp_path/'runtime';root.mkdir();(root/'META').mkdir()
    launcher=root/'app/ai2apps/model_worker/stage_launcher.py';launcher.parent.mkdir(parents=True);launcher.write_text('pass')
    executable=root/'Python/bin/python';executable.parent.mkdir(parents=True);executable.write_text('placeholder')
    entry=root/'app/stage.py';entry.write_text('pass')
    for name in ('qwen','nemo'):(root/f'profiles/{name}').mkdir(parents=True)
    value={'format':'ai2apps.framework-profiles/v1','profiles':{'qwen':{'site_packages':'profiles/qwen'},'nemo':{'site_packages':'profiles/nemo'}},'stages':{'detailed':{'qwen':'qwen','sortformer':'nemo'}},'stage_entrypoints':{'detailed':{'qwen':'app/stage.py','sortformer':'app/stage.py'}}}
    manifest=root/'META/framework-profiles.json';manifest.write_text(json.dumps(value))
    runner=m.DetailedStageProcess.from_runtime(root,executable,'detailed')
    assert all(command[1]=='-I' for command in runner.runtime_commands.values())
    assert runner.runtime_commands['sortformer'][-1]=='sortformer'
    del value['stages']['detailed']['sortformer'];manifest.write_text(json.dumps(value))
    with pytest.raises(RuntimeError,match='not declared'):
        m.DetailedStageProcess.from_runtime(root,executable,'detailed')
    with pytest.raises(RuntimeError,match='belong to Runtime'):
        m.DetailedStageProcess.from_runtime(root,Path(sys.executable),'detailed')
