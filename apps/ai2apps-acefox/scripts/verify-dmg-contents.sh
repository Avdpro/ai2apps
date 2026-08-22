#!/bin/zsh

set -euo pipefail

APP=${APP:-${1:-}}
DMG=${DMG:-${2:-}}
PRODUCT_APP_NAME=${PRODUCT_APP_NAME:-AI2Apps.app}

fail() {
  print -u2 "verify-dmg-contents: $*"
  exit 64
}

[[ -n ${APP} && -d ${APP} ]] || fail "set APP to the signed release App"
[[ -n ${DMG} && -f ${DMG} && ${DMG:e} == dmg ]] || fail "set DMG to the matching .dmg"
[[ ${PRODUCT_APP_NAME} == ${PRODUCT_APP_NAME:t} && ${PRODUCT_APP_NAME} == *.app ]] || \
  fail "PRODUCT_APP_NAME must be a plain .app bundle name"

MOUNT_POINT=$(mktemp -d "${TMPDIR:-/tmp}/ai2apps-dmg-verify.XXXXXX")
MOUNTED=0
cleanup() {
  if [[ ${MOUNTED} == 1 ]]; then
    hdiutil detach "${MOUNT_POINT}" >/dev/null 2>&1 || true
  fi
  rmdir "${MOUNT_POINT}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

hdiutil attach -readonly -nobrowse -mountpoint "${MOUNT_POINT}" "${DMG}" >/dev/null
MOUNTED=1
EMBEDDED_APPS=("${MOUNT_POINT}"/*.app(N/))
[[ ${#EMBEDDED_APPS} == 1 ]] || fail "DMG must contain exactly one top-level App"
EMBEDDED_APP=${EMBEDDED_APPS[1]}
[[ ${EMBEDDED_APP:t} == ${PRODUCT_APP_NAME} ]] || fail "DMG App name is not ${PRODUCT_APP_NAME}"

codesign --verify --deep --strict "${APP}" || fail "source App signature is invalid"
codesign --verify --deep --strict "${EMBEDDED_APP}" || fail "embedded App signature is invalid"

signature_value() {
  local bundle=$1
  local field=$2
  codesign -dvvv "${bundle}" 2>&1 | sed -n "s/^${field}=//p" | head -n 1
}

SOURCE_CDHASH=$(signature_value "${APP}" CDHash)
EMBEDDED_CDHASH=$(signature_value "${EMBEDDED_APP}" CDHash)
[[ -n ${SOURCE_CDHASH} && ${SOURCE_CDHASH} == ${EMBEDDED_CDHASH} ]] || \
  fail "embedded App CDHash does not match source App"
SOURCE_TEAM=$(signature_value "${APP}" TeamIdentifier)
EMBEDDED_TEAM=$(signature_value "${EMBEDDED_APP}" TeamIdentifier)
[[ -n ${SOURCE_TEAM} && ${SOURCE_TEAM} == ${EMBEDDED_TEAM} ]] || \
  fail "embedded App signing team does not match source App"

SOURCE_INFO=${APP}/Contents/Info.plist
EMBEDDED_INFO=${EMBEDDED_APP}/Contents/Info.plist
for key in \
  CFBundleIdentifier \
  CFBundleShortVersionString \
  CFBundleVersion \
  AI2AppsInstanceID \
  LSMinimumSystemVersion; do
  SOURCE_VALUE=$(/usr/libexec/PlistBuddy -c "Print :${key}" "${SOURCE_INFO}")
  EMBEDDED_VALUE=$(/usr/libexec/PlistBuddy -c "Print :${key}" "${EMBEDDED_INFO}")
  [[ ${SOURCE_VALUE} == ${EMBEDDED_VALUE} ]] || fail "embedded App differs at ${key}"
done

SOURCE_MANIFEST=${APP}/Contents/Library/LoginItems/AI2AppsHelper.app/Contents/Resources/AI2AppsLocal/runtime-manifest.json
EMBEDDED_MANIFEST=${EMBEDDED_APP}/Contents/Library/LoginItems/AI2AppsHelper.app/Contents/Resources/AI2AppsLocal/runtime-manifest.json
cmp -s "${SOURCE_MANIFEST}" "${EMBEDDED_MANIFEST}" || \
  fail "embedded Runtime manifest does not match source App"

print "Verified DMG contains the matching signed App ${SOURCE_CDHASH}"
