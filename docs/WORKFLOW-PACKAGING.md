# Workflow de packaging multi-plateforme

Ce document décrit le chemin complet entre une version source et ses paquets.
Je le garde volontairement en deux temps : je décide et publie la version
source, puis chaque machine produit ce qu'elle sait réellement construire. Le
dépôt de distribution réunit les plateformes sans que je copie des binaires
dans Git.

## Les deux releases à ne pas confondre

Chaque version porte deux releases distinctes.

| Rôle | Dépôt | Tag | Titre |
| --- | --- | --- | --- |
| Autorité de la version source | dépôt du projet | `vX.Y.Z` | `nomProjet - vX.Y.Z` |
| Distribution des installables | morfPackages | `nomprojet-vX.Y.Z` | `nomProjet - vX.Y.Z` |

La première est créée dans le même workspace que les sources : la sandbox crée
des releases privées sur ses remotes privés, la production crée les releases
canoniques après ma mise à jour manuelle. Elle ne reçoit pas les binaires. La
seconde est créée automatiquement au premier packaging réussi et reçoit les
`.deb`, `.zip`, firmwares, `manifest.json` et `checksums.sha256`.

## 1. Préparer une version source

Je choisis les projets et une même version pour chaque projet concerné. Je
vérifie que les sources sont propres et je pousse mon dépôt de travail. La
propagation vers la production reste une action délibérée, hors de
`package-all`.

Une fois les dépôts source du workspace courant à jour, je crée leurs releases
d'autorité en une passe depuis son dossier `morfTools` :

```bash
python3 ./create-source-releases.py --all \
  --notes "Source release for {project} {version}."
```

Sous PowerShell, la même commande s'écrit :

```powershell
python .\create-source-releases.py --all `
  --notes "Source release for {project} {version}."
```

Pour ne créer que certains projets, je remplace `--all` :

```bash
python3 ./create-source-releases.py --only morfCollector morfNotify morfMonitor \
  --notes "Source release for {project} {version}."
```

La commande vérifie et avance rapidement chaque clone avant de créer, si besoin,
le tag `vX.Y.Z`, le titre `nomProjet - vX.Y.Z` et le texte indiqué. Elle lit le
remote de chaque clone : elle teste donc la chaîne complète sur les remotes
privés de la sandbox, sans effectuer de synchronisation vers la production.

Pour une release isolée, les commandes `gh` directes restent possibles :

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

Si la release existe déjà, je vérifie au lieu de la recréer :

```bash
gh release view "v${version}" --repo "morfredus/${project}"
```

`morfPackages` refusera volontairement un artefact si cette release source
n'existe pas.

## 2. Construire et publier depuis Windows

Je me place dans le dossier `morfTools` de mon workspace de travail. Avant de
lancer la commande, les projets ciblés doivent être propres et à jour.

```powershell
cd C:\Users\frede\Codage\01-Travail\morfTools

python .\package-all.py --sync --out ..\dist `
  --release-notes "Windows and Linux installables for morfCollector 0.7.0." `
  --only morfCollector
```

Pour plusieurs projets, j'ajoute simplement leurs noms après `--only` :

```powershell
python .\package-all.py --sync --out ..\dist `
  --release-notes "Windows installables for the selected projects." `
  --only morfCollector morfNotify morfMonitor
```

La commande sélectionne les cibles Windows natives, construit les ZIP, écrit
leur sidecar `.metadata.json`, puis les publie automatiquement dans
morfPackages. Le préflight de morfPackages fait `fetch --prune`, vérifie que
l'arbre est propre et non divergent, puis applique `pull --ff-only` si besoin.

## 3. Construire et publier depuis Linux

Je fais la même chose sur la machine Linux AMD64 ou ARM64. Le dossier de sortie
s'écrit avec des slashs Linux : `../dist`, jamais une barre oblique inversée.

```bash
cd ~/Codage/01-Travail/morfTools

python3 ./package-all.py --sync --out ../dist \
  --release-notes "Windows and Linux installables for morfCollector 0.7.0." \
  --only morfCollector
```

Pour plusieurs projets :

```bash
python3 ./package-all.py --sync --out ../dist \
  --release-notes "Linux installables for the selected projects." \
  --only morfCollector morfNotify morfMonitor
```

Une machine ARM64 produit les `.deb` ARM64, une machine AMD64 les `.deb` AMD64.
Un firmware est produit sur toute machine qui possède PlatformIO.

## 4. Réunir les plateformes

Je n'ai pas besoin de transporter un dossier `dist` entre Windows et Linux.
`--sync` télécharge au début les assets déjà présents dans la release de ce
projet et de cette version. La machine suivante ajoute seulement son livrable
manquant. Chaque release morfPackages finit donc par contenir toutes les
plateformes disponibles.

Je peux néanmoins garder un dossier `dist` commun pour mon contrôle visuel. Il
est jetable : Git l'ignore et les assets GitHub restent la distribution de
référence.

## 5. Publier manuellement un livrable déjà créé

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

La note n'est utilisée que si la release de distribution est créée à cette
occasion. Les passages suivants ajoutent les assets manquants. Un même nom avec
un commit ou un SHA-256 différent est un conflit et s'arrête sans écraser quoi
que ce soit.

## Contrôles utiles

Avant une production, je peux inspecter le plan sans rien construire ni publier :

```bash
python3 ./package-all.py --dry-run --sync --out ../dist --only morfCollector
```

Après une production :

```bash
gh release view morfcollector-v0.7.0 --repo morfredus/morfPackages
```

Le tag de distribution reste volontairement différent du tag source : il permet
à une seule release morfPackages de rassembler les plateformes d'un projet sans
mélanger les versions de projets différents.
