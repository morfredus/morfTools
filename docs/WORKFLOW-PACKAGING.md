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

## 1. Préparer une version source

Choisir les projets concernés. Pour chacun, la commande utilise la version
déclarée dans son propre fichier `VERSION`. Vérifier que les sources sont
propres et pousser le dépôt de travail. La
propagation vers la production reste une action délibérée, hors de
`package-all`.

Une fois les dépôts source du workspace courant à jour, créer leurs releases
d'autorité en une passe depuis le dossier `morfTools` :

```bash
python3 ./create-source-releases.py --all \
  --notes "Source release for {project} {version}."
```

Sous PowerShell, la même commande s'écrit :

```powershell
python .\create-source-releases.py --all `
  --notes "Source release for {project} {version}."
```

Pour ne créer que certains projets, remplacer `--all` :

```bash
python3 ./create-source-releases.py --only morfCollector morfNotify morfMonitor \
  --notes "Source release for {project} {version}."
```

La commande vérifie et avance rapidement chaque clone avant de créer, si besoin,
le tag `vX.Y.Z`, le titre `nomProjet - vX.Y.Z` et le texte indiqué. Elle lit le
remote de chaque clone : elle teste donc la chaîne complète sur les remotes
privés de la sandbox, sans effectuer de synchronisation vers la production.

Les commandes `gh` directes ci-dessous sont réservées à la création
exceptionnelle d'une release sur le dépôt public canonique, après propagation
volontaire et vérifiée des sources vers la production. Elles ne remplacent pas
`create-source-releases.py`, qui déduit les remotes du workspace courant et
permet donc de valider la chaîne sur les dépôts privés :

```text
projet=morfCollector
version=0.7.0
notes="Packaging release: provenance-checked Windows and Linux artifacts."
```

Sous PowerShell :

```powershell
$project = "morfCollector"
$version = "0.7.0"
$notes = "Packaging release: provenance-checked Windows and Linux artifacts."

gh release create "v$version" --repo "morfredus/$project" `
  --title "$project - v$version" --notes $notes
```

Sous Linux :

```bash
project="morfCollector"
version="0.7.0"
notes="Packaging release: provenance-checked Windows and Linux artifacts."

gh release create "v${version}" --repo "morfredus/${project}" \
  --title "${project} - v${version}" --notes "$notes"
```

Si la release existe déjà, la vérifier au lieu de la recréer :

```bash
gh release view "v${version}" --repo "morfredus/${project}"
```

`morfPackages` refusera volontairement un artefact si cette release source
n'existe pas.

## Parc complet : les commandes en une passe

Il n'y a pas de build global distinct à lancer : `package-all` construit toutes
les cibles réellement natives de la machine qui l'exécute. Créer d'abord les
releases source une seule fois depuis l'une des machines, puis lancer le
packaging complet sur Windows et sur chaque Linux utile. Omettre
volontairement `--release-notes` ci-dessous afin que chaque projet utilise son
propre résumé de changelog ou son éventuel `RELEASE-NOTES.md`.

Pour les projets portant un script de packaging propre, la commande lance aussi
leur configuration et leur build CMake avec le preset déclaré avant le script.

### 1. Créer les releases source une seule fois

Exécuter cette étape depuis **une seule** des machines du workspace courant,
Windows ou Linux. Le résultat est identique : les remotes privés de
la sandbox ou les remotes canoniques de production sont déduits automatiquement.

Sous Windows :

```powershell
python .\create-source-releases.py --all `
  --notes "Source release for {project} {version}."
```

Sous Linux :

```bash
python3 ./create-source-releases.py --all \
  --notes "Source release for {project} {version}."
```

### 2. Construire et publier depuis chaque plateforme

Sous Windows, depuis le dossier `morfTools` du workspace courant :

```powershell
python .\package-all.py --sync --out ..\dist
```

Sous Linux AMD64, depuis le dossier `morfTools` du workspace courant :

```bash
python3 ./package-all.py --sync --out ../dist
```

Sous Linux ARM64, la même commande produit les `.deb` ARM64 :

```bash
python3 ./package-all.py --sync --out ../dist
```

Le premier passage crée ou complète la release utilisateur du projet. Les
suivants téléchargent les assets indexés grâce à `--sync`, puis ajoutent
uniquement les formats manquants. Relancer sans `--force` après un échec de
publication : un livrable déjà construit avec son sidecar est repris et publié
sans rebuild.

## 2. Construire et publier depuis Windows

Se placer dans le dossier `morfTools` du workspace de travail. Avant de lancer
la commande, les projets ciblés doivent être propres et à jour.

```powershell
cd C:\Users\frede\Codage\01-Travail\morfTools

