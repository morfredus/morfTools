#!/usr/bin/env bash
# morfNetInstall.sh
# Installe le watchdog reseau morfNet (script + config admin + units systemd) et
# l'active. Idempotent : relancable sans casse. Par defaut la config /etc n'est
# ecrite que si absente, pour ne pas ecraser les reglages propres a l'hote
# (doctrine FS morfSystem) ; `--reset-config` force la reecriture avec la config
# par defaut du depot.
#
# Convention : le service systemd est en minuscules (morfnetwatchdog), le script
# installe garde son nom morfNet* (morfNetWatchdog.sh).
#
# Usage :
#   sudo ./morfNetInstall.sh                  # installe/met a jour, config preservee
#   sudo ./morfNetInstall.sh --reset-config   # idem mais ecrase la config /etc
#   sudo ./morfNetInstall.sh --uninstall      # retire script + units (config conservee)

set -euo pipefail

SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
SBIN="/usr/local/sbin/morfNetWatchdog.sh"
CONF_DIR="/etc/morfsystem"
CONF="${CONF_DIR}/morfnetwatchdog.conf"
UNIT_DIR="/etc/systemd/system"

ACTION="install"
FORCE_CONFIG="no"

# --- Analyse des arguments -------------------------------------------------
for arg in "$@"; do
    case "$arg" in
        --uninstall)    ACTION="uninstall" ;;
        --reset-config) FORCE_CONFIG="yes" ;;
        -h|--help)      grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *)              echo "Option inconnue : $arg" >&2; exit 2 ;;
    esac
done

[ "$(id -u)" -eq 0 ] || { echo "A lancer en root (sudo)." >&2; exit 1; }

if [ "$ACTION" = "uninstall" ]; then
    systemctl disable --now morfnetwatchdog.timer 2>/dev/null || true
    rm -f "${UNIT_DIR}/morfnetwatchdog.timer" "${UNIT_DIR}/morfnetwatchdog.service" "$SBIN"
    systemctl daemon-reload
    echo "Desinstalle. La config ${CONF} et l'etat /var/lib sont conserves (a retirer a la main si besoin)."
    exit 0
fi

# Script principal.
install -m 0755 "${SRC_DIR}/morfNetWatchdog.sh" "$SBIN"

# Config admin : preservee par defaut, reecrite seulement avec --reset-config.
install -d -m 0755 "$CONF_DIR"
if [ -f "$CONF" ] && [ "$FORCE_CONFIG" = "no" ]; then
    echo "Config existante conservee : ${CONF} (--reset-config pour l'ecraser)"
elif [ -f "$CONF" ]; then
    install -m 0644 "${SRC_DIR}/morfnetwatchdog.conf" "$CONF"
    echo "Config par defaut reecrite (--reset-config) : ${CONF}"
else
    install -m 0644 "${SRC_DIR}/morfnetwatchdog.conf" "$CONF"
    echo "Config par defaut installee : ${CONF}"
fi

# Units systemd.
install -m 0644 "${SRC_DIR}/morfnetwatchdog.service" "${UNIT_DIR}/morfnetwatchdog.service"
install -m 0644 "${SRC_DIR}/morfnetwatchdog.timer"   "${UNIT_DIR}/morfnetwatchdog.timer"

systemctl daemon-reload
systemctl enable --now morfnetwatchdog.timer

echo
echo "Installe et actif. Verifs utiles :"
echo "  systemctl list-timers morfnetwatchdog.timer"
echo "  sudo ${SBIN}            # execution manuelle (silencieux si le lien est OK)"
echo "  journalctl -u morfnetwatchdog -f"
