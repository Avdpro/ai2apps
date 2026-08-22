#!/bin/zsh

set -euo pipefail

SCRIPT_DIR=${0:A:h}
PROJECT_DIR=${SCRIPT_DIR:h}
REPO_ROOT=${PROJECT_DIR:h:h}
ACEFOX_APP=${ACEFOX_APP:-}
RUNTIME_LAYERS=${RUNTIME_LAYERS:-${REPO_ROOT}/packaging/_export}
RUNTIME_PROFILE=${RUNTIME_PROFILE:-full}
OUTPUT_APP=${OUTPUT_APP:-${PROJECT_DIR}/.build/release/AI2Apps.app}
PRODUCT_IDENTIFIER=${PRODUCT_IDENTIFIER:-com.ai2apps.desktop}
INSTANCE_ID=${INSTANCE_ID:-default}
SIGN_IDENTITY=${SIGN_IDENTITY:--}
BUILD_NUMBER=${BUILD_NUMBER:-}
ENTITLEMENTS_DIR=${ENTITLEMENTS_DIR:-${PROJECT_DIR}/entitlements}
KEEP_FAILED_STAGING=${KEEP_FAILED_STAGING:-0}
SANDBOX_MODE=${SANDBOX_MODE:-0}
TEAM_IDENTIFIER=${TEAM_IDENTIFIER:-}

fail() {
  print -u2 "build-release-app: $*"
  exit 64
}

