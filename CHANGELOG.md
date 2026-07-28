# Changelog

## [0.5.0] - 2026-07-28

### Modifié

- **morfdeploy : `uninstall --purge` retire tout le `config_dir` du service**
  (`/etc/morfsystem/<service>`), et non plus seulement le fichier de config
  déclaré. Les fichiers créés au runtime (coffre de secrets, état) ne survivent
  donc plus à un purge. Le parent partagé `/etc/morfsystem` est préservé.
- **`reset-parc.sh` : `/etc/morfsystem` est le point d'entrée unique** ; les
  anciens `/etc/<service>` passent en emplacements hérités (nettoyés). Ajout de
  morfcollector aux unités et dossiers `/opt`.


## [0.4.23] - 2026-07-26

### Modifié

- **Un service installé mais arrêté n'est plus un échec.** Il peut l'être
  volontairement : `doctor` le présente désormais comme un **avertissement**
  (« service installed but not running; may be intentional »), sans action
  alarmante, et ne fait plus échouer le diagnostic. Auparavant, un service
  simplement arrêté sortait en `[FAIL]` et donnait un code de retour 1.
- **Remède de mise à jour adapté à l'état du service.** Pour un service installé
  mais inactif et en retard, `--update` précise « service installé mais inactif »
  et donne la commande **en deux lignes** : `update` (tirer la source), puis, si
  souhaité, `upgrade` (reconstruire et redéployer). Un service actif reçoit
  directement `upgrade` ; un projet sans service (application de bureau) ou non
  installé ici reçoit `update`.
- **Plus de double affichage.** Quand un service inactif est aussi en retard,
  l'avertissement « installé mais inactif » est **replié dans l'entrée de mise à
  jour** (qui le mentionne déjà) au lieu d'apparaître en double dans deux
  sections. Le repli est conservé pour `--verbose`.

## [0.4.22] - 2026-07-26

### Modifié

