#!/usr/bin/env bash
#
# reset-parc.sh — wipe the installed morfSystem state from this machine.
#
# Stops and unregisters every parc service, then removes their binaries (/opt),
# their configurations (/etc) and the locations earlier conventions left behind
# and migrations preserved. Run it before a clean reinstall, to start from
# nothing.
#
# The normal way to uninstall is `morf.py uninstall` (one service or the whole
# parc, with --purge and --backup), which reads each service's own manifest.
# THIS script is the standalone fallback: hard-coded, no dependency on the
# clones or on python, for wiping a machine whose repositories are already gone.
#
# It acts ONLY on the explicit footprint listed below -- read it, it is the
# whole of what this script can touch. It does NOT touch the cloned git
# repositories: delete those by hand if you also want a fresh clone.
#
# Usage:
#   sudo ./scripts/reset-parc.sh              # list what exists, ask, then remove
#   sudo ./scripts/reset-parc.sh --dry-run    # list only, remove nothing
#   sudo ./scripts/reset-parc.sh --yes        # skip the confirmation (a second run)

set -uo pipefail   # NOT -e: an item already absent is not a failure, and one
                   # removal must never stop the rest.

# --- The footprint, spelled out --------------------------------------------
# Explicit rather than discovered, on purpose: a teardown you cannot audit at a
# glance is one you should not run as root. Every path this script may remove is
# on one of these lists and nowhere else.

# systemd units. 'dashboard' is the pre-1.6.1 name of morfdashboard, still
# installed on any machine updated since.
UNITS=(
    morfmonitor morfnotify morfsensor morfanalytics
    morfsync morftemplate morfdashboard
    dashboard
)

# Binaries and (before the /etc move) the configurations kept beside them.
OPT_DIRS=(
    /opt/morfmonitor /opt/morfnotify /opt/morfsensor /opt/morfanalytics
    /opt/morfsync /opt/morftemplate /opt/morfdashboard
)

# Current configurations, plus the shared parc file read by morfMonitor and the
# dashboard. Removing a directory takes its backups (*.bak-*) with it.
ETC_DIRS=(
    /etc/morfmonitor /etc/morfnotify /etc/morfsensor /etc/morfanalytics
    /etc/morfsync /etc/morftemplate /etc/morfdashboard
    /etc/morfsystem
)

# Locations earlier conventions used, preserved by the declared migrations and
# never removed by an install. morfSync alone accounts for all of these.
LEGACY=(
    /usr/local/bin/morfSync      # its binary before the /opt convention
    /etc/homeserverhub           # its very first config home
)

DRY_RUN=0
ASSUME_YES=0
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        --yes|-y)  ASSUME_YES=1 ;;
        *) echo "Unknown option: $arg" >&2; exit 2 ;;
    esac
done

# RESET_ROOT prefixes every path and lets the removal run against a copy of the
# tree instead of the real one -- the only way to exercise a teardown without a
# machine to tear down. Empty in normal use, so the paths above are absolute and
# real. When set, root is not required (nothing system-wide is touched) and
# systemctl is skipped.
RESET_ROOT="${RESET_ROOT:-}"

if [[ -z "$RESET_ROOT" && "${EUID}" -ne 0 ]]; then
    echo "This script must be run with sudo:  sudo $0 $*" >&2
    exit 1
fi

# systemctl is meaningless against a copy: only drive it on the real system.
sc() { [[ -n "$RESET_ROOT" ]] || systemctl "$@"; }

UNIT_DIR="$RESET_ROOT/etc/systemd/system"

# --- Survey: what is actually present --------------------------------------
present_units=()
for u in "${UNITS[@]}"; do
    if [[ -f "$UNIT_DIR/$u.service" ]] || sc list-units --all --type=service \
         --no-legend 2>/dev/null | grep -q "^\s*$u\.service"; then
        present_units+=("$u")
    fi
done

present_paths=()
for p in "${OPT_DIRS[@]}" "${ETC_DIRS[@]}" "${LEGACY[@]}"; do
    [[ -e "$RESET_ROOT$p" ]] && present_paths+=("$RESET_ROOT$p")
done

# Discovery, not action: flag any morf* unit not on the list above, so a service
# added since this script was written is noticed rather than silently spared.
unknown_units=()
while IFS= read -r unit; do
    base="$(basename "$unit" .service)"
    known=0
    for u in "${UNITS[@]}"; do [[ "$u" == "$base" ]] && known=1 && break; done
    [[ "$known" -eq 0 ]] && unknown_units+=("$base")
done < <(ls "$UNIT_DIR"/morf*.service 2>/dev/null)

# --- Report ----------------------------------------------------------------
echo "=== morfSystem teardown ==="
echo

if ((${#present_units[@]} == 0 && ${#present_paths[@]} == 0)); then
    echo "Nothing installed: no parc service, no /opt or /etc footprint."
    [[ ${#unknown_units[@]} -gt 0 ]] && \
        printf 'Note: unrecognised morf* unit still present: %s\n' "${unknown_units[*]}"
    exit 0
fi

if ((${#present_units[@]})); then
    echo "Services to stop and unregister:"
    printf '    %s.service\n' "${present_units[@]}"
    echo
fi
if ((${#present_paths[@]})); then
    echo "Directories and files to remove:"
    printf '    %s\n' "${present_paths[@]}"
    echo
fi
if ((${#unknown_units[@]})); then
    echo "UNRECOGNISED morf* units -- NOT touched, review by hand:"
    printf '    %s.service\n' "${unknown_units[@]}"
    echo
fi

echo "The cloned git repositories are NOT affected."
echo

if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "--dry-run: nothing was removed."
    exit 0
fi

if [[ "$ASSUME_YES" -ne 1 ]]; then
    printf "Type 'yes' to remove everything listed above: "
    read -r reply
    if [[ "$reply" != "yes" ]]; then
        echo "Aborted. Nothing was removed."
        exit 0
    fi
fi

# --- Act -------------------------------------------------------------------
echo
for u in "${present_units[@]}"; do
    echo "[$u] stopping and unregistering"
    sc stop "$u"     2>/dev/null || true
    sc disable "$u"  2>/dev/null || true
    rm -f "$UNIT_DIR/$u.service"
    # Clear the failed state a crash-loop may have left, so a fresh install
    # starts from a clean slate rather than an old error.
    sc reset-failed "$u" 2>/dev/null || true
done
sc daemon-reload 2>/dev/null || true

for p in "${present_paths[@]}"; do
    echo "[rm] $p"
    rm -rf "$p"
done

echo
echo "Done. The machine is back to a clean state."
echo "Re-clone and follow the install guide:  morfTools/docs/GUIDE-DEMARRAGE.md"
