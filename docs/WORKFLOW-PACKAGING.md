# Workflow de packaging multi-plateforme

Ce document décrit le chemin complet entre une version source et ses paquets.
Suivre volontairement deux temps : décider et publier la version source, puis
laisser chaque machine produire ce qu'elle sait réellement construire. Le dépôt
de distribution réunit les plateformes sans copier de binaires dans Git.

> Point de contrôle indispensable : `create-source-releases.py` crée le tag et
> la page GitHub, **sans aucun binaire**. `publish-dist.py` ne construit rien :
> il ne peut publier que les couples déjà présents dans `dist` - un livrable et
> son fichier voisin `.metadata.json`. Après une release source, lancer donc
> obligatoirement `package-all.py` sur au moins une plateforme avant toute
> publication finale. Un résultat `[SKIP] ... no matching sidecar` signifie
> exactement qu'aucun paquet correspondant n'a été reconstruit dans ce `dist`.

| Étape | Produit | Condition pour passer à la suivante |
| --- | --- | --- |
| Release source | tag et page GitHub sans asset | les dépôts sont propres et poussés |
| `package-all` Windows/Linux | binaire + `.metadata.json` dans `dist` | version et commit identiques au tag |
| `publish-dist` | assets attachés à la release projet | au moins un sidecar est présent dans `dist` |

## Une release utilisateur, deux rôles techniques

Chaque version possède une seule release destinée aux utilisateurs : celle du
dépôt du projet. Elle est à la fois l'autorité de la version et le point de
téléchargement des installables.

| Rôle | Dépôt | Tag | Titre |
| --- | --- | --- | --- |
| Release utilisateur, source et installables | dépôt du projet | `vX.Y.Z` | `nomProjet - vX.Y.Z` |
| Index technique de provenance | morfPackages | `nomprojet-vX.Y.Z` | `nomProjet - vX.Y.Z` |

La première est créée dans le même workspace que les sources : la sandbox crée
des releases privées sur ses remotes privés, la production crée les releases
canoniques après une mise à jour manuelle. Après publication, elle reçoit les
installables validés, leur manifeste et leurs sommes de contrôle. L'index de
morfPackages conserve les mêmes assets pour la synchronisation entre plateformes
et la vérification stricte de leur provenance ; il ne constitue pas une seconde
release à présenter aux utilisateurs.

Avant toute publication dans l'index technique, morfPackages
résout le tag distant `vX.Y.Z` du dépôt source d'autorité du workspace. Le SHA
complet désigné par ce tag doit correspondre au commit du sidecar et à tous les
assets déjà inscrits dans le manifeste. Un écart bloque l'opération avant tout
upload : un même index de distribution ne peut donc réunir que des paquets
issus du même commit source.

## Notes de release par projet

Sans option supplémentaire, la release utilisateur du projet contient un
résumé de trois éléments au plus, extrait de la section de `CHANGELOG.md` dont
le numéro correspond à `VERSION`. Le changelog complet reste dans le dépôt : la
release GitHub ne le recopie pas.

Pour ajouter une formulation personnelle à un projet, créer à sa racine un
fichier `RELEASE-NOTES.md`. Les variables `{project}` et `{version}` y sont
disponibles. Le marqueur `{{changelog_summary}}` est remplacé par le résumé à
l'emplacement choisi. S'il est absent, le résumé est ajouté à la fin.

```markdown
## {project} {version}

Cette version consolide le packaging avant les prochains déploiements.

{{changelog_summary}}
```

`--release-notes` reste disponible pour une campagne ponctuelle : il remplace
alors ces notes pour tous les projets concernés. Il accepte aussi `{project}`
et `{version}`.

## Parc entier - tout construire avant une publication unique

Choisir ce parcours pour vérifier tous les paquets avant d'attacher le premier
asset à GitHub. `--no-publish` produit le binaire et son sidecar dans `dist`,
sans téléverser quoi que ce soit. Il ne faut pas ajouter `--sync` à cette
commande : aucun asset n'est encore publié à synchroniser.

Préparer les versions, changelogs et éventuels `RELEASE-NOTES.md`, puis les
committer et les pousser avant de commencer. Se placer dans le dossier
`morfTools` du workspace courant. Les trois blocs ci-dessous s'exécutent sur
leurs plateformes respectives, pas sur une même machine.

