#!/bin/zsh

set -euo pipefail

SOURCE_APP=${1:?pass source App containing embedded update tools}
INSTALLED_APP=${2:?pass older installed App}
DMG=${3:?pass candidate DMG}
METADATA=${4:?pass candidate release metadata}
ROOT=$(mktemp -d /tmp/ai2apps-immutable-stage.XXXXXX)
cleanup() {
  rm -rf "${ROOT}"
}
trap cleanup EXIT

PYTHON=${SOURCE_APP}/Contents/Library/LoginItems/AI2AppsHelper.app/Contents/Resources/AI2AppsLocal/Python/cpython-3.11/bin/python3.11
STAGER=${SOURCE_APP}/Contents/Resources/Update/stage-update-candidate.py
OUTPUT=${ROOT}/AI2Apps.app

codesign --verify --deep --strict "${SOURCE_APP}"
[[ -z $(find "${SOURCE_APP}" -type f -name '*.pyc' -print -quit) ]]
PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  "${PYTHON}" -I -B "${STAGER}" \
  --installed-app "${INSTALLED_APP}" \
  --dmg "${DMG}" \
  --metadata "${METADATA}" \
  --output-app "${OUTPUT}" \
  --internal-candidate
codesign --verify --deep --strict "${SOURCE_APP}"
codesign --verify --deep --strict "${OUTPUT}"
[[ -z $(find "${SOURCE_APP}" -type f -name '*.pyc' -print -quit) ]]
print "immutable staging case: source signature preserved"
