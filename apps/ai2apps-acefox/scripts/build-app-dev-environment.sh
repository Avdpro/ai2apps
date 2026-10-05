#!/bin/zsh

set -euo pipefail

SCRIPT_DIR=${0:A:h}
PROJECT_DIR=${SCRIPT_DIR:h}
REPO_ROOT=${PROJECT_DIR:h:h}
SDK_ROOT=${REPO_ROOT:h}

# This is the one durable identity for App-Shell App development. Do not vary
# these values per feature: parallelism comes from keeping this environment
# separate from the ordinary AI2Apps-dev.app / dev instance.
OUTPUT_APP=${PROJECT_DIR}/.build/AI2Apps-app-dev.app
PRODUCT_IDENTIFIER=com.ai2apps.desktop.appdev
INSTANCE_ID=app-dev
APP_DISPLAY_NAME="AI2Apps-App-Dev"
APP_ICON_UPPER_COLOR='#E2D5F8'

ACEFOX_APP=${ACEFOX_APP:-${SDK_ROOT}/moz/acefox-firefox-153/obj-aarch64-apple-darwin/dist/firefox/Acefox.app}
ACEFOX_SHELL_SOURCE=${ACEFOX_SHELL_SOURCE:-${SDK_ROOT}/moz/acefox-firefox-153/browser/components/ai2apps/content/shell.mjs}
RUNTIME_LAYERS=${RUNTIME_LAYERS:-${REPO_ROOT}/packaging/_export}

fail() {
  print -u2 "build-app-dev-environment: $*"
  exit 64
}

[[ -d ${ACEFOX_APP} ]] || fail "AceFox App not found: ${ACEFOX_APP}"
[[ -f ${ACEFOX_SHELL_SOURCE} ]] || fail "AceFox Shell source not found: ${ACEFOX_SHELL_SOURCE}"
[[ -d ${RUNTIME_LAYERS}/cpython-3.11 ]] || \
  fail "embedded Runtime export not found; run .venv/bin/python packaging/build.py --venvstacks-only"
[[ -d ${RUNTIME_LAYERS}/framework-control-plane ]] || \
  fail "embedded control-plane layer not found in ${RUNTIME_LAYERS}"

STAGING_ROOT=$(mktemp -d "${PROJECT_DIR}/.build/app-dev-staging.XXXXXX")
STAGED_APP=${STAGING_ROOT}/AI2Apps-app-dev.app
cleanup() {
  rm -rf "${STAGING_ROOT}"
}
trap cleanup EXIT

ACEFOX_APP=${ACEFOX_APP} \
RUNTIME_LAYERS=${RUNTIME_LAYERS} \
RUNTIME_PROFILE=cloud \
OUTPUT_APP=${STAGED_APP} \
PRODUCT_IDENTIFIER=${PRODUCT_IDENTIFIER} \
INSTANCE_ID=${INSTANCE_ID} \
APP_DISPLAY_NAME=${APP_DISPLAY_NAME} \
APP_ICON_UPPER_COLOR=${APP_ICON_UPPER_COLOR} \
DEVELOPMENT_BUILD=1 \
DEVELOPMENT_SOURCE_ROOT=${REPO_ROOT} \
MENUBAR_ICON_BADGE=app-dev \
ALLOW_INSTANCE_DATA_RESET=1 \
ACEFOX_SHELL_SOURCE=${ACEFOX_SHELL_SOURCE} \
SHELL_TITLE_PREFIX=${APP_DISPLAY_NAME} \
SIGN_IDENTITY=- \
SANDBOX_MODE=0 \
UPDATE_MANIFEST_URL= \
  "${SCRIPT_DIR}/build-release-app.sh"

APP_DEV_HELPER_INFO=${STAGED_APP}/Contents/Library/LoginItems/AI2AppsHelper.app/Contents/Info.plist
[[ $(/usr/libexec/PlistBuddy -c 'Print :AI2AppsAllowInstanceDataReset' "${APP_DEV_HELPER_INFO}" 2>/dev/null || true) == true ]] || \
  fail "App-Dev Helper is missing its data-reset capability"

if [[ -e ${OUTPUT_APP} ]]; then
  ARCHIVE_DIR=${PROJECT_DIR}/.build/archive
  ARCHIVE_STEM="AI2Apps-app-dev-$(date +%Y%m%d-%H%M%S)"
  ARCHIVE_APP=${ARCHIVE_DIR}/${ARCHIVE_STEM}.app
  ARCHIVE_SUFFIX=1
  mkdir -p "${ARCHIVE_DIR}"
  while [[ -e ${ARCHIVE_APP} ]]; do
    ARCHIVE_APP=${ARCHIVE_DIR}/${ARCHIVE_STEM}-${ARCHIVE_SUFFIX}.app
    (( ARCHIVE_SUFFIX += 1 ))
  done
  mv "${OUTPUT_APP}" "${ARCHIVE_APP}"
  print "Archived previous App development environment as ${ARCHIVE_APP}"
fi

mv "${STAGED_APP}" "${OUTPUT_APP}"
print "Built fixed App development environment ${OUTPUT_APP}"
print "Instance data: ~/Library/Application Support/AI2Apps/instances/${INSTANCE_ID}"
