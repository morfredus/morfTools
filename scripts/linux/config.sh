#!/usr/bin/env bash
#
# config.sh — single entry point for configuration deployment across the parc.
#
# Two kinds of configuration exist, and they belong in different places:
#
#   shared   /etc/morfsystem/morfsystem.json — describes WHAT IS SUPERVISED and
#            is read by morfMonitor *and* RaspberryDashboard. No component owns
#            it, so morfTools does.
#
#   deploy   a project's OWN configuration (morfmonitor.json, morfsensor.json…).
#            Each project owns its file, its install directory and its service
#            name. This command therefore DELEGATES to the project's own
#            script rather than knowing any of that — the same way `morf build`
#            delegates to each project's build system instead of learning
#            CMake and PlatformIO.
#
# Consequence worth keeping: a project cloned on its own still deploys its
# configuration without morfTools. Nothing here is a prerequisite.
#
# Usage:
#   ./config.sh shared status|validate|edit|diff|install|apply
#   ./config.sh deploy                 # list the projects that support it
#   ./config.sh deploy morfMonitor     # deploy that project's configuration

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
tool_dir="$(cd "$script_dir/../.." && pwd)"
workspace="$(cd "$tool_dir/.." && pwd)"
manifest="$tool_dir/ecosystem.json"
[[ "$(basename "$tool_dir")" == *_travail ]] && sandbox=true || sandbox=false

usage() {
    cat <<'EOF'
Usage: config.sh <command>

Commands:
  shared <action>     Manage the shared parc configuration
                      (/etc/morfsystem/morfsystem.json), read by morfMonitor
                      and RaspberryDashboard.
                      Actions: status | validate | edit | diff | install | apply

  deploy [project]    Deploy a project's OWN configuration by running its
                      deploy-config script. Without a project name, lists the
                      projects that provide one.
EOF
}

projects() {
    python3 -c 'import json,sys; print("\n".join(json.load(open(sys.argv[1]))["projects"]))' \
        "$manifest" | tr -d '\r'
}

local_project() { $sandbox && printf '%s_travail\n' "$1" || printf '%s\n' "$1"; }

# Renvoie TOUJOURS 0 : sous « set -e », une fonction sortant non nul dans une
# affectation par substitution ($(...)) fait mourir le script sur-le-champ —
# donc avant le message d'erreur cense expliquer ce qui manque. Le code de
# sortie etait juste, et l'utilisateur ne voyait rien.
deploy_script_of() {
    local path="$workspace/$(local_project "$1")/scripts/linux/deploy-config.sh"
    [[ -f "$path" ]] && printf '%s\n' "$path"
    return 0
}

action="${1:-}"
shift || true

case "$action" in

shared)
    exec "$script_dir/shared-config.sh" "$@"
    ;;

deploy)
    target="${1:-}"
    if [[ -z "$target" ]]; then
        echo "Projects providing a configuration deployment script:"
        found=0
        while IFS= read -r project; do
            if [[ -n "$(deploy_script_of "$project")" ]]; then
                printf '    %s\n' "$project"
                found=1
            fi
        done < <(projects)
        (( found )) || echo "    (none — clone a project first)"
        echo
        # A project name is required rather than defaulting to "all": this
        # overwrites deployed configurations, and doing that to every project
        # because an argument was forgotten is not a reasonable default.
        echo "Name one:  ./config.sh deploy <project>"
        exit 0
    fi

    script="$(deploy_script_of "$target")"
    [[ -n "$script" ]] || {
        echo "No deployment script for '$target'." >&2
        echo "Expected: $(local_project "$target")/scripts/linux/deploy-config.sh" >&2
        echo "Run './config.sh deploy' to list the projects that provide one." >&2
        exit 1
    }
    shift || true
    echo "[$target] $script"
    exec bash "$script" "$@"
    ;;

help|-h|--help|"") usage ;;
*) echo "Unknown command: $action" >&2; usage >&2; exit 2 ;;
esac
