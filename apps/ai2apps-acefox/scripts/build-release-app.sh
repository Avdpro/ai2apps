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
# An explicitly empty value disables update discovery for isolated development
# bundles. An unset value retains the production default.
UPDATE_MANIFEST_URL=${UPDATE_MANIFEST_URL-https://coder.ai2apps.com/updates/stable.json}
APP_DISPLAY_NAME=${APP_DISPLAY_NAME:-AI2Apps}
APP_ICON_UPPER_COLOR=${APP_ICON_UPPER_COLOR:-}
DEVELOPMENT_BUILD=${DEVELOPMENT_BUILD:-0}
DEVELOPMENT_SOURCE_ROOT=${DEVELOPMENT_SOURCE_ROOT:-}
MENUBAR_ICON_BADGE=${MENUBAR_ICON_BADGE:-none}
ALLOW_INSTANCE_DATA_RESET=${ALLOW_INSTANCE_DATA_RESET:-0}
ACEFOX_SHELL_SOURCE=${ACEFOX_SHELL_SOURCE:-}
SHELL_TITLE_PREFIX=${SHELL_TITLE_PREFIX:-AI2Apps}

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
ACEFOX_EXECUTABLE=${ACEFOX_APP}/Contents/MacOS/firefox
[[ -x ${ACEFOX_EXECUTABLE} ]] || \
  fail "ACEFOX_APP does not contain an executable Contents/MacOS/firefox"
/usr/bin/strings "${ACEFOX_EXECUTABLE}" | /usr/bin/grep -Fqx 'AI2APPS_BROWSER_ROLE' || \
  fail "ACEFOX_APP is a plain AceFox build without AI2Apps shell support; use the patched acefox-firefox-153 build"
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
[[ ${DEVELOPMENT_BUILD} == 0 || ${DEVELOPMENT_BUILD} == 1 ]] || \
  fail "DEVELOPMENT_BUILD must be 0 or 1"
[[ ${ALLOW_INSTANCE_DATA_RESET} == 0 || ${ALLOW_INSTANCE_DATA_RESET} == 1 ]] || \
  fail "ALLOW_INSTANCE_DATA_RESET must be 0 or 1"

# The two fixed non-production identities own fixed visual contracts.  Resolve
# these centrally instead of trusting every wrapper/caller to remember a tint
# and badge argument.  A partial use of either reserved identity is rejected so
# an ad-hoc build cannot accidentally look like another AI2Apps instance.
ICON_CONTRACT=standard
if [[ ${INSTANCE_ID} == test && ${PRODUCT_IDENTIFIER} == com.ai2apps.desktop.test && \
      ${APP_DISPLAY_NAME} == AI2Apps-test ]]; then
  ICON_CONTRACT=test
elif [[ ${INSTANCE_ID} == app-dev && ${PRODUCT_IDENTIFIER} == com.ai2apps.desktop.appdev && \
        ${APP_DISPLAY_NAME} == AI2Apps-App-Dev ]]; then
  ICON_CONTRACT=app-dev
elif [[ ${INSTANCE_ID} == test || ${PRODUCT_IDENTIFIER} == com.ai2apps.desktop.test || \
        ${APP_DISPLAY_NAME} == AI2Apps-test || ${INSTANCE_ID} == app-dev || \
        ${PRODUCT_IDENTIFIER} == com.ai2apps.desktop.appdev || \
        ${APP_DISPLAY_NAME} == AI2Apps-App-Dev ]]; then
  fail "reserved Test/App-Dev identity fields must use their complete fixed identity tuple"
fi

case ${ICON_CONTRACT} in
  test)
    APP_ICON_UPPER_COLOR='#C7E7FA'
    MENUBAR_ICON_BADGE=test
    [[ ${DEVELOPMENT_BUILD} == 0 && ${ALLOW_INSTANCE_DATA_RESET} == 1 ]] || \
      fail "the fixed Test identity must be non-development and resettable"
    ;;
  app-dev)
    APP_ICON_UPPER_COLOR='#E2D5F8'
    MENUBAR_ICON_BADGE=app-dev
    [[ ${DEVELOPMENT_BUILD} == 1 && ${ALLOW_INSTANCE_DATA_RESET} == 1 ]] || \
      fail "the fixed App-Dev identity must be a resettable Development Bundle"
    ;;
  standard)
    [[ -z ${APP_ICON_UPPER_COLOR} && ${MENUBAR_ICON_BADGE} == none ]] || \
      fail "special App/tray icons are reserved for the fixed Test and App-Dev identities"
    ;;
