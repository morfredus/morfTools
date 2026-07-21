#!/usr/bin/env bash
set -euo pipefail

command_name="${1:?Usage: morf.sh <command> [message] [--preset <name>]}"
shift
message=""
preset=""
while (($#)); do
  case "$1" in
    --preset|-p|--profile)
      (($# >= 2)) || { echo "Missing value for $1." >&2; exit 2; }
      preset="$2"
      shift 2
      ;;
    --) shift; message="$*"; break ;;
    *) [[ -z "$message" ]] || { echo "Unexpected argument: $1" >&2; exit 2; }; message="$1"; shift ;;
  esac
done
[[ -z "$preset" || "$command_name" == build || "$command_name" == upgrade ]] ||
  { echo "--preset is only supported by build and upgrade." >&2; exit 2; }
if [[ -z "$preset" && -n "$message" && ( "$command_name" == build || "$command_name" == upgrade ) ]]; then
  preset="$message"
  message=""
fi
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tool_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
manifest="$tool_dir/ecosystem.json"
[[ "$(basename "$tool_dir")" == *_travail ]] && sandbox=true || sandbox=false

# python3 on Windows (Git Bash) turns \n into \r\n on stdout: without tr -d '\r'
# project names become "ComponentHub\r_travail" and every project is skipped.
projects() { python3 -c 'import json,sys; print("\n".join(json.load(open(sys.argv[1]))["projects"]))' "$manifest" | tr -d '\r'; }
branch() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["branch"])' "$manifest" | tr -d '\r'; }
clone_url() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["cloneUrlTemplate"].replace("{name}",sys.argv[2]))' "$manifest" "$1" | tr -d '\r'; }
local_project() { $sandbox && printf '%s_travail\n' "$1" || printf '%s\n' "$1"; }

# Configure presets declared by a project (empty when it has none).
project_presets() {
  python3 -c '
import json, os, sys
path = os.path.join(sys.argv[1], "CMakePresets.json")
try:
    data = json.load(open(path))
except (OSError, ValueError):
    sys.exit(0)
for entry in data.get("configurePresets", []):
    if not entry.get("hidden") and entry.get("name"):
        print(entry["name"])
' "$1" | tr -d '\r'
}

has_preset() { project_presets "$1" | grep -qx -- "$2"; }

# stdin is consumed by the main loop: answers are read from /dev/tty
# through fd 3. When it cannot be opened (cron, CI, pipe), refuse to guess.
open_tty() { { exec 3</dev/tty; } 2>/dev/null; }

