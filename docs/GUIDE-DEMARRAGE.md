# morfSystem — guide de démarrage

Ce guide suppose que vous ne connaissez rien à morfSystem. Il répond, dans
l'ordre où elles se posent, aux questions : **qu'est-ce que c'est et à quoi ça
sert**, **comment l'installer**, **comment le configurer**, **comment le
consulter** et **comment le désinstaller** — avec l'ordre des commandes à chaque
étape.

---

## 1. Ce que vous installez

morfSystem n'est pas un logiciel, c'est **un ensemble de petits services
indépendants** qui vivent sur votre réseau local. Chacun fait une seule chose et
tourne tout seul.

```
                     ┌────────────────────┐
                     │   morfDashboard    │   affiche
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
| **morfDashboard** | Affiche cet état sur un écran. Ne collecte rien. |
| **morfSync** | Synchronise des données entre machines, sans cloud. |
| **morfNotify**, **morfSensor**, **morfAnalytics** | Notifications, capteurs, analyses. |
| **morfTemplateService** | Le patron dont on clone un nouveau service. Ne sert à rien en production. |

Avec l'autonomie, une seconde idée explique tout le reste : **les services se
découvrent tout seuls.** Chacun annonce sa présence sur le réseau local ; les
autres l'entendent. Vous n'avez jamais à dire à morfMonitor où se trouve
morfSync — il l'apprend.

Commencez donc par ce dont vous avez besoin. Vous pourrez en ajouter plus tard
sans rien reconfigurer : un nouveau service s'annonce, et il apparaît.

### À quoi tout cela sert : les applications du parc

Les services ci-dessus sont le **socle**. Ils prennent tout leur sens avec les
applications qui s'appuient dessus — elles s'annoncent sur le réseau, apparaissent
dans morfMonitor, et pour certaines synchronisent leurs données par morfSync,
sans cloud :

| Application | Ce qu'elle fait | S'appuie sur |
|---|---|---|
| **ComponentHub** | Mémoire technique d'un atelier d'électronique : inventaire des composants, modules, outils, stocks et emplacements | s'annonce, **synchronise** (morfSync) |
| **SiteWatch** | Administration et supervision de sites web, application Qt multiplateforme | s'annonce (morfBeacon) |
| **MeteoHub** | Station météo ESP32-S3 : capteurs, prévisions et journaux sur écran OLED et page web embarquée | s'annonce (morfBeacon) |
| **GatewayLab** | Passerelle ESP32-S3 qui découvre et historise les équipements du réseau local | s'annonce (morfBeacon) |

Aucune n'a **besoin** du parc pour fonctionner — c'est le principe d'autonomie,
dans les deux sens. Mais lorsqu'il est là, il les enrichit : ComponentHub
retrouve ses données sur une autre machine par morfSync, MeteoHub et GatewayLab
deviennent visibles et surveillables depuis morfMonitor, SiteWatch signale sa
présence au reste du réseau. **Le parc n'est pas une fin en soi : c'est ce qui
relie et surveille vos applications.**

Au fil du temps, d'autres applications compatibles viendront enrichir
l'écosystème. Aucune n'a de dépendance obligatoire envers morfSystem : elles
restent pleinement fonctionnelles lorsqu'il est absent. Mais dès qu'elles
détectent les services du parc, elles peuvent activer d'elles-mêmes des
fonctionnalités supplémentaires — supervision, synchronisation de données,
analyses avancées, notifications. Chaque projet évolue ainsi de son côté, tout
en profitant des capacités de l'écosystème quand il est là. Cette liste de quatre
applications n'est donc qu'un instantané : elle grandira.

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

> **Sur un premier clone, `doctor` peut signaler des scripts « non-executable ».**
> C'est fréquent : Git ne conserve pas toujours le bit d'exécution selon la
> machine d'origine du dépôt. Un seul geste répare tout le parc, **depuis le
> dossier `morfTools`** :
>
> ```bash
> python3 scripts/exec-bits.py ..
> ```
>
> **Utilisez `python3`, pas `./exec-bits.sh`.** Le wrapper `.sh` aurait besoin du
> bit qu'il s'apprête justement à restaurer : sur un clone neuf il ne peut pas
> démarrer (`Permission denied`). L'invoquer par `python3` ignore le bit —
> exactement la raison pour laquelle `python3 morf.py` fonctionne toujours.
> Une fois cette commande passée, `./exec-bits.sh`, `./service.py` et les autres
> redeviennent lançables. Relancez `python3 morf.py doctor` : il doit être vert.
>
> **Pour que le correctif tienne** (si vous avez les droits de push sur les
> dépôts) : `exec-bits` ne fait que *mettre en scène* le changement. Sans
> `commit` + `push`, le dépôt distant garde les fichiers non-exécutables, et le
> prochain `pull` qui les touche **retire à nouveau le bit**. Rendez-le durable,
> en une fois pour tout le parc :
>
> ```bash
> python3 morf.py commit -m "chore: restore executable bit on scripts"
> python3 morf.py push
> ```
>
> Si vous n'avez pas les droits de push, la réparation locale suffit à travailler ;
> c'est au propriétaire des dépôts de la rendre définitive une bonne fois.

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

### Étape 4 — Installer les services

Chaque service s'installe **depuis son propre dossier**, avec la **même
commande**. En première installation, vous ne savez pas forcément lesquels
prendre — voici la liste complète, et par quoi commencer.

```bash
cd ~/Codage/morfMonitor && sudo ./service.py install
```

C'est tout. La commande compile si nécessaire, copie le binaire dans un dossier
fixe (`/opt/morfmonitor`), installe la configuration dans `/etc/morfmonitor`,
enregistre le service auprès du système et le démarre.

**Les services que vous pouvez installer**, chacun avec `sudo ./service.py
install` depuis son dossier :

| Dossier | Service | Rôle | À installer ? |
|---|---|---|---|
| `morfMonitor` | morfmonitor | collecte et expose l'état, sert l'interface web | **oui, en premier** — c'est le cœur |
| `morfSync` | morfsync | synchronisation de données entre machines, sans cloud | si une appli synchronise (ex. ComponentHub) |
| `morfNotify` | morfnotify | point de diffusion des notifications | si vous voulez des alertes |
| `morfSensor` | morfsensor | acquisition de capteurs | si vous avez des capteurs |
| `morfAnalytics` | morfanalytics | analyses | si vous exploitez des analyses |
| `morfTemplateService` | morftemplate | **patron** pour créer un service — **n'installez pas** en production | non |

**Installez-en un seul si vous voulez** : chacun est autonome. Le minimum utile
est **morfMonitor** — il vous donne déjà l'interface web et voit tout ce qui
s'annonce sur le réseau. Ajoutez les autres au fur et à mesure de vos besoins,
sans rien reconfigurer.

Le **Raspberry Dashboard** (l'écran OLED) s'installe différemment, par son propre
script, et suppose l'écran branché :

```bash
cd ~/Codage/morfDashboard && sudo ./scripts/linux/install-service.sh
```

**La même commande `service.py` partout** — Linux, Windows, Raspberry Pi. Seul le
mécanisme sous-jacent change (systemd, services Windows), et vous n'avez pas à le
savoir.

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
| `morfsystem.json` | Ce qui est **supervisé** : services, sondes, applications | morfMonitor **et** morfDashboard |

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

## 5. Consulter le parc

Une fois morfMonitor installé, tout se regarde **depuis un navigateur**, sur
n'importe quelle machine du réseau local — y compris quand le Pi n'a aucun écran.

### D'abord : l'adresse de VOTRE machine

Dans tous les exemples ci-dessous, `<votre-machine>` désigne le Raspberry Pi (ou
la machine qui fait tourner morfMonitor). Remplacez-le par **votre** adresse.
Deux façons de la désigner :

- **Par son nom**, si le réseau résout le mDNS : le nom de la machine suivi de
  `.local`. Le nom se lit avec la commande `hostname`. Une machine nommée
  `pi4fred` se joint alors par **`pi4fred.local`** — c'est l'exemple utilisé
  dans tout ce guide, adaptez-le au vôtre. Le mDNS est fourni par Avahi (installé
  d'origine sur Raspberry Pi OS) et reconnu par macOS et Windows récents. S'il ne
  répond pas sur votre réseau, passez à l'adresse IP.
- **Par son adresse IP**, toujours valable : `hostname -I` sur le Pi la donne
  (ex. `192.168.1.55`), ou lisez-la dans l'onglet **État général** de morfMonitor.
  L'accès devient alors `http://192.168.1.55:8790/`.

