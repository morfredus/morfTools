# morfSystem - principes et invariants d'architecture

Ce document énonce les règles qui valent pour **tout le parc**, et non pour un
composant en particulier.

## Pourquoi elles vivent ici

Une règle valable pour l'ensemble ne doit pas être écrite dans un composant qui
n'a autorité sur aucun autre. Le plan d'adressage des ports l'a démontré : il a
vécu dans un commentaire de la configuration de morfMonitor, y est devenu
incomplet, et personne ne pouvait le savoir. Il est désormais dans
`ecosystem.json`, et vérifié par `morf doctor`.

Le même raisonnement s'applique aux invariants d'architecture. morfTools est le
seul artefact qui porte sur le parc entier ; c'est donc ici qu'ils sont
consignés - y compris ceux qui contraignent morfTools lui-même.

Un invariant qui ne vit que dans une conversation n'existe pas. C'est
précisément ainsi qu'une architecture dérive : non par une décision contraire,
mais par une suite de demandes raisonnables auxquelles rien d'écrit ne s'oppose.

---

## Les sept principes fondateurs

1. **Une responsabilité métier = un service.**
2. **Les services sont autonomes.**
3. **Le terrain reste propriétaire de ses données.**
4. **Les consommateurs dépendent de capacités, pas d'identifiants.**
5. **Le partage de code est limité à l'infrastructure ; le métier reste indépendant.**
6. **La reproductibilité prime sur la réduction maximale de duplication.**
7. **L'architecture fonctionne en réseau local, sans dépendance au cloud.**

Ces principes sont le référentiel d'évaluation de l'écosystème. Une proposition
ne se juge pas à sa ressemblance avec ce qui se fait ailleurs, mais à sa
compatibilité avec eux.

---

## Invariant : morfMonitor est un observatoire, pas un portail

morfMonitor peut **découvrir, référencer et présenter** les services de
l'écosystème. Il ne doit **jamais médiatiser leur accès**.

Concrètement, et sans exception :

- pas de proxy HTTP ;
- pas de relais de requêtes ;
- pas de gestion de session ;
- pas de courtier d'authentification ;
- pas d'agrégation de trafic.

Les liens de son interface Web restent de simples `href` pointant directement
vers le service concerné.

### Le test qui tranche

> **Si morfMonitor disparaît, les services continuent de fonctionner à
> l'identique. Seule la facilité de navigation disparaît.**

Cette propriété doit rester vraie. Elle est vérifiable à tout moment : couper
morfMonitor et atteindre chaque service en tapant son adresse. Le jour où cette
manipulation échoue, l'invariant est rompu.

### Pourquoi « observatoire » et pas « portail »

Le vocabulaire n'est pas neutre. Un portail attire progressivement les sessions,
l'authentification, les proxys, les relais et les tableaux de bord agrégés -
chacun défendable isolément. À la fin, il est un point de passage obligatoire,
et donc un point de défaillance unique pour l'accès à tout le reste.

Un observatoire observe, découvre, référence et présente. Il propose un lien
vers les interfaces qui existent. Il ne devient jamais intermédiaire entre
l'utilisateur et un service.

La dérive ne viendra pas d'une décision de principe, mais d'une demande
ponctuelle et raisonnable. C'est à ce moment-là que ce paragraphe doit être
relu.

---

## Invariant : la découverte est déclarative

Un consommateur ne doit connaître **aucune application par son nom**. Il
découvre des services et lit les **capacités** qu'ils déclarent (principe 4).

Ajouter un service à l'écosystème ne doit modifier aucun consommateur existant.

### Répartition heartbeat / HTTP

morfBeacon repose sur **push presence / pull detail**. Cette séparation est
structurante et doit être préservée :

| Où | Quoi | Pourquoi |
| --- | --- | --- |
| Heartbeat UDP | Présence, identité, **capacités** | Diffusé toutes les 15 s par chaque service : doit rester compact et stable. |
| `/status` HTTP | Détail des capacités (chemin, libellé, description…) | Interrogé à la demande : peut évoluer sans toucher au protocole. |

Un service exposant une interface Web déclare donc une **capacité** dans son
heartbeat ; les informations nécessaires à son ouverture vivent derrière
`/status`. Le heartbeat ne devient pas un catalogue de métadonnées.

### Portée : toutes les plateformes

L'objectif est que tout composant morfSystem soit découvert de façon homogène,
quelle que soit sa plateforme - Linux, Windows, Raspberry Pi ou **ESP32**.

Les listes statiques et la configuration spécifique (sondes réseau déclarées
dans `morfsystem.json`) sont un état transitoire, pas la cible. Le protocole
`morfbeacon/1` est du JSON compact en UDP et n'exige aucune dépendance
particulière : un émetteur embarqué est réaliste.

#### Validation (23 juillet 2026)

La découverte distribuée fonctionne sur un environnement **hétérogène**
- Windows, Linux, Raspberry Pi et ESP32 - **sans aucune configuration
manuelle**. Les instances de morfMonitor se découvrent mutuellement, et les
services publiés par le Raspberry Pi apparaissent automatiquement sur Windows
comme l'inverse.

