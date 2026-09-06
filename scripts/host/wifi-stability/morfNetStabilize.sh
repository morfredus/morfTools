#!/usr/bin/env bash
# morfNetStabilize.sh
# Reglages NetworkManager pour limiter les blocages du pilote Wi-Fi (roaming /
# band steering, economie d'energie) sur Raspberry Pi et machines similaires.
# Universel : la connexion est passee en argument ou detectee automatiquement.
#
# Usage :
#   morfNetStabilize.sh [profil] [--band a|bg] [--bssid AA:BB:CC:DD:EE:FF]
#                       [--powersave 0|1|2|3] [--dry-run]
# Exemples :
#   morfNetStabilize.sh                         # detecte le profil Wi-Fi actif, coupe le powersave
#   morfNetStabilize.sh monreseau --band a      # verrouille la bande 5 GHz
#   morfNetStabilize.sh monreseau --band a --bssid B0:19:21:89:56:3F  # epingle un point d'acces
#
# Rappel : verrouiller la bande evite le steering 2,4<->5 GHz cote client, mais
# le volet decisif reste cote box/mesh (desactiver le band steering / 802.11v
# pour cet appareil). Le client seul ne peut pas empecher un AP qui l'ejecte.

set -euo pipefail

CONN=""
BAND=""
BSSID=""
POWERSAVE="2"     # 2 = disable : recommande sur un hote serveur toujours allume
DRY_RUN="no"

# --- Analyse des arguments -------------------------------------------------
while [ $# -gt 0 ]; do
    case "$1" in
        --band)      BAND="${2:-}"; shift 2 ;;
        --bssid)     BSSID="${2:-}"; shift 2 ;;
        --powersave) POWERSAVE="${2:-}"; shift 2 ;;
        --dry-run)   DRY_RUN="yes"; shift ;;
        -h|--help)   grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        --*)         echo "Option inconnue : $1" >&2; exit 2 ;;
        *)           CONN="$1"; shift ;;
    esac
done

command -v nmcli >/dev/null || { echo "nmcli introuvable" >&2; exit 1; }

# --- Detection du profil Wi-Fi actif si non fourni -------------------------
if [ -z "$CONN" ]; then
    CONN="$(nmcli -t -f NAME,TYPE connection show --active \
        | awk -F: '$2 == "802-11-wireless" {print $1; exit}')"
fi
[ -n "$CONN" ] || { echo "Aucun profil Wi-Fi trouve : precisez-le en argument." >&2; exit 1; }

echo "Profil Wi-Fi cible : ${CONN}"

# --- Construction de la liste des reglages a appliquer ---------------------
settings=( "802-11-wireless.powersave" "$POWERSAVE" )
[ -n "$BAND" ]  && settings+=( "802-11-wireless.band"  "$BAND" )
[ -n "$BSSID" ] && settings+=( "802-11-wireless.bssid" "$BSSID" )

echo "Reglages : ${settings[*]}"
if [ "$DRY_RUN" = "yes" ]; then
    echo "(dry-run) nmcli connection modify \"$CONN\" ${settings[*]}"
    echo "(dry-run) nmcli connection down \"$CONN\" && nmcli connection up \"$CONN\""
    exit 0
fi

# --- Application -----------------------------------------------------------
# Attention : le down/up coupe brievement le Wi-Fi. A lancer en console locale
# (ou via un lien filaire), pas dans la session SSH que l'on est en train de couper.
nmcli connection modify "$CONN" "${settings[@]}"
nmcli connection down "$CONN"
nmcli connection up "$CONN"

echo "Termine. Etat :"
nmcli -f GENERAL.STATE,GENERAL.CONNECTION,IP4.ADDRESS device show \
    "$(nmcli -t -f DEVICE,TYPE device status | awk -F: '$2=="wifi"{print $1; exit}')" || true