Le port **8790** est celui de morfMonitor et ne change pas.

### L'interface web de morfMonitor

Ouvrez, depuis votre PC, votre téléphone, n'importe quel navigateur du réseau :

```
http://<votre-machine>:8790/
```

Vous y trouverez, en six onglets :

| Onglet | Ce qu'il répond |
|---|---|
| État général | identité de la machine, uptime, santé des services, résumé des anomalies |
| Ressources | CPU, mémoire, charge, swap, stockage, processus |
| Réseau | interfaces, IPv4/IPv6, MAC, état des liens |
| Services morfSystem | unités systemd et sondes réseau supervisées |
| **Écosystème** | tous les services et applications découverts sur le réseau, avec version, dernier heartbeat, et un lien direct vers leur propre interface |
| Diagnostic | anomalies détectées, cause du dernier redémarrage, état de la config partagée |

L'onglet **Écosystème** est le cœur : c'est là qu'apparaissent ComponentHub,
MeteoHub, SiteWatch, GatewayLab et les services, à mesure qu'ils s'annoncent. Un
service qui déclare une interface web y affiche un lien qui **pointe directement
vers lui** — morfMonitor observe et référence, il ne relaie rien.

L'interface n'est qu'une **seconde vue** des mêmes données que l'API : tout ce
qu'elle montre est aussi lisible en JSON, par exemple `http://<votre-machine>:8790/api/all`.

