# morfSystem — guide de démarrage

Ce guide suppose que vous ne connaissez rien à morfSystem. Il répond à trois
questions, dans l'ordre où elles se posent : **qu'est-ce que c'est**, **comment
l'installer**, **comment le configurer** — et dans quel ordre lancer les
commandes.

---

## 1. Ce que vous installez

morfSystem n'est pas un logiciel, c'est **un ensemble de petits services
indépendants** qui vivent sur votre réseau local. Chacun fait une seule chose et
tourne tout seul.

```
                     ┌────────────────────┐
                     │ RaspberryDashboard │   affiche
                     └──────────┬─────────┘
                                │  lit /api/
                     ┌──────────▼─────────┐
                     │    morfMonitor     │   centralise et expose
                     └──────────▲─────────┘
                                │  entend les annonces (morfbeacon/1)
        ┌───────────┬───────────┼───────────┬───────────┐
    morfSync    morfSensor  morfNotify   MeteoHub   GatewayLab
        └───────────┴───────────┴───────────┴───────────┘
              chacun tourne seul, et annonce sa présence
```

Les flèches vont dans **un seul sens**. Les services annoncent leur présence ;
morfMonitor les entend et expose ce qu'il sait ; le Dashboard lit morfMonitor.
Personne ne pilote personne.

Conséquence directe, et c'est le test qui tranche : **arrêtez morfMonitor, et
tout le reste continue de fonctionner**. Vous perdez la vue d'ensemble, pas les
services. morfMonitor est un observatoire, pas un portail — il ne s'interpose
jamais entre vous et un service.

> ### Important — chaque projet est autonome
>
> Vous pouvez n'installer **que** morfMonitor. Ou **que** morfSync. Ou **que**
> MeteoHub. Aucun ne dépend des autres pour démarrer.
>
> morfSystem n'est **pas une dépendance obligatoire** : c'est un ensemble de
> services qui **enrichissent** les applications lorsqu'ils sont présents. Une
> application qui n'entend aucune annonce fonctionne normalement — elle affiche
> simplement moins de choses.
>
> C'est la différence principale avec la plupart des écosystèmes, où retirer une
> brique casse les autres. Ici, une brique absente est une information en moins,
> jamais une panne.

| Service | Ce qu'il fait |
|---|---|
| **morfMonitor** | **Centralise et expose** l'état d'une machine en JSON — ce que ses propres modules mesurent, et ce que les autres services annoncent. N'affiche rien. |
| **RaspberryDashboard** | Affiche cet état sur un écran. Ne collecte rien. |
| **morfSync** | Synchronise des données entre machines, sans cloud. |
| **morfNotify**, **morfSensor**, **morfAnalytics** | Notifications, capteurs, analyses. |
| **morfTemplateService** | Le patron dont on clone un nouveau service. Ne sert à rien en production. |

Avec l'autonomie, une seconde idée explique tout le reste : **les services se
découvrent tout seuls.** Chacun annonce sa présence sur le réseau local ; les
autres l'entendent. Vous n'avez jamais à dire à morfMonitor où se trouve
morfSync — il l'apprend.

Commencez donc par ce dont vous avez besoin. Vous pourrez en ajouter plus tard
sans rien reconfigurer : un nouveau service s'annonce, et il apparaît.

---

## 2. Ce qu'il vous faut

- **Git**, **Python 3**, **CMake**, un compilateur C++
- **Qt 6** pour la plupart des services (pas pour morfSync)
- Sur Raspberry Pi : tout est dans les dépôts Raspberry Pi OS

Systèmes officiellement supportés : **Windows x64**, **Linux x64**, **Linux
ARM64 (Raspberry Pi)**. macOS n'est pas supporté — voir
[ECOSYSTEM-PRINCIPLES.md](ECOSYSTEM-PRINCIPLES.md).

---

## 3. Première installation, dans l'ordre

### Étape 1 — Récupérer les projets

