#!/bin/zsh

set -euo pipefail

APP=${APP:-}

fail() {
  print -u2 "verify-release-app: $*"
  exit 65
}

[[ -n ${APP} && -d ${APP} && ${APP:t} == *.app ]] || fail "set APP to a release .app bundle"
[[ -x ${APP}/Contents/MacOS/AI2Apps ]] || fail "missing launcher"
UPDATER_PROTOCOL=$(/usr/libexec/PlistBuddy -c 'Print :AI2AppsUpdaterProtocol' "${APP}/Contents/Info.plist" 2>/dev/null || true)
if [[ -n ${UPDATER_PROTOCOL} ]]; then
  [[ ${UPDATER_PROTOCOL} == 1 ]] || fail "unsupported updater protocol"
  [[ -x ${APP}/Contents/Helpers/AI2AppsUpdater ]] || fail "missing declared updater"
fi
STAGING_PROTOCOL=$(/usr/libexec/PlistBuddy -c 'Print :AI2AppsUpdateStagingProtocol' "${APP}/Contents/Info.plist" 2>/dev/null || true)
if [[ -n ${STAGING_PROTOCOL} ]]; then
  [[ ${STAGING_PROTOCOL} == 1 ]] || fail "unsupported update staging protocol"
  [[ ${UPDATER_PROTOCOL} == 1 ]] || fail "update staging requires updater protocol 1"
  for update_script in \
    stage-update-candidate.py \
    verify-update-candidate.py \
    verify-release-metadata.py \
    generate-release-metadata.py \
    verify-dmg-contents.sh; do
    [[ -x ${APP}/Contents/Resources/Update/${update_script} ]] || \
      fail "missing declared update resource ${update_script}"
  done
fi
[[ -x ${APP}/Contents/Library/LoginItems/AI2AppsHelper.app/Contents/MacOS/AI2AppsHelper ]] || fail "missing Helper"
HELPER_APP=${APP}/Contents/Library/LoginItems/AI2AppsHelper.app
[[ -s ${HELPER_APP}/Contents/Resources/menubar-logo.svg ]] || fail "Helper is missing its menu bar SVG logo"
[[ -s ${HELPER_APP}/Contents/Resources/menubar-logo-update.svg ]] || \
  fail "Helper is missing its update-download menu bar SVG logo"
[[ -s ${HELPER_APP}/Contents/Resources/menubar-logo-work.svg ]] || \
  fail "Helper is missing its update-busy menu bar SVG logo"
[[ -s ${HELPER_APP}/Contents/Resources/menubar-logo-ready.svg ]] || \
  fail "Helper is missing its update-ready menu bar SVG logo"
RUNTIME_ROOT=${HELPER_APP}/Contents/Resources/AI2AppsLocal
SHELL_APP=${APP}/Contents/Applications/AI2AppsShell.app
[[ -x ${RUNTIME_ROOT}/bin/omlx ]] || fail "missing Helper-owned Local entrypoint"
[[ -x ${RUNTIME_ROOT}/Python/cpython-3.11/bin/python3.11 ]] || \
  fail "missing Helper-owned update staging Python"
[[ -f ${RUNTIME_ROOT}/runtime-manifest.json ]] || fail "missing Runtime manifest"
RUNTIME_PROFILE=$(/usr/libexec/PlistBuddy -c 'Print :AI2AppsRuntimeProfile' "${APP}/Contents/Info.plist" 2>/dev/null || print full)
MANIFEST_RUNTIME_PROFILE=$(plutil -extract runtime_profile raw "${RUNTIME_ROOT}/runtime-manifest.json" 2>/dev/null || print full)
[[ ${RUNTIME_PROFILE} == full || ${RUNTIME_PROFILE} == cloud ]] || fail "unsupported Runtime profile"
[[ ${MANIFEST_RUNTIME_PROFILE} == ${RUNTIME_PROFILE} ]] || fail "Runtime profile does not match manifest"
if [[ ${RUNTIME_PROFILE} == cloud ]]; then
  [[ -d ${RUNTIME_ROOT}/Python/framework-control-plane ]] || fail "cloud Runtime is missing control-plane layer"
  [[ ! -e ${RUNTIME_ROOT}/Python/framework-mlx-base ]] || fail "cloud Runtime contains MLX framework layer"
  CLOUD_SITE=${RUNTIME_ROOT}/Python/framework-control-plane/lib/python3.11/site-packages
  [[ -n $(find "${CLOUD_SITE}" -maxdepth 1 -type d -name 'huggingface_hub-*.dist-info' -print -quit) ]] || \
    fail "cloud Runtime is missing the Host checkpoint downloader dependency"
  [[ -z $(find "${CLOUD_SITE}" -maxdepth 1 \( -name mlx -o -name 'mlx_*' -o -name 'mlx-*' \) -print -quit) ]] || \
    fail "cloud Runtime contains an MLX Python package"