- **La commande proposée pour une mise à jour dépend de l'état du service.** Si
  le service du projet est **actif** sur cette machine, le remède reste
  `upgrade` (reconstruire et redéployer en place). S'il n'est **pas actif** -
  non installé ici, application de bureau sans service, ou service arrêté - le
  remède devient `update` : tirer la source, sans rien redéployer. Proposer
  `upgrade` pour un service qui ne tourne pas reviendrait à reconstruire et
  relancer ce que la machine n'exécute pas. L'état est lu de la sonde que
  `doctor` vient de faire (le point d'état a-t-il répondu une version ?), sans
  second aller-retour réseau.

## [0.4.21] - 2026-07-26

### Corrigé

- **Le remède d'auto-mise-à-jour de morfTools ne contient plus de chemin
  absolu.** Il affichait `git -C /home/<user>/…/morfTools_travail pull
  --ff-only` : un chemin propre à une seule machine, qui casse sur une autre.
  C'est désormais un simple **`git pull --ff-only`**, conforme au reste de
  l'outil - toutes les commandes morf se lancent déjà depuis le dossier
  morfTools (c'est ainsi que `python3 morf.py …` se résout), donc
  l'auto-mise-à-jour part du même endroit. Aucune commande ne dépend plus d'un
  chemin en dur.

## [0.4.20] - 2026-07-26

### Modifié

- **Option `--updates` renommée `--update`** (alias court `-u` inchangé), pour
  suivre la convention habituelle des drapeaux booléens au singulier
  (`--verbose`, `--force`). Le pluriel n'aura vécu que la 0.4.19 ; l'entrée de
  cette version a été relue en conséquence. Règle générale retenue : nommer les
  options selon la norme des outils standard.

## [0.4.19] - 2026-07-26

### Modifié

- **Le contrôle des nouvelles versions passe sur option.** Introduit en 0.4.18
  comme systématique, il ajoutait un `git fetch` par dépôt - une trentaine de
  secondes sur le parc complet, trop pour un `doctor` de routine. Il ne s'exécute
  désormais qu'avec **`--update`**. Par défaut, `doctor` reste local et
  instantané, et se termine par `Tout est conforme (versions non vérifiées).` en
  rappelant la commande.
- **Distinction « non vérifié » / « à jour ».** Le résumé n'affiche le décompte
  des mises à jour que si le contrôle a réellement eu lieu : afficher « 0 mise à
  jour » sans avoir vérifié laisserait croire à une vérification qui n'a pas eu
  lieu.

### Ajouté

- **Indicateur de progression** pendant `--update` : une ligne réécrite en place
  sur `stderr` (`vérification des versions… 3/14 <projet>`), pour ne pas laisser
  l'utilisateur dans le flou le temps des `fetch`. Sur un terminal seulement ;
  redirigé ou journalisé, le contrôle reste silencieux plutôt que d'empiler des
  images d'animation. Comme elle vit sur `stderr`, elle ne pollue jamais le
  rapport, qui est sur `stdout`.

### Vérifié

Défaut sans réseau (indication « versions non vérifiées » + rappel de la
commande) ; `--update` effectue les `fetch`, ajoute la section « Mises à jour
disponibles » et l'auto-vérification de morfTools ; garde `--update` refusée
hors `doctor` ; progression rendue en place puis effacée sur un terminal,
muette une fois redirigée.

## [0.4.18] - 2026-07-26

### Ajouté

- **`doctor` signale les mises à jour disponibles.** À chaque exécution, il
  compare chaque clone à `origin/main` et, s'il est en retard, l'annonce dans
  une section **« Mises à jour disponibles »** avec les deux commandes à lancer :
  `morf pull --only <projet>` puis `morf upgrade --only <projet>`. Le signal est
  « le distant a des commits que je n'ai pas », et non « une release GitHub a été
  publiée » : la moitié des dépôts ne publient aucune release, alors que tous ont
  un distant. Il n'utilise que `git` - ni `gh`, ni jeton, rien qui puisse manquer
  sur le Pi.
- **morfTools s'auto-vérifie.** L'outil n'étant pas un projet du manifeste, rien
  ne signalait qu'il était lui-même en retard. Il apparaît désormais dans le
  rapport sous « Outil », avec pour remède un `git pull --ff-only` (depuis son dossier)
  en place (`morf pull` agit sur les autres projets, pas sur l'outil qui le
  lance).

### Notes

- Une mise à jour disponible n'est **pas un échec** : elle ne fait pas passer le
  code de retour à 1 et n'entre ni dans les avertissements ni dans les échecs.
  Être en retard est une information, pas une anomalie.
- Le contrôle est un pas réseau : un `git fetch` borné (20 s, invites
  d'identifiants désactivées) par dépôt. Hors-ligne ou distant injoignable, il se
  dégrade en `[SKIP]` sans alarme et sans bloquer. Compter quelques dizaines de
  secondes sur le parc complet ; il reste hors de `cmd_doctor`, qui demeure
  utilisable sans réseau.

### Vérifié

Parc réel : « conforme et à jour » en ~37 s. Détection en conditions réelles en
reculant un dépôt propre d'un commit - signalé avec les bonnes commandes, puis
restauré. morfTools inclus dans le rapport. Hors-ligne : `[SKIP]` propre.

## [0.4.17] - 2026-07-26

### Modifié

- **`doctor` rend un résumé lisible au lieu d'un flot de lignes.** Sain, le
  diagnostic imprimait une soixantaine de lignes vertes ; un vrai problème s'y
  noyait. Par défaut, les vérifications conformes sont désormais comptées et
  regroupées (Écosystème / Projets), seules les exceptions sont détaillées, et
  le rapport se termine par un **résumé chiffré** puis une section **« À
  corriger »** listant chaque échec avec l'action concrète à mener.
- **L'action réutilise le remède que la vérification imprime déjà** (commande de
  resynchronisation vendorée, commande de mise à niveau) quand il existe ; sinon
  elle est déduite du message. Une vérification qui améliore son propre conseil
  améliore ce résumé sans y toucher.
- **Les « impossible de vérifier » ne sont plus comptés comme des
  avertissements.** Sur un poste qui ne peut pas joindre les services (ils
  tournent sur le Pi), le contrôle de version active répondait « unavailable » :
  six faux avertissements par exécution. C'est une non-évaluation, traitée comme
  telle. Un service réellement installé qui ne répond pas reste, lui, un échec.
- **`doctor --verbose` rétablit la sortie ligne par ligne**, inchangée, pour qui
  veut le détail complet.
- **Sortie forcée en UTF-8** (avec remplacement) : le résumé emploie des accents
  et des marqueurs qu'une console Windows en cp1252 refusait, interrompant le
  rapport en cours par une `UnicodeEncodeError`.

### Vérifié

Parc sain : 61 lignes ramenées à 10. Cas en échec (collision de port, dérive
vendorée, version décalée, service en panne) : chaque problème rendu avec son
action, réutilisant le remède du producteur pour la resynchronisation et la
mise à niveau. `--verbose` conserve les 70 lignes détaillées.

## [0.4.16] - 2026-07-26

### Corrigé

- **Le contrôle des ports laissait passer un doublon entre projets.** La
  troisième passe de `check_ports` testait si un port déclaré *existait* dans le
  registre, pas s'il appartenait au projet qui le déclare : un service fraîchement
  cloné qui gardait le `8901` du gabarit passait, puisque `8901` est bien
  enregistré - au nom du gabarit. La passe compare désormais le **propriétaire**
  du port au projet déclarant, ce qui est la forme même d'un doublon. C'est la
  collision qui a mis morfAnalytics à terre (8799 pris par morfMonitor) et qu'un
  test par valeur seule ne pouvait pas voir. Reproduite sur un parc piège, puis
  corrigée et vérifiée.

### Ajouté

- **Discipline de la plage template appliquée dans les deux sens.** Un port de la
  plage `8900-8999` ne peut appartenir qu'à une allocation marquée
  `"template": true`, et une allocation template ne peut utiliser qu'un port de
  cette plage. En production, tout port de la plage template est refusé, même
  libre : c'est la barrière qui garantit qu'un gabarit ne livre jamais un numéro
  qu'un vrai service pourrait prendre. `morfTemplateService` est marqué
  `template` dans le registre.
- **Suggestion de port pour un nouveau projet** : `ecosystem-check.py … next-port`
  imprime le plus petit port libre du bloc service. `new-service.sh` l'exécute et
  affiche le numéro concret à réserver, au lieu de « choisis-en un ». Lire le
  registre à l'œil pour trouver un trou est précisément ce qui met deux projets
  sur le même port.

### Contexte

Le registre `ecosystem.json` était déjà l'autorité unique sur les ports, et
`morf doctor` en vérifiait la cohérence. Ces changements ferment le dernier trou
- un projet réutilisant en silence le port d'un autre - et rendent l'attribution
d'un port à un futur projet mécanique plutôt que manuelle.

## [0.4.15] - 2026-07-25

### Corrigé

- **Instruction de mise à niveau affichée par `doctor`.** Le diagnostic indique
  désormais la commande exécutable depuis morfTools :
  `python3 morf.py upgrade --only <projet>`.

## [0.4.14] - 2026-07-25

### Corrigé

- **`morf doctor` ne confond plus le dépôt à jour avec le service à jour.** Pour
  chaque service installé qui déclare un point `/status`, il compare désormais
  la version active à la version du fichier `VERSION` du projet. Un décalage,
  un service injoignable ou une réponse sans version font échouer le contrôle
  et indiquent la commande `python3 morf.py upgrade --only <projet>` à exécuter. Les
  services non installés sont explicitement ignorés ; si le point d'état ne
  répond pas et que le gestionnaire de services est protégé, l'absence de droits
  reste un avertissement, jamais un faux « non installé ».

## [0.4.13] - 2026-07-24

### Ajouté

- **Modèle d'issue GitHub « Premier test de morfSystem »**
  (`.github/ISSUE_TEMPLATE/premier-test.md`) : le retour demandé par
  `docs/FIRST-TEST.md` se dépose désormais en issue, avec les six questions
  prioritaires déjà en place. Le document pointe vers le formulaire et
  recommande d'ouvrir l'issue **avant** de commencer, pour la compléter au fil
  de l'eau plutôt que de tout écrire de mémoire à la fin - et d'ouvrir
  plusieurs issues courtes plutôt qu'un seul long compte rendu, un blocage
  précis se traitant et se clôturant, là où il se noierait dans un récit.

## [0.4.12] - 2026-07-24

### Ajouté

- **`docs/FIRST-TEST.md`** - demande de retour après une **première**
  installation, destinée à quelqu'un qui ne connaît pas morfSystem. C'est le
  seul test que le parc n'a jamais subi : tout a été éprouvé par son auteur, qui
  sait déjà ce qu'il faut faire et se trouve donc le moins capable de voir ce
  qui manque.

  Le document demande explicitement un retour **honnête plutôt qu'aimable**, et
  pose deux règles qui font sa valeur : ne demander d'aide à personne - chaque
  question qui surgit est notée au lieu d'être posée, car une question posée à
  l'auteur est une information perdue - et ne pas corriger le tir mentalement,
  ce réflexe effaçant justement le défaut.

  Six questions sont marquées comme prioritaires, dont le **point d'abandon**
  (« à quel moment auriez-vous arrêté si vous n'aviez pas accepté de rendre
  service ? ») et l'**écart entre l'attendu et l'obtenu même quand tout
  fonctionne** - ces moments-là ne produisent aucune erreur et n'apparaissent
  dans aucun journal. Référencé depuis le guide de démarrage et le README.

## [0.4.11] - 2026-07-24

### Corrigé

- **Un `update` sans changement ne redémarre plus le service.** La séquence
  était inconditionnelle : compiler, arrêter, recopier le binaire - fût-il
  identique octet pour octet - ré-enregistrer, redémarrer. Le premier `upgrade`
  réel du Pi a donc arrêté et relancé **cinq** services alors qu'aucun n'avait
  changé. Ce n'est pas neutre : c'est une coupure de supervision, un uptime
  remis à zéro et, pour un service au milieu d'une tâche, une interruption -
  payés au moment précis où l'on croyait ne rien toucher.

  `update` compare désormais **l'empreinte du contenu** du binaire construit et
  de l'installé (SHA-256 ; ni la taille ni la date, qu'un `git checkout` ou une
  recompilation réécrivent sur des octets identiques), vérifie que les
  configurations sont en place, et s'arrête là s'il n'y a rien à déployer - en
  le disant clairement, y compris que **le service n'a pas été redémarré**.
  `--force` redéploie et redémarre quand c'est justement l'intention.

- **Deux fonctionnalités annoncées mais jamais branchées le sont enfin.**
  `enrich_configs` (0.4.0, enrichissement des configurations à la mise à jour)
  et `verify_writable` (0.4.2, vérification que l'utilisateur du service peut
  écrire dans son dossier) existaient en code mort : `git log -S` ne trouve
  aucun commit ayant jamais contenu leur appel. Le changelog les décrivait
  comme livrées. Elles sont désormais appelées par `install` et `update`.

  L'enrichissement participe de surcroît à la décision ci-dessus : une clé
  ajoutée dans un fichier que le processus a lu au démarrage ne change rien
  tant qu'il ne l'a pas relu - un enrichissement effectif justifie donc le
  redémarrage, et lui seul.

## [0.4.10] - 2026-07-24

### Corrigé

- **`upgrade` ne laisse plus morfDashboard en arrière, en silence.** Le
  redéploiement ajouté en 0.4.7 ne reconnaissait que les projets dotés d'un
  `service.py` ; morfDashboard, seul service encore piloté par ses scripts
  shell, sortait sur « pas un service » sans rien afficher - son nouveau code
  était récupéré et le service continuait de tourner sur l'ancien. Exactement le
  piège que la fonctionnalité devait fermer, resté ouvert pour un projet, et de
  la pire manière : sans un mot. Constaté sur le premier `upgrade` réel du Pi.

### Modifié

- **La branche legacy de `uninstall` disparaît.** morfDashboard expose désormais
  la même interface que les autres (morfDashboard 1.10.0), si bien que morfTools
  s'en tient à une règle sans exception : un projet qui est un service porte un
  `service.py`. La connaissance d'un projet cesse de vivre dans l'outil qui
  l'administre.

## [0.4.9] - 2026-07-24

### Corrigé

- **« Pas installé » n'est plus conclu de « je n'avais pas le droit de
  demander ».** Lancé sans élévation sous Windows, `service.py update`
  répondait « morfMonitor n'est pas installé sur cette machine. Lancez d'abord
  install » - à propos d'un service en cours d'exécution, qui répondait sur son
  port à la seconde près. `schtasks` renvoie « accès refusé » pour une tâche
  enregistrée en SYSTEM, avec le code de retour de « cette tâche n'existe pas » ;
  le message envoyait donc vers `install`, exactement le mauvais geste.

  `update` et `status` interrogent désormais `can_query_installation()` avant de
  conclure, et nomment la vraie cause avec la manière d'y remédier. Le garde-fou
  existait depuis la 0.4.7 pour le balayage de `morf.py upgrade` ; il manquait
  là où une personne le lit directement.

  Constaté en testant sur une machine Windows réelle, service actif : aucun de
  ces deux défauts n'était visible à la lecture du code.

## [0.4.8] - 2026-07-24

### Corrigé

- **Sous Windows, un service est désactivé, arrêté, et son arrêt réel attendu
  avant que ses fichiers soient remplacés.** Windows refuse d'écraser un
  exécutable qu'un processus tient ouvert, et `schtasks /End` rend la main dès
  la demande émise, sans attendre la sortie effective : la copie qui suivait
  échouait sur une erreur de permission qui ne disait rien de sa cause - la
  précédente instance encore vivante. Trois gestes remplacent l'unique arrêt :

  - **désactivation d'abord** - un arrêt que quelque chose peut défaire n'en est
    pas un : un wrapper SCM (WinSW, NSSM) relance un service qu'il croit planté,
    et il reviendrait en tenant les fichiers qu'on s'apprête à remplacer. La
    désactivation est toujours défaite par l'appelant (install et update
    ré-enregistrent le service entièrement, uninstall le supprime) ;
  - **arrêt** ;
  - **attente de la libération réelle** du binaire, éprouvée en l'ouvrant en
    écriture - Windows accorde la poignée à l'instant où le processus disparaît.
    Un dépassement de délai avertit au lieu d'échouer, en nommant la cause et la
    commande pour s'en sortir.

  Linux n'a pas besoin de cette étape : `systemctl stop` ne rend la main
  qu'une fois l'unité réellement arrêtée. Le correctif vit dans le backend
  Windows, donc `install`, `update` et `uninstall` de **tous** les projets en
  héritent par leur `service.py` - copie vendorée resynchronisée dans les six
  services.

