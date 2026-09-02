#!/bin/zsh

set -euo pipefail

SCRIPT_DIR=${0:A:h}
PROJECT_DIR=${SCRIPT_DIR:h}
REPO_ROOT=${PROJECT_DIR:h:h}
ACEFOX_APP=${ACEFOX_APP:-}
LOCAL_EXECUTABLE=${LOCAL_EXECUTABLE:-}
OUTPUT_APP=${OUTPUT_APP:-${PROJECT_DIR}/.build/AI2Apps-dev.app}
PRODUCT_IDENTIFIER=${PRODUCT_IDENTIFIER:-com.ai2apps.desktop.dev}
INSTANCE_ID=${INSTANCE_ID:-dev}

if [[ -z ${ACEFOX_APP} || ! -d ${ACEFOX_APP} ]]; then
  print -u2 "Set ACEFOX_APP to a built Acefox.app"
  exit 64
fi
ACEFOX_EXECUTABLE="${ACEFOX_APP}/Contents/MacOS/firefox"
if [[ ! -x ${ACEFOX_EXECUTABLE} ]]; then
  print -u2 "ACEFOX_APP does not contain an executable Contents/MacOS/firefox"
  exit 64
fi
if ! /usr/bin/strings "${ACEFOX_EXECUTABLE}" | /usr/bin/grep -Fqx 'AI2APPS_BROWSER_ROLE'; then
  print -u2 "ACEFOX_APP is a plain AceFox build without AI2Apps shell support"
  print -u2 "Use the patched acefox-firefox-153 build, not sdk/moz/firefox or sdk/moz/pkg"
  exit 64
fi
if [[ -z ${LOCAL_EXECUTABLE} || ! -x ${LOCAL_EXECUTABLE} ]]; then
  print -u2 "Set LOCAL_EXECUTABLE to an executable AI2Apps Local entrypoint"
  exit 64
fi
swift build --package-path "${PROJECT_DIR}" --product ai2apps-helper
swift build --package-path "${PROJECT_DIR}" --product ai2apps-launcher
swift build --package-path "${PROJECT_DIR}" --product ai2apps-updater

BUILD_BIN=$(swift build --package-path "${PROJECT_DIR}" --show-bin-path)
STAGING_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/ai2apps-dev-app.XXXXXX")
trap 'rm -rf "${STAGING_ROOT}"' EXIT
APP="${STAGING_ROOT}/AI2Apps.app"
SHELL_APP="${APP}/Contents/Applications/AI2AppsShell.app"

mkdir -p "${SHELL_APP}"
rsync -aL "${ACEFOX_APP}/" "${SHELL_APP}/"
# Objdir bundles contain a one-shot marker that Gecko deletes on first launch.
# It must not be part of a signed product resource seal.
find "${SHELL_APP}" -name .purgecaches -type f -delete
rm -f "${SHELL_APP}/Contents/moz.build"
mv "${SHELL_APP}/Contents/MacOS/firefox" "${SHELL_APP}/Contents/MacOS/acefox-bin"
if ! /usr/bin/strings "${SHELL_APP}/Contents/MacOS/acefox-bin" | \
    /usr/bin/grep -Fqx 'AI2APPS_BROWSER_ROLE'; then
  print -u2 "Staged AceFox lost the required AI2Apps shell marker"
  exit 65
fi
ACTOR_ROOT="${SHELL_APP}/Contents/Resources/browser/chrome/browser/content/browser/ai2apps"
ACTOR_PARENT='chrome/browser/content/browser/ai2apps/ManagedBrowserParent.sys.mjs'
ACTOR_CHILD='chrome/browser/content/browser/ai2apps/ManagedBrowserChild.sys.mjs'
BROWSER_OMNI="${SHELL_APP}/Contents/Resources/browser/omni.ja"
ACTOR_CONTRACT_VALID=false
if [[ -f "${ACTOR_ROOT}/ManagedBrowserParent.sys.mjs" && \
      -f "${ACTOR_ROOT}/ManagedBrowserChild.sys.mjs" ]] && \
    /usr/bin/grep -Fq 'export class AI2AppsManagedBrowserParent' \
      "${ACTOR_ROOT}/ManagedBrowserParent.sys.mjs" && \
    /usr/bin/grep -Fq 'export class AI2AppsManagedBrowserChild' \
      "${ACTOR_ROOT}/ManagedBrowserChild.sys.mjs" && \
    /usr/bin/grep -Fq 'async receiveMessage(message)' \
      "${ACTOR_ROOT}/ManagedBrowserChild.sys.mjs"; then
  ACTOR_CONTRACT_VALID=true
