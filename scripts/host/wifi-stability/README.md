# wifi-stability - durcissement Wi-Fi d'un hote (morfNet)

Kit de stabilisation reseau pour un hote Wi-Fi (Raspberry Pi en tete) qui doit
rester joignable en continu. Il repond a un incident concret : le pilote Wi-Fi
Broadcom `brcmfmac` d'un Pi peut se figer lors d'un roaming mesh (band steering
802.11v), laissant la machine allumee mais sans reseau pendant des heures.

Le kit ne s'installe qu'une fois par hote. Il regroupe deux volets independants :

1. **Stabiliser** le Wi-Fi pour eviter le blocage (cause probable).
2. **Surveiller** le lien avec un watchdog progressif, filet de securite si le
   pilote se rebloque malgre tout.

Le watchdog est **independant des services morf\*** : il ne s'appuie que sur
systemd, `nmcli` et `modprobe`. morfTools sert seulement a le deployer ; une fois
installe, il tourne seul.

Convention de nommage : les **scripts** portent le prefixe `morfNet` (majuscule),
comme les composants du parc ; le **service systemd** installe est en minuscules
(`morfnetwatchdog`), comme les autres services (morfmonitor, morfnotify...).

## Contenu

| Fichier | Role |
|---|---|
| `morfNetStabilize.sh` | Applique les reglages NetworkManager anti-blocage (volet 1). |
| `morfNetWatchdog.sh` | Le watchdog progressif (volet 2), installe en `/usr/local/sbin/`. |
| `morfnetwatchdog.conf` | Config admin (deposee dans `/etc/morfsystem/`). |
| `morfnetwatchdog.service` / `.timer` | Units systemd (service `morfnetwatchdog`, execution chaque minute). |
| `morfNetInstall.sh` | Installe/active le watchdog, ou le retire (`--uninstall`). |

## Volet 1 - stabiliser le Wi-Fi

```bash
# Detecte le profil Wi-Fi actif et coupe l'economie d'energie
sudo ./morfNetStabilize.sh

# Verrouille la bande 5 GHz (evite le steering 2,4<->5 GHz cote client)
sudo ./morfNetStabilize.sh monreseau --band a

# Version stricte : epingle un point d'acces precis (supprime le roaming,
# mais decroche si ce noeud change de BSSID -> le watchdog rattrape ce cas)
sudo ./morfNetStabilize.sh monreseau --band a --bssid B0:19:21:89:56:3F
```

A lancer en **console locale** (ou via un lien filaire), jamais dans la session
SSH que le `down/up` va couper. `--dry-run` affiche les commandes sans les appliquer.

**Volet decisif cote box/mesh** : le blocage est souvent declenche par le point
d'acces qui ejecte le client (`WNM: Disassociation Imminent`). Le client seul ne
peut pas l'empecher. Desactiver le **band steering / 802.11v (BSS Transition)**
pour cet appareil dans l'interface de la box, ou le fixer sur un noeud.

## Volet 2 - watchdog reseau

```bash
sudo ./morfNetInstall.sh
```

L'installation copie le script dans `/usr/local/sbin/morfNetWatchdog.sh`, depose
la config dans `/etc/morfsystem/morfnetwatchdog.conf` (sans ecraser une config
existante), installe les units systemd et active le timer.

Escalade, sur le nombre d'echecs consecutifs (timer = 60 s) :

| Palier | Delai | Action |
|---|---|---|
| `WATCHDOG_STEP_RECONNECT` | ~3 min | reconnexion de l'interface / du profil |
| `WATCHDOG_STEP_NM_RESTART` | ~5 min | `systemctl restart NetworkManager` |
| `WATCHDOG_STEP_MODULE_RELOAD` | ~8 min | rechargement du pilote Wi-Fi (deblocage cible) |
| `WATCHDOG_STEP_REBOOT` | ~12 min | `reboot` (dernier recours, garde anti-boucle 30 min) |

Principes :

- Le test porte **uniquement sur la passerelle LAN** : pas de reaction a une
  panne d'internet ou de DNS cote FAI, seulement quand le lien local a disparu.
- Le **rechargement du pilote precede le reboot** : souvent, il suffit a
  debloquer la puce sans redemarrer la machine.
- **Anti-boucle** : apres un reboot force, pas de second reboot avant 30 min ; si
  le materiel est reellement mort, le watchdog journalise au lieu de boucler.

Verifier / observer :

```bash
systemctl list-timers morfnetwatchdog.timer
sudo /usr/local/sbin/morfNetWatchdog.sh   # execution manuelle, silencieux si le lien est OK
journalctl -u morfnetwatchdog -f
```

## Rendre le kit universel (autres hotes, autres utilisateurs)

Rien n'est code en dur. L'adaptation a un autre hote passe uniquement par
`/etc/morfsystem/morfnetwatchdog.conf` :

- **Interface et passerelle** : `WATCHDOG_IFACE="auto"` et `WATCHDOG_GATEWAY="auto"`
  detectent la route par defaut. Aucun reglage pour un hote a une seule interface.
  En coupure totale (plus de route par defaut), `auto` retombe sur la derniere
  interface qui avait la connectivite (memorisee dans `/var/lib/morfnetwatchdog`),
  puis a froid sur la premiere interface Wi-Fi presente - le palier 3 sait donc
  toujours quel pilote recharger. Forcer une valeur (`WATCHDOG_IFACE="wlp2s0"`)
  reste possible sur un hote multi-interfaces.
- **Pilote Wi-Fi** : `WATCHDOG_WIFI_MODULES="auto"` lit le pilote de l'interface.
  Sur un materiel ou l'auto-detection ne suffit pas, donner la liste exacte
  (ex. Pi recent : `"brcmfmac_cyw brcmfmac"`, dans l'ordre de dechargement).
- **Profondeur d'escalade** : chaque palier se desactive avec `0`. Un hote
  critique qui ne doit jamais rebooter tout seul : `WATCHDOG_STEP_REBOOT=0`. Un
  hote ou l'on ne veut pas toucher au pilote : `WATCHDOG_STEP_MODULE_RELOAD=0`.
- **Rythme** : ajuster les seuils (nombre d'echecs) et, pour changer la cadence,
  `OnUnitActiveSec` dans le `.timer`.
- **Profil NetworkManager** : `WATCHDOG_CONN` est facultatif ; vide, le watchdog
  fait un `nmcli device reconnect` de l'interface, valable quel que soit le SSID.

Le volet 1 (`morfNetStabilize.sh`) est deja parametrable par arguments : profil,
bande, BSSID et powersave. Aucune valeur propre a un reseau donne n'y figure.

Pour un poste filaire, le kit reste pertinent (il surveille l'interface de la
route par defaut, Ethernet comprise) ; seul le palier de rechargement de pilote
Wi-Fi n'a alors pas d'objet et peut etre mis a `0`.
