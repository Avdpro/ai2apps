#!/bin/sh

set -eu

REAL_PATH=$(realpath "$0")
RUNTIME_ROOT=$(CDPATH= cd -- "$(dirname -- "$REAL_PATH")/.." && pwd)
PYTHON_ROOT="$RUNTIME_ROOT/Python"
CPYTHON="$PYTHON_ROOT/cpython-3.11"
PYTHON="$CPYTHON/bin/python3"
APP_SITE="$RUNTIME_ROOT/app"

if [ -d "$PYTHON_ROOT/framework-control-plane" ]; then
  FRAMEWORK_SITE="$PYTHON_ROOT/framework-control-plane/lib/python3.11/site-packages"
  export AI2APPS_RUNTIME_PROFILE=cloud
else
  FRAMEWORK_SITE="$PYTHON_ROOT/framework-mlx-base/lib/python3.11/site-packages"
  export AI2APPS_RUNTIME_PROFILE=full
fi

export PYTHONHOME="$CPYTHON"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONNOUSERSITE=1
export PYTHONPATH="$APP_SITE:$FRAMEWORK_SITE"
export AI2APPS_TRUSTED_FRAMEWORK_SITE_PACKAGES="$FRAMEWORK_SITE"
export PATH="$CPYTHON/bin:/usr/bin:/bin:/usr/sbin:/sbin"
unset PYTHONSTARTUP PYTHONUSERBASE PYTHONEXECUTABLE __PYVENV_LAUNCHER__
unset VIRTUAL_ENV CONDA_PREFIX OPENSSL_CONF

exec "$PYTHON" -m ai2apps.cli "$@"