Ce n'est plus une intention : c'est un comportement constaté sur le parc réel,
quatre plateformes simultanées, aucune adresse IP écrite nulle part. La portée
annoncée ci-dessus est donc **éprouvée**, conformément à l'invariant « on ne
promet que ce qu'on peut éprouver ».

Deux corrections ont été nécessaires pour y parvenir, l'une et l'autre nées de
cette confrontation au réel plutôt que d'une revue de code :

- **l'identité d'instance** (`app@host`) sert de clef de découverte : indexées
  par le seul nom, deux machines faisant tourner le même service s'écrasaient
  l'une l'autre ;
- **l'adresse retenue est celle du réseau local**, pas celle du dernier
  datagramme reçu : un émetteur multi-domicilié (WSL, Hyper-V, VPN) s'annonçait
  sur un réseau virtuel injoignable depuis les autres machines.

---

## Invariant : l'accès distant est un composant dédié

L'accès depuis l'extérieur du réseau local sera traité par **un composant
séparé**, dont c'est l'unique responsabilité (principe 1).

Ce composant porte la sécurité, l'authentification et l'établissement de la
connexion. Les services existants - morfMonitor, morfAnalytics, morfNotify,
MeteoHub, GatewayLab et les suivants - **exposent exactement les mêmes
interfaces qu'aujourd'hui** et ignorent totalement qu'ils sont consultés depuis
Internet.

**Aucun mécanisme d'authentification propre à chaque service ne sera
introduit.** L'objectif n'est pas un service centralisé ni un cloud, mais de
retrouver à distance la même expérience que sur le réseau local.

### Ce que cela implique, et qu'il faut avoir en tête

Le modèle « LAN de confiance » n'est pas une propriété de la passerelle : c'en
est une **du parc entier**. Aucun service n'authentifie ses appelants, ce qui
était cohérent tant que rien n'était joignable de l'extérieur.

Dès qu'un chemin distant existe, le composant d'accès devient la **seule** chose
entre Internet et des services qui supposent tout appelant légitime. Et le parc
ne contient pas que des tableaux de bord en lecture :

| Service | Surface d'administration exposée sans authentification |
| --- | --- |
| MeteoHub | Mise à jour OTA du firmware, gestionnaire de fichiers |
| GatewayLab | Configuration WiFi, débogage |
| morfNotify | Émission de courriels et de messages Telegram |

Ce constat ne remet pas en cause le choix - il le qualifie. La séparation des
responsabilités est saine ; en contrepartie, la robustesse du composant d'accès
n'est pas un détail d'implémentation, c'est **la** condition de sûreté du parc.

### Statut : décision ouverte (R5)

Ce qui précède fixe les **contraintes**, pas la solution. Le choix du mécanisme
reste à arbitrer - c'est la recommandation **R5** du rapport d'architecture, le
seul point d'architecture du parc délibérément laissé ouvert, et le **préalable
obligatoire** à toute ligne de code d'accès distant.

Rien ne doit être exposé hors du LAN avant cet arbitrage. Tant qu'il n'a pas eu
lieu, le parc reste sur son modèle « confiance = réseau local », qui est sûr
*parce que* rien n'est joignable de l'extérieur.

Trois familles d'options sont à peser, toutes compatibles avec les contraintes
ci-dessus (composant dédié, aucun changement dans les services) :

| Option | Idée | À mettre en balance |
| --- | --- | --- |
| **VPN** (WireGuard…) | le distant *entre* sur le LAN, rien n'est publié | simple et robuste ; suppose un client VPN sur chaque appareil consultant |
| **Reverse-proxy authentifiant** | une passerelle unique porte TLS + authentification devant les services | accès par simple navigateur ; c'est elle qui devient la surface critique |
| **Composant dédié sur mesure** | un service du parc, écrit pour ce rôle | contrôle total ; le plus de travail, et sa sûreté est celle du parc |

L'arbitrage doit produire : un inventaire de ce que chaque service expose
réellement, le mécanisme retenu avec son coût, et la place exacte de la sécurité.
Il engage la sûreté de **tout** le parc - d'où le choix de ne pas le précipiter.

---

## Invariant : un seul cœur d'orchestration, des mécanismes natifs

L'outillage du parc est écrit **une fois**, en Python. Ce qui est propre à un
système d'exploitation vit derrière une interface étroite, dans un module que
le cœur sélectionne à l'exécution.

Le partage passe la frontière ou ne la passe pas, et la ligne est nette :

| | |
|---|---|
| **Cœur, écrit une fois** | trouver ou compiler le binaire, arrêter ce qui tourne, copier binaire et configurations, remettre au gestionnaire de services |
| **Backend, propre à l'OS** | systemd, services Windows, launchd |

La règle de conception qui rend cette frontière tenable : **le cœur ne demande
jamais sur quel système il tourne**. Un seul module fait ce test ; tout ce qui
est en aval reçoit un backend et n'interroge plus rien. Sans cette discipline,
`platform.system()` reconquiert l'orchestration cas particulier par cas
particulier, et le cœur unique n'est plus qu'une étiquette sur l'ancienne
duplication.

