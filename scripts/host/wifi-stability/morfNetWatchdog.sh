#!/usr/bin/env bash
# morfNetWatchdog.sh
# Filet de securite reseau independant des services morf*.
# Installe sous le service systemd (minuscules) morfnetwatchdog.
# Detecte une perte de lien LAN (typiquement un pilote Wi-Fi fige : brcmfmac sur
# Raspberry Pi) et remonte le reseau PROGRESSIVEMENT, le reboot n'etant que le
# tout dernier recours.
#
# Universel : aucune valeur n'est codee en dur. Tout se regle via le fichier de
# configuration (voir CONFIG_FILE ci-dessous) ou par variables d'environnement ;
# a defaut, l'interface, la passerelle et le pilote Wi-Fi sont auto-detectes.
#
# Escalade (timer toutes les 60 s, sur le nombre d'echecs consecutifs) :
#   WATCHDOG_STEP_RECONNECT     -> nmcli device reconnect / connection up
#   WATCHDOG_STEP_NM_RESTART    -> systemctl restart NetworkManager
#   WATCHDOG_STEP_MODULE_RELOAD -> rechargement du pilote Wi-Fi (deblocage cible)
#   WATCHDOG_STEP_REBOOT        -> reboot (dernier recours, garde anti-boucle)
# Mettre un palier a 0 le desactive : chaque hote choisit jusqu'ou aller.
#
# Le test porte UNIQUEMENT sur la passerelle LAN : on ne veut pas agir sur une
# simple panne d'internet ou de DNS cote FAI, seulement quand le lien local
# lui-meme a disparu.

set -u

# --- Chargement de la configuration ---------------------------------------
# Le fichier /etc est la config admin (doctrine FS morfSystem, lecture seule).
# Il est source ici pour que le script fonctionne aussi en execution manuelle,
# sans dependre de l'EnvironmentFile du service systemd.
CONFIG_FILE="${WATCHDOG_CONFIG_FILE:-/etc/morfsystem/morfnetwatchdog.conf}"
# shellcheck disable=SC1090
[ -r "$CONFIG_FILE" ] && . "$CONFIG_FILE"

# Valeurs par defaut si ni le fichier ni l'environnement ne les fournissent.
IFACE="${WATCHDOG_IFACE:-auto}"
GATEWAY="${WATCHDOG_GATEWAY:-auto}"
CONN="${WATCHDOG_CONN:-}"
WIFI_MODULES="${WATCHDOG_WIFI_MODULES:-auto}"
STEP_RECONNECT="${WATCHDOG_STEP_RECONNECT:-3}"
STEP_NM_RESTART="${WATCHDOG_STEP_NM_RESTART:-5}"
STEP_MODULE_RELOAD="${WATCHDOG_STEP_MODULE_RELOAD:-8}"
STEP_REBOOT="${WATCHDOG_STEP_REBOOT:-12}"
REBOOT_GUARD_S="${WATCHDOG_REBOOT_GUARD_S:-1800}"
PING_TRIES="${WATCHDOG_PING_TRIES:-3}"

STATE_DIR="/run/morfnetwatchdog"              # etat volatil (efface au reboot)
COUNT_FILE="${STATE_DIR}/count"                # compteur d'echecs consecutifs
PERSIST_DIR="/var/lib/morfnetwatchdog"        # etat persistant (survit au reboot)
LAST_REBOOT_FILE="${PERSIST_DIR}/last-reboot"  # horodatage du dernier reboot force

# Journalise dans le journal systemd (logger) et sur stdout.
log() { logger -t morfnetwatchdog -- "$*"; echo "morfnetwatchdog: $*"; }

mkdir -p "$STATE_DIR" "$PERSIST_DIR"

# --- Auto-detections -------------------------------------------------------
# Interface de la route par defaut (ex. wlan0, wlp2s0) si IFACE vaut "auto".
detect_iface() {
    ip route show default 2>/dev/null \
        | awk '{for (i = 1; i <= NF; i++) if ($i == "dev") { print $(i + 1); exit }}'
}
# Passerelle de la route par defaut si GATEWAY vaut "auto".
detect_gateway() {
    ip route show default 2>/dev/null | awk '/default/ {print $3; exit}'
}
# Pilote de l'interface (ex. brcmfmac) si WIFI_MODULES vaut "auto".
detect_driver() {
    local link
    link="$(readlink -f "/sys/class/net/${IFACE}/device/driver" 2>/dev/null)" || return
    [ -n "$link" ] && basename "$link"
}

