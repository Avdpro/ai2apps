#!/bin/zsh

set -euo pipefail

APP=${APP:-}
OUTPUT_DMG=${OUTPUT_DMG:-}
VOLUME_NAME=${VOLUME_NAME:-AI2Apps}
PRODUCT_APP_NAME=${PRODUCT_APP_NAME:-AI2Apps.app}
SIGN_IDENTITY=${SIGN_IDENTITY:-}
SCRIPT_DIR=${0:A:h}

fail() {
  print -u2 "build-release-dmg: $*"
  exit 64
}

[[ -n ${APP} && -d ${APP} && ${APP:t} == *.app ]] || fail "set APP to a release .app bundle"
[[ -n ${OUTPUT_DMG} && ${OUTPUT_DMG:e} == dmg ]] || fail "set OUTPUT_DMG to a .dmg path"
[[ ${PRODUCT_APP_NAME} == ${PRODUCT_APP_NAME:t} && ${PRODUCT_APP_NAME} == *.app ]] || \
  fail "PRODUCT_APP_NAME must be a plain .app bundle name"
[[ ! -e ${OUTPUT_DMG} ]] || fail "output already exists: ${OUTPUT_DMG}"
APP="${APP}" "${SCRIPT_DIR}/verify-release-app.sh" || fail "App verification failed"

STAGING_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/ai2apps-dmg.XXXXXX")
cleanup() {
  rm -rf "${STAGING_ROOT}"
}
trap cleanup EXIT

PAYLOAD=${STAGING_ROOT}/payload
mkdir -p "${PAYLOAD}" "${OUTPUT_DMG:h}"
# Artifact filenames may carry a release suffix, but the installed product name
# must remain stable for Finder, Dock, upgrades, and user documentation.
ditto "${APP}" "${PAYLOAD}/${PRODUCT_APP_NAME}"
ln -s /Applications "${PAYLOAD}/Applications"
[[ -d ${PAYLOAD}/${PRODUCT_APP_NAME} ]] || fail "stable product App was not staged"
STAGED_APP_COUNT=$(find "${PAYLOAD}" -maxdepth 1 -type d -name '*.app' | wc -l | tr -d ' ')
[[ ${STAGED_APP_COUNT} == 1 ]] || fail "DMG payload must contain exactly one App"

hdiutil create \
  -fs HFS+ \
  -format UDZO \
  -imagekey zlib-level=9 \
  -srcfolder "${PAYLOAD}" \
  -volname "${VOLUME_NAME}" \
  "${OUTPUT_DMG}"

if [[ ${SIGN_IDENTITY} == - ]]; then
  codesign --force --sign - "${OUTPUT_DMG}"
  codesign --verify --verbose=2 "${OUTPUT_DMG}"
elif [[ -n ${SIGN_IDENTITY} ]]; then
  codesign --force --timestamp --sign "${SIGN_IDENTITY}" "${OUTPUT_DMG}"
  codesign --verify --verbose=2 "${OUTPUT_DMG}"
fi

hdiutil verify "${OUTPUT_DMG}"
"${SCRIPT_DIR}/verify-dmg-contents.sh" "${APP}" "${OUTPUT_DMG}"
print "Built release image ${OUTPUT_DMG}"