> L'écran répond à « est-ce que tout va bien ? ». L'interface web répond à
> « pourquoi ? ».

Elle écoute sur toutes les interfaces réseau par défaut (`bind_address:
0.0.0.0`). Sur une machine exposée hors du LAN, restreignez-la à l'adresse locale
— il n'y a pas d'authentification, le modèle de confiance est le réseau local
(voir [ECOSYSTEM-PRINCIPLES.md](ECOSYSTEM-PRINCIPLES.md)).

### L'écran du Raspberry : morfDashboard

Si votre Pi porte un petit écran OLED, **morfDashboard** y affiche l'essentiel
en un coup d'œil — identité, ressources, présence des services — sans clavier ni
navigateur. Il ne collecte rien lui-même : il lit morfMonitor et l'affiche. C'est
la réponse rapide à « est-ce que tout va bien ? », l'interface web restant là pour
le « pourquoi ? ».

Depuis la version 1.8, le Dashboard **s'annonce lui aussi** : il apparaît dans
l'onglet Écosystème comme les autres, et sert un `http://<votre-machine>:8791/status`.

---

## 6. Au quotidien : quelle commande, quand

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

## 7. Désinstaller

La désinstallation est **prudente par défaut** : elle retire le service, mais
**garde votre configuration**. Vos réglages ne disparaissent jamais sans que
vous l'ayez demandé.

### Un service

Depuis le dossier du projet :

```bash
cd ~/Codage/morfMonitor
sudo ./service.py uninstall
```

Le service est arrêté et retiré du système ; `/etc/morfmonitor` (votre config)
et `/opt/morfmonitor` (le binaire) restent en place. Vous pouvez réinstaller
plus tard sans avoir rien perdu.

**Pour tout effacer, y compris la configuration**, ajoutez `--purge` — et
`--backup` pour en garder une copie avant :

```bash
sudo ./service.py uninstall --purge                       # efface aussi la config
sudo ./service.py uninstall --purge --backup ~/sauvegarde # copie la config, puis efface
```

`--purge` retire la config, le binaire, et les emplacements que d'anciennes
versions avaient laissés. `--backup` copie d'abord chaque fichier de config dans
le dossier indiqué. La suppression n'est jamais destructive au point de vous
prendre par surprise : sans `--purge`, rien de personnel n'est touché.

### Depuis morfTools, plusieurs services d'un coup

```bash
cd ~/Codage/morfTools
python3 morf.py uninstall --only morfMonitor    # un seul
python3 morf.py uninstall                        # tous les services du parc
python3 morf.py uninstall --purge --backup ~/sauvegarde   # tous, config sauvegardée puis effacée
```

### Repartir totalement à blanc

Pour vider entièrement une machine — tous les services, toutes les configs, y
compris les vestiges des migrations — avant une réinstallation propre :