Tout part de **morfTools**, l'outil qui pilote les autres.

```bash
mkdir -p ~/Codage && cd ~/Codage
git clone https://github.com/morfredus/morfTools.git
cd morfTools
python3 morf.py clone          # clone tous les projets déclarés, à côté
```

Vous obtenez un dossier par projet, côte à côte. **Cette disposition compte** :
les outils se cherchent les uns les autres en remontant d'un cran.

```
~/Codage/
├── morfTools/          ← vous êtes ici
├── morfMonitor/
├── morfSync/
└── ...
```

### Étape 2 — Vérifier que tout est cohérent

```bash
python3 morf.py doctor
```

À lancer **avant** de compiler quoi que ce soit. Il vérifie ce qu'aucun projet
ne peut vérifier seul : que deux services ne se disputent pas le même port, que
les bibliothèques recopiées n'ont pas divergé, que les scripts sont exécutables.
Si tout est `[OK]`, continuez.

### Étape 3 — Compiler

```bash
python3 morf.py build
```

Il vous demandera un *preset* — le profil de compilation :

| Preset | Quand |
|---|---|
| `linux` | PC Linux |
| `linux-arm64` | Raspberry Pi |
| `mingw` | Windows |

### Étape 4 — Installer un service

**Un service à la fois**, en commençant par celui dont vous avez besoin.

```bash
cd ~/Codage/morfMonitor
sudo ./service.py install
```

C'est tout. La commande compile si nécessaire, copie le binaire dans un dossier
fixe (`/opt/morfmonitor`), installe la configuration dans `/etc/morfmonitor`, enregistre le service
auprès du système et le démarre.

**La même commande partout** — Linux, Windows, Raspberry Pi. Seul le mécanisme
sous-jacent change (systemd, services Windows), et vous n'avez pas à le savoir.

### Étape 5 — Vérifier

```bash
./service.py status
curl http://127.0.0.1:8790/status
```

---

## 4. La configuration : le point où tout le monde se perd

**C'est ici que se produit la confusion la plus fréquente**, alors elle mérite
d'être dite franchement.

### Le service ne lit PAS les fichiers du dépôt

```
   dépôt (vous éditez)                      installé (le service lit)
   config/morfmonitor.json    ──installe──> /etc/morfmonitor/morfmonitor.json
   config/morfsystem.json     ──installe──> /etc/morfsystem/morfsystem.json
```

**Toute configuration vit dans `/etc`**, jamais à côté du binaire. `/opt` ne
contient que des exécutables. C'est la convention Linux — `/etc` est le premier
endroit où l'on regarde — et ça a une conséquence pratique : effacer
`/opt/morfmonitor` pour réinstaller proprement n'emporte pas vos réglages.

| | |
|---|---|
| `/opt/<service>/` | le binaire, remplacé à chaque mise à jour |
| `/etc/<service>/` | sa configuration, **jamais** écrasée |
| `/etc/morfsystem/` | la configuration partagée, lue par plusieurs programmes |

Modifier un fichier dans le dépôt **ne change rien** tant que vous n'avez pas
relancé le déploiement. C'est la cause numéro un du « pourtant je l'ai
corrigé ».

### Deux fichiers, deux rôles

| Fichier | Contient | Lu par |
|---|---|---|
| `morfmonitor.json` | Le **service** : port, adresse d'écoute | morfMonitor seul |
| `morfsystem.json` | Ce qui est **supervisé** : services, sondes, applications | morfMonitor **et** RaspberryDashboard |

Pour ajouter quelque chose à surveiller, vous éditez `morfsystem.json`. Rien
d'autre. Aucun code à modifier.

### Le fichier réel gagne sur l'exemple

Chaque projet fournit un `.example.json` **qui fonctionne tel quel**. Si les
valeurs par défaut vous conviennent, ne créez rien.

