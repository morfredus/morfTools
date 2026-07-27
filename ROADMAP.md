# Roadmap - morfTools

morfTools administre l'écosystème morfSystem sans rien connaître de son métier.
Il clone, compile, met à jour et diagnostique des projets déclarés dans un
manifeste, et il détient les registres qui font autorité à l'échelle du parc :
plan d'adressage des ports, inventaire des copies vendorées.

Sa direction tient en une phrase : **rendre vérifiable ce qui repose
aujourd'hui sur la vigilance.**

## Pistes

- **`morf versions` - inventaire des versions du parc.** Les quatorze projets
  portent désormais tous un fichier `VERSION` faisant autorité, y compris les
  deux projets embarqués dont la version était écrite en dur dans
  `platformio.ini`. Rien n'exploite encore cette uniformité : une commande
  listant version déclarée, version compilée et dernier tag Git dirait d'un
  coup d'œil ce qui est déployé et ce qui a dérivé.

- **Attribution assistée des ports.** Le registre est vérifié, il n'est pas
  encore *serviable* : réserver un port se fait toujours à la main. Une
  commande proposant le premier port libre du bloc de service et écrivant
  l'entrée supprimerait l'étape où l'on recopie le port du voisin.

- **Tests de contrat.** C'est la lacune la plus structurante de l'écosystème.
  Un système dont la cohésion repose sur des contrats - enveloppe de
  synchronisation, protocole `morfbeacon/1`, schémas JSON des API - voit
  aujourd'hui ces contrats vérifiés par la seule exécution manuelle. Un
  datagramme de référence rejoué par les implémentations C++ et Python figerait
  le protocole ; un schéma de réponse d'API attraperait les divergences entre
  ce qu'un service produit et ce que ses consommateurs lisent.

- **Intégration continue.** `doctor` sort déjà en code non nul et se prête à
  une étape de CI ou à un crochet de pré-envoi.

- **Rapport de filiation du squelette.** Les cinq services partagent une
  ossature issue de `morfTemplateService`, et l'harmonisation des noms rend
  enfin la comparaison mécanique possible. Un rapport **informatif** dirait où
  chaque service a divergé - utile pour aller chercher ailleurs un défaut
  d'infrastructure trouvé quelque part. Voir les non-objectifs : ce serait un
  rapport, jamais un contrôle de conformité.

## Non-objectifs

- **Aucun code métier.** Une commande qui aurait besoin de savoir ce que *fait*
  un projet appartient à ce projet, pas ici.

- **Pas de gestionnaire de paquets.** Les bibliothèques communes restent
  recopiées dans leurs consommateurs. Ce choix garantit une compilation
  identique sous Windows, Linux x64 et Raspberry Pi sans dépendre d'un dépôt
  externe : la reproductibilité prime sur la réduction de duplication. Le rôle
  de morfTools est de **vérifier** ces copies, pas de les supprimer.

- **Pas de contrôle de conformité du squelette de service.**
  `morfTemplateService` est un gabarit de création, pas un framework
  d'exécution. Les services sont autonomes et évoluent indépendamment : la
  divergence est l'état attendu. Un contrôle qui la signalerait serait rouge en
  permanence et pousserait vers une uniformité que l'architecture refuse.

- **Pas de remplacement de Git.** morfTools enchaîne des commandes Git sur
  plusieurs dépôts ; il n'ajoute ni sa propre notion de branche, ni son propre
  historique.

- **Pas d'interface.** L'administration se fait en ligne de commande, sur une
  machine de développement comme en SSH sur un Raspberry Pi.