```bash
cd ~/Codage/morfTools
sudo ./scripts/reset-parc.sh --dry-run    # liste ce qui serait supprimé, sans rien toucher
sudo ./scripts/reset-parc.sh              # supprime, après confirmation (tapez « yes »)
```

`reset-parc.sh` liste tout ce qu'il va retirer, demande confirmation, et
**ne touche jamais aux dépôts clonés** — seulement à ce qui est installé.
Utilisez-le pour valider une installation complète en partant de zéro.

---

## 8. Quand ça ne marche pas

| Symptôme | Cause probable | Que faire |
|---|---|---|
| J'ai édité un fichier, rien n'a changé | Le service lit la copie installée | Relancer le déploiement |
| Toutes les routes `/api/` répondent **503** | Aucun module de supervision déclaré | `./scripts/linux/config-tool.sh check` |
| Les listes sont vides | `morfsystem.json` pas installé | `python3 config.py shared install` |
| Un équipement n'apparaît jamais | Il n'annonce rien, ou l'UDP est filtré | `python3 tools/check-protocol.py` depuis morfBeacon |
| Une application est signalée en permanence | `enabled: true` sur un programme occasionnel | Passer à `false` |
| Le service ne redémarre pas au boot | Il n'est pas *activé* | `systemctl is-enabled <service>` |
| `doctor` dit **non-executable**, et `./exec-bits.sh` répond `Permission denied` | Le bit d'exécution manque, y compris sur le script de réparation | `python3 scripts/exec-bits.py ..` (par `python3`, jamais `./…`) |
| `./service.py install` répond `Permission denied` | Même cause : bit manquant sur un clone neuf | Réparer d'abord : `python3 scripts/exec-bits.py ..` depuis morfTools |
| `Permission denied (publickey)` sur **tous** les dépôts, ou `cannot open .git/FETCH_HEAD` | Un `morf.py update` a tourné **sous sudo** : clé SSH de root inexistante, et fichiers root laissés dans `.git` | `sudo chown -R $USER:$USER ~/Codage/*/.git` puis relancer **sans sudo** — `morf.py` le refuse désormais |

Pour lire les journaux d'un service :

```bash
journalctl -u morfmonitor -f          # Linux
./service.py status                   # partout
```

---

## 9. La philosophie de morfSystem

morfSystem repose sur quelques principes simples qui guident l'ensemble des
projets :

- chaque service a une **responsabilité unique** ;
- chaque projet reste **autonome** et fonctionne sans dépendre du reste du parc ;
- les services se **découvrent automatiquement** grâce à morfBeacon ;
- les applications sont **enrichies** par l'écosystème, jamais rendues dépendantes
  de lui ;
- les configurations sont **déclaratives** et vivent dans des fichiers JSON,
  jamais dans le code ;
- morfTools centralise le développement, le déploiement et la maintenance, tandis
  que les services restent **indépendants une fois installés**.

Ces principes expliquent la plupart des choix d'architecture présentés dans ce
guide, et permettent à l'écosystème de grandir sans remettre en cause les
projets existants. Le **pourquoi** de chacun — et les frontières qu'ils posent —
est détaillé dans [ECOSYSTEM-PRINCIPLES.md](ECOSYSTEM-PRINCIPLES.md).

---

## 10. Pour aller plus loin

| Document | Sujet |
|---|---|
| [ECOSYSTEM-PRINCIPLES.md](ECOSYSTEM-PRINCIPLES.md) | Les principes et invariants, et **pourquoi** ils existent |
| [ECOSYSTEM-CHECKS.md](ECOSYSTEM-CHECKS.md) | Ce que `morf doctor` vérifie, et ce qu'il ne peut pas vérifier |
| `README.md` de chaque projet | Ce que fait ce service, et son API |

**Et après ?** Une évolution est déjà cadrée sans être encore décidée :
l'**accès distant** (atteindre le parc hors du réseau local). Le modèle de
confiance à retenir — la décision R5 — est documenté dans
[ECOSYSTEM-PRINCIPLES.md](ECOSYSTEM-PRINCIPLES.md), avec les options à peser. Rien
n'est exposé hors du LAN tant qu'elle n'est pas tranchée.

Une chose à retenir si vous n'en retenez qu'une : **le parc se configure par des
fichiers JSON, jamais par du code**. Ajouter un service à superviser, un capteur,
une sonde réseau, c'est éditer un fichier et le déployer.
