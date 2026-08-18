# Chantier morfTools - Audit des capacités (étape 0)

Inventaire préalable exigé par les sections 15 et 17 du brief : **ne pas figer
le contrat commun avant d'avoir vu ce que les projets savent déjà faire.**

Ce document décrit l'état RÉEL au moment de l'audit. Il ne décide de rien : il
sert de socle factuel pour concevoir ensuite le contrat de capacités.

Date de l'audit : 2026-08-17.

---

## 1. Constat central

Les capacités ne varient pas d'un projet à l'autre. Chaque `service.py` du parc
est une coquille d'une quarantaine de lignes qui délègue tout à `morfdeploy`
(vendoré sous `third_party/morf/`). La connaissance vit dans morfdeploy, pas
dans les projets.

Autrement dit : le contrat commun existe déjà, mais il est **uniforme et
implicite**, alors que le brief veut un contrat **annoncé et potentiellement
divergent** (un projet annonce ce qu'il sait purger, un autre non).

Le vrai travail n'est donc pas de créer un contrat à partir de rien. C'est :

1. rendre le contrat explicite (chaque projet annonce ce qu'il expose) ;
2. permettre la divergence là où elle a du sens (purge par catégories surtout) ;
3. réduire la surface de morfTools à l'orchestration.

---

## 2. Contrat morfdeploy actuel

Actions exposées par tout `service.py` (via `morfdeploy.cli`) :

```text
install
update
uninstall   [--purge] [--backup DIR]
status
is-installed          # muet : le code de retour EST la réponse (0/1/2)
config      [--mode merge|push] [--force]
```

Correspondance avec le vocabulaire du brief :

| Brief (§5)        | morfdeploy actuel                    | Écart                              |
| ----------------- | ------------------------------------ | ---------------------------------- |
| `config keep`     | ne pas appeler `config`              | pas une valeur nommée              |
| `config merge`    | `config --mode merge` (défaut)       | OK, à renommer côté façade         |
| `config replace`  | `config --mode push --force`         | nom différent (`push`)             |
| `purge database`  | -                                    | **inexistant** (purge monolithique)|
| `doctor` (projet) | -                                    | inexistant (doctor = morfTools)    |
| `--dry-run`       | -                                    | inexistant partout                 |
| presets plateforme| presets **CMake** (build)            | sémantique différente              |

`purge` aujourd'hui = tout ou rien : `uninstall --purge` retire config +
répertoire binaire. Aucune notion de catégorie de données.

---

## 3. Matrice des projets

Trois familles nettes.

### 3.1 Services (service.py + service.json → morfdeploy)

Toutes les capacités sont identiques (délégation morfdeploy). La colonne « état
persistant » indique ce qui existe et pourrait devenir purgeable par catégorie.

| Projet              | service.py | service.json | état persistant déclaré     | remarque                          |
| ------------------- | :--------: | :----------: | --------------------------- | --------------------------------- |
| morfAnalytics       |     oui    |     oui      | state_dir + cache           | candidat purge multi-catégories   |
| morfCollector       |     oui    |     oui      | state_dir (coffre)          | coffre = donnée sensible          |
| morfMonitor         |     oui    |     oui      | -                           | historique registre à confirmer   |
| morfNotify          |     oui    |     oui      | -                           |                                   |
| morfPhoto           |     oui    |     oui      | state_dir (SQLite)          | candidat purge database + cache   |
| morfSensor          |     oui    |     oui      | -                           | matériel optionnel (capteur)      |
| morfSync            |     oui    |     oui      | state_dir                   | curseurs/séquences de sync        |
| morfTemplateService |     oui    |     oui      | state_dir                   | `template: true` : jamais déployé |

### 3.2 Service à mécanique propre (modèle du §4/§16)

| Projet       | service.py | service.json | mécanique                                   |
| ------------ | :--------: | :----------: | ------------------------------------------- |
| morfDashboard|     oui    |    **non**   | scripts/linux/ (rsync arbre Python + unité) |

morfDashboard est déjà l'exemple abouti du principe visé : il expose l'interface
commune (`service.py` : install/update/uninstall/status/is-installed) mais garde
sa connaissance propre dans `scripts/linux/`. C'est le patron à généraliser
quand un projet ne rentre pas dans le moule morfdeploy.

### 3.3 Non-services (ni service.py ni service.json)

| Projet       | nature                    | ce que morfTools en fait aujourd'hui     |
| ------------ | ------------------------- | ---------------------------------------- |
| morfBeacon   | bibliothèque C++          | build seulement ; pas déployable seul    |
| morfDeploy   | dépôt du socle (v0.1.1)   | source du vendoring ; pas un service     |
| morfUpdate   | bibliothèque C++/Qt       | build seulement (voir §7)                |
| morfSystem   | méta / docs de l'écosystème| build/doc                               |
| ComponentHub | app desktop Qt            | build (GUI, sauté si headless)           |
| PhotoHub     | app desktop Qt            | build (GUI)                              |
| SiteWatch    | app desktop Qt            | build (GUI)                              |
| GatewayLab   | firmware ESP32 (PlatformIO)| build `pio run` ; flash manuel          |
| MeteoHub     | firmware ESP32 (PlatformIO)| build `pio run` ; flash manuel          |

Implication pour `deploy` (§6) : la sélection interactive `[x] composant` ne
concerne que la famille 3.1/3.2. Les apps desktop et les firmwares ne
« s'installent » pas comme des services - le brief le prévoit (un projet peut
annoncer qu'il n'est pas disponible sur une opération/plateforme, §18).

---

## 4. Surface morfTools actuelle vs cible

Commandes actuelles (`lib/morftools/commands.py`) :

```text
clone  fetch  pull  update(=pull)  status  push  commit          # git
build  clean                                                     # build
install  uninstall  upgrade                                      # cycle de vie
doctor                                                           # diagnostic
```

Cible (§2 du brief) :

```text
doctor  deploy  update  upgrade  purge  uninstall
```

Écarts :

- Les commandes git (clone/fetch/pull/push/commit/status) sont un usage
  développeur, pas de l'administration de machine. Décision à prendre : les
  sortir du coeur `morf` administrateur, ou les garder dans un espace séparé.
- Pas de `deploy` : `install` existe mais sur tout le parc (`--only` = 1 seul
  projet, pas de multi-sélection interactive).
- `purge` n'est pas une commande : c'est un drapeau de `uninstall`.
- Pas de `--dry-run`.
- Pas de presets plateforme (`linux/linux-arm64/windows`) ; `--preset` = CMake.

---

## 5. Ce que l'audit implique pour le contrat

1. **Le socle du contrat est déjà là** (morfdeploy uniforme). Ne pas le
   réécrire : l'étendre et le rendre déclaratif.
2. **La divergence utile se concentre sur la purge.** C'est le seul endroit où
   « annoncer ses capacités » a une valeur immédiate (morfPhoto : database +
   cache ; morfAnalytics : plusieurs historiques). À concevoir côté morfdeploy
   (catégories dans service.json) ET côté chaque service (savoir purger).
3. **`config` : renommer sans casser.** Exposer keep/merge/replace en façade,
   mappé sur l'existant (rien / merge / push --force).
4. **`--dry-run` est un ajout transverse** : il doit descendre dans morfdeploy
   pour être honnête (§10), pas simulé par morfTools.
5. **Ne rien imposer aux non-services.** Le contrat doit rester optionnel par
   capacité : un firmware ou une app desktop annonce ce qu'il sait faire (build,
   éventuellement flash), pas install/purge.
