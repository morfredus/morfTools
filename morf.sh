#!/usr/bin/env bash
set -euo pipefail

command_name="${1:?Usage: morf.sh <command> [message]}"
message="${2:-}"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tool_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
manifest="$tool_dir/ecosystem.json"
[[ "$(basename "$tool_dir")" == *_travail ]] && sandbox=true || sandbox=false

projects() { python3 -c 'import json,sys; print("\n".join(json.load(open(sys.argv[1]))["projects"]))' "$manifest"; }
branch() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["branch"])' "$manifest"; }
clone_url() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["cloneUrlTemplate"].replace("{name}",sys.argv[2]))' "$manifest" "$1"; }
local_project() { $sandbox && printf '%s_travail\n' "$1" || printf '%s\n' "$1"; }

while IFS= read -r project; do
  local_name="$(local_project "$project")"
  path="$root/$local_name"
  if [[ "$command_name" == clone ]]; then
    [[ -e "$path" ]] && { echo "[SKIP] $local_name (already present)"; continue; }
    git clone --branch "$(branch)" "$(clone_url "$local_name")" "$path"
    continue
  fi
  [[ -d "$path" ]] || { echo "[SKIP] $local_name (not cloned)"; continue; }
  echo "[$local_name]"
  (
    cd "$path"
    case "$command_name" in
      fetch) git fetch --prune ;;
      pull|update) git pull --ff-only origin "$(branch)" ;;
      status) git status --short --branch ;;
      push) git push origin "$(branch)" ;;
      commit) [[ -n "$message" ]] || { echo 'A commit message is required.' >&2; exit 2; }; git add -A; [[ -z "$(git status --porcelain)" ]] || git commit -m "$message" ;;
      build) if [[ -f platformio.ini ]]; then pio run; elif [[ -f CMakeLists.txt ]]; then cmake -S . -B build && cmake --build build; else echo '[SKIP] no known build definition'; fi ;;
      install) if [[ -f requirements.txt ]]; then python3 -m pip install -r requirements.txt; else echo '[SKIP] no generic install definition'; fi ;;
      upgrade) git pull --ff-only origin "$(branch)"; [[ ! -f CMakeLists.txt ]] || { cmake -S . -B build && cmake --build build; } ;;
      clean) [[ ! -d build ]] || rm -rf build ;;
      doctor)
        git rev-parse --is-inside-work-tree >/dev/null
        remote="$(git remote get-url origin)"
        [[ "$remote" == *"$local_name"* ]] && echo '[OK] remote name matches' || echo "[WARN] unexpected origin: $remote"
        ;;
      *) echo "Unknown command: $command_name" >&2; exit 2 ;;
    esac
  )
done < <(projects)
