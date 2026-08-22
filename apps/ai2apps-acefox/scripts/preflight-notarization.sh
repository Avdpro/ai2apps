#!/bin/zsh

set -euo pipefail

SCRIPT_DIR=${0:A:h}
APP=${APP:-}
DMG=${DMG:-}
METADATA=${METADATA:-}

fail() {
  print -u2 "preflight-notarization: $*"
  exit 64
}

[[ -n ${APP} && -d ${APP} ]] || fail "set APP to the signed release App"
[[ -n ${DMG} && -f ${DMG} ]] || fail "set DMG to the signed source DMG"
[[ ${DMG:e} == dmg ]] || fail "DMG must use the .dmg extension"
[[ -x ${SCRIPT_DIR}/verify-release-app.sh ]] || fail "missing verify-release-app.sh"
[[ -x ${SCRIPT_DIR}/verify-release-metadata.py ]] || fail "missing verify-release-metadata.py"
[[ -x ${SCRIPT_DIR}/verify-dmg-contents.sh ]] || fail "missing verify-dmg-contents.sh"
command -v xcrun >/dev/null || fail "xcrun is unavailable"
command -v hdiutil >/dev/null || fail "hdiutil is unavailable"

"${SCRIPT_DIR}/verify-release-app.sh" "${APP}"
codesign --verify --verbose=2 "${DMG}" || fail "DMG signature is invalid"
hdiutil verify "${DMG}" >/dev/null || fail "DMG checksum is invalid"

if [[ -n ${METADATA} ]]; then
  [[ -f ${METADATA} ]] || fail "METADATA does not exist"
  "${SCRIPT_DIR}/verify-release-metadata.py" \
    --metadata "${METADATA}" \
    --app "${APP}" \
    --dmg "${DMG}"
  STATUS=$(/usr/bin/python3 -c \
    'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["notarization"]["status"])' \
    "${METADATA}")
  [[ ${STATUS} == not_stapled ]] || fail "source metadata must describe a not_stapled candidate"
else
  "${SCRIPT_DIR}/verify-dmg-contents.sh" "${APP}" "${DMG}"
fi

if xcrun stapler validate "${DMG}" >/dev/null 2>&1; then
  fail "source DMG is already stapled; do not resubmit it"
fi

print "Notarization preflight passed for ${DMG}"