else
  [[ -d ${RUNTIME_ROOT}/Python/framework-mlx-base ]] || fail "full Runtime is missing MLX framework layer"
fi
[[ -f ${SHELL_APP}/Contents/Resources/omni.ja ]] || fail "missing Shell Gecko omni.ja"
[[ -f ${SHELL_APP}/Contents/Resources/browser/omni.ja ]] || fail "missing Shell browser omni.ja"
[[ ! -e ${HELPER_APP}/Contents/Resources/AceFoxAgent.app ]] || \
  fail "duplicated Agent Gecko bundle is still packaged"
[[ ! -e ${APP}/Contents/Library/Helpers/AI2AppsModelCacheBroker.app ]] || \
  fail "retired Model Cache Broker is still packaged"
[[ ! -e ${APP}/Contents/Library/LaunchAgents ]] || \
  fail "App must not package a cross-instance model-cache LaunchAgent"
[[ $(/usr/libexec/PlistBuddy -c 'Print :CFBundleExecutable' "${SHELL_APP}/Contents/Info.plist") == acefox-bin ]] || \
  fail "Shell must start the native AceFox executable directly"
[[ $(/usr/libexec/PlistBuddy -c 'Print :AI2AppsBrowserRole' "${SHELL_APP}/Contents/Info.plist" 2>/dev/null || true) == shell ]] || \
  fail "Shell is missing its signed browser role"
[[ $(/usr/libexec/PlistBuddy -c 'Print :AI2AppsSharedBrowserBundle' "${SHELL_APP}/Contents/Info.plist" 2>/dev/null || true) == true ]] || \
  fail "Shell is missing its shared browser bundle contract"
strings "${SHELL_APP}/Contents/MacOS/acefox-bin" | grep -Fqx 'AI2APPS_BROWSER_ROLE' || \
  fail "AceFox binary does not support shared Agent roles"
[[ $(/usr/libexec/PlistBuddy -c 'Print :AI2AppsDisableRemoteServer' "${SHELL_APP}/Contents/Info.plist" 2>/dev/null || true) == true ]] || \
  fail "Shell must disable the legacy Gecko remote server"
SHELL_STORAGE_MODE=$(/usr/libexec/PlistBuddy -c 'Print :AI2AppsStorageMode' "${SHELL_APP}/Contents/Info.plist" 2>/dev/null || true)
[[ ${SHELL_STORAGE_MODE} == app-group || ${SHELL_STORAGE_MODE} == user-library ]] || \
  fail "Shell has an unsupported signed storage mode"
[[ ! -e ${SHELL_APP}/Contents/MacOS/AI2AppsBrowserLauncher ]] || \
  fail "Shell contains the retired browser-launcher wrapper"
[[ $(/usr/libexec/PlistBuddy -c 'Print :LSMinimumSystemVersion' "${APP}/Contents/Info.plist") == 13.0 ]] || \
  fail "main App minimum system version must be 13.0"
[[ $(/usr/libexec/PlistBuddy -c 'Print :LSMinimumSystemVersion' "${APP}/Contents/Library/LoginItems/AI2AppsHelper.app/Contents/Info.plist") == 13.0 ]] || \
  fail "Helper minimum system version must be 13.0"