esac

[[ ${MENUBAR_ICON_BADGE} == none || ${MENUBAR_ICON_BADGE} == app-dev || \
   ${MENUBAR_ICON_BADGE} == test ]] || \
  fail "MENUBAR_ICON_BADGE must be none, app-dev, or test"
[[ ${MENUBAR_ICON_BADGE} != app-dev || ${DEVELOPMENT_BUILD} == 1 ]] || \
  fail "the app-dev menu bar badge requires DEVELOPMENT_BUILD=1"
[[ ${MENUBAR_ICON_BADGE} != test || ( ${DEVELOPMENT_BUILD} == 0 && \
   ${ALLOW_INSTANCE_DATA_RESET} == 1 ) ]] || \
  fail "the test menu bar badge requires a non-development resettable build"
[[ -n ${APP_DISPLAY_NAME} && ${APP_DISPLAY_NAME} != *$'\n'* && ${APP_DISPLAY_NAME} != *$'\r'* ]] || \
  fail "APP_DISPLAY_NAME must be a non-empty single-line value"
if [[ -n ${APP_ICON_UPPER_COLOR} ]]; then
  print -r -- "${APP_ICON_UPPER_COLOR}" | /usr/bin/grep -Eq '^#[0-9A-Fa-f]{6}$' || \
    fail "APP_ICON_UPPER_COLOR must use #RRGGBB"
fi
[[ -n ${SHELL_TITLE_PREFIX} ]] || fail "SHELL_TITLE_PREFIX must not be empty"
print -r -- "${SHELL_TITLE_PREFIX}" | /usr/bin/grep -Eq '^[A-Za-z0-9._ -]+$' || \
  fail "SHELL_TITLE_PREFIX contains unsupported characters"
