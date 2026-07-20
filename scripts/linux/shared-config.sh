#!/usr/bin/env bash
set -euo pipefail

action="${1:-status}"
shift || true
tool_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
workspace="$(cd "$tool_dir/.." && pwd)"
if [[ "$(basename "$tool_dir")" == *_travail ]]; then
    monitor_dir="$workspace/morfMonitor_travail"
else
    monitor_dir="$workspace/morfMonitor"
fi
source_config="$monitor_dir/config/morfsystem.example.json"
target_dir="/etc/morfsystem"
target_config="$target_dir/morfsystem.json"

usage() {
    cat <<'EOF'
Usage: shared-config.sh <command>

Commands:
  status    Show the editable source and installed configuration paths.
  validate  Validate the editable JSON source.
  edit      Open the editable source with $EDITOR (nano by default), then validate it.
  diff      Compare the editable source with /etc/morfsystem/morfsystem.json.
  install   Validate, back up the installed file, and copy the source to /etc/morfsystem.
  apply     Same as install, then restart morfmonitor and morfdashboard when installed.
EOF
}

require_source() {
    [[ -f "$source_config" ]] ||
        { echo "Source configuration not found: $source_config" >&2; exit 1; }
}

validate() {
    require_source
    command -v python3 >/dev/null 2>&1 ||
        { echo "python3 is required to validate JSON." >&2; exit 1; }
    python3 -m json.tool "$source_config" >/dev/null
    echo "[OK] Valid JSON: $source_config"
}

case "$action" in
    status)
        echo "Editable source: $source_config"
        echo "Installed file:  $target_config"
        [[ -f "$source_config" ]] && echo "[OK] source present" || echo "[WARN] source missing"
        [[ -f "$target_config" ]] && echo "[OK] installed file present" || echo "[WARN] installed file missing"
        ;;
    validate) validate ;;
    edit)
        require_source
        editor="${EDITOR:-nano}"
        read -r -a editor_command <<< "$editor"
        "${editor_command[@]}" "$source_config"
        validate
        echo "Run '$0 install' to deploy the validated file."
        ;;
    diff)
        require_source
        if [[ ! -f "$target_config" ]]; then
            echo "[WARN] Installed file is absent: $target_config"
            exit 1
        fi
        sudo diff -u "$target_config" "$source_config" || test "$?" -eq 1
        ;;
    install|apply)
        validate
        timestamp="$(date +%Y%m%d-%H%M%S)"
        if sudo test -f "$target_config"; then
            backup="$target_config.bak-$timestamp"
            sudo cp -p "$target_config" "$backup"
            echo "Backup created: $backup"
        fi
        sudo install -d -m 0755 "$target_dir"
        sudo install -m 0644 "$source_config" "$target_config"
        echo "Installed: $target_config"
        if [[ "$action" == apply ]]; then
            for service in morfmonitor morfdashboard; do
                if sudo systemctl cat "$service" >/dev/null 2>&1; then
                    sudo systemctl restart "$service"
                    echo "Restarted: $service"
                else
                    echo "[SKIP] Service not installed: $service"
                fi
            done
        fi
        ;;
    help|-h|--help) usage ;;
    *) echo "Unknown command: $action" >&2; usage >&2; exit 2 ;;
esac