### 1. Windows - créer les releases source et produire les ZIP

Exécuter la création des releases source une seule fois, ici ou sur l'une des
machines Linux. `--all` inclut aussi morfTools, même s'il ne produit pas lui-même
de paquet.

```powershell
python .\create-source-releases.py --all `
  --notes "Source release for {project} {version}."

python .\package-all.py --no-publish --out ..\dist
```

### 2. Linux AMD64 - produire les paquets AMD64

Si l'étape Windows n'est pas exécutée, créer d'abord les releases source ici,
une seule fois. Sinon, supprimer les deux premières lignes du bloc.

```bash
python3 ./create-source-releases.py --all \
  --notes "Source release for {project} {version}."
```

```bash
python3 ./package-all.py --no-publish --out ../dist
```

### 3. Linux ARM64 - produire les paquets ARM64

Si cette machine est la première et la seule à exécuter le workflow, conserver
la création des releases source. Sinon, supprimer les deux premières lignes du
bloc.

```bash
python3 ./create-source-releases.py --all \
  --notes "Source release for {project} {version}."
```

```bash
python3 ./package-all.py --no-publish --out ../dist
```

### 4. Réunir les livrables et publier une seule fois

Choisir un `dist` final, puis y réunir les ZIP Windows et les `.deb` Linux. Pour
chaque livrable, copier aussi son voisin portant le suffixe `.metadata.json`.
Ne pas modifier ni régénérer ces sidecars. Les dossiers `dist` ne sont pas
recopiés automatiquement entre workspaces.

Depuis le `morfTools` qui possède ce `dist` final, publier tous les assets :

```powershell
python .\publish-dist.py --all --out ..\dist
```

```bash
python3 ./publish-dist.py --all --out ../dist
```

Cette unique commande crée ou complète la release de chaque projet avec son
titre, ses notes automatisées et tous les formats présents dans le `dist` final.

## Parcours rapide - publication au fil des builds

Préparer les versions, changelogs et éventuels `RELEASE-NOTES.md`, puis les
committer et les pousser avant de commencer. Se placer ensuite dans le dossier
`morfTools` du workspace courant. Les trois blocs ci-dessous ne s'exécutent pas
sur la même machine : copier chaque bloc sur la plateforme indiquée.

### 1. Windows - créer les releases source et produire les ZIP

Exécuter cette étape de création des releases source une seule fois, ici ou sur
l'une des machines Linux. Ne pas la répéter sur les deux Linux.
`--all` inclut aussi morfTools, même s'il ne produit pas lui-même de paquet.

```powershell
python .\create-source-releases.py --all `
  --notes "Source release for {project} {version}."

python .\package-all.py --sync --out ..\dist
```

Sous Windows, cette commande construit les cibles `windows-x86_64-zip` (services
morfdeploy et applications : PhotoHub, ComponentHub, SiteWatch), récupère les
`.deb` déjà indexés, puis publie **tous** les assets de la version (Linux et
Windows) sur la release GitHub.

### 2. Linux AMD64 - produire les paquets AMD64

Si l'étape Windows n'est pas exécutée, créer d'abord les releases source ici,
une seule fois :

```bash
python3 ./create-source-releases.py --all \
  --notes "Source release for {project} {version}."
```

```bash
python3 ./package-all.py --sync --out ../dist
```

### 3. Linux ARM64 - produire les paquets ARM64

Si cette machine est la première et la seule à exécuter le workflow, commencer
par créer les releases source, une seule fois :

```bash
python3 ./create-source-releases.py --all \
  --notes "Source release for {project} {version}."
```

```bash
python3 ./package-all.py --sync --out ../dist
```

### 4. Publication finale depuis le `dist` réuni - uniquement après les builds

Cette dernière étape est facultative après des passages `package-all --sync`,
car ceux-ci publient déjà chaque asset. Elle sert à reprendre un `dist` réuni,
mais ne remplace jamais les trois builds précédents. Avant de la lancer,
contrôler que `dist` contient au moins un couple `nom-du-paquet` et
`nom-du-paquet.metadata.json` pour la version concernée.

Sous Windows :

```powershell
python .\publish-dist.py --all --out ..\dist
```

Sous Linux AMD64 ou ARM64 :