## [0.4.7] - 2026-07-24

### Ajouté

- **`morf.py upgrade` met désormais à jour les services installés.** Il
  s'arrêtait à la compilation : la machine continuait de faire tourner
  l'ancien binaire jusqu'à ce qu'on pense à visiter chaque projet pour y lancer
  son `service.py update` - un piège que le guide devait signaler plutôt que
  l'outil l'éviter. `upgrade` tient maintenant sa promesse : `git pull`,
  recompilation, puis remplacement des binaires **des seuls services
  réellement installés sur cette machine**. Un projet présent dans les dépôts
  sans y être installé est ignoré discrètement : le parc est un jeu de dépôts
  déployé différemment sur chaque machine, pas une anomalie.

  Le `git` reste exécuté en votre nom et **seul le déploiement est élevé** :
  `upgrade` refuse toujours de tourner sous `sudo` (la garde 0.4.3), et
  demande donc lui-même l'élévation au moment de remplacer le premier binaire.

- **`service.py is-installed`** - action muette dont le **code de retour est la
  réponse** : `0` installé, `1` absent, `2` impossible à déterminer. La
  troisième valeur n'est pas un luxe : sous Windows, `schtasks /Query` répond
  « accès refusé » pour une tâche enregistrée en SYSTEM, avec un code de retour
  indiscernable de « cette tâche n'existe pas ». Sans cette distinction, un
  balayage non élevé aurait conclu « rien n'est installé », sauté un service en
  cours d'exécution et annoncé un succès. `upgrade` avertit désormais au lieu
  de se taire. La sortie de `status` n'est toujours jamais analysée : une
  décision se demande au backend qui connaît la plateforme.

