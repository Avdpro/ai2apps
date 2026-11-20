"""Read only allowlisted Terminal config paths, never credential contents."""
import os
from pathlib import Path
import pwd
import subprocess
from functools import lru_cache

CONFIG_KEYS=('HF_HOME','HF_TOKEN_PATH','MODELSCOPE_HOME','MODELSCOPE_CACHE','XDG_CACHE_HOME','XDG_CONFIG_HOME')

@lru_cache(maxsize=1)
def terminal_config():
    seed=dict(os.environ)
    for name in ('HF_HOME','HF_TOKEN_PATH','HF_HUB_CACHE','HUGGINGFACE_HUB_CACHE','TRANSFORMERS_CACHE','HF_TOKEN','HUGGING_FACE_HUB_TOKEN'):
        seed.pop(name,None)
    shell=seed.get('SHELL') or pwd.getpwuid(os.getuid()).pw_shell
    if not Path(shell).is_absolute():return {}
    # Fixed shell program, only directory/path variables. No env dump or tokens.
    command="printf '__AI2APPS_CLI_ENV_BEGIN__\\n'; for cli_key in "+' '.join(CONFIG_KEYS)+"; do printf '%s=' \"$cli_key\"; /usr/bin/printenv \"$cli_key\"; printf '\\n'; done; printf '__AI2APPS_CLI_ENV_END__\\n'"
    try:
        result=subprocess.run([shell,'-ilc',command],env=seed,cwd=Path.home(),stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,timeout=3)
        text=result.stdout.split('__AI2APPS_CLI_ENV_BEGIN__\n',1)[1].split('__AI2APPS_CLI_ENV_END__',1)[0]
        values={}
        for line in text.splitlines():
            key,sep,value=line.partition('=')
            if sep and key in CONFIG_KEYS and value and Path(value).is_absolute():values[key]=value
        return values
    except (OSError,subprocess.TimeoutExpired,IndexError,UnicodeError):return {}


def external_environment(values):
    result=dict(values)
    if os.environ.get('AI2APPS_SUPERVISED') or os.environ.get('AI2APPS_MODEL_CACHE_MODE')=='isolated':
        # Supervisor overrides model cache/credential paths for Local workers.
        # These are not the Terminal account the user explicitly selected here.
        for name in ('HF_HOME','HF_TOKEN_PATH'):result.pop(name,None)
        result.update(terminal_config())
    return result