```bash
python3 ./publish-dist.py --all --out ../dist
```

Ne pas ajouter `--notes` à cette commande pour conserver la description
automatique par projet : `RELEASE-NOTES.md` est utilisé en priorité, puis le
résumé de la version courante dans `CHANGELOG.md`.

## Publier les binaires déjà réunis dans `dist`

Il n'y a normalement pas de seconde commande de publication à lancer :
`package-all.py --sync` indexe automatiquement chaque binaire validé dans
`morfPackages`, puis l'attache à la release utilisateur du projet. Après les
passages Windows et Linux, le contenu de `dist` est donc déjà publié dans la
release que les utilisateurs voient en premier.

Ne pas exécuter cette commande juste après `create-source-releases.py` : le
résultat sera seulement une série de `[SKIP]`, puisque la page GitHub ne contient
encore aucun fichier et que `dist` ne contient pas les sidecars attendus.

Pour publier en une seule passe les sidecars et binaires déjà réunis dans
`dist`, sans reconstruire, exécuter depuis `morfTools` :

```powershell
python .\publish-dist.py --all --out ..\dist
```

```bash
python3 ./publish-dist.py --all --out ../dist
```

Limiter à certains projets si nécessaire :

```powershell
python .\publish-dist.py --only morfCollector morfNotify --out ..\dist
```

La commande valide chaque sidecar, vérifie le tag source et refuse tout conflit
de commit ou de somme de contrôle avant l'upload. Vérifier par exemple la
release publique du projet depuis le dossier de celui-ci :

```bash
gh release view v0.7.0
```

Pour donner un texte propre à la release utilisateur avant sa première
publication, créer `RELEASE-NOTES.md` à la racine du projet, le committer et le
pousser avant de créer la release source. La note peut garder le résumé concis
du changelog :

```markdown
## {project} {version}

Décrire ici les points utiles à connaître pour cette version.

{{changelog_summary}}
```

Relancer ensuite le packaging habituel ou `publish-dist.py`. Le premier binaire
publié crée la release avec ce titre et ce texte ; les passages suivants ajoutent
les formats Windows ou Linux manquants. La note de la release source est aussi
mise à jour, afin que la page ouverte par l'utilisateur reste complète.

Pour appliquer exceptionnellement le même texte à tous les projets d'une
campagne, ajouter `--release-notes` à `package-all.py` :

```powershell
python .\package-all.py --sync --out ..\dist `
  --release-notes "Packages for {project} {version}."
```

Pour modifier le texte d'une release utilisateur qui existe déjà, sans toucher
à ses binaires, exécuter cette commande depuis le dépôt du projet. Utiliser le
tag source `vX.Y.Z` :

```powershell
$project = "morfCollector"
$version = "0.7.0"
$notes = @"
## morfCollector 0.7.0

Texte personnalisé de la release.
"@

gh release edit "v$version" `
  --title "$project - v$version" --notes $notes
```

```bash
project="morfCollector"
version="0.7.0"
notes=$'## morfCollector 0.7.0\n\nTexte personnalisé de la release.'

gh release edit "v${version}" \
  --title "${project} - v${version}" --notes "$notes"
```

## Prendre les paquets d'un run GitHub Actions

Un projet dont le dépôt a un workflow de paquets (ComponentHub : `packages.yml`) peut le
déclarer, **cible par cible**, dans `morfproject.json`. `package-all.py` récupère alors le
paquet du run GitHub Actions au lieu de le compiler. Les projets sans bloc `ci` ne changent
pas : le workflow n'est jamais exigé ni lancé par le script.

```json
"package": { "format": "deb", "architecture": "arm64",
             "ci": { "workflow": "packages.yml",
                     "artifact": "componenthub-deb-arm64",
                     "file": "componenthub_{version}_arm64.deb" } }
```

Pour chaque cible qui porte un bloc `ci`, dans l'ordre :

1. un paquet valide déjà présent dans `dist` (avec sa provenance) est conservé ;
2. sinon, un run **réussi** du workflow est cherché pour le commit exact extrait (`HEAD`).
   Un run d'un autre commit ou en échec n'est jamais utilisé. L'artefact est téléchargé,
   renommé au nom public et reçoit son `.metadata.json`, qui consigne le run (`ci.run_id`) ;