set_localized_bundle_name() {
  local bundle=$1
  local display_name=$2
  local localized_info
  # A localized InfoPlist.strings value overrides Info.plist on macOS. Keep
  # Gecko's localized metadata, but make the visible product name match the
  # role of each embedded App bundle.
  for localized_info in "${bundle}"/Contents/Resources/*.lproj/InfoPlist.strings(N); do
    /usr/libexec/PlistBuddy -c "Set :CFBundleName ${display_name}" "${localized_info}" 2>/dev/null || \
      /usr/libexec/PlistBuddy -c "Add :CFBundleName string ${display_name}" "${localized_info}"
    /usr/libexec/PlistBuddy -c "Set :CFBundleDisplayName ${display_name}" "${localized_info}" 2>/dev/null || \
      /usr/libexec/PlistBuddy -c "Add :CFBundleDisplayName string ${display_name}" "${localized_info}"
  done
}

[[ -n ${ACEFOX_APP} && -d ${ACEFOX_APP} ]] || fail "set ACEFOX_APP to a built Acefox.app"
[[ -f ${ACEFOX_APP}/Contents/Resources/omni.ja ]] || \
  fail "ACEFOX_APP must be a packaged AceFox bundle with Resources/omni.ja"
[[ -d ${RUNTIME_LAYERS}/cpython-3.11 ]] || fail "missing cpython-3.11 in RUNTIME_LAYERS"
[[ ${RUNTIME_PROFILE} == full || ${RUNTIME_PROFILE} == cloud ]] || \
  fail "RUNTIME_PROFILE must be full or cloud"
if [[ ${RUNTIME_PROFILE} == cloud ]]; then
  FRAMEWORK_LAYER=framework-control-plane
else
  FRAMEWORK_LAYER=framework-mlx-base
fi
[[ -d ${RUNTIME_LAYERS}/${FRAMEWORK_LAYER} ]] || \
  fail "missing ${FRAMEWORK_LAYER} in RUNTIME_LAYERS"
[[ -n ${PRODUCT_IDENTIFIER} && ${PRODUCT_IDENTIFIER} != *[^A-Za-z0-9.-]* ]] || fail "invalid PRODUCT_IDENTIFIER"
[[ -n ${INSTANCE_ID} && ${INSTANCE_ID} != *[^a-z0-9.-]* ]] || fail "invalid INSTANCE_ID"
[[ ${INSTANCE_ID[1]} != [.-] && ${INSTANCE_ID[-1]} != [.-] ]] || fail "invalid INSTANCE_ID"
[[ ${#INSTANCE_ID} -le 64 ]] || fail "INSTANCE_ID is too long"
[[ ${SANDBOX_MODE} == 0 || ${SANDBOX_MODE} == 1 ]] || fail "SANDBOX_MODE must be 0 or 1"
if [[ ${SANDBOX_MODE} == 1 ]]; then
  [[ ${SIGN_IDENTITY} != - ]] || \
    fail "Sandbox App Group builds require an Apple signing identity; ad-hoc signing is unsupported"
  [[ ${#TEAM_IDENTIFIER} -eq 10 && ${TEAM_IDENTIFIER} != *[^A-Z0-9]* ]] || \
    fail "TEAM_IDENTIFIER is required for Sandbox builds"
  APPLICATION_GROUP_IDENTIFIER=${TEAM_IDENTIFIER}.${PRODUCT_IDENTIFIER}.instance
fi
[[ ! -e ${OUTPUT_APP} ]] || fail "output already exists: ${OUTPUT_APP}"

RUNTIME_VERSION=$(sed -n 's/^__version__ = "\([^"]*\)"/\1/p' "${REPO_ROOT}/ai2apps/_version.py")
[[ -n ${RUNTIME_VERSION} ]] || fail "cannot read AI2Apps runtime version"
if [[ -z ${BUILD_NUMBER} ]]; then
  BUILD_NUMBER=$(git -C "${REPO_ROOT}" rev-list --count HEAD 2>/dev/null || print 1)
fi
[[ ${BUILD_NUMBER} == <-> && ${BUILD_NUMBER} -ge 1 ]] || fail "BUILD_NUMBER must be a positive integer"

swift build --configuration release --package-path "${PROJECT_DIR}" --product ai2apps-helper
swift build --configuration release --package-path "${PROJECT_DIR}" --product ai2apps-launcher
swift build --configuration release --package-path "${PROJECT_DIR}" --product ai2apps-updater
BUILD_BIN=$(swift build --configuration release --package-path "${PROJECT_DIR}" --show-bin-path)

STAGING_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/ai2apps-release-app.XXXXXX")
cleanup() {
  local exit_code=$?
  if [[ ${exit_code} -ne 0 && ${KEEP_FAILED_STAGING} == 1 ]]; then
    print -u2 "build-release-app: preserved failed staging at ${STAGING_ROOT}"
  else
    rm -rf "${STAGING_ROOT}"
  fi
}
trap cleanup EXIT
APP=${STAGING_ROOT}/AI2Apps.app
SHELL_APP=${APP}/Contents/Applications/AI2AppsShell.app
mkdir -p "${SHELL_APP}"
rsync -aL "${ACEFOX_APP}/" "${SHELL_APP}/"
# Objdir bundles contain a one-shot marker that Gecko deletes on first launch.
# It must not be part of a signed product resource seal.
find "${SHELL_APP}" -name .purgecaches -type f -delete
# The objdir development bundle also exposes the packaging moz.build at the
# bundle root.  It is source metadata, not a runtime resource, and codesign
# classifies the .build suffix as a nested code object under Developer ID.
rm -f "${SHELL_APP}/Contents/moz.build"

mv "${SHELL_APP}/Contents/MacOS/firefox" "${SHELL_APP}/Contents/MacOS/acefox-bin"
mkdir -p "${APP}/Contents/MacOS" "${APP}/Contents/Resources"
cp "${SHELL_APP}/Contents/Info.plist" "${APP}/Contents/Info.plist"
for icon in "${SHELL_APP}/Contents/Resources"/*.icns(N); do
  cp "${icon}" "${APP}/Contents/Resources/${icon:t}"
done
cp "${BUILD_BIN}/ai2apps-launcher" "${APP}/Contents/MacOS/AI2Apps"
mkdir -p "${APP}/Contents/Helpers"
cp "${BUILD_BIN}/ai2apps-updater" "${APP}/Contents/Helpers/AI2AppsUpdater"
UPDATE_RESOURCES=${APP}/Contents/Resources/Update
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

HELPER_APP=${APP}/Contents/Library/LoginItems/AI2AppsHelper.app
mkdir -p "${HELPER_APP}/Contents/MacOS" "${HELPER_APP}/Contents/Resources"
cp "${BUILD_BIN}/ai2apps-helper" "${HELPER_APP}/Contents/MacOS/AI2AppsHelper"
cp "${REPO_ROOT}/ai2apps/web/static/logo-light.svg" \
  "${HELPER_APP}/Contents/Resources/menubar-logo.svg"
plutil -create xml1 "${HELPER_APP}/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :CFBundleIdentifier string ${PRODUCT_IDENTIFIER}.helper" "${HELPER_APP}/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :CFBundleExecutable string AI2AppsHelper" "${HELPER_APP}/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :CFBundleName string AI2Apps Helper" "${HELPER_APP}/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :CFBundlePackageType string APPL" "${HELPER_APP}/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :LSUIElement bool true" "${HELPER_APP}/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :LSMinimumSystemVersion string 13.0" "${HELPER_APP}/Contents/Info.plist"
if [[ ${SANDBOX_MODE} == 1 ]]; then
  /usr/libexec/PlistBuddy -c "Add :AI2AppsApplicationGroupIdentifier string ${APPLICATION_GROUP_IDENTIFIER}" "${HELPER_APP}/Contents/Info.plist"
fi
RUNTIME_ROOT=${HELPER_APP}/Contents/Resources/AI2AppsLocal
mkdir -p "${RUNTIME_ROOT}/Python" "${RUNTIME_ROOT}/app" "${RUNTIME_ROOT}/bin"
ditto "${RUNTIME_LAYERS}/cpython-3.11" "${RUNTIME_ROOT}/Python/cpython-3.11"
ditto "${RUNTIME_LAYERS}/${FRAMEWORK_LAYER}" "${RUNTIME_ROOT}/Python/${FRAMEWORK_LAYER}"
if [[ -d ${RUNTIME_LAYERS}/__venvstacks__ ]]; then
  ditto "${RUNTIME_LAYERS}/__venvstacks__" "${RUNTIME_ROOT}/Python/__venvstacks__"
fi
# Export layers may carry bytecode produced by the packaging interpreter. It is
# unnecessary in the immutable App and can target a different CPython ABI.
find "${RUNTIME_ROOT}/Python" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
find "${RUNTIME_ROOT}/Python" -type d -name __pycache__ -empty -delete
rsync -a \
  --exclude='__pycache__' --exclude='*.pyc' --exclude='tests' --exclude='.git' \
  --exclude='custom_kernels/*/csrc' \
  "${REPO_ROOT}/ai2apps/" "${RUNTIME_ROOT}/app/ai2apps/"
OMLX_PROFILE_EXCLUDES=()
if [[ ${RUNTIME_PROFILE} == cloud ]]; then
  OMLX_PROFILE_EXCLUDES=(
    --exclude='custom_kernels'
    --exclude='eval'
    --exclude='oq_calibration_data.json'
    --exclude='oqe_calibration_data.json'
  )
fi
rsync -a \
  --exclude='__pycache__' --exclude='*.pyc' --exclude='tests' --exclude='.git' \
  --exclude='custom_kernels/*/csrc' \
  "${OMLX_PROFILE_EXCLUDES[@]}" \
  "${REPO_ROOT}/omlx/" "${RUNTIME_ROOT}/app/omlx/"
# The working tree may contain locally built extensions for another Python
# (currently CPython 3.13).  The embedded Runtime is CPython 3.11; shipping a
# mismatched extension creates a latent import failure.  These kernels all
# provide a Python/MLX fallback when no compatible native extension is present.
find "${RUNTIME_ROOT}/app" -type f -name '*.cpython-*.so' \
  ! -name '*.cpython-311-*.so' -delete
# venvstacks' dynlib directory may retain links into packages deliberately
# stripped from the release export. They are unusable and make strict bundle
# verification fail with a misleading top-level "No such file" error.
find -L "${RUNTIME_ROOT}/Python" -type l -exec rm -f {} +
cp "${SCRIPT_DIR}/runtime-entrypoint.sh" "${RUNTIME_ROOT}/bin/omlx"
chmod 755 "${RUNTIME_ROOT}/bin/omlx"
/usr/bin/python3 "${SCRIPT_DIR}/generate-runtime-manifest.py" \
  --root "${RUNTIME_ROOT}" --runtime-version "${RUNTIME_VERSION}" \
  --runtime-profile "${RUNTIME_PROFILE}"

INFO_PLIST=${APP}/Contents/Info.plist
/usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier ${PRODUCT_IDENTIFIER}" "${INFO_PLIST}"
/usr/libexec/PlistBuddy -c "Set :CFBundleExecutable AI2Apps" "${INFO_PLIST}"
/usr/libexec/PlistBuddy -c "Set :CFBundleName AI2Apps" "${INFO_PLIST}"
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString ${RUNTIME_VERSION}" "${INFO_PLIST}"
/usr/libexec/PlistBuddy -c "Set :CFBundleVersion ${BUILD_NUMBER}" "${INFO_PLIST}"
/usr/libexec/PlistBuddy -c "Set :LSMinimumSystemVersion 13.0" "${INFO_PLIST}" 2>/dev/null || \
  /usr/libexec/PlistBuddy -c "Add :LSMinimumSystemVersion string 13.0" "${INFO_PLIST}"
/usr/libexec/PlistBuddy -c "Delete :AI2AppsDevelopment" "${INFO_PLIST}" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Add :AI2AppsInstanceID string ${INSTANCE_ID}" "${INFO_PLIST}"
/usr/libexec/PlistBuddy -c "Add :AI2AppsRuntimeVersion string ${RUNTIME_VERSION}" "${INFO_PLIST}"
/usr/libexec/PlistBuddy -c "Add :AI2AppsRuntimeProfile string ${RUNTIME_PROFILE}" "${INFO_PLIST}"
/usr/libexec/PlistBuddy -c "Add :AI2AppsUpdaterProtocol integer 1" "${INFO_PLIST}"
/usr/libexec/PlistBuddy -c "Add :AI2AppsUpdateStagingProtocol integer 1" "${INFO_PLIST}"
if [[ ${SANDBOX_MODE} == 1 ]]; then
  /usr/libexec/PlistBuddy -c "Add :AI2AppsApplicationGroupIdentifier string ${APPLICATION_GROUP_IDENTIFIER}" "${INFO_PLIST}"
fi
/usr/libexec/PlistBuddy -c "Set :CFBundleDisplayName AI2Apps" "${INFO_PLIST}" 2>/dev/null || \
  /usr/libexec/PlistBuddy -c "Add :CFBundleDisplayName string AI2Apps" "${INFO_PLIST}"

SHELL_INFO=${SHELL_APP}/Contents/Info.plist
/usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier ${PRODUCT_IDENTIFIER}.shell" "${SHELL_INFO}"
/usr/libexec/PlistBuddy -c "Set :CFBundleExecutable acefox-bin" "${SHELL_INFO}"
/usr/libexec/PlistBuddy -c "Set :CFBundleName AI2Apps" "${SHELL_INFO}"
/usr/libexec/PlistBuddy -c "Set :CFBundleDisplayName AI2Apps" "${SHELL_INFO}" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Add :AI2AppsInstanceID string ${INSTANCE_ID}" "${SHELL_INFO}"
/usr/libexec/PlistBuddy -c "Add :AI2AppsBrowserRole string shell" "${SHELL_INFO}"
/usr/libexec/PlistBuddy -c "Add :AI2AppsSharedBrowserBundle bool true" "${SHELL_INFO}"
/usr/libexec/PlistBuddy -c "Add :AI2AppsDisableRemoteServer bool true" "${SHELL_INFO}"
set_localized_bundle_name "${SHELL_APP}" "AI2Apps"
if [[ ${SANDBOX_MODE} == 1 ]]; then
  /usr/libexec/PlistBuddy -c "Add :AI2AppsStorageMode string app-group" "${SHELL_INFO}"
  /usr/libexec/PlistBuddy -c "Add :AI2AppsApplicationGroupIdentifier string ${APPLICATION_GROUP_IDENTIFIER}" "${SHELL_INFO}"
else
  /usr/libexec/PlistBuddy -c "Add :AI2AppsStorageMode string user-library" "${SHELL_INFO}"
fi

/usr/libexec/PlistBuddy -c "Add :AI2AppsInstanceID string ${INSTANCE_ID}" "${HELPER_APP}/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :AI2AppsMainBundleIdentifier string ${PRODUCT_IDENTIFIER}" "${HELPER_APP}/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :AI2AppsBuildNumber string ${BUILD_NUMBER}" "${HELPER_APP}/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :AI2AppsRuntimeVersion string ${RUNTIME_VERSION}" "${HELPER_APP}/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :AI2AppsRuntimeProfile string ${RUNTIME_PROFILE}" "${HELPER_APP}/Contents/Info.plist"

APP="${APP}" SIGN_IDENTITY="${SIGN_IDENTITY}" \
  ENTITLEMENTS_DIR="${ENTITLEMENTS_DIR}" MODE=full \
  SANDBOX_MODE="${SANDBOX_MODE}" \
  APPLICATION_GROUP_IDENTIFIER="${APPLICATION_GROUP_IDENTIFIER:-}" \
  "${SCRIPT_DIR}/sign-release-app.sh"
# Signing changes Mach-O digests inside the embedded Runtime. Refresh the
# Runtime contract, then update only the top-level resource seal.
/usr/bin/python3 "${SCRIPT_DIR}/generate-runtime-manifest.py" \
  --root "${RUNTIME_ROOT}" --runtime-version "${RUNTIME_VERSION}" \
  --runtime-profile "${RUNTIME_PROFILE}"
APP="${APP}" SIGN_IDENTITY="${SIGN_IDENTITY}" \
  ENTITLEMENTS_DIR="${ENTITLEMENTS_DIR}" MODE=seal \
  SANDBOX_MODE="${SANDBOX_MODE}" \
  APPLICATION_GROUP_IDENTIFIER="${APPLICATION_GROUP_IDENTIFIER:-}" \
  "${SCRIPT_DIR}/sign-release-app.sh"
codesign --verify --deep --strict "${APP}"
APP="${APP}" "${SCRIPT_DIR}/verify-release-app.sh"

mkdir -p "${OUTPUT_APP:h}"
# Keep the Developer ID signature valid when the staging directory and output
# directory live on different filesystems. A cross-volume `mv` may fall back
# to a copy implementation that does not preserve every bundle attribute in
# the same way as Apple's bundle-aware copier.
ditto "${APP}" "${OUTPUT_APP}"
codesign --verify --deep --strict "${OUTPUT_APP}"
APP="${OUTPUT_APP}" "${SCRIPT_DIR}/verify-release-app.sh"
print "Built release bundle ${OUTPUT_APP}"