BUNDLE_ID=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "${APP}/Contents/Info.plist")
INSTANCE_ID=$(/usr/libexec/PlistBuddy -c 'Print :AI2AppsInstanceID' "${APP}/Contents/Info.plist")
HELPER_ID=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "${APP}/Contents/Library/LoginItems/AI2AppsHelper.app/Contents/Info.plist")
[[ ${HELPER_ID} == ${BUNDLE_ID}.helper ]] || fail "Login Item identity does not match the main App"
for component_info in \
  "${SHELL_APP}/Contents/Info.plist" \
  "${HELPER_APP}/Contents/Info.plist"; do
  [[ $(/usr/libexec/PlistBuddy -c 'Print :AI2AppsInstanceID' "${component_info}" 2>/dev/null || true) == ${INSTANCE_ID} ]] || \
    fail "embedded component instance identity does not match the main App"
done
codesign --verify --deep --strict "${APP}" || fail "signature verification failed"
[[ -z $(find -L "${APP}" -type l -print -quit) ]] || fail "bundle contains broken symlinks"
[[ -z $(find "${APP}" -name .purgecaches -type f -print -quit) ]] || fail "bundle contains a mutable Gecko purge marker"
[[ ! -e ${APP}/Contents/moz.build ]] || fail "bundle contains objdir source metadata"
[[ -z $(find "${RUNTIME_ROOT}" -type f \( -name '*.pyc' -o -name '*.pyo' \) -print -quit) ]] || fail "Runtime contains Python bytecode"
[[ -z $(find "${RUNTIME_ROOT}" -type f -name '*.cpython-*.so' ! -name '*.cpython-311-*.so' -print -quit) ]] || fail "Runtime contains an extension for the wrong CPython ABI"

SANDBOX_APP=0
SIGNING_DETAILS=$(codesign -dv --verbose=4 "${APP}" 2>&1)
BROWSER_ENTITLEMENTS=$(codesign -d --entitlements :- "${SHELL_APP}" 2>&1)
if [[ ${SIGNING_DETAILS} == *'Authority=Developer ID Application'* ]]; then
  APP_TEAM=$(print -r -- "${SIGNING_DETAILS}" | sed -n 's/^TeamIdentifier=//p')
  [[ -n ${APP_TEAM} ]] || fail "Developer ID App is missing TeamIdentifier"
  [[ ${BROWSER_ENTITLEMENTS} == *'<key>com.apple.security.cs.allow-jit</key><true/>'* ]] || \
    fail "Developer ID browser process is missing allow-jit"
  [[ ${BROWSER_ENTITLEMENTS} == *'<key>com.apple.security.cs.disable-library-validation</key><true/>'* ]] || \
    fail "Developer ID browser process is missing disable-library-validation"
  while IFS= read -r -d '' runtime_file; do
    [[ $(file -b "${runtime_file}") == *'Mach-O'* ]] || continue
    RUNTIME_SIGNING_DETAILS=$(codesign -dv --verbose=4 "${runtime_file}" 2>&1) || \
      fail "Runtime Mach-O is not signed: ${runtime_file:t}"
    [[ ${RUNTIME_SIGNING_DETAILS} == *"TeamIdentifier=${APP_TEAM}"* ]] || \
      fail "Runtime Mach-O TeamIdentifier does not match the App: ${runtime_file:t}"
  done < <(find "${RUNTIME_ROOT}" -type f -print0)
  for browser_root in "${SHELL_APP}"; do
    while IFS= read -r -d '' browser_file; do
      [[ $(file -b "${browser_file}") == *'Mach-O'* ]] || continue
      BROWSER_FILE_SIGNING_DETAILS=$(codesign -dv --verbose=4 "${browser_file}" 2>&1) || \
        fail "Browser Mach-O is not signed: ${browser_file:t}"
      [[ ${BROWSER_FILE_SIGNING_DETAILS} == *"TeamIdentifier=${APP_TEAM}"* ]] || \
        fail "Browser Mach-O TeamIdentifier does not match the App: ${browser_file}"
    done < <(find "${browser_root}" -type f -print0)
  done