6. **morfDashboard = patron** du « interface commune, mécanique propre » pour
   tout projet hors moule morfdeploy.

---

## 6. Questions ouvertes avant de figer le contrat

- Où vit le schéma du contrat de capacités : dans morfDeploy (dépôt autonome)
  puisque service.json est lu par morfdeploy ? À trancher (le vendoring impose
  que la source soit le dépôt morfDeploy).
- Les commandes git restent-elles dans `morf` ou partent-elles dans un outil
  développeur séparé ?
- `morfUpdate` (v0.1.1) : quel rôle vis-à-vis de `morf update` / upgrade ?
- Découpage des catégories de purge : par service, qui décide de la
  nomenclature (database/cache/history) ? Un vocabulaire commun conseillé mais
  non imposé.

---

## 7. Verdict morfUpdate (étape 1 du chantier)

morfUpdate est une **bibliothèque C++/Qt statique** (cible `morfUpdate::morfUpdate`
= Qt Core + Network ; couche `morfUpdate::Widgets` optionnelle), embarquée dans
les applications desktop (ComponentHub, SiteWatch, PhotoHub). Elle compare la
version installée à la dernière **GitHub Release** et **notifie** l'utilisateur,
sans jamais installer quoi que ce soit. Aucun `service.py`, aucune CLI, aucun
déploiement : famille 3.3 (build seulement), comme morfBeacon.

**Collision uniquement lexicale, pas fonctionnelle.** `morf update` (administrer
le parc : `git pull` des clones) et `morfUpdate` (lib desktop) n'ont aucun
recouvrement de fonction. morfUpdate n'apparaîtra jamais dans la CLI `morf`.