if [[ -n ${DEVELOPMENT_SOURCE_ROOT} ]]; then
  [[ ${DEVELOPMENT_BUILD} == 1 ]] || \
    fail "DEVELOPMENT_SOURCE_ROOT requires DEVELOPMENT_BUILD=1"
  [[ ${DEVELOPMENT_SOURCE_ROOT} == /* ]] || \
    fail "DEVELOPMENT_SOURCE_ROOT must be absolute"
  [[ -f ${DEVELOPMENT_SOURCE_ROOT}/ai2apps/__init__.py ]] || \
    fail "DEVELOPMENT_SOURCE_ROOT must contain ai2apps/__init__.py"
fi
if [[ -n ${ACEFOX_SHELL_SOURCE} ]]; then
  [[ ${DEVELOPMENT_BUILD} == 1 ]] || \
    fail "ACEFOX_SHELL_SOURCE requires DEVELOPMENT_BUILD=1"
  [[ -f ${ACEFOX_SHELL_SOURCE} ]] || \
    fail "ACEFOX_SHELL_SOURCE is not a file: ${ACEFOX_SHELL_SOURCE}"
  /usr/bin/grep -Fq 'function setShellTitle(deviceName, localOrigin)' \
    "${ACEFOX_SHELL_SOURCE}" || \
    fail "ACEFOX_SHELL_SOURCE lacks the Local-aware Shell title contract"
fi
if [[ -n ${UPDATE_MANIFEST_URL} ]]; then
  [[ ${UPDATE_MANIFEST_URL} == https://* ]] || fail "UPDATE_MANIFEST_URL must use HTTPS"
fi
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
SHELL_APP=${APP}/Contents/Applications/AI2Apps.app
mkdir -p "${SHELL_APP}"
rsync -aL "${ACEFOX_APP}/" "${SHELL_APP}/"
# Objdir bundles contain a one-shot marker that Gecko deletes on first launch.
# It must not be part of a signed product resource seal.
find "${SHELL_APP}" -name .purgecaches -type f -delete
# The objdir development bundle also exposes the packaging moz.build at the
# bundle root.  It is source metadata, not a runtime resource, and codesign
# classifies the .build suffix as a nested code object under Developer ID.
rm -f "${SHELL_APP}/Contents/moz.build"

if [[ -n ${ACEFOX_SHELL_SOURCE} ]]; then
  # The packaged AceFox input is intentionally immutable, but its browser
  # omni.ja can lag behind the current App-Shell source used by the objdir Dev
  # App. Overlay the Shell and its native prompt actor into this Development
  # bundle so window and dialog titles match the current source.
  BROWSER_OMNI=${SHELL_APP}/Contents/Resources/browser/omni.ja
  [[ -f ${BROWSER_OMNI} ]] || fail "packaged AceFox is missing browser/omni.ja"
  SHELL_RESOURCE=chrome/browser/content/browser/ai2apps/shell.mjs
  SHELL_DOCUMENT_RESOURCE=chrome/browser/content/browser/ai2apps/shell.xhtml
  SHELL_DOCUMENT_SOURCE=${ACEFOX_SHELL_SOURCE:h}/shell.xhtml
  [[ -f ${SHELL_DOCUMENT_SOURCE} ]] || fail "matching AceFox Shell document is missing"
  PROMPT_RESOURCE=actors/PromptParent.sys.mjs
  PROMPT_SOURCE=${ACEFOX_SHELL_SOURCE:h:h:h:h}/actors/PromptParent.sys.mjs
  [[ -f ${PROMPT_SOURCE} ]] || fail "matching AceFox PromptParent source is missing"
  SHELL_OVERLAY_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/ai2apps-shell-overlay.XXXXXX")
  mkdir -p "${SHELL_OVERLAY_ROOT}/${SHELL_RESOURCE:h}"
  cp "${SHELL_DOCUMENT_SOURCE}" "${SHELL_OVERLAY_ROOT}/${SHELL_DOCUMENT_RESOURCE}"
  mkdir -p "${SHELL_OVERLAY_ROOT}/${PROMPT_RESOURCE:h}"
  cp "${PROMPT_SOURCE}" "${SHELL_OVERLAY_ROOT}/${PROMPT_RESOURCE}"
  /usr/bin/sed \
    "s@const title = \`AI2Apps: \${deviceName} \${localAddress}\`;@const title = \`${SHELL_TITLE_PREFIX}: \${deviceName} \${localAddress}\`;@" \
    "${ACEFOX_SHELL_SOURCE}" > "${SHELL_OVERLAY_ROOT}/${SHELL_RESOURCE}"
  /usr/bin/grep -Fq \
    "const title = \`${SHELL_TITLE_PREFIX}: \${deviceName} \${localAddress}\`;" \
    "${SHELL_OVERLAY_ROOT}/${SHELL_RESOURCE}" || \
    fail "could not apply SHELL_TITLE_PREFIX to ACEFOX_SHELL_SOURCE"
  (
    cd "${SHELL_OVERLAY_ROOT}"
    /usr/bin/zip -q -X "${BROWSER_OMNI}" "${SHELL_RESOURCE}" "${SHELL_DOCUMENT_RESOURCE}" "${PROMPT_RESOURCE}"
  )
  rm -rf "${SHELL_OVERLAY_ROOT}"
fi

mv "${SHELL_APP}/Contents/MacOS/firefox" "${SHELL_APP}/Contents/MacOS/acefox-bin"
/usr/bin/strings "${SHELL_APP}/Contents/MacOS/acefox-bin" | \
  /usr/bin/grep -Fqx 'AI2APPS_BROWSER_ROLE' || \
  fail "staged AceFox lost the required AI2Apps shell marker"
mkdir -p "${APP}/Contents/MacOS" "${APP}/Contents/Resources"
LICENSE_ROOT=${APP}/Contents/Resources/Licenses
mkdir -p "${LICENSE_ROOT}/LICENSES"
for license_file in LICENSE LICENSE-POLICY.md NOTICE TRADEMARKS.md; do
  [[ -s ${REPO_ROOT}/${license_file} ]] || fail "missing release license ${license_file}"
  cp "${REPO_ROOT}/${license_file}" "${LICENSE_ROOT}/${license_file}"
done
cp "${REPO_ROOT}/LICENSES/AI2APPS-CLOUD-CONNECTOR-BSL-1.1.md" "${LICENSE_ROOT}/LICENSES/"
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
cp "${REPO_ROOT}/ai2apps/web/static/menubar-logo-update.svg" \
  "${HELPER_APP}/Contents/Resources/menubar-logo-update.svg"
cp "${REPO_ROOT}/ai2apps/web/static/menubar-logo-work.svg" \
  "${HELPER_APP}/Contents/Resources/menubar-logo-work.svg"
cp "${REPO_ROOT}/ai2apps/web/static/menubar-logo-ready.svg" \
  "${HELPER_APP}/Contents/Resources/menubar-logo-ready.svg"
if [[ ${MENUBAR_ICON_BADGE} == app-dev ]]; then
  # Keep the normal icon and its status variants recognizable, while making
  # the isolated App-Shell development Helper obvious in the menu bar.
  for menubar_icon in "${HELPER_APP}/Contents/Resources"/menubar-logo*.svg; do
    badge_staging=${menubar_icon}.badge
    /usr/bin/sed 's@</svg>@  <circle id="ai2apps-app-dev-badge" cx="7.5" cy="7.5" r="6.25" fill="#FF9500" stroke="#FFF" stroke-width="1.5"/>\
</svg>@' "${menubar_icon}" > "${badge_staging}"
    mv "${badge_staging}" "${menubar_icon}"
  done
elif [[ ${MENUBAR_ICON_BADGE} == test ]]; then
  # Purple diamonds in both top corners distinguish the release-shaped test
  # Helper from production and single-badge App-Dev at menu-bar size.
  for menubar_icon in "${HELPER_APP}/Contents/Resources"/menubar-logo*.svg; do
    badge_staging=${menubar_icon}.badge
    /usr/bin/sed 's@</svg>@  <path id="ai2apps-test-badge-left" d="M7.5 1.25 13.75 7.5 7.5 13.75 1.25 7.5Z" fill="#AF52DE" stroke="#FFF" stroke-width="1.5" stroke-linejoin="round"/>\
  <path id="ai2apps-test-badge-right" d="M45.416666 1.25 51.666666 7.5 45.416666 13.75 39.166666 7.5Z" fill="#AF52DE" stroke="#FFF" stroke-width="1.5" stroke-linejoin="round"/>\
</svg>@' "${menubar_icon}" > "${badge_staging}"
    mv "${badge_staging}" "${menubar_icon}"
  done
fi
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
if [[ -n ${APP_ICON_UPPER_COLOR} ]]; then
  ICON_TINT_PYTHON=${RUNTIME_ROOT}/Python/cpython-3.11/bin/python3.11
  ICON_TINT_SITE=${RUNTIME_ROOT}/Python/${FRAMEWORK_LAYER}/lib/python3.11/site-packages
  for app_icon in \
    "${APP}/Contents/Resources/firefox.icns" \
    "${SHELL_APP}/Contents/Resources/firefox.icns"; do
    [[ -f ${app_icon} ]] || fail "missing App icon to tint: ${app_icon}"
    env \
      PYTHONHOME="${RUNTIME_ROOT}/Python/cpython-3.11" \
      PYTHONNOUSERSITE=1 \
      PYTHONDONTWRITEBYTECODE=1 \
      PYTHONPATH="${ICON_TINT_SITE}" \
      "${ICON_TINT_PYTHON}" "${SCRIPT_DIR}/tint_app_icon.py" \
      --icns "${app_icon}" --color "${APP_ICON_UPPER_COLOR}"
  done
fi

# Fail before signing if a future build path drops, duplicates, or mixes the
# fixed visual identities.  Both Dock icons must be byte-identical, and every
# Helper state must carry exactly the badge assigned to its instance role.
/usr/bin/cmp -s \
  "${APP}/Contents/Resources/firefox.icns" \
  "${SHELL_APP}/Contents/Resources/firefox.icns" || \
  fail "main App and embedded Shell icons do not match"
for menubar_icon in "${HELPER_APP}/Contents/Resources"/menubar-logo*.svg; do
  case ${ICON_CONTRACT} in
    test)
      /usr/bin/grep -Fq 'id="ai2apps-test-badge-left"' "${menubar_icon}" && \
        /usr/bin/grep -Fq 'id="ai2apps-test-badge-right"' "${menubar_icon}" || \
        fail "Test Helper icon is missing its two dedicated badges: ${menubar_icon:t}"
      ;;
    app-dev)
      /usr/bin/grep -Fq 'id="ai2apps-app-dev-badge"' "${menubar_icon}" || \
        fail "App-Dev Helper icon is missing its dedicated badge: ${menubar_icon:t}"
      ;;
    standard)
      ! /usr/bin/grep -Eq 'id="ai2apps-(test|app-dev)-badge' "${menubar_icon}" || \
        fail "standard Helper icon unexpectedly contains a reserved badge: ${menubar_icon:t}"
      ;;
  esac
done
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
if [[ ${DEVELOPMENT_BUILD} == 1 ]]; then
  /usr/libexec/PlistBuddy -c "Add :AI2AppsDevelopment bool true" "${INFO_PLIST}"
fi
if [[ -n ${DEVELOPMENT_SOURCE_ROOT} ]]; then
  /usr/libexec/PlistBuddy -c "Add :AI2AppsDevelopmentSourceRoot string ${DEVELOPMENT_SOURCE_ROOT}" "${INFO_PLIST}"
fi
/usr/libexec/PlistBuddy -c "Add :AI2AppsInstanceID string ${INSTANCE_ID}" "${INFO_PLIST}"
/usr/libexec/PlistBuddy -c "Add :AI2AppsRuntimeVersion string ${RUNTIME_VERSION}" "${INFO_PLIST}"
/usr/libexec/PlistBuddy -c "Add :AI2AppsRuntimeProfile string ${RUNTIME_PROFILE}" "${INFO_PLIST}"
/usr/libexec/PlistBuddy -c "Add :AI2AppsIconContract string ${ICON_CONTRACT}" "${INFO_PLIST}"
/usr/libexec/PlistBuddy -c "Add :AI2AppsUpdaterProtocol integer 1" "${INFO_PLIST}"
/usr/libexec/PlistBuddy -c "Add :AI2AppsUpdateStagingProtocol integer 1" "${INFO_PLIST}"
if [[ -n ${UPDATE_MANIFEST_URL} ]]; then
  /usr/libexec/PlistBuddy -c "Add :AI2AppsUpdateManifestURL string ${UPDATE_MANIFEST_URL}" "${INFO_PLIST}"
fi
if [[ ${SANDBOX_MODE} == 1 ]]; then
  /usr/libexec/PlistBuddy -c "Add :AI2AppsApplicationGroupIdentifier string ${APPLICATION_GROUP_IDENTIFIER}" "${INFO_PLIST}"
fi
/usr/libexec/PlistBuddy -c "Set :CFBundleName ${APP_DISPLAY_NAME}" "${INFO_PLIST}"
/usr/libexec/PlistBuddy -c "Set :CFBundleDisplayName ${APP_DISPLAY_NAME}" "${INFO_PLIST}" 2>/dev/null || \
  /usr/libexec/PlistBuddy -c "Add :CFBundleDisplayName string ${APP_DISPLAY_NAME}" "${INFO_PLIST}"

SHELL_INFO=${SHELL_APP}/Contents/Info.plist
/usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier ${PRODUCT_IDENTIFIER}.shell" "${SHELL_INFO}"
/usr/libexec/PlistBuddy -c "Set :CFBundleExecutable acefox-bin" "${SHELL_INFO}"
/usr/libexec/PlistBuddy -c "Set :CFBundleName AI2Apps" "${SHELL_INFO}"
/usr/libexec/PlistBuddy -c "Set :CFBundleDisplayName AI2Apps" "${SHELL_INFO}" 2>/dev/null || \
  /usr/libexec/PlistBuddy -c "Add :CFBundleDisplayName string AI2Apps" "${SHELL_INFO}"
/usr/libexec/PlistBuddy -c "Add :AI2AppsInstanceID string ${INSTANCE_ID}" "${SHELL_INFO}"
/usr/libexec/PlistBuddy -c "Add :AI2AppsBrowserRole string shell" "${SHELL_INFO}"
/usr/libexec/PlistBuddy -c "Add :AI2AppsSharedBrowserBundle bool true" "${SHELL_INFO}"
/usr/libexec/PlistBuddy -c "Add :AI2AppsDisableRemoteServer bool true" "${SHELL_INFO}"
/usr/libexec/PlistBuddy -c "Add :AI2AppsIconContract string ${ICON_CONTRACT}" "${SHELL_INFO}"
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
/usr/libexec/PlistBuddy -c "Add :AI2AppsIconContract string ${ICON_CONTRACT}" "${HELPER_APP}/Contents/Info.plist"
if [[ ${ALLOW_INSTANCE_DATA_RESET} == 1 ]]; then
  /usr/libexec/PlistBuddy -c "Add :AI2AppsAllowInstanceDataReset bool true" "${HELPER_APP}/Contents/Info.plist"
fi
if [[ ${DEVELOPMENT_BUILD} == 1 ]]; then
  /usr/libexec/PlistBuddy -c "Add :AI2AppsDevelopment bool true" "${HELPER_APP}/Contents/Info.plist"
fi
if [[ -n ${DEVELOPMENT_SOURCE_ROOT} ]]; then
  /usr/libexec/PlistBuddy -c "Add :AI2AppsDevelopmentSourceRoot string ${DEVELOPMENT_SOURCE_ROOT}" "${HELPER_APP}/Contents/Info.plist"
fi

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
