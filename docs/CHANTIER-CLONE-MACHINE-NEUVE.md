# Chantier morfTools - `morf clone` sur une machine neuve

`morf clone` supposait implicitement l'environnement du poste de dev : Git + SSH
+ clé + clé connue de GitHub + authentification fonctionnelle. Vrai sur le Legion,
faux sur une machine fraîche (révélé par l'Asus Windows 10 avec une toolchain Qt
neuve). La commande ne doit pas dépendre de cette préparation historique.

Philosophie identique au reste du chantier :
**détecter → expliquer → proposer → faire valider → exécuter → vérifier.**

## Fait (morfTools 0.18.0)

- **`gitaccess.py`** (lecture seule, ne configure JAMAIS) : `git_available`,
  `ssh_available`, `ssh_key_present`, **`ssh_github_access`** (test réel par
  `git ls-remote` en `BatchMode`, sans prompt), `https_reachable`, `diagnose`,
  `ssh_setup_hint`.
- **`--protocol auto|ssh|https`** :
  - `auto` : SSH si l'accès GitHub SSH est réellement vérifié ; sinon SSH absent →
    propose HTTPS ; SSH présent mais non authentifié → menu interactif
    (configurer SSH = montrer comment / HTTPS / annuler), ou repli HTTPS
    non-interactif avec `--yes`.
    - `ssh` : échoue proprement si non opérationnel (diagnostic + marche à suivre).
    - `https` : mode d'accès valide, URL dérivée de la template SSH ou
      `httpsUrlTemplate`.
  - `--yes` autorise le repli HTTPS en non-interactif. Aucune création de clé,
    aucune modif `~/.ssh`, aucun changement de remote implicite.
- **`workspace.clone_url(name, protocol)`** : dérive l'URL HTTPS de la template SSH.
- **`morf doctor` → section « Accès Git »** (git/ssh/clé/accès GitHub SSH/HTTPS),
  réseau gated sur `--update`.

## Frontière

Détection ≠ configuration. La génération/installation assistée d'une clé SSH
serait une **capacité distincte**, à n'ajouter que si un besoin réel apparaît
(pas avant). morfTools détecte les moyens utilisables, l'utilisateur arbitre,
morfTools exécute et vérifie sans configuration implicite.

## Reste (à éprouver sur une vraie machine neuve)

- Le vrai test : cloner le parc depuis l'Asus fraîche (SSH absent) et confirmer le
  parcours HTTPS de bout en bout, puis le menu SSH-présent-mais-non-configuré.
- Éventuelle capacité distincte d'assistance à la création de clé SSH, si besoin.