fi
APP_GROUP=$(/usr/libexec/PlistBuddy -c 'Print :AI2AppsApplicationGroupIdentifier' "${APP}/Contents/Info.plist" 2>/dev/null || true)
if [[ -n ${APP_GROUP} ]]; then
  SANDBOX_APP=1
  [[ ${SHELL_STORAGE_MODE} == app-group ]] || fail "Sandbox Shell must use App Group storage"
  HELPER_GROUP=$(/usr/libexec/PlistBuddy -c 'Print :AI2AppsApplicationGroupIdentifier' "${HELPER_APP}/Contents/Info.plist" 2>/dev/null || true)
  [[ ${HELPER_GROUP} == ${APP_GROUP} ]] || fail "Helper App Group does not match the main App"
  SHELL_GROUP=$(/usr/libexec/PlistBuddy -c 'Print :AI2AppsApplicationGroupIdentifier' "${SHELL_APP}/Contents/Info.plist" 2>/dev/null || true)
  [[ ${SHELL_GROUP} == ${APP_GROUP} ]] || fail "Shell App Group does not match the main App"
  for executable in \
    "${APP}" \
    "${SHELL_APP}" \
    "${HELPER_APP}"; do
    ENTITLEMENTS=$(codesign -d --entitlements :- "${executable}" 2>&1)
    [[ ${ENTITLEMENTS} == *'<key>com.apple.security.app-sandbox</key><true/>'* ]] || \
      fail "Sandbox executable is missing App Sandbox: ${executable:t}"
    [[ ${ENTITLEMENTS} == *"<string>${APP_GROUP}</string>"* ]] || \
      fail "Sandbox executable is missing its instance App Group: ${executable:t}"
  done
  HELPER_ENTITLEMENTS=$(codesign -d --entitlements :- "${HELPER_APP}" 2>&1)
  [[ ${HELPER_ENTITLEMENTS} != *'com.ai2apps.model-cache-broker'* ]] || \
    fail "Helper retains the retired model-cache Mach exception"
  RUNTIME_ENTITLEMENTS=$(codesign -d --entitlements :- "${RUNTIME_ROOT}/Python/cpython-3.11/bin/python3.11" 2>&1)
  [[ ${RUNTIME_ENTITLEMENTS} == *'<key>com.apple.security.app-sandbox</key><true/>'* &&
     ${RUNTIME_ENTITLEMENTS} == *'<key>com.apple.security.inherit</key><true/>'* ]] || \
    fail "embedded Python is missing Sandbox inheritance"
  [[ $(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "${SHELL_APP}/Contents/Info.plist") == ${BUNDLE_ID}.shell ]] || \
    fail "Shell App identity does not match the main App"
else
  [[ ${SHELL_STORAGE_MODE} == user-library ]] || fail "Non-Sandbox Shell must use the user Library"
fi

if [[ ${SANDBOX_APP} == 1 ]]; then
  # An executable signed with com.apple.security.inherit must be launched by a
  # sandboxed parent.  Running the embedded Python through this verifier's
  # ordinary shell is therefore invalid; exercise the same health path through
  # the sandboxed Launcher that production uses.
  "${APP}/Contents/MacOS/AI2Apps" --post-update-health-only
else
  PYTHON_ROOT=${RUNTIME_ROOT}/Python
  CPYTHON=${PYTHON_ROOT}/cpython-3.11
  if [[ ${RUNTIME_PROFILE} == cloud ]]; then
    FRAMEWORK_SITE=${PYTHON_ROOT}/framework-control-plane/lib/python3.11/site-packages
  else
    FRAMEWORK_SITE=${PYTHON_ROOT}/framework-mlx-base/lib/python3.11/site-packages
  fi
  env \
    AI2APPS_RUNTIME_PROFILE="${RUNTIME_PROFILE}" \
    PYTHONHOME="${CPYTHON}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONNOUSERSITE=1 \
    PYTHONPATH="${RUNTIME_ROOT}/app:${FRAMEWORK_SITE}" \
    PATH="${CPYTHON}/bin:/usr/bin:/bin:/usr/sbin:/sbin" \
    "${CPYTHON}/bin/python3" -c \
      'from importlib.metadata import version; from packaging.version import Version; import av, huggingface_hub, omlx.server, rfc8785; assert Version(version("huggingface-hub")) >= Version("1.19.0"); assert Version(version("rfc8785")) >= Version("0.1.4")' || \
    fail "embedded Host dependencies are unavailable or too old"
  "${RUNTIME_ROOT}/bin/omlx" info >/dev/null
fi
codesign --verify --deep --strict "${APP}" || fail "Runtime probe modified the signed bundle"
print "Verified release App ${APP}"
