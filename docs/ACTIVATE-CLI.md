# Activation des commandes CLI de l'espace de travail (`activate-cli.sh`)

Ce guide explique comment exposer les commandes publiques de l'écosystème
morfSystem (`morf`, `screenctl`, ...) pour pouvoir les appeler depuis n'importe
quel répertoire, sans jamais déplacer les scripts hors de leur projet.

> En une phrase : **désigner quel espace de travail fournit actuellement les
> commandes morfSystem de mon shell**, et rien de plus.

---

## Le problème

morfSystem est un ensemble de projets **frères** posés côte à côte dans une même
racine de travail. Selon la machine, cette racine peut porter des noms
différents :

```text
/home/user/01-Travail/            ou      /home/user/morfSystem/
├── morfTools/                            ├── morfTools/
├── morfDashboard/                        ├── morfDashboard/
├── morfMonitor/                          ├── morfMonitor/
└── ...                                   └── ...
```

`01-Travail` et `morfSystem` sont deux **racines alternatives** valides. Il
n'existe pas de dossier intermédiaire : les projets sont directement sous la
racine.

Certains projets fournissent de vraies commandes utilisateur. On veut pouvoir
écrire, depuis n'importe où :

```bash
morf doctor
screenctl status
```

sans se déplacer au préalable dans `morfTools` ou `morfDashboard`, et **sans**
copier ou déplacer les scripts hors de leur projet propriétaire.

---

## Le principe

Les commandes publiques sont exposées dans le dossier standard de l'utilisateur :

```text
~/.local/bin/
```

Les scripts sources, eux, **restent dans leur projet** : ils ne sont ni déplacés
ni copiés. Selon leur fonctionnement, une commande est exposée de deux manières :

| Mode      | Ce qui est créé dans `~/.local/bin` | Pour quels scripts |
|-----------|-------------------------------------|--------------------|
| `direct`  | un **lien symbolique** vers le script | ceux dont le comportement ne dépend pas du répertoire courant |
| `project` | un petit **lanceur** qui entre dans le projet avant d'exécuter | ceux qui doivent être lancés depuis leur propre dossier |

Le mode est **toujours déclaré** explicitement par le projet. Le mécanisme ne le
devine jamais en analysant le code.

---

## Activation : volontaire, jamais automatique

La création de ces commandes **ne fait pas partie** de l'installation du parc.
Elle n'est jamais déclenchée par `morf install` ni `morf update`, ni par
l'installation d'un projet particulier.

Plusieurs espaces de travail peuvent cohabiter légitimement sur une machine et
contenir les mêmes projets, donc les mêmes commandes. Une seule origine doit
alimenter `~/.local/bin` à un instant donné, et **ce choix appartient à
l'utilisateur**.

Pour activer l'espace contenant une copie donnée de morfTools :

```bash
# Utiliser les projets de 01-Travail
cd ~/01-Travail/morfTools
./activate-cli.sh

# ... ou basculer vers ceux de morfSystem
cd ~/morfSystem/morfTools
./activate-cli.sh
```

Le script active les CLI de **l'espace auquel appartient cette copie de
morfTools**. La racine est déterminée seule : c'est le dossier **parent** de
morfTools. Aucun chemin n'est codé en dur.

```text
/home/user/01-Travail/morfTools/activate-cli.sh   ->  racine = /home/user/01-Travail
/home/user/morfSystem/morfTools/activate-cli.sh   ->  racine = /home/user/morfSystem
```

---

## Une activation concerne tout l'espace

Règle impérative : **une activation ne mélange jamais deux espaces**. Si vous
activez `01-Travail`, toutes les commandes exposées proviennent de projets situés
sous `01-Travail`. Il ne doit jamais être possible d'obtenir par accident :

```text
morf       -> /home/user/01-Travail/morfTools/morf.py
screenctl  -> /home/user/morfSystem/morfDashboard/screenctl.py   (INTERDIT)
```

L'espace est activé comme un ensemble cohérent. Pour basculer, on relance
`activate-cli.sh` depuis l'autre copie de morfTools : les liens et lanceurs sont
réorientés, et les commandes qui n'existent que dans l'ancien espace sont
retirées.

---

## Déclarer une commande : `cli.manifest`

Chaque projet **propriétaire** déclare ses commandes dans un fichier
`cli.manifest` à sa racine. La présence d'un `.py` ou d'un `.sh` ne suffit
pas : seule cette liste explicite fait foi. Les helpers internes, scripts de
migration, outils de build privés restent internes.

Format, une commande par ligne (colonnes séparées par des espaces) :

```text
# <nom-public>   <mode>   <script-relatif-au-projet>
morf             direct   morf.py
screenctl        direct   screenctl.py
build-dashboard  project  build.py
```

Le **projet est implicite** : c'est le dossier qui contient le manifeste. On ne
répète donc pas son nom, et le mécanisme fonctionne à l'identique que le dossier
s'appelle `morfDashboard` ou `morfDashboard_travail`.

Exemple réel (`morfDashboard/cli.manifest`) :

```text
screenctl   direct   screenctl.py
```

---

## Choisir le mode : `direct` ou `project`

La question n'est pas « le script utilise-t-il des ressources de son projet ? »
Un script peut dépendre de `assets/` de son projet et rester `direct`, s'il
localise ces ressources à partir de **son propre fichier** (en Python, via
`__file__`). La vraie question est :

> **Le comportement du script dépend-il du répertoire courant (`cwd`) ?**

- **Non** → mode `direct`. Exposé par lien symbolique. Une modification du script
  dans son dépôt est immédiatement effective (le lien ne duplique rien).
- **Oui** (chemins relatifs `./config.json`, `./templates/`, environnement de
  compilation...) → mode `project`. Un lanceur entre dans le projet avant
  d'exécuter.

