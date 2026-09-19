#!/bin/zsh

set -euo pipefail

SCRIPT_DIR=${0:A:h}
PROJECT_DIR=${SCRIPT_DIR:h}
REPO_ROOT=${PROJECT_DIR:h:h}
SDK_ROOT=${REPO_ROOT:h}

# AI2Apps-test is a release-shaped, non-development build with a durable,
# isolated identity. It intentionally does not mount repository source.
OUTPUT_APP=${PROJECT_DIR}/.build/AI2Apps-test.app
PRODUCT_IDENTIFIER=com.ai2apps.desktop.test
INSTANCE_ID=test
APP_DISPLAY_NAME=AI2Apps-test
APP_ICON_UPPER_COLOR='#C7E7FA'

ACEFOX_APP=${ACEFOX_APP:-${SDK_ROOT}/moz/acefox-firefox-153/obj-aarch64-apple-darwin/dist/firefox/Acefox.app}
RUNTIME_LAYERS=${RUNTIME_LAYERS:-${REPO_ROOT}/packaging/_export}
SIGN_IDENTITY=${SIGN_IDENTITY:--}

fail() {
  print -u2 "build-test-app: $*"
  exit 64
}

[[ -d ${ACEFOX_APP} ]] || fail "AceFox App not found: ${ACEFOX_APP}"
[[ -d ${RUNTIME_LAYERS}/cpython-3.11 ]] || \
  fail "embedded Runtime export not found; run .venv/bin/python packaging/build.py --venvstacks-only"
[[ -d ${RUNTIME_LAYERS}/framework-control-plane ]] || \
  fail "embedded control-plane layer not found in ${RUNTIME_LAYERS}"

STAGING_ROOT=$(mktemp -d "${PROJECT_DIR}/.build/test-app-staging.XXXXXX")
STAGED_APP=${STAGING_ROOT}/AI2Apps-test.app
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
DEVELOPMENT_BUILD=0 \
ALLOW_INSTANCE_DATA_RESET=1 \
MENUBAR_ICON_BADGE=test \
SIGN_IDENTITY=${SIGN_IDENTITY} \
SANDBOX_MODE=0 \
  "${SCRIPT_DIR}/build-release-app.sh"

TEST_INFO=${STAGED_APP}/Contents/Info.plist
TEST_HELPER_INFO=${STAGED_APP}/Contents/Library/LoginItems/AI2AppsHelper.app/Contents/Info.plist
[[ $(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "${TEST_INFO}") == ${PRODUCT_IDENTIFIER} ]] || \
  fail "built App has the wrong bundle identifier"
[[ $(/usr/libexec/PlistBuddy -c 'Print :AI2AppsInstanceID' "${TEST_INFO}") == ${INSTANCE_ID} ]] || \
  fail "built App has the wrong instance identity"
[[ $(/usr/libexec/PlistBuddy -c 'Print :AI2AppsRuntimeProfile' "${TEST_INFO}") == cloud ]] || \
  fail "test App must use the production cloud Runtime profile"
[[ $(/usr/libexec/PlistBuddy -c 'Print :AI2AppsAllowInstanceDataReset' "${TEST_HELPER_INFO}" 2>/dev/null || true) == true ]] || \
  fail "test Helper is missing its data-reset capability"
for test_icon in "${STAGED_APP}/Contents/Library/LoginItems/AI2AppsHelper.app/Contents/Resources"/menubar-logo*.svg; do
  /usr/bin/grep -Fq 'id="ai2apps-test-badge-left"' "${test_icon}" && \
    /usr/bin/grep -Fq 'id="ai2apps-test-badge-right"' "${test_icon}" || \
    fail "test Helper icon is missing its two dedicated badges: ${test_icon:t}"
done
[[ -z $(/usr/libexec/PlistBuddy -c 'Print :AI2AppsDevelopment' "${TEST_INFO}" 2>/dev/null || true) ]] || \
  fail "test App must not be a Development Bundle"

if [[ -e ${OUTPUT_APP} ]]; then
  ARCHIVE_DIR=${PROJECT_DIR}/.build/archive
  ARCHIVE_STEM="AI2Apps-test-$(date +%Y%m%d-%H%M%S)"
  ARCHIVE_APP=${ARCHIVE_DIR}/${ARCHIVE_STEM}.app
  ARCHIVE_SUFFIX=1
  mkdir -p "${ARCHIVE_DIR}"
  while [[ -e ${ARCHIVE_APP} ]]; do
    ARCHIVE_APP=${ARCHIVE_DIR}/${ARCHIVE_STEM}-${ARCHIVE_SUFFIX}.app
    (( ARCHIVE_SUFFIX += 1 ))
  done
  mv "${OUTPUT_APP}" "${ARCHIVE_APP}"
  print "Archived previous test App as ${ARCHIVE_APP}"
fi

mv "${STAGED_APP}" "${OUTPUT_APP}"
print "Built fixed release-test App ${OUTPUT_APP}"
print "Instance data: ~/Library/Application Support/AI2Apps/instances/${INSTANCE_ID}"
print "Instance cache: ~/Library/Caches/AI2Apps/instances/${INSTANCE_ID}"