case "$IFACE"   in auto|"") IFACE="$(detect_iface)" ;;   esac
case "$GATEWAY" in auto|"") GATEWAY="$(detect_gateway)" ;; esac

# --- Test de lien ----------------------------------------------------------
# Retourne 0 si la passerelle repond, 1 sinon. Plusieurs essais pour absorber
# une perte de paquet isolee sans declencher de fausse alerte.
link_ok() {
    [ -n "$GATEWAY" ] || return 1              # aucune route par defaut = lien perdu
    local i
    for i in $(seq 1 "$PING_TRIES"); do
        ping -c1 -W2 "$GATEWAY" >/dev/null 2>&1 && return 0
    done
    return 1
}

# --- Rechargement du pilote Wi-Fi (palier cible avant reboot) ---------------
reload_wifi_driver() {
    local drv rdeps
    if [ "$WIFI_MODULES" = "auto" ] || [ -z "$WIFI_MODULES" ]; then
        drv="$(detect_driver)"
    else
        drv="$WIFI_MODULES"                    # liste forcee par la config
    fi
    if [ -z "$drv" ]; then
        log "palier 3 ignore : pilote Wi-Fi introuvable (regler WATCHDOG_WIFI_MODULES)"
        return
    fi
    log "palier 3 : rechargement du pilote Wi-Fi (${drv})"
    # Decharger d'abord les modules qui dependent du pilote (colonne "Used by").
    rdeps="$(lsmod | awk -v d="$drv" '$1 != d && $NF ~ d {print $1}')"
    # shellcheck disable=SC2086
    [ -n "$rdeps" ] && modprobe -r $rdeps 2>/dev/null
    # shellcheck disable=SC2086
    modprobe -r $drv 2>/dev/null
    sleep 2
    # shellcheck disable=SC2086
    modprobe $drv
    sleep 2
    systemctl restart NetworkManager
}

# --- Compteur courant ------------------------------------------------------
count="$(cat "$COUNT_FILE" 2>/dev/null || echo 0)"
case "$count" in ''|*[!0-9]*) count=0 ;; esac

# --- Cas nominal : le lien repond -----------------------------------------
if link_ok; then
    if [ "$count" -ne 0 ]; then
        log "lien LAN retabli (${IFACE:-?} via ${GATEWAY:-?}) apres ${count} echec(s)"
    fi
    echo 0 > "$COUNT_FILE"
    exit 0
fi

# --- Cas degrade : le lien ne repond pas ----------------------------------
count=$((count + 1))
echo "$count" > "$COUNT_FILE"
log "lien LAN indisponible (${IFACE:-?}, passerelle ${GATEWAY:-aucune}), echec #${count}"

# Paliers d'action : on agit UNE fois a chaque seuil, pour laisser a chaque
# remediation le temps d'operer avant de passer a la suivante. Un palier a 0
# (desactive) ne se declenche jamais.
if [ "$STEP_RECONNECT" -gt 0 ] && [ "$count" -eq "$STEP_RECONNECT" ]; then
    if [ -n "$CONN" ]; then
        log "palier 1 : remontee du profil '${CONN}'"
        nmcli connection up "$CONN" 2>&1 | logger -t morfnetwatchdog
    else
        log "palier 1 : reconnexion de l'interface ${IFACE}"
        nmcli device reconnect "$IFACE" 2>&1 | logger -t morfnetwatchdog
    fi
fi

if [ "$STEP_NM_RESTART" -gt 0 ] && [ "$count" -eq "$STEP_NM_RESTART" ]; then
    log "palier 2 : redemarrage de NetworkManager"
    systemctl restart NetworkManager
fi

if [ "$STEP_MODULE_RELOAD" -gt 0 ] && [ "$count" -eq "$STEP_MODULE_RELOAD" ]; then
    reload_wifi_driver
fi

# Palier 4 : reboot, uniquement en dernier recours et jamais en boucle serree.
if [ "$STEP_REBOOT" -gt 0 ] && [ "$count" -ge "$STEP_REBOOT" ]; then
    now="$(date +%s)"
    last="$(cat "$LAST_REBOOT_FILE" 2>/dev/null || echo 0)"
    case "$last" in ''|*[!0-9]*) last=0 ;; esac
    if [ $((now - last)) -ge "$REBOOT_GUARD_S" ]; then
        log "palier 4 : reboot (dernier recours, lien absent depuis ~${count} min)"
        echo "$now" > "$LAST_REBOOT_FILE"
        systemctl reboot
    else
        log "reboot deja effectue recemment : on n'enchaine pas (defaut materiel ?)"
    fi
fi

exit 0
