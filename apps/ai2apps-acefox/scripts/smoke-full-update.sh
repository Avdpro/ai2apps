#!/bin/zsh

set -euo pipefail

OLD_APP=${1:?pass old App}
CANDIDATE_APP=${2:?pass candidate App}
UPDATER=${CANDIDATE_APP}/Contents/Helpers/AI2AppsUpdater
OLD_BUILD=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleVersion' "${OLD_APP}/Contents/Info.plist")
NEW_BUILD=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleVersion' "${CANDIDATE_APP}/Contents/Info.plist")
ROOT=$(mktemp -d /tmp/ai2apps-full-update-smoke.XXXXXX)
cleanup() {
  rm -rf "${ROOT}"
}
trap cleanup EXIT

INSTALLED=${ROOT}/AI2Apps.app
BACKUP=${ROOT}/AI2Apps.previous.app
MARKER=${ROOT}/.AI2Apps.app.update.pending
cp -cR "${OLD_APP}" "${INSTALLED}"
codesign --verify --deep --strict "${INSTALLED}"
codesign --verify --strict "${UPDATER}"

sleep 1 &
SHELL_PID=$!
: > "${MARKER}"
"${UPDATER}" \
  --installed-app "${INSTALLED}" \
  --candidate-app "${CANDIDATE_APP}" \
  --backup-app "${BACKUP}" \
  --pending-marker "${MARKER}" \
  --wait-pid "${SHELL_PID}"

[[ $(/usr/libexec/PlistBuddy -c 'Print :CFBundleVersion' "${INSTALLED}/Contents/Info.plist") == ${NEW_BUILD} ]]
[[ $(/usr/libexec/PlistBuddy -c 'Print :AI2AppsUpdaterProtocol' "${INSTALLED}/Contents/Info.plist") == 1 ]]
[[ $(/usr/libexec/PlistBuddy -c 'Print :CFBundleVersion' "${BACKUP}/Contents/Info.plist") == ${OLD_BUILD} ]]
codesign --verify --deep --strict "${INSTALLED}"
codesign --verify --deep --strict "${BACKUP}"
[[ ! -e ${MARKER} ]]
print "full update case: installed=${NEW_BUILD} protocol=1 backup=${OLD_BUILD}"
