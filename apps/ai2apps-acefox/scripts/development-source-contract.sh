# Sourced by zsh builders before staging or replacing any App.
validate_fixed_development_source() {
  local repo_root=$1 source_root=$2 product_identifier=$3 instance_id=$4
  if [[ ${product_identifier} != com.ai2apps.desktop.dev &&
        ${product_identifier} != com.ai2apps.desktop.appdev &&
        ${instance_id} != dev && ${instance_id} != app-dev ]]; then
    return 0
  fi
  if [[ -z ${source_root} || ${source_root} != /* ||
        ${source_root:A} != ${repo_root:A} ||
        ! -e ${repo_root}/.git ||
        ! -f ${repo_root}/ai2apps/__init__.py ||
        $(git -C "${repo_root}" rev-parse --show-toplevel 2>/dev/null) != ${repo_root:A} ]]; then
    print -u2 "Fixed Dev/App-Dev must load the live builder checkout: ${repo_root}"
    print -u2 "Release snapshots/source-baseline overlays are forbidden; use isolated Test."
    return 64
  fi
}
