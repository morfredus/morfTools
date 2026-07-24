# Premier test de morfSystem — demande de retour

Ce document s'adresse à une personne qui **ne connaît pas** morfSystem et qui
accepte d'en tenter l'installation depuis zéro, en suivant
[GUIDE-DEMARRAGE.md](GUIDE-DEMARRAGE.md).

Merci d'avance. Ce test est le seul que le projet n'a jamais subi : tout a été
éprouvé jusqu'ici par son auteur, qui sait déjà ce qu'il faut faire — et qui est
donc la personne la moins capable de voir ce qui manque.

---

## Ce qui est demandé

**Un retour honnête, pas un retour aimable.**

Un « c'était bien » ne sert à rien. Un « je n'ai pas compris ce que faisait
cette commande » vaut une journée de travail. Les remarques utiles sont
précisément celles qu'on hésite à écrire :

- « je ne voyais pas à quoi ça servait » ;
- « j'ai cru que ça avait échoué » ;
- « j'ai fait autre chose que ce qui était écrit, sans savoir pourquoi » ;
- « j'ai abandonné ici ».

Aucune de ces phrases n'est un reproche. Chacune désigne un endroit où le
document suppose quelque chose que le lecteur n'a pas.

Il n'y a **rien à ménager**. Le retour ne sera pas discuté ni justifié : un
malentendu constaté est un fait, même si l'auteur pense que « c'était pourtant
écrit ». Si c'était écrit et que ça n'a pas été compris, c'est le document qui
est en cause.

---

## Deux règles qui font la valeur du test

### 1. Ne demander d'aide à personne

Ni à l'auteur, ni à quelqu'un d'autre. Chercher sur internet est permis — c'est
ce que ferait n'importe qui.

**Chaque fois qu'une question surgit, la noter au lieu de la poser.** Ces
questions sont le résultat principal du test : chacune correspond à un passage
manquant de la documentation. Une question posée à l'auteur est une information
perdue.

Si le blocage est total et que le test s'arrête là, c'est un **résultat**, pas
un échec. Le noter et s'arrêter.

### 2. Ne pas corriger le tir mentalement

Il est tentant de deviner ce qui était voulu et de faire « ce qu'il faut ». Ce
réflexe efface justement le défaut. Suivre ce qui est **écrit**, littéralement,
et noter l'écart quand le résultat surprend.

---

## Contexte du test

Quelques lignes suffisent.

| | |
|---|---|
| Machine et système | *(ex. Raspberry Pi 4, Raspberry Pi OS 64 bits)* |
| Aisance avec un terminal Linux | *(aucune / j'y touche parfois / à l'aise)* |
| Expérience de compilation C++ ou de services systemd | *(aucune / un peu / oui)* |
| Temps total passé | |
| Le test est-il allé jusqu'au bout ? | |

---

## Pendant l'installation

Pour chaque étape du guide : ce qui s'est passé, et surtout ce qui a manqué.

### Avant de commencer — sections 1 et 2 du guide

- Après lecture de la section 1, **qu'attendiez-vous d'obtenir** à la fin ?
- La réponse était-elle claire *avant* de lancer la moindre commande ?
- La liste des prérequis (section 2) était-elle complète ? Qu'a-t-il fallu
  installer qui n'y figurait pas ?

### Étape 1 — Récupérer les projets

- Le premier `clone` a-t-il fonctionné du premier coup ?
- Ce qui a été téléchargé était-il compréhensible (pourquoi *tous* ces
  projets) ?

### Étape 2 — Vérifier la cohérence (`doctor`)

- La sortie de `doctor` était-elle lisible ? Qu'a-t-elle affiché ?
- Un avertissement a-t-il été pris pour une erreur, ou l'inverse ?
- Le cas échéant, le message sur les **bits d'exécution** était-il suivable
  sans aide extérieure ?

### Étape 3 — Compiler

- Durée. Est-ce qu'à un moment le doute s'est installé (« est-ce que c'est
  planté ? »).
- Des projets ont-ils été sautés ? Cela avait-il l'air normal ou inquiétant ?

### Étape 4 — Installer les services

- **Le choix des services à installer était-il clair ?** Comment a-t-il été
  fait ?
- Un service a-t-il été installé sans savoir à quoi il servait ?
- Un service a-t-il été **omis** faute d'avoir compris qu'il fallait
  l'installer ?
