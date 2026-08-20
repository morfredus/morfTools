# Workflow de packaging multi-plateforme

Ce document décrit le chemin complet entre une version source et ses paquets.
Suivre volontairement deux temps : décider et publier la version source, puis
laisser chaque machine produire ce qu'elle sait réellement construire. Le dépôt
de distribution réunit les plateformes sans copier de binaires dans Git.

## Les deux releases à ne pas confondre

Chaque version porte deux releases distinctes.

| Rôle | Dépôt | Tag | Titre |
| --- | --- | --- | --- |
| Autorité de la version source | dépôt du projet | `vX.Y.Z` | `nomProjet - vX.Y.Z` |
| Distribution des installables | morfPackages | `nomprojet-vX.Y.Z` | `nomProjet - vX.Y.Z` |

La première est créée dans le même workspace que les sources : la sandbox crée
des releases privées sur ses remotes privés, la production crée les releases
canoniques après une mise à jour manuelle. Après publication, elle reçoit les
installables validés, leur manifeste et leurs sommes de contrôle. La seconde
reste l'index de distribution qui réunit exactement les mêmes assets.

Avant toute création ou mise à jour de cette seconde release, morfPackages
résout le tag distant `vX.Y.Z` du dépôt source d'autorité du workspace. Le SHA
complet désigné par ce tag doit correspondre au commit du sidecar et à tous les
assets déjà inscrits dans le manifeste. Un écart bloque l'opération avant tout
upload : une même release de distribution ne peut donc réunir que des paquets
issus du même commit source.

## Notes de release par projet

Sans option supplémentaire, la première release de distribution contient un
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

## Parcours rapide - commandes à copier dans l'ordre

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

### 4. Publication finale depuis le `dist` réuni

Cette dernière étape est facultative après des passages `package-all --sync`,
car ceux-ci publient déjà chaque asset. Elle est utile pour republier en une
seule passe un dossier `dist` réuni ou pour vérifier que toutes les releases
projet reçoivent bien leurs assets et leur description automatique, sans aucun
rebuild.

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
`package-all.py --sync` attache automatiquement chaque binaire validé à la
release de distribution correspondante dans `morfPackages`, puis à la release
source du projet. Après les passages Windows et Linux, le contenu de `dist` est
donc déjà publié dans la release que les utilisateurs voient en premier.

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

Pour donner un texte propre à une release de distribution avant sa première
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

Pour modifier le texte d'une release de distribution qui existe déjà, sans
toucher à ses binaires, exécuter cette commande depuis `morfPackages`. Le tag
de distribution est en minuscules et ne doit pas être confondu avec le tag
source `vX.Y.Z` :

```powershell
$project = "morfCollector"
$version = "0.7.0"
$notes = @"
## morfCollector 0.7.0

Texte personnalisé de la release.
"@

gh release edit "morfcollector-v$version" `
  --title "$project - v$version" --notes $notes
```

```bash
project="morfCollector"
version="0.7.0"
notes=$'## morfCollector 0.7.0\n\nTexte personnalisé de la release.'

gh release edit "morfcollector-v${version}" \
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

Le premier passage crée une release de distribution par projet. Les suivants
téléchargent ses assets grâce à `--sync`, puis ajoutent uniquement les formats
manquants. Relancer sans `--force` après un échec de publication : un
livrable déjà construit avec son sidecar est repris et publié sans rebuild.

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