elif [[ -f ${BROWSER_OMNI} ]] && \
    /usr/bin/unzip -p "${BROWSER_OMNI}" "${ACTOR_PARENT}" | \
      /usr/bin/grep -Fq 'export class AI2AppsManagedBrowserParent' && \
    /usr/bin/unzip -p "${BROWSER_OMNI}" "${ACTOR_CHILD}" | \
      /usr/bin/grep -Fq 'export class AI2AppsManagedBrowserChild' && \
    /usr/bin/unzip -p "${BROWSER_OMNI}" "${ACTOR_CHILD}" | \
      /usr/bin/grep -Fq 'async receiveMessage(message)'; then
  ACTOR_CONTRACT_VALID=true
fi
if [[ ${ACTOR_CONTRACT_VALID} != true ]]; then
  print -u2 "Staged AceFox has an invalid AI2Apps Window Actor contract"
  exit 65
fi

mkdir -p "${APP}/Contents/MacOS" "${APP}/Contents/Resources"
cp "${SHELL_APP}/Contents/Info.plist" "${APP}/Contents/Info.plist"
for icon in "${SHELL_APP}"/Contents/Resources/*.icns(N); do
  cp "${icon}" "${APP}/Contents/Resources/${icon:t}"
done
cp "${BUILD_BIN}/ai2apps-launcher" "${APP}/Contents/MacOS/AI2Apps"
mkdir -p "${APP}/Contents/Helpers"
cp "${BUILD_BIN}/ai2apps-updater" "${APP}/Contents/Helpers/AI2AppsUpdater"
UPDATE_RESOURCES="${APP}/Contents/Resources/Update"
mkdir -p "${UPDATE_RESOURCES}"
for update_script in \
  stage-update-candidate.py \
  verify-update-candidate.py \
  verify-release-metadata.py \
  generate-release-metadata.py \
  verify-dmg-contents.sh; do
  cp "${PROJECT_DIR}/scripts/${update_script}" "${UPDATE_RESOURCES}/${update_script}"
  chmod 755 "${UPDATE_RESOURCES}/${update_script}"
done

HELPER_APP="${APP}/Contents/Library/LoginItems/AI2AppsHelper.app"
mkdir -p "${HELPER_APP}/Contents/MacOS" "${HELPER_APP}/Contents/Resources"
cp "${BUILD_BIN}/ai2apps-helper" "${HELPER_APP}/Contents/MacOS/AI2AppsHelper"
cp "${REPO_ROOT}/ai2apps/web/static/logo-light.svg" \
  "${HELPER_APP}/Contents/Resources/menubar-logo.svg"
cp "${REPO_ROOT}/ai2apps/web/static/menubar-logo-update.svg" \
  "${HELPER_APP}/Contents/Resources/menubar-logo-update.svg"
cp "${REPO_ROOT}/ai2apps/web/static/menubar-logo-work.svg" \
  "${HELPER_APP}/Contents/Resources/menubar-logo-work.svg"
cp "${REPO_ROOT}/ai2apps/web/static/menubar-logo-ready.svg" \
  "${HELPER_APP}/Contents/Resources/menubar-logo-ready.svg"
plutil -create xml1 "${HELPER_APP}/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :CFBundleIdentifier string ${PRODUCT_IDENTIFIER}.helper" "${HELPER_APP}/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :CFBundleExecutable string AI2AppsHelper" "${HELPER_APP}/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :CFBundleName string AI2Apps Helper" "${HELPER_APP}/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :CFBundlePackageType string APPL" "${HELPER_APP}/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :LSUIElement bool true" "${HELPER_APP}/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :LSMinimumSystemVersion string 13.0" "${HELPER_APP}/Contents/Info.plist"

RUNTIME_ROOT="${HELPER_APP}/Contents/Resources/AI2AppsLocal"
mkdir -p "${RUNTIME_ROOT}/bin"
cp "${LOCAL_EXECUTABLE}" "${RUNTIME_ROOT}/bin/omlx"
chmod 755 "${RUNTIME_ROOT}/bin/omlx"

INFO_PLIST="${APP}/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier ${PRODUCT_IDENTIFIER}" "${INFO_PLIST}"
/usr/libexec/PlistBuddy -c "Set :CFBundleExecutable AI2Apps" "${INFO_PLIST}"
/usr/libexec/PlistBuddy -c "Set :CFBundleName AI2Apps" "${INFO_PLIST}"
/usr/libexec/PlistBuddy -c "Add :AI2AppsDevelopment bool true" "${INFO_PLIST}"
/usr/libexec/PlistBuddy -c "Add :AI2AppsInstanceID string ${INSTANCE_ID}" "${INFO_PLIST}"
/usr/libexec/PlistBuddy -c "Add :AI2AppsUpdaterProtocol integer 1" "${INFO_PLIST}"
/usr/libexec/PlistBuddy -c "Add :AI2AppsUpdateStagingProtocol integer 1" "${INFO_PLIST}"
/usr/libexec/PlistBuddy -c "Set :CFBundleDisplayName AI2Apps" "${INFO_PLIST}" 2>/dev/null || \
  /usr/libexec/PlistBuddy -c "Add :CFBundleDisplayName string AI2Apps" "${INFO_PLIST}"

SHELL_INFO="${SHELL_APP}/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier ${PRODUCT_IDENTIFIER}.shell" "${SHELL_INFO}"
/usr/libexec/PlistBuddy -c "Set :CFBundleExecutable acefox-bin" "${SHELL_INFO}"
/usr/libexec/PlistBuddy -c "Set :CFBundleName AI2Apps" "${SHELL_INFO}"
/usr/libexec/PlistBuddy -c "Set :CFBundleDisplayName AI2Apps" "${SHELL_INFO}" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Add :AI2AppsInstanceID string ${INSTANCE_ID}" "${SHELL_INFO}"
/usr/libexec/PlistBuddy -c "Add :AI2AppsBrowserRole string shell" "${SHELL_INFO}"
/usr/libexec/PlistBuddy -c "Add :AI2AppsSharedBrowserBundle bool true" "${SHELL_INFO}"
/usr/libexec/PlistBuddy -c "Add :AI2AppsDisableRemoteServer bool true" "${SHELL_INFO}"
/usr/libexec/PlistBuddy -c "Add :AI2AppsStorageMode string user-library" "${SHELL_INFO}"

/usr/libexec/PlistBuddy -c "Add :AI2AppsInstanceID string ${INSTANCE_ID}" "${HELPER_APP}/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :AI2AppsMainBundleIdentifier string ${PRODUCT_IDENTIFIER}" "${HELPER_APP}/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :AI2AppsBuildNumber string development" "${HELPER_APP}/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :AI2AppsRuntimeVersion string development" "${HELPER_APP}/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :AI2AppsDevelopment bool true" "${HELPER_APP}/Contents/Info.plist"

# Localized metadata overrides Info.plist on macOS, including for nested Apps.
for localized_info in "${SHELL_APP}"/Contents/Resources/*.lproj/InfoPlist.strings(N); do
  /usr/libexec/PlistBuddy -c "Set :CFBundleName AI2Apps" "${localized_info}" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c "Add :CFBundleName string AI2Apps" "${localized_info}"
  /usr/libexec/PlistBuddy -c "Set :CFBundleDisplayName AI2Apps" "${localized_info}" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c "Add :CFBundleDisplayName string AI2Apps" "${localized_info}"
done
# Use the same ordered signing pass as release builds. A blanket --deep
# re-sign strips the browser bundle's audio-input/JIT entitlements, leaving
# Firefox permission state at "granted" while macOS refuses microphone input.
APP="${APP}" SIGN_IDENTITY=- MODE=full \
  "${PROJECT_DIR}/scripts/sign-release-app.sh"
codesign --verify --deep --strict "${APP}"
mkdir -p "${OUTPUT_APP:h}"
if [[ -e ${OUTPUT_APP} ]]; then
  ARCHIVE_DIR="${OUTPUT_APP:h}/archive"
  ARCHIVE_STEM="${OUTPUT_APP:t:r}-$(date +%Y%m%d-%H%M%S)"
  ARCHIVE_APP="${ARCHIVE_DIR}/${ARCHIVE_STEM}.app"
  ARCHIVE_SUFFIX=1
  mkdir -p "${ARCHIVE_DIR}"
  while [[ -e ${ARCHIVE_APP} ]]; do
    ARCHIVE_APP="${ARCHIVE_DIR}/${ARCHIVE_STEM}-${ARCHIVE_SUFFIX}.app"
    (( ARCHIVE_SUFFIX += 1 ))
  done
  mv "${OUTPUT_APP}" "${ARCHIVE_APP}"
  print "Archived previous development App as ${ARCHIVE_APP}"
fi
mv "${APP}" "${OUTPUT_APP}"
print "Built ${OUTPUT_APP}"