- Le recours à `sudo` était-il expliqué ?

### Étape 5 — Vérifier

- Comment savoir que « ça marche » ? La réponse était-elle évidente ?
- L'interface web a-t-elle été atteinte du premier coup ? Sinon, qu'a-t-il
  fallu chercher ?

### Configuration — section 4

C'est la section que le guide lui-même annonce comme « le point où tout le monde
se perd ». Est-ce le cas ?

- La distinction entre **le fichier du dépôt** et **le fichier lu par le
  service** était-elle claire ? À quel moment ?
- Un fichier a-t-il été modifié sans effet ? Combien de temps avant de
  comprendre pourquoi ?
- La phrase « déclarer, c'est s'attendre » a-t-elle un sens après lecture ?

---

## Les questions qui comptent le plus

Si le temps manque pour tout le reste, **répondre au moins à celles-ci**.

### 1. Le point d'abandon

> À quel moment auriez-vous arrêté si vous n'aviez pas accepté de rendre
> service ?

Une seule réponse, précise. C'est la question la plus utile du document.

### 2. Les questions non posées

> Lister les questions notées pendant le test, dans l'ordre où elles sont
> venues.

Même — surtout — celles qui semblent naïves. Une question « bête » qui vient à
l'esprit d'un lecteur est un défaut de la documentation, jamais du lecteur.

### 3. Les mots incompris

> Quels termes ont été rencontrés sans être compris ?

Par exemple : *parc*, *service*, *unité*, *manifeste*, *heartbeat*, *beacon*,
*preset*, *vendoré*, *promotion*… La liste réelle est plus intéressante que
celle-ci.

### 4. L'écart entre l'attendu et l'obtenu

> Y a-t-il eu un moment où le résultat obtenu ne correspondait pas à ce qui
> était attendu, **même quand tout fonctionnait** ?

Ces moments-là ne produisent aucune erreur et ne se voient donc jamais dans les
journaux. Ils ne se découvrent que comme ceci.

### 5. Le silence inquiétant

> Y a-t-il eu un moment où rien ne s'affichait et où il était impossible de
> savoir si le système travaillait, attendait, ou avait échoué ?

### 6. La correction unique

> Si une seule chose pouvait être corrigée avant le prochain test, laquelle ?

---

## Après le test

- Sauriez-vous **réinstaller** sans relire le guide ?
- Sauriez-vous **désinstaller** proprement ?
- Sauriez-vous expliquer à quelqu'un d'autre à quoi sert morfSystem ?
- Y a-t-il quelque chose que vous auriez aimé savoir **avant** de commencer ?

---

## Ce qui n'est pas demandé

Pour éviter du travail inutile :

- **Aucun correctif.** Décrire suffit ; corriger fait disparaître la trace.
- **Aucune reformulation de la documentation.** Signaler qu'un passage est
  obscur a plus de valeur que de proposer une meilleure phrase.
- **Aucun jugement sur l'architecture.** Le sujet ici est la **première
  expérience**, pas la conception. Les questions d'architecture sont bienvenues,
  mais séparément.

---

## Comment renvoyer le retour

**Par une issue GitHub**, sur le dépôt morfTools :

<https://github.com/morfredus/morfTools/issues/new?template=premier-test.md>

Le modèle **Premier test de morfSystem** reprend les questions prioritaires
ci-dessus. Ouvrir l'issue *avant* de commencer et la compléter au fil de l'eau
fonctionne mieux que tout écrire à la fin, de mémoire.

Plusieurs issues valent mieux qu'une seule très longue : un blocage précis dans
son propre fil se traite, se référence et se clôt, là où il se noierait au
milieu d'un compte rendu.

Deux points qui pèsent plus que la forme :

- **Les notes brutes sont préférables à un compte rendu rédigé.** La formulation
  immédiate d'un agacement dit plus que sa version polie une heure plus tard.
  Les coller telles quelles.
- **Copier les messages d'erreur littéralement**, en entier. Une erreur
  reformulée perd souvent la partie qui aurait permis de la comprendre. Une
  capture d'écran fait aussi bien.

Aucune mise en forme n'est attendue. Un retour mal écrit et sincère vaut mieux
qu'un retour soigné et prudent.
