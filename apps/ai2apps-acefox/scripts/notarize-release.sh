#!/bin/zsh

set -euo pipefail

SCRIPT_DIR=${0:A:h}
ARTIFACT=${ARTIFACT:-}
APP=${APP:-}
SOURCE_METADATA=${SOURCE_METADATA:-}
OUTPUT_DMG=${OUTPUT_DMG:-}
OUTPUT_METADATA=${OUTPUT_METADATA:-}
KEYCHAIN_PROFILE=${KEYCHAIN_PROFILE:-}

fail() {
  print -u2 "notarize-release: $*"
  exit 64
}

[[ -n ${ARTIFACT} && -f ${ARTIFACT} ]] || fail "set ARTIFACT to the signed source DMG"
[[ ${ARTIFACT:e} == dmg ]] || fail "ARTIFACT must use the .dmg extension"
[[ -n ${APP} && -d ${APP} ]] || fail "set APP to the matching signed release App"
[[ -n ${OUTPUT_DMG} ]] || fail "set OUTPUT_DMG to a new final .dmg path"
[[ ${OUTPUT_DMG:e} == dmg ]] || fail "OUTPUT_DMG must use the .dmg extension"
[[ ${OUTPUT_DMG:A} != ${ARTIFACT:A} ]] || fail "OUTPUT_DMG must differ from ARTIFACT"
[[ ! -e ${OUTPUT_DMG} ]] || fail "OUTPUT_DMG already exists"
[[ -n ${OUTPUT_METADATA} ]] || fail "set OUTPUT_METADATA to a new final release record"
[[ ${OUTPUT_METADATA:e} == json ]] || fail "OUTPUT_METADATA must use the .json extension"
[[ ! -e ${OUTPUT_METADATA} ]] || fail "OUTPUT_METADATA already exists"
[[ -n ${KEYCHAIN_PROFILE} ]] || fail "set KEYCHAIN_PROFILE to a notarytool profile"

APP=${APP:A}
ARTIFACT=${ARTIFACT:A}
OUTPUT_DMG=${OUTPUT_DMG:A}
OUTPUT_METADATA=${OUTPUT_METADATA:A}
if [[ -n ${SOURCE_METADATA} ]]; then
  SOURCE_METADATA=${SOURCE_METADATA:A}
fi

APP=${APP} DMG=${ARTIFACT} METADATA=${SOURCE_METADATA} \
  "${SCRIPT_DIR}/preflight-notarization.sh"

mkdir -p "${OUTPUT_DMG:h}" "${OUTPUT_METADATA:h}"
STAGED_DMG="${OUTPUT_DMG:r}.notarizing.$$.dmg"
[[ ! -e ${STAGED_DMG} ]] || fail "temporary output already exists"
cleanup() {
  rm -f "${STAGED_DMG}"
}
trap cleanup EXIT

cp -p "${ARTIFACT}" "${STAGED_DMG}"
xcrun notarytool submit "${STAGED_DMG}" \
  --keychain-profile "${KEYCHAIN_PROFILE}" \
  --wait
xcrun stapler staple "${STAGED_DMG}"
xcrun stapler validate "${STAGED_DMG}"
codesign --verify --verbose=2 "${STAGED_DMG}"
spctl --assess \
  --type open \
  --context context:primary-signature \
  --verbose=2 \
  "${STAGED_DMG}"

mv "${STAGED_DMG}" "${OUTPUT_DMG}"
"${SCRIPT_DIR}/generate-release-metadata.py" \
  --app "${APP}" \
  --dmg "${OUTPUT_DMG}" \
  --output "${OUTPUT_METADATA}"
APP=${APP} DMG=${OUTPUT_DMG} METADATA=${OUTPUT_METADATA} \
  "${SCRIPT_DIR}/verify-notarized-release.sh"

print "Notarized release ${OUTPUT_DMG}"