Si vous créez un fichier réel à côté (sans `.example`), **c'est lui** qui sera
installé, et l'exemple cesse d'être consulté.

### Déclarer, c'est s'attendre

Une application déclarée avec `"enabled": true` est *attendue* : son absence
devient une anomalie, en rouge. Une application non déclarée qui s'arrête ne
déclenche rien.

Réservez `true` à ce qui tourne en permanence. Sinon vous verrez une alerte
rouge permanente pour un programme qui n'a jamais eu vocation à tourner.

---

## 5. Au quotidien : quelle commande, quand

| Vous voulez | Commande | Où |
|---|---|---|
| Récupérer le code à jour | `python3 morf.py update` | morfTools |
| Récupérer **et** recompiler | `python3 morf.py upgrade` | morfTools |
| Vérifier la cohérence du parc | `python3 morf.py doctor` | morfTools |
| Installer un service | `sudo ./service.py install` | le projet |
| **Mettre à jour un service installé** | `sudo ./service.py update` | le projet |
| Désinstaller | `sudo ./service.py uninstall` | le projet |
| Voir l'état du parc | `python3 config.py shared status` | morfTools |
| Pousser une config modifiée | `python3 config.py shared apply` | morfTools |

### Le piège de `update` et `upgrade`

Trois choses portent ce nom et ne font pas la même chose :

| | Agit sur | Effet |
|---|---|---|
| `morf.py update` | les **sources** | `git pull`, rien d'autre |
| `morf.py upgrade` | les **sources** | `git pull` **et** recompile |
| `service.py update` | le service **installé** | recompile, remplace le binaire, redémarre |

Les deux premiers ne touchent à **rien d'installé**. Après un `upgrade`, votre
Raspberry Pi continue de faire tourner l'ancienne version jusqu'à ce que vous
lanciez le `service.py update` du projet.

### La séquence d'une mise à jour complète

```bash
cd ~/Codage/morfTools
python3 morf.py update            # 1. récupérer le code
python3 morf.py doctor            # 2. vérifier la cohérence

cd ~/Codage/morfMonitor
sudo ./service.py update          # 3. recompiler et remplacer, service par service
```

Vos configurations ne sont **jamais** écrasées par une mise à jour. Les
réglages que vous avez faits à la main survivent.

---

## 6. Quand ça ne marche pas

| Symptôme | Cause probable | Que faire |
|---|---|---|
| J'ai édité un fichier, rien n'a changé | Le service lit la copie installée | Relancer le déploiement |
| Toutes les routes `/api/` répondent **503** | Aucun module de supervision déclaré | `./scripts/linux/config-tool.sh check` |
| Les listes sont vides | `morfsystem.json` pas installé | `python3 config.py shared install` |
| Un équipement n'apparaît jamais | Il n'annonce rien, ou l'UDP est filtré | `python3 tools/check-protocol.py` depuis morfBeacon |
| Une application est signalée en permanence | `enabled: true` sur un programme occasionnel | Passer à `false` |
| Le service ne redémarre pas au boot | Il n'est pas *activé* | `systemctl is-enabled <service>` |

Pour lire les journaux d'un service :

```bash
journalctl -u morfmonitor -f          # Linux
./service.py status                   # partout
```

---

## 7. Pour aller plus loin

| Document | Sujet |
|---|---|
| [ECOSYSTEM-PRINCIPLES.md](ECOSYSTEM-PRINCIPLES.md) | Les principes et invariants, et **pourquoi** ils existent |
| [ECOSYSTEM-CHECKS.md](ECOSYSTEM-CHECKS.md) | Ce que `morf doctor` vérifie, et ce qu'il ne peut pas vérifier |
| `README.md` de chaque projet | Ce que fait ce service, et son API |

Une chose à retenir si vous n'en retenez qu'une : **le parc se configure par des
fichiers JSON, jamais par du code**. Ajouter un service à superviser, un capteur,
une sonde réseau, c'est éditer un fichier et le déployer.