3. sinon, la cible est compilée en local comme avant. Une cible non native pour la machine
   (Windows depuis WSL, arm64 depuis un x86_64) est alors ignorée : seul un run CI peut la fournir.

Options : `--no-ci` compile tout en local ; `--wait-ci` attend le run du commit (même s'il n'est pas
encore apparu, 90 s au plus après la création du tag) **pour les cibles que la machine ne sait pas
compiler** ; une cible native se compile plus vite qu'elle n'attend le run, elle ne prend donc le
paquet CI que si le run est déjà terminé. Les chaînes de release passent `--wait-ci`, et `morf dev build --skip-ci-packaged` à l'étape 3/5 :
un projet dont tous les livrables natifs viennent de la CI n'est pas compilé en préparation (le
packaging le compile de lui-même si aucun run n'existe). Pour éviter
toute compilation locale d'une cible native, laisser `packages.yml` finir sur le commit (il tourne à chaque
push sur `main`, ou en lancement manuel) avant la chaîne : un run réussi du commit est utilisé
tout de suite, même si un autre run du même commit est encore en cours. Les artefacts GitHub expirent (14 jours pour ComponentHub) : passé
ce délai, la compilation locale reprend. Le nom d'artefact et le motif `file` doivent
correspondre à ce que le workflow publie (`{version}` est remplacé par le contenu de `VERSION`).

## Workflows GitHub Actions des projets (générés)

Les workflows de tous les projets sont **générés** par `scripts/gen-ci-workflows.py` : on corrige
le générateur, jamais un `ci.yml` à la main. Pour chaque projet qui déclare des cibles de paquets
dans `morfproject.json`, il écrit `.github/workflows/ci.yml` (compile et lance `ctest` à chaque
pull request : Ubuntu 24.04 = Qt 6.4, Linux arm64, Windows MSYS2 UCRT64), `.github/workflows/packages.yml`
(les paquets, à chaque push sur `main` ou en lancement manuel), `scripts/ci/build-deb-container.sh`
(le `.deb` construit dans un conteneur Debian Trixie, comme celui du Pi) et le bloc `package.ci`
de chaque cible. Les dépendances de compilation viennent du `CMakeLists.txt` du projet
(`find_package`), sans liste à tenir à la main.

```powershell
python scripts\gen-ci-workflows.py                       # plan, rien n'est écrit
python scripts\gen-ci-workflows.py --write --only morfMonitor
python scripts\gen-ci-workflows.py --write --bump        # + version mineure, badges, CHANGELOG, README
```

Trois familles : application CMake (`package-deb.sh`, `package-win.ps1`), service morfdeploy
(`service.py package --target ...`) et firmware PlatformIO. Un firmware qui compile des valeurs
privées (`include/secrets.h` : Wi-Fi, clé d'API, jeton) n'a que le `ci.yml` : un binaire fabriqué
avec le `secrets_example.h` serait inutilisable, il reste construit en local. Les projets sans
paquet (bibliothèque, outil, documentation, gabarit) et `morfDashboard` (archive source) n'ont pas
de workflow.

Les dépôts **sandbox** ont GitHub Actions désactivé : les workflows y sont versionnés mais ne
tournent qu'en production (réactivation : `gh api -X PUT repos/<dépôt>/actions/permissions -F enabled=true`).

## Commandes ciblées et contrôles

Pour limiter le parcours à quelques projets, remplacer `--all` par `--only` et
indiquer leurs noms. Conserver les chemins adaptés à la plateforme : `..\dist`
sous PowerShell, `../dist` sous Linux.

```powershell
python .\package-all.py --no-publish --out ..\dist `
  --only morfCollector morfNotify

python .\publish-dist.py --only morfCollector morfNotify --out ..\dist
```

```bash
python3 ./package-all.py --no-publish --out ../dist \
  --only morfCollector morfNotify

python3 ./publish-dist.py --only morfCollector morfNotify --out ../dist
```

Avant la publication, contrôler le plan sans téléverser :

```powershell
python .\publish-dist.py --all --out ..\dist --dry-run
```

```bash
python3 ./publish-dist.py --all --out ../dist --dry-run
```

Après publication, vérifier une release projet en remplaçant la version :

```bash
gh release view v0.7.0
```