### Vérifier une commande `direct`

Avant de déclarer un script `direct`, testez-le depuis plusieurs emplacements :

```bash
cd ~            ; screenctl status
cd /tmp         ; screenctl status
cd ~/01-Travail ; screenctl status
```

Le comportement doit être **identique**. Une différence révèle une dépendance
cachée au répertoire courant : le script doit alors passer en `project`.

### Le mode est déclaré, jamais deviné

Si un script auparavant indépendant du `cwd` en devient dépendant, sa ligne doit
explicitement passer de `direct` à `project`. Cette décision appartient au projet
et à son développeur ; elle ne doit jamais changer silencieusement au gré d'une
évolution interne.

---

## Comment fonctionne un lanceur `project`

Pour une commande `project`, le champ « projet » (déduit du dossier du manifeste)
sert à construire le répertoire de travail `racine/projet/`. Le lanceur généré
ressemble à :

```bash
#!/usr/bin/env bash
# morfsystem-cli-wrapper/1
# Genere par morfTools activate-cli.sh - NE PAS EDITER.
# Workspace : /home/user/01-Travail
# Project   : morfDashboard
# Source    : build.py
# Command   : build-dashboard
cd "/home/user/01-Travail/morfDashboard" || exit 1
exec "./build.py" "$@"
```

Il ne contient **aucune logique métier** : il rejoint le projet, puis exécute le
script en transmettant tous les arguments (`"$@"`) et en conservant le code de
retour (`exec`). Ainsi `build-dashboard --release` équivaut exactement à :

```bash
cd /home/user/01-Travail/morfDashboard
./build.py --release
```

Une commande `project` ne cherche **jamais** un dépôt du même nom ailleurs sur la
machine. `project=morfDashboard` avec la racine `01-Travail` signifie
exclusivement `/home/user/01-Travail/morfDashboard`. Si ce projet ou son script
n'existe pas dans l'espace actif, la commande n'est simplement pas créée. Une
absence reste une absence.

---

## Sécurité : ne jamais écraser un fichier inconnu

Avant de créer une commande, `activate-cli.sh` regarde ce qui existe déjà dans
`~/.local/bin` :

- si l'entrée est **gérée par morfSystem** (un de nos liens vers le même
  projet/script, un de nos lanceurs reconnaissables à leur marqueur, ou une
  entrée du registre), elle peut être remplacée : c'est l'activation volontaire ;
- si l'entrée est **inconnue** (un fichier que nous n'avons pas créé), elle
  n'est **jamais** remplacée. Le script le signale et passe à la suivante :

```text
!!  screenctl existe deja dans ~/.local/bin et n'est pas gere par morfSystem.
    aucune modification pour cette commande (securite).
```

La sécurité prime sur la commodité.

---

## Utilisation

```bash
./activate-cli.sh              # active l'espace de cette copie de morfTools
./activate-cli.sh --dry-run    # montre ce qui changerait, sans rien modifier
./activate-cli.sh --status     # espace actif + commandes actuellement gerees
./activate-cli.sh --deactivate # retire toutes les commandes gerees
./activate-cli.sh --help
```

Variable d'environnement utile (tests) : `MORF_CLI_BIN` remplace `~/.local/bin`.

Un registre `~/.local/bin/.morfsystem-cli` mémorise les commandes que le script a
créées : il lui permet, à l'activation suivante, de réorienter ou de retirer
proprement ces commandes sans jamais toucher à un fichier étranger.

### Le PATH

`~/.local/bin` doit être dans votre `PATH`. Si le script vous avertit qu'il ne
l'est pas, ajoutez à votre `~/.bashrc` :

```bash
export PATH="$HOME/.local/bin:$PATH"
```

---

## Ce que `activate-cli.sh` ne fait jamais

L'activation des CLI est **totalement indépendante** du déploiement du parc. Le
script :

- n'installe, ne désinstalle et ne met à jour **aucun service** ;
- ne met à jour **aucun dépôt** et ne compile **aucun composant** ;
- ne modifie **aucune configuration métier** ;
- ne touche **rien** sous `/opt`, `/etc` ou `/var/lib`.

Il ne modifie que `~/.local/bin`, l'environnement de l'utilisateur.

Réciproquement, `morf install` / `morf update` ne changent **jamais** l'espace de
travail actif des CLI. Une fois `01-Travail` activé, il le reste jusqu'à ce que
vous relanciez volontairement `activate-cli.sh` depuis un autre espace.

---

## Le modèle en une image

```text
                       ~/.local/bin
                            │
                     espace CLI actif
                            │
                            ▼
                     WORKSPACE_ROOT  (parent de cette copie de morfTools)
                            │
          ┌─────────────────┼──────────────────┐
          │                 │                  │
      morfTools       morfDashboard      autres projets
          │                 │
       morf.py         screenctl.py
          │                 │
       direct             direct
          │                 │
          └──── liens symboliques ──────►  ~/.local/bin


Commande dépendante de son projet (mode project) :

  ~/.local/bin/<commande>
        │
        ▼
   lanceur généré
        ├── cd "$WORKSPACE_ROOT/$PROJECT"
        └── exec ./<script> "$@"
```

---

## Ajouter une commande à un projet (mémo)

1. Le script doit exister à la racine du projet (ou dans un sous-dossier).
2. Décider du mode : tester le script depuis `~` et `/tmp` (voir plus haut).
3. Ajouter une ligne à `<projet>/cli.manifest` :
   `nom-public   direct|project   chemin/vers/le/script`.
4. Relancer `./activate-cli.sh` depuis `morfTools` de l'espace concerné.
5. Vérifier avec `./activate-cli.sh --status`.
