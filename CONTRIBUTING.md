# Contribuer à morfTools

morfTools est le projet d'administration de l'écosystème morfSystem. Il ne
contient aucun code métier : uniquement des commandes génériques qui pilotent
les autres dépôts, et les registres qui font autorité à l'échelle du parc.

## 1. Philosophie

**morfTools ne connaît aucun métier.** Il clone, compile, met à jour et
diagnostique des projets déclarés dans un manifeste. Une commande qui aurait
besoin de savoir *ce que fait* un projet n'a pas sa place ici - elle appartient
au projet concerné.

**Le manifeste fait autorité.** `ecosystem.json` porte la liste des projets, le
plan d'adressage des ports et l'inventaire des copies vendorées. Ces
informations ne doivent exister nulle part ailleurs : une copie partielle dans
un autre fichier finit toujours par diverger, et c'est précisément ce qui s'est
produit quand le plan des ports vivait dans un commentaire de la configuration
de morfMonitor.

**Une règle écrite doit être vérifiable.** Consigner une convention ne suffit
pas : tant qu'aucun contrôle ne l'applique, elle repose sur la vigilance et
cède tôt ou tard. Toute règle ajoutée au manifeste devrait s'accompagner de sa
vérification dans `morf doctor`.

**Un projet absent n'est pas une erreur.** Un espace de travail partiellement
cloné est un état normal. Une commande signale `[SKIP]` et poursuit ; elle ne
s'arrête pas.

## 2. Faire évoluer morfTools

### Ajouter une commande

Une commande vit une seule fois, dans `morf.py` : le point d'entrée délègue à
`lib/morftools/cli.py`, qui analyse les arguments, et les commandes elles-mêmes
vivent dans `lib/morftools/commands.py`. Les anciens dispatchers `morf.sh` et
`morf.ps1` faisaient la même chose deux fois ; les remplacer par un seul programme
Python a supprimé toute possibilité d'asymétrie entre Linux et Windows.

Les commandes opèrent projet par projet, dans la boucle du manifeste. Une
vérification qui porte sur une ressource **partagée** (ports, copies vendorées)
n'entre pas dans cette boucle : elle s'exécute une fois, avant, car elle est
invisible depuis l'intérieur d'un projet.

### Où mettre la logique

| Nature | Où | Pourquoi |
| --- | --- | --- |
| Orchestration, Git, CMake | `lib/morftools/` (appelé par `morf.py`) | Un seul code pour toutes les plateformes ; seuls les outils appelés diffèrent. |
| Contrôles d'écosystème autonomes | `scripts/*.py` | Lançables seuls, et appelés par `morf doctor`. |

Python est le seul langage qui tourne à l'identique sous Windows, Linux et
Raspberry Pi. Réécrire une comparaison ou une fusion JSON en Bash *et* en
PowerShell donnerait deux implémentations libres de se contredire - exactement le
problème que `morf doctor` sert à détecter ailleurs.

### Sortie des scripts

**En anglais.** Tous les messages des dispatchers et des scripts sont en
anglais. Cette règle a déjà été enfreinte une fois puis rétablie ; s'en écarter
produit une sortie moitié française, moitié anglaise, selon l'ancienneté du
message.

Les préfixes sont `[OK]`, `[WARN]`, `[FAIL]`, `[SKIP]`. Un échec ajoute le
projet à la liste des échecs et fait sortir la commande en code non nul, sans
interrompre les projets restants.

## 3. Style

- Un commentaire explique **pourquoi**, pas quoi. Le code dit déjà quoi.
- Un correctif documente le symptôme qu'il supprime : c'est ce qui permet, plus
  tard, de savoir si la contrainte est encore justifiée.
- Chemins résolus depuis l'emplacement du script, jamais en absolu : le projet
  doit pouvoir être déplacé ou renommé.
- Le mode bac à sable ou production se déduit du **nom du dossier** de
  morfTools. Aucune commande ne demande à l'utilisateur dans quel espace il se
  trouve.

## 4. Avant de proposer une modification

```bash
python3 morf.py doctor                  # contrôles d'écosystème + état des dépôts
python3 morf.py status                  # état Git de chaque projet
python3 -m py_compile morf.py lib/morftools/*.py scripts/*.py
```

Un seul programme sert toutes les plateformes, mais les outils qu'il appelle
(Git, CMake, systemd ou le gestionnaire de services Windows) diffèrent : une
modification qui touche l'un d'eux se vérifie sous Linux **et** sous Windows.

## 5. Licence

En contribuant, vous acceptez que votre contribution soit distribuée sous
**GPL-3.0-only**, comme le reste de l'écosystème.