### Documentation

- **La découverte distribuée est consignée comme éprouvée** dans
  `docs/ECOSYSTEM-PRINCIPLES.md` : elle fonctionne sur un environnement
  hétérogène (Windows, Linux, Raspberry Pi, ESP32) sans aucune configuration
  manuelle, les instances de morfMonitor se découvrant mutuellement et les
  services du Raspberry Pi apparaissant automatiquement sur Windows comme
  l'inverse. La section « Portée : toutes les plateformes » ne décrit plus une
  intention. L'invariant « on ne promet que ce qu'on peut éprouver » note que
  Windows a franchi son seuil de support le 23 juillet 2026, et que les trois
  défauts révélés ce jour-là étaient tous invisibles à la lecture du code.

## [0.4.6] - 2026-07-23

### Corrigé

- **Les DLL tierces de Qt sont déployées sans dépendre d'un shell.** windeployqt
  place les bibliothèques Qt et le runtime du compilateur, mais **pas** les
  bibliothèques tierces contre lesquelles Qt6Core est lié (brotli,
  double-conversion, ICU, pcre2…) : le service s'arrêtait sur
  « libbrotlidec.dll introuvable », une par une. Le balayage de repli s'appuyait
  sur `ldd` d'un shell MSYS2 - absent depuis un PowerShell ordinaire, et c'est
  précisément là que ces DLL manquaient. Il est remplacé par `objdump` (livré
  dans le même `bin` MinGW que windeployqt, donc présent dès que windeployqt
  l'est, et sans shell) : la table d'imports de chaque binaire est lue, et toute
  DLL importée présente dans le `bin` du toolchain - une bibliothèque MinGW/Qt,
  pas une DLL système - est copiée, en suivant ses propres imports jusqu'à
  fermeture. Testé de bout en bout : 15 DLL au total, dont les quatre qui
  manquaient (libbrotlidec, libdouble-conversion, libicuin78, libicuuc78).
  No-op sous Linux inchangé. Copie vendorée resynchronisée dans les six services.

## [0.4.5] - 2026-07-23

### Corrigé

- **L'install Windows trouve `windeployqt` toute seule, depuis n'importe quel
  terminal.** La 0.4.4 exigeait de lancer l'install depuis le shell MSYS2 qui
  avait compilé, faute de quoi elle s'arrêtait sur « windeployqt introuvable » -
  y compris depuis un PowerShell ordinaire. morfdeploy lit désormais le
  `CMakeCache.txt` du build pour localiser Qt (`Qt6_DIR` → `<qt>/bin`, le même
  point d'ancrage que le CMake de ComponentHub) et préfixe le PATH du
  sous-processus avec le `bin` de Qt, pour qu'`objdump` et les DLL du runtime
  MinGW se résolvent sans dépendre du shell appelant. Testé de bout en bout :
  15 DLL (Qt6Core, Qt6Network, libgcc, libstdc++, pcre2, icu…) et les dossiers
  de plugins `networkinformation/` et `tls/` déployés à côté du binaire. Sous
  Linux, toujours un no-op. Copie vendorée resynchronisée dans les six services.

## [0.4.4] - 2026-07-23

### Corrigé

- **Un service Qt installé sous Windows embarque désormais ses DLL.** Installé
  seul, `morfmonitor.exe` démarrait sur une erreur « Qt6Core.dll introuvable »
  que le gestionnaire de services ne rapporte que comme un échec de démarrage,
  sans nommer un seul fichier manquant. Sous Linux, les bibliothèques
  partagées viennent du système ; Windows n'a pas d'équivalent. morfdeploy
  place maintenant, à l'installation comme à la mise à jour, les DLL Qt et
  MinGW à côté du binaire, via `windeployqt` (livré avec Qt) puis un balayage
  `ldd` de repli pour les dépendances tierces restantes. Le correctif vit dans
  le backend Windows - la seule couche qui interroge la plateforme - donc tout
  service du parc en bénéficie, sans toucher au CMake d'aucun projet. Sous
  Linux, l'appel est un no-op sans coût. Copie vendorée resynchronisée dans
  les six services concernés.

## [0.4.3] - 2026-07-22

### Corrigé

- **Les commandes git refusent de tourner sous sudo.** Élevé, git s'authentifie
  avec la clé SSH de root - inexistante : les treize dépôts répondent
  `Permission denied (publickey)` - et le fetch laisse des fichiers root dans
  chaque `.git` (`FETCH_HEAD`), si bien que les exécutions suivantes, en
  utilisateur, échouent sur leurs propres dépôts (`cannot open .git/FETCH_HEAD`).
  Les deux sont arrivés d'un seul `sudo` par habitude. Le refus nomme la cause
  et la commande correcte ; seul `uninstall` (et les `service.py`) exige
  l'élévation. Un vrai login root (sans `SUDO_USER`) n'est pas concerné.


## [0.4.2] - 2026-07-22

### Corrigé

- **Le dossier applicatif dédié appartient de nouveau à l'utilisateur du
  service.** Le rétrécissement du `chown` (protection de `/usr/local/bin`) avait
  emporté l'entrée du dossier lui-même : créé sous sudo lors d'une installation
  from-scratch, `/opt/<service>` restait à root, et un module y créant ses
  données d'exécution (cache, sqlite) échouait - silencieusement, avec un
  message d'interface pointant la configuration. Le `chown` couvre l'entrée du
  dossier, jamais récursif, et seulement quand son nom est celui du service.

- **`install` et `update` vérifient que l'utilisateur du service peut écrire
  dans son dossier** (`sudo -u <user> test -w`) et avertissent avec la commande
  de réparation. L'erreur devient bruyante au moment du geste, pour tous les
  services, au lieu d'un symptôme lointain.


## [0.4.1] - 2026-07-22

### Corrigé

- **Le conseil de réparation de `exec-bits` ne se sabote plus lui-même.** Sur un
  premier clone dont les scripts ont perdu le bit d'exécution, `doctor` invitait
  à lancer `./exec-bits.sh` - un wrapper qui a besoin du bit qu'il doit
  justement restaurer, donc `Permission denied` : le remède renvoyait à sa
  propre forme cassée. Le message donne désormais `python3 scripts/exec-bits.py ..`,
  qui s'exécute quel que soit le bit (même raison que `python3 morf.py`), et
  explique pourquoi. Le guide de démarrage documente la sortie, à l'étape
  `doctor` et en dépannage.

- **Le message post-réparation d'`exec-bits` explique comment rendre le
  correctif durable.** Le bit restauré n'est que *mis en scène* ; sans `commit`
  + `push`, le dépôt distant garde le fichier non-exécutable et le prochain
  `pull` retire à nouveau le bit sous Linux. Le message donne la séquence
  parc-wide (`morf.py commit` puis `morf.py push`) et distingue ce geste durable
  d'un simple déstage, qui laisserait le correctif aussi fragile.

- **La promotion vers la production restaure le bit d'exécution automatiquement.**
  `sync-to-morfsystem.ps1` lance `exec-bits.py` après le robocopy : la copie
  Windows perdait le bit à chaque report, obligeant chaque clone neuf du Pi à le
  réparer. Le correctif est désormais à l'unique endroit où le bit se perd. Il
  est mis en scène (fileMode-indépendant, survit au `git add -A` du commit de
  promotion, vérifié) ; le push le rend permanent.

## [0.4.0] - 2026-07-22
### Ajouté

- **`morf uninstall`** - désinstalle un service (`--only`) ou tout le parc, avec
  `--purge` (efface aussi config et binaire) et `--backup` (copie la config
  d'abord). Délègue au `service.py` de chaque projet.
- **`scripts/reset-parc.sh`** - remet une machine à blanc : arrête et désinstalle
  tous les services, retire `/opt`, `/etc` et les vestiges des migrations.
  Empreinte explicite auditable, `--dry-run`, confirmation, ne touche jamais aux
  dépôts.
- **morfdeploy enrichit la config à la mise à jour** : une clé introduite par une
  nouvelle version est ajoutée avec sa valeur par défaut, sans jamais toucher un
  réglage existant ni supprimer de clé. Remplace le `merge-config.py` dupliqué
  par service.
- **`morf build`/`upgrade` sautent les applications GUI sur une machine sans
  affichage** (Linux sans DISPLAY) ; `--gui` force. Reconnues par ce qu'elles
  lient (Qt Widgets), pas par une liste.

### Modifié

- **La configuration des services vit dans `/etc/<service>`**, séparée du binaire
  dans `/opt`. Conforme à la FHS ; migration déclarée, config adoptée jamais
  écrasée.
- **Les scripts shell remplacés par les entrées Python sont supprimés**
  (`morf.sh`/`.ps1`, `config.sh`/`.ps1`, `shared-config`, et les alias). `morf.py`
  et `config.py` sont l'interface unique, toutes plateformes.

### Corrigé

- **Une installation sans configuration à poser échoue désormais** au lieu
  d'enregistrer un service qui redémarre en boucle contre un fichier absent.

### Documentation

- **Guide de démarrage** (`docs/GUIDE-DEMARRAGE.md`) : cycle complet installer →
  configurer → consulter → désinstaller, applications du parc, et chapitre
  philosophie.
- **R5 (modèle de confiance / accès distant)** documenté comme décision ouverte
  dans `docs/ECOSYSTEM-PRINCIPLES.md`, avec les options à peser.

- **`morf.py` replaces `morf.sh` and `morf.ps1`**, which were the same algorithm
  written twice: iterate the projects, run git, read a JSON manifest. Nothing in
  either was platform-specific, so the duplication bought nothing and cost a
  second implementation free to disagree with the first.

  The shell version already called `python3 -c` five times to read the same
  manifest -- one process per project -- and every call site carried a
  `tr -d '
'` to undo the CRLF that Git Bash added on the way back. That
  workaround has no cause left and is gone rather than translated.

  Output is byte-identical to `morf.sh` for `doctor` and `status`, and the exit
  codes match. `--only <project>` is new: it restricts any command to a single
  project.

  Both shell versions stay in place until the Python one has been exercised on
  the Pi.

## [0.3.0] - 2026-07-21

- **`exec-bits` restores the executable bit across the parc**, and `doctor` now
  reports its absence. Forty-six tracked scripts were recorded as `100644`,
  including all five of morfMonitor - among them the `deploy-config.sh` the
  README tells people to run.

  The defect cannot be observed from the machine that creates it. Windows has no
  executable permission, so Git records new files as non-executable; the working
  copy runs fine because `bash script.sh` never consults the bit. The Pi clones
  the same repository, `./script.sh` answers `Permission denied`, and nothing in
  that message points back at Windows.

  So the fix targets the **index mode**, not the filesystem: `chmod` on Windows
  is a no-op Git ignores, while `git update-index --chmod=+x` records 100755 in
  the tree every other clone will see. What counts as runnable is the
  **shebang**, not the extension - that is the author's own statement of intent,
  and it covers `.sh` and `.py` alike without a list of extensions free to drift.

- **`morfTools` gains the `.gitattributes` every other project already had.** It
  was the only repository without one, and the only one whose scripts run on the
  Pi. Nothing had broken yet: its seventeen `.sh` were kept LF by the local
  Git configuration alone, which is not a property of the repository and does not
  travel with a clone. A `.sh` stored with CRLF fails there with
  `bad interpreter: /usr/bin/env bash^M` - the same class of defect as the
  missing bit, invisible from the machine that introduces it.

- **The three meanings of "update" are now documented.** `update` is a pure
  alias of `pull`; `upgrade` pulls **and rebuilds**; a project's own
  `update-service.sh` is the only one that touches an installed service. The
  first two act on sources, so a Pi keeps serving the previous binary after an
  `upgrade` until the project's own script runs.

## [0.2.1] - 2026-07-21

- **`doctor` compares the vendored `VERSION` file too.** It only compared `src`
  and `include`, so seven copies could announce 0.2.1 while carrying the code of
  0.4.1 and the check stayed green. The exclusion was too broad: the vendored
  `CMakeLists.txt` is legitimately adapted to its embedding context, `VERSION`
  is not - it is simply copied, and a copy that lies about its version is worse
  than no version at all, because it is trusted.

## [0.2.0] - 2026-07-21

- **`config` becomes the single entry point for configuration deployment**, on
  both platforms: `config shared <action>` for the parc file, `config deploy
  <project>` for a project's own file. `shared-config` still works and points at
  the new name.

  `deploy` **delegates** to the project's own script rather than learning its
  install directory and service name - the rule that keeps morfTools free of
  business knowledge, and that `morf build` already follows by delegating to
  each project's build system. A project cloned on its own therefore still
  deploys its configuration without morfTools.

  A project name is required rather than defaulting to "all": the command
  overwrites deployed configurations, and doing that to every project because an
  argument was forgotten is not a reasonable default.

- **Fixed a trap in `shared-config`: the source was hard-coded to
  `morfsystem.example.json`.** A clone carrying a real `config/morfsystem.json`
  beside it - which is the normal case - saw `install` silently deploy the
  sample OVER the parc description. Both platforms now prefer the real file and
  fall back to the example, the same rule `deploy-config` already applied.

- `install` shows a capped diff of what it changes. Overwriting a parc
  description without showing what moves is a poor way to be simple.

- Fixed a silent failure in the new dispatcher: under `set -e`, a helper
  returning non-zero inside `$(...)` killed the script **before** the error
  message explaining what was missing. The exit code was right and the user saw
  nothing.

- Added the standard ecosystem documents the project was missing: `VERSION` (first published version, 0.1.0), `LICENSE` (GPL-3.0-only, identical body to every sibling project), `CONTRIBUTING.md`, `ROADMAP.md` and a French `README.fr.md`. morfTools drives the whole parc yet was the only project without a version of its own, so no inventory could include the tool performing it.
- `CONTRIBUTING.md` records two rules that were previously only implicit and had each already been broken once: script output stays in English, and JSON logic stays in Python called by both dispatchers rather than reimplemented in Bash and PowerShell.

- `ecosystem.json` now owns the **port allocation registry** (`ports`), raised to `schemaVersion` 2. The parc plan previously existed only as a `_comment_port` string inside `morfMonitor/config/morfmonitor.example.json`: a component with no authority over the others, holding a partial copy of an ecosystem-wide fact. That copy was already incomplete - it omitted 8789 (morfNotify) and 8787 (the morfBeacon status default) - so a developer consulting it to pick a free port got wrong information with no way to know it.
- Fixed the resulting collision: `morfTemplateService` shipped `http_port: 8799`, the port allocated to morfAnalytics. Every service created through the documented procedure therefore started on an occupied port. The template now uses 8901, inside a `templateRange` (8900-8999) reserved for templates and examples and deliberately outside the 8787-8799 service block, so a clone that has not yet reserved its own port is visibly unfinished instead of silently conflicting.
- `ecosystem.json` also declares the **vendored copies** (`vendored`): the shared libraries copied into `third_party/morf/`, with their canonical source project. The copy strategy itself is unchanged - it is what keeps the build reproducible across Windows, Linux x64 and Raspberry Pi without an external repository.
- `doctor` now runs both ecosystem-wide checks before its per-project pass, through `scripts/ecosystem-check.py`. Ports: registry self-consistency, registry against each declared configuration, and each configuration against the registry so an unmanaged allocation cannot keep the registry green while making it incomplete. Vendored copies: content comparison of `src` and `include` against the canonical project, with line endings normalised so a CRLF-converted copy is not reported as drift.
- The check logic lives in one Python script called by both `morf.sh` and `morf.ps1`. Neither gains a dependency (`morf.sh` already parses the manifest with `python3`, `morf.ps1` already calls `python` for `install`), and a PowerShell reimplementation would let the two checkers disagree.
- Documented the registries, the reserved ranges, the allocation procedure for a new service, and how to resolve reported drift in `docs/ECOSYSTEM-CHECKS.md`.

- Fixed `morf.sh` skipping every project on Windows: python3 emits CRLF on stdout, so project names were read as `Name\r_travail`.
- A project failing no longer aborts the remaining projects silently; failures are collected and reported, and the command exits non-zero.
- `morf.ps1` now checks the exit code of `cmake`, `git` and `pio` instead of chaining with `;`, so a failed configure no longer runs a build against a stale directory.
- `clean` now removes every build directory (`build`, `build-arm64`, `build-mingw`, …) instead of only `build`.
- `build` and `upgrade` no longer fall back to a default `build/` directory when no preset is given: they list the presets declared by the cloned projects, with the number of projects declaring each, and ask which one to use. `commit` prompts for a missing message. Without a terminal, both list the valid values and exit with status 2.
- A preset that a given project does not declare (such as `linux-arm64-cross`) is now reported as `[SKIP]` instead of failing that project.
- All script output is English again: the prompts and failure summaries added with the preset selection were briefly written in French, while every pre-existing message (`[SKIP] … (not cloned)`, `Unknown command`) was in English.
- Documented the sandbox/production mechanism in `README.md`: the tools directory name (`morfTools` vs `morfTools_travail`) decides which projects are driven, which was previously implicit.
- `ecosystem.json` declared `GateWayLab` while the production repository is named `GatewayLab`. The manifest is meant to hold canonical production names, and `doctor` compared them case-sensitively, so the project reported `[WARN] unexpected origin` in production. The manifest now uses `GatewayLab`.
- `doctor` compares the origin URL case-insensitively in both scripts: GitHub resolves repository names case-insensitively, so a spelling difference alone never indicates a wrong remote.

- Corrected synchronization destination resolution: relative paths now resolve next to the sandbox workspace.
- Updated user-facing documentation to use canonical production project names.
- Added a manifest-driven Windows synchronization script that preserves destination Git repositories and never rewrites text globally.
- Made `ecosystem.json` canonical: it contains production component names.
- Renamed the standalone tools project to morfTools.
- Made PowerShell and Bash tools resolve component names consistently in production.
- Replaced the legacy project configuration with root-aware command launchers.
- Documented the portable workspace architecture and remote safety rules.
- Registered GateWayLab and created its GitHub repository.