# A required option is never guessed: offer the alternatives instead.
choose_preset() {
  local names=() counts=() total=0 name path idx reply
  while IFS= read -r project; do
    path="$root/$(local_project "$project")"
    [[ -f "$path/CMakePresets.json" ]] || continue
    total=$((total + 1))
    while IFS= read -r name; do
      for idx in "${!names[@]}"; do
        [[ "${names[idx]}" == "$name" ]] && { counts[idx]=$((counts[idx] + 1)); continue 2; }
      done
      names+=("$name")
      counts+=(1)
    done < <(project_presets "$path")
  done < <(projects)

  ((${#names[@]})) || return 0   # no CMake project cloned: nothing to ask

  echo "No preset given for '$command_name'. Available presets:" >&2
  for idx in "${!names[@]}"; do
    printf '  %d) %-20s (%d/%d projects)\n' "$((idx + 1))" "${names[idx]}" "${counts[idx]}" "$total" >&2
  done

  if ! open_tty; then
    echo "Not a terminal: rerun with --preset <name>." >&2
    exit 2
  fi

  while true; do
    printf 'Choice [1-%d]: ' "${#names[@]}" >&2
    read -r reply <&3 || { echo >&2; exit 2; }
    if [[ "$reply" =~ ^[0-9]+$ ]] && ((reply >= 1 && reply <= ${#names[@]})); then
      preset="${names[reply - 1]}"
      echo "[INFO] selected preset: $preset" >&2
      return 0
    fi
    echo "Invalid answer." >&2
  done
}

ask_message() {
  local reply
  if ! open_tty; then
    echo "A commit message is required (not a terminal: use -- <message>)." >&2
    exit 2
  fi
  while [[ -z "$message" ]]; do
    printf 'Commit message: ' >&2
    read -r reply <&3 || { echo >&2; exit 2; }
    message="$reply"
  done
}

# A preset missing from THIS project (e.g. linux-arm64-cross, declared by 3
# repositories only) is a normal absence, not a build failure.
cmake_build() {
  if [[ -z "$preset" ]]; then
    cmake -S . -B build && cmake --build build
  elif has_preset . "$preset"; then
    cmake --preset "$preset" && cmake --build --preset "$preset"
  else
    echo "[SKIP] preset '$preset' not defined in this project"
  fi
}

case "$command_name" in
  build|upgrade) [[ -n "$preset" ]] || choose_preset ;;
  commit) [[ -n "$message" ]] || ask_message ;;
esac

failed=()

# The addressing plan and the conformance of vendored copies describe a SHARED
# resource: a port collision or a drifting copy is invisible from inside any
# single project, where each one stays individually valid. They are therefore
# checked once, before the project-by-project loop.
if [[ "$command_name" == doctor ]]; then
  echo "[ecosystem]"
  python3 "$tool_dir/scripts/ecosystem-check.py" "$root" "$manifest" || failed+=("ecosystem")
  echo
  # Same reasoning, one platform further: a script recorded as non-executable
  # runs perfectly on the machine that wrote it and answers "Permission denied"
  # once cloned on the Pi. Windows has no executable permission, so the defect
  # is created silently and cannot be observed from the machine that creates it.
  python3 "$tool_dir/scripts/exec-bits.py" "$root" --check || failed+=("exec-bits")
  echo
fi

while IFS= read -r project; do
  local_name="$(local_project "$project")"
  path="$root/$local_name"
  if [[ "$command_name" == clone ]]; then
    [[ -e "$path" ]] && { echo "[SKIP] $local_name (already present)"; continue; }
    git clone --branch "$(branch)" "$(clone_url "$local_name")" "$path" || failed+=("$local_name")
    continue
  fi
  [[ -d "$path" ]] || { echo "[SKIP] $local_name (not cloned)"; continue; }
  echo "[$local_name]"
  # The 'if' defeats set -e: a failing project must not silently stop
  # the remaining projects (their build-<preset> would stay stale).
  if ! (
    cd "$path"
    case "$command_name" in
      fetch) git fetch --prune ;;
      pull|update) git pull --ff-only origin "$(branch)" ;;
      status) git status --short --branch ;;
      push) git push origin "$(branch)" ;;
      commit) [[ -n "$message" ]] || { echo 'A commit message is required.' >&2; exit 2; }; git add -A; [[ -z "$(git status --porcelain)" ]] || git commit -m "$message" ;;
      build) if [[ -f platformio.ini ]]; then [[ -z "$preset" ]] || echo "[INFO] preset ignored for PlatformIO: $preset"; pio run; elif [[ -f CMakeLists.txt ]]; then cmake_build; else echo '[SKIP] no known build definition'; fi ;;
      install) if [[ -f requirements.txt ]]; then python3 -m pip install -r requirements.txt; else echo '[SKIP] no generic install definition'; fi ;;
      upgrade) git pull --ff-only origin "$(branch)"; [[ ! -f CMakeLists.txt ]] || cmake_build ;;
      clean) for dir in build build-*; do [[ ! -d "$dir" ]] || { echo "[RM] $dir"; rm -rf "$dir"; }; done ;;
      doctor)
        git rev-parse --is-inside-work-tree >/dev/null
        remote="$(git remote get-url origin)"
        # GitHub resolves repository names case-insensitively, so a spelling
        # difference alone (GatewayLab vs GateWayLab) is not a wrong origin.
        [[ "${remote,,}" == *"${local_name,,}"* ]] && echo '[OK] remote name matches' || echo "[WARN] unexpected origin: $remote"
        ;;
      *) echo "Unknown command: $command_name" >&2; exit 2 ;;
    esac
  ); then
    echo "[FAIL] $local_name" >&2
    failed+=("$local_name")
  fi
done < <(projects)

if ((${#failed[@]})); then
  echo >&2
  echo "[FAILED] $command_name failed on: ${failed[*]}" >&2
  exit 1
fi
