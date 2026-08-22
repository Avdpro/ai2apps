#!/bin/zsh

set -euo pipefail

UPDATER=${1:?pass updater executable}
IDENTITY='Developer ID Application: Avdpro Pang (84XL5V265N)'
ROOT=$(mktemp -d /tmp/ai2apps-updater-smoke.XXXXXX)
cleanup() {
  rm -rf "${ROOT}"
}
trap cleanup EXIT

make_app() {
  local app=$1
  local build=$2
  local executable=$3
  mkdir -p "${app}/Contents/MacOS"
  cp "${executable}" "${app}/Contents/MacOS/AI2Apps"
  plutil -create xml1 "${app}/Contents/Info.plist"
  /usr/libexec/PlistBuddy -c 'Add :CFBundleIdentifier string com.ai2apps.desktop.updater-smoke' "${app}/Contents/Info.plist"
  /usr/libexec/PlistBuddy -c 'Add :CFBundleExecutable string AI2Apps' "${app}/Contents/Info.plist"
  /usr/libexec/PlistBuddy -c 'Add :CFBundlePackageType string APPL' "${app}/Contents/Info.plist"
  /usr/libexec/PlistBuddy -c 'Add :AI2AppsInstanceID string updater-smoke' "${app}/Contents/Info.plist"
  /usr/libexec/PlistBuddy -c "Add :CFBundleVersion string ${build}" "${app}/Contents/Info.plist"
  codesign --force --timestamp --options runtime --sign "${IDENTITY}" "${app}"
}

run_success_case() {
  local root="${ROOT}/success"
  local installed="${root}/AI2Apps.app"
  local candidate="${root}/download/AI2Apps.app"
  local backup="${root}/AI2Apps.previous.app"
  local marker="${root}/.AI2Apps.app.update.pending"
  make_app "${installed}" 2198 /usr/bin/true
  make_app "${candidate}" 2199 /usr/bin/true
  sleep 1 &
  local shell_pid=$!
  : > "${marker}"
  "${UPDATER}" \
    --installed-app "${installed}" \
    --candidate-app "${candidate}" \
    --backup-app "${backup}" \
    --pending-marker "${marker}" \
    --wait-pid "${shell_pid}"
  [[ $(/usr/libexec/PlistBuddy -c 'Print :CFBundleVersion' "${installed}/Contents/Info.plist") == 2199 ]]
  [[ $(/usr/libexec/PlistBuddy -c 'Print :CFBundleVersion' "${backup}/Contents/Info.plist") == 2198 ]]
  codesign --verify --deep --strict "${installed}"
  codesign --verify --deep --strict "${backup}"
  [[ ! -e ${marker} ]]
  print 'success case: installed=2199 backup=2198'
}

run_rollback_case() {
  local root="${ROOT}/rollback"
  local installed="${root}/AI2Apps.app"
  local candidate="${root}/download/AI2Apps.app"
  local backup="${root}/AI2Apps.previous.app"
  local marker="${root}/.AI2Apps.app.update.pending"
  make_app "${installed}" 2198 /usr/bin/true
  make_app "${candidate}" 2200 /usr/bin/false
  sleep 1 &
  local shell_pid=$!
  : > "${marker}"
  if "${UPDATER}" \
    --installed-app "${installed}" \
    --candidate-app "${candidate}" \
    --backup-app "${backup}" \
    --pending-marker "${marker}" \
    --wait-pid "${shell_pid}"; then
    print -u2 'rollback case unexpectedly succeeded'
    return 1
  fi
  [[ $(/usr/libexec/PlistBuddy -c 'Print :CFBundleVersion' "${installed}/Contents/Info.plist") == 2198 ]]
  [[ ! -e ${backup} ]]
  codesign --verify --deep --strict "${installed}"
  [[ ! -e ${marker} ]]
  print 'rollback case: restored=2198 backup-consumed=true'
}

run_success_case
run_rollback_case
