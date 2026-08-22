#!/bin/zsh

set -euo pipefail

APP=${APP:-}
SIGN_IDENTITY=${SIGN_IDENTITY:--}
ENTITLEMENTS_DIR=${ENTITLEMENTS_DIR:-${0:A:h}/../entitlements}
MODE=${MODE:-full}
SANDBOX_MODE=${SANDBOX_MODE:-0}
APPLICATION_GROUP_IDENTIFIER=${APPLICATION_GROUP_IDENTIFIER:-}

fail() {
  print -u2 "sign-release-app: $*"
  exit 64
}

[[ -n ${APP} && -d ${APP} && ${APP:t} == *.app ]] || fail "set APP to an App bundle"
[[ ${MODE} == full || ${MODE} == seal ]] || fail "MODE must be full or seal"
BUNDLE_IDENTIFIER=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "${APP}/Contents/Info.plist")
[[ -n ${BUNDLE_IDENTIFIER} ]] || fail "main App is missing CFBundleIdentifier"

for entitlement in launcher browser helper runtime-inherit plugin-container media-plugin-helper; do
  [[ -f ${ENTITLEMENTS_DIR}/${entitlement}.plist ]] || \
    fail "missing ${ENTITLEMENTS_DIR}/${entitlement}.plist"
done

[[ ${SANDBOX_MODE} == 0 || ${SANDBOX_MODE} == 1 ]] || fail "SANDBOX_MODE must be 0 or 1"
GENERATED_ENTITLEMENTS=""
if [[ ${SANDBOX_MODE} == 1 ]]; then
  [[ -n ${APPLICATION_GROUP_IDENTIFIER} ]] || fail "APPLICATION_GROUP_IDENTIFIER is required"
  GENERATED_ENTITLEMENTS=$(mktemp -d "${TMPDIR:-/tmp}/ai2apps-entitlements.XXXXXX")
  cleanup_entitlements() {
    rm -rf "${GENERATED_ENTITLEMENTS}"
  }
  trap cleanup_entitlements EXIT
  for entitlement in launcher browser helper; do
    cp "${ENTITLEMENTS_DIR}/${entitlement}.plist" "${GENERATED_ENTITLEMENTS}/${entitlement}.plist"
    /usr/libexec/PlistBuddy -c "Add :com.apple.security.app-sandbox bool true" "${GENERATED_ENTITLEMENTS}/${entitlement}.plist"
    /usr/libexec/PlistBuddy -c "Add :com.apple.security.network.client bool true" "${GENERATED_ENTITLEMENTS}/${entitlement}.plist"
    /usr/libexec/PlistBuddy -c "Add :com.apple.security.network.server bool true" "${GENERATED_ENTITLEMENTS}/${entitlement}.plist"
    /usr/libexec/PlistBuddy -c "Add :com.apple.security.application-groups array" "${GENERATED_ENTITLEMENTS}/${entitlement}.plist"
    /usr/libexec/PlistBuddy -c "Add :com.apple.security.application-groups:0 string ${APPLICATION_GROUP_IDENTIFIER}" "${GENERATED_ENTITLEMENTS}/${entitlement}.plist"
  done
  for entitlement in runtime-inherit plugin-container media-plugin-helper; do
    cp "${ENTITLEMENTS_DIR}/${entitlement}.plist" "${GENERATED_ENTITLEMENTS}/${entitlement}.plist"
    /usr/libexec/PlistBuddy -c "Add :com.apple.security.app-sandbox bool true" "${GENERATED_ENTITLEMENTS}/${entitlement}.plist"
    /usr/libexec/PlistBuddy -c "Add :com.apple.security.inherit bool true" "${GENERATED_ENTITLEMENTS}/${entitlement}.plist"
  done
  ACTIVE_ENTITLEMENTS_DIR=${GENERATED_ENTITLEMENTS}
else
  ACTIVE_ENTITLEMENTS_DIR=${ENTITLEMENTS_DIR}
fi

if [[ ${SIGN_IDENTITY} == - ]]; then
  SIGN_FLAGS=(--force --sign -)
else
  SIGN_FLAGS=(--force --timestamp --options runtime --sign "${SIGN_IDENTITY}")
fi