Ce que ça a coûté d'apprendre : six services portaient chacun leur copie des
mêmes quatre étapes, et la dérive était déjà là - `morfAnalytics` lisait le
`MT_APP_DIR` de morfMonitor, `morfSync` documentait une surcharge que rien ne
lisait, et `morfTemplateService` annonçait en en-tête « Installe morfSensor ».

### Ce qui n'appartient pas au cœur

Un mécanisme reste natif quand il *diffère par nature*, pas quand il diffère par
habitude. Un service Windows n'est pas une unité systemd traduite : le
gestionnaire de services attend que le programme le rappelle et annonce son état
sous une trentaine de secondes. Un programme Qt console ne le fait pas - il
s'enregistre sans broncher et échoue au démarrage en erreur 1053, dont le
message ne dit rien de la poignée de main manquante. La stratégie est donc
déclarée par le projet, et réclamer un vrai service sans enveloppe (WinSW, NSSM)
est **refusé à l'installation** plutôt que d'enregistrer un service condamné.

---

## Invariant : on ne promet que ce qu'on peut éprouver

| Plateforme | Statut |
|---|---|
| Windows x64 | supportée |
| Linux x64 | supportée |
| Linux ARM64 (Raspberry Pi) | supportée |
| macOS | **architecture prévue, support non promis** |

macOS a son module. Il lève une exception avec un message qui dit pourquoi, et
ce qu'un contributeur doit écrire pour le compléter. Il ne lance pas des
commandes plausibles dont personne n'a jamais observé les modes d'échec.

C'est un choix, pas un oubli. Un backend à moitié fonctionnel est **pire**
qu'un backend qui refuse : il échoue plus loin, sur une machine que son auteur
ne peut pas atteindre, et la personne qui le rencontre ne peut pas distinguer sa
propre erreur de configuration d'un code jamais éprouvé.

En projet libre, cette honnêteté vaut mieux qu'une case cochée : l'architecture
est prête, seules les plateformes qu'on peut développer *et valider* sont
annoncées. Personne n'attend ce qui n'existe pas, et la porte reste ouverte.

Le corollaire vaut pour toute plateforme future : elle devient « supportée » le
jour où quelqu'un l'exerce sur une vraie machine, pas le jour où le code est
écrit.

Windows a franchi ce seuil le 23 juillet 2026 : installation d'un service par
morfdeploy, démarrage, collecte des ressources et découverte croisée avec le
Raspberry Pi et les ESP32, sur une machine réelle. Les trois défauts révélés ce
jour-là - DLL Qt absentes à l'installation, ressources non collectées faute de
`/proc`, adresse annoncée sur un réseau virtuel - illustrent exactement ce que
cet invariant protège : aucun n'était visible à la lecture du code, tous les
trois se sont manifestés à la première mise en service. Voir la validation de
la découverte distribuée, plus haut.

---

## Invariant : morfTools est une dépendance d'administration, pas d'exécution

C'est la seule dépendance commune du parc, et elle ne vaut que pendant le cycle
de vie - **jamais à l'exécution**. Une fois installés, morfMonitor, morfSync,
morfNotify, morfAnalytics, morfSensor ou n'importe quel service démarrent avec
la machine, se découvrent par morfBeacon et remplissent leur mission sans que
morfTools soit présent. **Retirer morfTools d'une machine n'arrête aucun service
déjà installé.**

morfTools n'intervient que pour l'administration :

| | |
|---|---|
| cloner les dépôts | `morf clone` |
| vérifier la cohérence du parc | `morf doctor` |
| compiler | `morf build` |
| installer, mettre à jour, désinstaller un service ou tout le parc | `morf install` / `service.py` / `morf uninstall` |
| migrer une ancienne installation | déclaré dans les manifestes, appliqué à l'install |
| gérer la configuration partagée | `config shared` |

Le test qui tranche : **coupez morfTools, et rien de ce qui tourne ne s'arrête.**
Comme pour l'observatoire, l'absence du composant central ne retire qu'un
confort d'administration, jamais une fonction.

La distinction dicte où vit chaque chose. Ce qui relève de l'exécution est
**embarqué** dans le service (le binaire, sa config, sa copie vendorée de
morfBeacon et de morfdeploy) : un clone isolé s'installe et tourne sans aucun
voisin. Ce qui relève de l'administration est **centralisé** dans morfTools,
pour n'exister qu'une fois plutôt qu'être recopié dans chaque projet - la
duplication d'un `merge-config.py` par service était exactement le travers que
cette frontière corrige.

Conséquence pratique : ajouter un service ne modifie plus les outils centraux.
Il fournit un manifeste décrivant ses besoins, morfTools l'orchestre à partir de
cette déclaration, et le service reste autonome une fois posé. **Administration
centralisée, exécution distribuée et autonome.**

---

## Ce que ces invariants ne disent pas

Ils fixent des frontières, pas des solutions. Le choix des technologies, la
forme des interfaces, le rythme des évolutions restent libres. Un invariant
n'existe que pour être opposé à une proposition qui, prise isolément, paraîtrait
raisonnable.