python .\package-all.py --sync --out ..\dist `
  --only morfCollector
```

Pour plusieurs projets, ajouter simplement leurs noms après `--only` :

```powershell
python .\package-all.py --sync --out ..\dist `
  --only morfCollector morfNotify morfMonitor
```

La commande sélectionne les cibles Windows natives, construit les ZIP, écrit
leur sidecar `.metadata.json`, puis les publie automatiquement dans
morfPackages. Le préflight de morfPackages fait `fetch --prune`, vérifie que
l'arbre est propre et non divergent, puis applique `pull --ff-only` si besoin.

## 3. Construire et publier depuis Linux AMD64

Effectuer cette opération sur la machine Linux AMD64. Le dossier de sortie
s'écrit avec des slashs Linux : `../dist`, jamais une barre oblique inversée.

```bash
cd ~/Codage/01-Travail/morfTools

python3 ./package-all.py --sync --out ../dist \
  --only morfCollector
```

Pour plusieurs projets :

```bash
python3 ./package-all.py --sync --out ../dist \
  --only morfCollector morfNotify morfMonitor
```

Cette machine produit les `.deb` AMD64. Un firmware est produit si PlatformIO
est disponible.

## 4. Construire et publier depuis Linux ARM64

Utiliser la même commande sur la machine ARM64. Elle sélectionne alors les
cibles ARM64 et produit les `.deb` ARM64 :

```bash
cd ~/Codage/01-Travail/morfTools

python3 ./package-all.py --sync --out ../dist \
  --only morfCollector
```

Pour tout le parc, omettre `--only` :

```bash
python3 ./package-all.py --sync --out ../dist
```

## 5. Réunir les plateformes

Il n'est pas nécessaire de transporter un dossier `dist` entre Windows et Linux.
`--sync` télécharge au début les assets déjà présents dans la release de ce
projet et de cette version. La machine suivante ajoute seulement son livrable
manquant. Chaque release morfPackages finit donc par contenir toutes les
plateformes disponibles.

Un dossier `dist` commun peut néanmoins être conservé pour un contrôle visuel.
Il est jetable : Git l'ignore et les assets GitHub restent la distribution de
référence.

## 6. Publier manuellement un livrable déjà créé

Normalement, `package-all` publie lui-même. Cette commande sert seulement à
reprendre un livrable valide déjà présent dans `dist`, sans reconstruire :

Sous PowerShell :

```powershell
cd C:\Users\frede\Codage\01-Travail\morfPackages

python .\scripts\release.py publish --project morfCollector --version 0.7.0 `
  --metadata ..\dist\morfcollector-0.7.0-windows-x86_64.zip.metadata.json `
  --notes "Windows and Linux installables for morfCollector 0.7.0."
```

Sous Linux :

```bash
cd ~/Codage/01-Travail/morfPackages

python3 ./scripts/release.py publish --project morfCollector --version 0.7.0 \
  --metadata ../dist/morfcollector-0.7.0-linux-arm64.deb.metadata.json \
  --notes "Windows and Linux installables for morfCollector 0.7.0."
```

La note crée la description de distribution si nécessaire et met aussi à jour la
description de la release source. Les passages suivants ajoutent les assets
manquants. Un même nom avec un commit ou un SHA-256 différent est un conflit et
s'arrête sans écraser quoi que ce soit.

## Contrôles utiles

Avant une production, inspecter le plan sans rien construire ni publier :

```bash
python3 ./package-all.py --dry-run --sync --out ../dist --only morfCollector
```

Pour visualiser toutes les releases de distribution du workspace courant :

```bash
cd ../morfPackages
gh release list
```

Après une production :

```bash
gh release view morfcollector-v0.7.0 --repo morfredus/morfPackages
```

Le tag de distribution reste volontairement différent du tag source : il permet
à une seule release morfPackages de rassembler les plateformes d'un projet sans
mélanger les versions de projets différents.