# Apple's trusted timestamp service can occasionally fail one otherwise valid
# nested signing operation. Retry only the exact codesign invocation; never
# weaken Developer ID flags or continue with an untimestamped signature.
sign_code() {
  local attempt
  for attempt in 1 2 3; do
    if codesign "$@"; then
      return 0
    fi
    [[ ${SIGN_IDENTITY} != - && ${attempt} -lt 3 ]] || return 1
    sleep ${attempt}
  done
  return 1
}

if [[ ${MODE} == full ]]; then
  while IFS= read -r -d '' candidate; do
    if [[ ${candidate} == */Contents/Resources/AI2AppsLocal/* &&
          $(file -b "${candidate}") == *'Mach-O'* ]]; then
      if [[ ${SANDBOX_MODE} == 1 &&
            ${candidate} == */Contents/Resources/AI2AppsLocal/Python/cpython-3.11/bin/python3.11 ]]; then
        sign_code "${SIGN_FLAGS[@]}" \
          --entitlements "${ACTIVE_ENTITLEMENTS_DIR}/runtime-inherit.plist" \
          "${candidate}"
      else
        sign_code "${SIGN_FLAGS[@]}" "${candidate}"
      fi
      continue
    fi
    if [[ ${candidate} == "${APP}/Contents/MacOS/AI2Apps" ||
          ${candidate} == "${APP}/Contents/MacOS/"*.app/* ||
          ${candidate} == "${APP}/Contents/Library/LoginItems/AI2AppsHelper.app/Contents/MacOS/AI2AppsHelper" ||
          ${candidate} == "${APP}/Contents/Frameworks/"*.framework/* ]]; then
      continue
    fi
    if [[ $(file -b "${candidate}") == *'Mach-O'* ]]; then
      if [[ ${candidate} == */Contents/MacOS/acefox-bin ]]; then
        # Firefox's JIT entitlement belongs to the browser process executable,
        # including when a signed bundle launcher execs the Gecko engine.
        BROWSER_BUNDLE=${candidate:h:h:h}
        BROWSER_IDENTIFIER=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' \
          "${BROWSER_BUNDLE}/Contents/Info.plist")
        sign_code "${SIGN_FLAGS[@]}" \
          --identifier "${BROWSER_IDENTIFIER}.engine" \
          --entitlements "${ACTIVE_ENTITLEMENTS_DIR}/browser.plist" \
          "${candidate}"
      else
        sign_code "${SIGN_FLAGS[@]}" "${candidate}"
      fi
    fi
  done < <(find "${APP}/Contents" -type f -print0)

  while IFS= read -r -d '' nested_app; do
    case ${nested_app:t} in
      plugin-container.app)
        sign_code "${SIGN_FLAGS[@]}" \
          --entitlements "${ACTIVE_ENTITLEMENTS_DIR}/plugin-container.plist" \
          "${nested_app}"
        ;;
      media-plugin-helper.app)
        sign_code "${SIGN_FLAGS[@]}" \
          --entitlements "${ACTIVE_ENTITLEMENTS_DIR}/media-plugin-helper.plist" \
          "${nested_app}"
        ;;
      *)
        sign_code "${SIGN_FLAGS[@]}" "${nested_app}"
        ;;
    esac
  done < <(find "${APP}" -type d \( -name plugin-container.app -o -name media-plugin-helper.app -o -name gpu-helper.app \) -print0)

  while IFS= read -r -d '' framework; do
    sign_code "${SIGN_FLAGS[@]}" "${framework}"
  done < <(find "${APP}" -type d -name '*.framework' -print0)
  for browser_app in \
    "${APP}/Contents/Applications/AI2AppsShell.app"; do
    sign_code "${SIGN_FLAGS[@]}" \
      --entitlements "${ACTIVE_ENTITLEMENTS_DIR}/browser.plist" \
      "${browser_app}"
  done
fi

# The Runtime manifest is refreshed after the full signing pass and lives
# inside the Helper bundle. Re-seal the Helper in both modes before sealing
# the containing App.
for login_item in "${APP}/Contents/Library/LoginItems"/*.app(N); do
  if [[ ${SANDBOX_MODE} == 1 ]]; then
    sign_code "${SIGN_FLAGS[@]}" \
      --entitlements "${ACTIVE_ENTITLEMENTS_DIR}/helper.plist" \
      "${login_item}"
  else
    sign_code "${SIGN_FLAGS[@]}" "${login_item}"
  fi
done

sign_code "${SIGN_FLAGS[@]}" \
  --entitlements "${ACTIVE_ENTITLEMENTS_DIR}/launcher.plist" \
  "${APP}"