**Frontière à figer** - deux mécanismes de détection de version, cohérents avec
la nature de chaque cible :

| Cible          | Livraison        | Détection d'une nouvelle version         |
| -------------- | ---------------- | ---------------------------------------- |
| Services 3.1   | par source (git) | `morf doctor/update/upgrade` (git)       |
| Apps desktop   | binaire (Release)| bibliothèque morfUpdate (GitHub Releases)|

Conclusion : **garder le nom**, ne rien fusionner. Le seul soin à prendre est
rédactionnel (docs de la façade), pour que le lecteur ne confonde pas la
commande d'admin et la bibliothèque.

---

## 8. Décisions arrêtées (Fred)

Tranchages retenus pour la suite du chantier :

1. **Le contrat existe déjà (morfdeploy) ; il faut le rendre explicite,
   extensible et rétrocompatible**, pas le réinventer. Valeurs par défaut
   rétrocompatibles pour les capacités déjà implicites ; seule une capacité
   réellement divergente exige une déclaration.
2. **morfDashboard = preuve, pas modèle de remplacement.** morfdeploy reste le
   socle des services 3.1. Aucune refonte des projets « pour faire propre ».
3. **Contrat de PROJET, pas de service.** Un projet annonce les capacités de sa
   nature (`install/update/config/purge/uninstall` pour un service ;
   `build/package` pour une app ; `build/flash` pour un firmware ; `build` pour
   une lib). morfTools choisit celles pertinentes pour sa surface d'admin.
4. **Séparation de namespace CLI** (pas de suppression) : admin machine d'un
   côté, outillage développeur de l'autre. Piste conceptuelle :
   `morf deploy/update/upgrade/purge/uninstall/doctor` et
   `morf dev clone/pull/status/build/clean/push` (syntaxe non figée).
5. **Purge : identifiants libres + conventions documentées.** Vocabulaire
   conseillé (`database`, `cache`, `history`, `thumbnails`, `activities`,
   `metrics`, `sync-state`…) mais jamais une enum rigide. Chaque catégorie porte
   un **label humain**, un **caractère destructif** et, si possible, le support
   du **dry-run**. Ajouter une catégorie ne doit pas modifier morfDeploy.
6. **Schéma du contrat : dans morfDeploy** (dépôt autonome), qui possède déjà la
   sémantique de `service.json` ; le vendoring en fait la source canonique.
7. **`--dry-run` d'abord dans morfdeploy, puis dans morfTools** : sinon un
   `morf --dry-run` mentirait dès qu'il franchit la frontière du projet.

### Ordre d'exécution

1. Clarifier les rôles (morfUpdate) - **fait** (§7).
2. Bascule du canonique morfdeploy vers le dépôt dédié morfDeploy - **fait**
   (no-op fonctionnel vérifié par `ecosystem-check` ; `lib/morfdeploy` retiré de
   morfTools). Fait AVANT la purge, pour ne pas développer la nouvelle
   architecture depuis une source dont on savait qu'elle était au mauvais endroit.
3. Contrat `purge` dans morfDeploy (`service.json` : bloc `purge`, catégories à
   identifiants libres, types `path`/`command`, rétrocompatible) - **fait**
   (morfDeploy 0.2.0). Resynchronisé dans les 8 services consommateurs.
