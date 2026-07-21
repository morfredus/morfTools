# morfSystem — principes et invariants d'architecture

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
consignés — y compris ceux qui contraignent morfTools lui-même.

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
l'authentification, les proxys, les relais et les tableaux de bord agrégés —
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
quelle que soit sa plateforme — Linux, Windows, Raspberry Pi ou **ESP32**.

Les listes statiques et la configuration spécifique (sondes réseau déclarées
dans `morfsystem.json`) sont un état transitoire, pas la cible. Le protocole
`morfbeacon/1` est du JSON compact en UDP et n'exige aucune dépendance
particulière : un émetteur embarqué est réaliste.

---

## Invariant : l'accès distant est un composant dédié

L'accès depuis l'extérieur du réseau local sera traité par **un composant
séparé**, dont c'est l'unique responsabilité (principe 1).

Ce composant porte la sécurité, l'authentification et l'établissement de la
connexion. Les services existants — morfMonitor, morfAnalytics, morfNotify,
MeteoHub, GatewayLab et les suivants — **exposent exactement les mêmes
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

Ce constat ne remet pas en cause le choix — il le qualifie. La séparation des
responsabilités est saine ; en contrepartie, la robustesse du composant d'accès
n'est pas un détail d'implémentation, c'est **la** condition de sûreté du parc.

---

## Ce que ces invariants ne disent pas

Ils fixent des frontières, pas des solutions. Le choix des technologies, la
forme des interfaces, le rythme des évolutions restent libres. Un invariant
n'existe que pour être opposé à une proposition qui, prise isolément, paraîtrait
raisonnable.
