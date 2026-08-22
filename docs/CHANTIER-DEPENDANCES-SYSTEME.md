# Chantier morfDeploy - Gestion des dépendances système

Prolongement de morfDeploy : gérer de façon **déclarative** les dépendances
système (paquets) nécessaires aux projets et à leurs capacités, sans transformer
morfDeploy en gestionnaire de paquets généraliste ni modifier la machine en
silence.

Cycle : **détecter → proposer → faire valider → installer/mettre à jour →
vérifier**.

## Principes (rappel du brief)

1. **Aucune installation système silencieuse.** Toute modification est
   identifiée, présentée, validée (interactif) ou explicitement autorisée
   (`--yes` en non-interactif), simulable (`--dry-run`), puis vérifiée.
2. **Obligatoire vs optionnel.** Une dépendance obligatoire manquante interrompt
   proprement l'opération ; une optionnelle manquante ne bloque pas le reste
   (parallèle morfSensor↔Qt SerialPort, morfPhoto↔exiftool).
3. **Le projet déclare le besoin, pas le gestionnaire.** `system_dependencies`
   dans `service.json` (id, label, required_for, packages par famille, required).
   morfDeploy détecte plateforme + gestionnaire et résout le paquet.
4. **Jamais de `apt upgrade` global.** morfDeploy ne touche qu'aux paquets
   explicitement déclarés.
5. **Garde-fous partagés** : `--dry-run` (même résolution que le réel, sans rien
   modifier), `--yes` (autorisation explicite en non-interactif), `--force` n'est
   PAS un « oui à tout ».
6. **Étape du cycle de vie**, pas forcément une commande isolée : `deploy` (et le
   futur `update`) résout les dépendances avant le build.
7. **Souveraineté utilisateur** : l'automatisation supprime les oublis, pas la
   maîtrise de la machine.

## Contrat `service.json`

```jsonc
"system_dependencies": [
  {
    "id": "qt-serialport",
    "label": "Qt SerialPort",
    "required_for": ["ld2410c"],
    "packages": { "debian": ["qt6-serialport-dev"] },
    "required": false
  }
]
```

Le projet sait « la capacité X nécessite Qt SerialPort ». Il ne sait pas
« lancer apt install ». Cette responsabilité est à morfDeploy.

## Portabilité

Le contrat est indépendant du gestionnaire. morfDeploy détecte la famille
(debian/fedora/arch/…) et le gestionnaire disponible (apt/dnf/pacman/…), puis
résout `packages[famille]`. On part des plateformes réellement testables
aujourd'hui (Debian/apt : Pi, Mint) et on étend au besoin. Une dépendance sans
paquet déclaré pour la plateforme courante n'est ni vérifiable ni installable ici
et n'est pas traitée comme un échec.

## État

- Contrat `system_dependencies` + validation - **fait** (morfDeploy 0.7.0,
  `manifest.py`).
- Détection plateforme/gestionnaire + résolution - **fait** (`sysdeps.py` :
  apt/dnf/pacman ; famille debian testée, autres à éprouver).
- Action `service.py deps` (`--list` JSON, `--dry-run`, `--yes`) - **fait**.
- Intégration à `install` (donc `deploy`) : résolution **avant le build** - **fait**.
- Consommateurs initiaux : **morfSensor** (qt-serialport, optionnel, 0.4.3),
  **morfPhoto** (exiftool, optionnel, 0.7.2).
- **Vérifié ici (Windows + simulation)** : `deps --list` (JSON), `deps --dry-run`
  (plan), gating obligatoire/optionnel, refus non-interactif sans `--yes`, garde
  root (sudo requis pour installer), plateforme sans gestionnaire signalée.

### Reste (à faire/vérifier sur Linux — Pi/Mint)

- **Install apt réelle** : `sudo service.py deps --yes` et `deploy` qui installe
  réellement `qt6-serialport-dev` / `libimage-exiftool-perl`, puis vérifie.
- **`morf deps`** côté morfTools (orchestration multi-projets) si souhaité, sur le
  modèle de `morf purge` (découverte via `deps --list`, plan agrégé).
- Étendre aux familles non-debian quand une machine réelle l'exige (dnf/pacman).
- Le futur `morf update` (« composants installés ») réutilisera cette résolution
  de dépendances avant de rebâtir.