4. `--dry-run` sur `purge`, dès l'introduction de l'action (même chemin de
   résolution que l'exécution réelle) - **fait**.
5. Doc morfSystem : doctrine d'effacement dans `FILESYSTEM.md` - **fait**.
6. Façade morfTools, tranche 1 : **`morf purge`** consommant le contrat - **fait**
   (morfTools 0.12.0). Découverte via `service.py purge --list` (morfDeploy 0.3.0,
   JSON ASCII-safe), ciblage projet/catégorie ou `--all`, `--dry-run` traversant,
   confirmation destructive à jeton, résumé final. morfTools ne lit aucun
   `service.json`.
7. Façade morfTools, tranche 2 : **séparation de namespace `morf dev`** - **fait**
   (0.13.0). Git/build sous `morf dev`, formes plates conservées.
8. Façade morfTools, tranche 3 : **`morf deploy`** sélectif/interactif +
   **`--config keep/merge/replace`** - **fait** (0.14.0). Sélection explicite/
   `--all`/interactive numérotée, `--dry-run`, résumé, garde `replace`.
9. Blocs `purge` réels : **morfPhoto** (`database`) déclaré (0.7.1). Pour les
   chemins **configurables**, morfDeploy 0.5.0 ajoute **`from_config`** (lit le
   vrai emplacement dans la config déployée, repli sur le défaut) - décision de
   Fred. **morfCollector** (0.4.4) déclare `vault` (`vault_root`) et `data`
   (`storage_root`). **morfAnalytics** (historiques dans un dossier configurable,
   granularité par fichier) et **morfSync** (change-stores par domaine) restent à
   déclarer et **vérifier sur le Pi** : morfAnalytics demandera un from_config
   dossier + sous-chemin (petite extension), morfSync des chemins sous state.

10. Sûreté de la purge et de la désinstallation - **fait** (morfDeploy 0.4.0,
    morfTools 0.15.0, morfDashboard 1.15.1) :
    - **Garde-fou « service actif »** : la purge réelle refuse d'effacer des
      données qu'un service en cours peut être en train d'écrire (`is_active` par
      backend) ; `--force` outrepasse ; le dry-run le signale.
    - **`uninstall --dry-run`** traversant, et **protections `--purge`** (jeton
      saisi `PURGE`/`PURGE ALL`, `--yes` requis en non-interactif).
    - morfDashboard (interface manuelle) remis à niveau du contrat (`--dry-run`).

11. **`--dry-run` transverse** à `pull`/`update` et `upgrade` - **fait**
    (morfTools 0.16.0). update = commits entrants sans fusion ; upgrade = plan
    complet par projet sans exécution (ni demande de preset).

12. Détection auto de preset (§18) - **fait** (morfTools 0.17.0).
13. Transition `update`/`upgrade` (§17) - **fait** (morfTools 0.17.0) : `morf
    update` (git) déprécié → `morf dev pull`, réservé au futur sens « composants
    installés » ; `upgrade` = maj machine complète.
14. `from_config` pour chemins configurables (décision de Fred) - **fait**
    (morfDeploy 0.5.0) ; appliqué à **morfCollector** (0.4.4).

15. Extension `from_config` **dossier + sous-chemin** (`from_config_kind: dir` +
    `default_dir`) - **fait** (morfDeploy 0.6.0). Appliquée à **morfAnalytics
    `sitewatch-history`** (0.29.5), seule donnée d'analytics adressable par une clé
    top-level (`sitewatch_cache_dir`).

### Reste (command-type binaire, C++, à faire et vérifier sur le Pi)

- **morfAnalytics** historiques `monitor` et `meteo` : chemins issus de params
  **par-module imbriqués** (`modules[].cache_dir`/`db_path`), non adressables par
  une clé top-level → purge de type `command` (le binaire connaît ses chemins).
- **morfSync** journaux de synchro : fichiers `{domain}.json` à **noms dynamiques**
  sous `state_dir` → purge `command` (le binaire les énumère) ou effacement du
  contenu de `state_dir` (qui ne contient que ces journaux).
- Ces deux cas exigent un sous-`purge` dans le binaire C++ concerné : à faire et
  éprouver sur le Pi avec le vrai service.
- Sens définitif de `morf update` (« mettre à jour les composants installés ») une
  fois la période de dépréciation écoulée - décision à prendre par Fred, et à
  définir en cohérence avec le chantier « dépendances système » (voir
  `CHANTIER-DEPENDANCES-SYSTEME.md`).

### Validation sur le Pi (opérations réelles, non exerçables sous Windows)

Le dry-run et la logique hors-privilèges ont été validés ici ; l'exécution réelle
(build + admin) reste à éprouver sur Linux. Séquence conseillée sur pi4fred :

1. `python3 morf.py deploy morfPhoto --dry-run` puis sans `--dry-run` (build +
   install + config) ; vérifier `service.py status`.
2. `python3 morf.py purge morfPhoto database --dry-run` (voir le vrai chemin
   `photos.db`), puis, service arrêté, sans `--dry-run` ; re-indexer ensuite.
3. `python3 morf.py purge morfCollector vault --dry-run` (vérifie la résolution
   `vault_root`/repli `state/vault`) ; ne PAS purger le vrai coffre sans intention.
4. `python3 morf.py purge morfAnalytics sitewatch-history --dry-run` (résolution
   `sitewatch_cache_dir`/repli `app/cache`).
5. `python3 morf.py uninstall morfPhoto --dry-run` puis, si voulu, réel + jeton.
6. Vérifier le **garde-fou** : purge réelle refusée tant que le service tourne
   (message clair) ; `--force` pour outrepasser une fois le service arrêté.
7. Vérifier la **détection de preset** : `deploy`/`upgrade` sans `--preset` doit
   choisir `linux-arm64` sur le Pi.
