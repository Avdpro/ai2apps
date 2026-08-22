#!/bin/zsh

set -euo pipefail

SCRIPT_DIR=${0:A:h}
APP=${APP:-}
DMG=${DMG:-}
METADATA=${METADATA:-}

fail() {
  print -u2 "verify-notarized-release: $*"
  exit 64
}

[[ -n ${APP} && -d ${APP} ]] || fail "set APP to the signed release App"
[[ -n ${DMG} && -f ${DMG} ]] || fail "set DMG to the stapled release DMG"
[[ ${DMG:e} == dmg ]] || fail "DMG must use the .dmg extension"
[[ -n ${METADATA} && -f ${METADATA} ]] || fail "set METADATA to the final release record"

"${SCRIPT_DIR}/verify-release-app.sh" "${APP}"
codesign --verify --verbose=2 "${DMG}" || fail "DMG signature is invalid"
hdiutil verify "${DMG}" >/dev/null || fail "DMG checksum is invalid"
xcrun stapler validate "${DMG}" || fail "DMG has no valid stapled ticket"
spctl --assess \
  --type open \
  --context context:primary-signature \
  --verbose=2 \
  "${DMG}" || fail "Gatekeeper rejected the DMG"

"${SCRIPT_DIR}/verify-release-metadata.py" \
  --metadata "${METADATA}" \
  --app "${APP}" \
  --dmg "${DMG}"
STATUS=$(/usr/bin/python3 -c \
  'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["notarization"]["status"])' \
  "${METADATA}")
[[ ${STATUS} == stapled ]] || fail "final metadata must report notarization.status=stapled"

print "Verified notarized release ${DMG}"
