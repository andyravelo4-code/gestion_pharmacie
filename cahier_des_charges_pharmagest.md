# Cahier des charges complet — Application web de gestion de pharmacie avec Django

**Projet :** PHARMAGEST  
**Sous-titre :** Conception et développement d'une application web de gestion pharmaceutique  
**Technologies clés :** Python, Django, SQLite, Bootstrap

---

## 1. Présentation générale du projet

### 1.1. Intitulé du projet
Conception et réalisation d'une application web de gestion d'une pharmacie avec Django.

### 1.2. Contexte
La gestion d'une pharmacie nécessite le suivi rigoureux des médicaments, des fournisseurs, des achats, des ventes, des stocks, des clients et des utilisateurs. Une gestion manuelle ou reposant sur des fichiers séparés peut entraîner des erreurs de saisie, des ruptures de stock, des pertes liées aux produits périmés et des difficultés à calculer les recettes.

Le projet **PharmaGest** consiste à développer une application web centralisée qui permet de gérer ces opérations à partir d'une interface simple, sécurisée et accessible depuis un navigateur.

### 1.3. Objectif général
Développer une application web avec Django permettant d'automatiser les principales opérations d'une pharmacie, depuis l'approvisionnement en médicaments jusqu'à leur vente, tout en assurant la traçabilité des mouvements de stock.

### 1.4. Objectifs spécifiques
L'application devra permettre de :
* Gérer les médicaments, leurs catégories, leurs photos et leurs caractéristiques.
* Gérer les fournisseurs et les clients.
* Enregistrer les achats et les réceptions de marchandises.
* Suivre les quantités disponibles et les mouvements de stock.
* Enregistrer les ventes, les paiements et les retours autorisés.
* Gérer les utilisateurs, les rôles et les permissions.
* Détecter les stocks faibles et les médicaments proches de la péremption.
* Produire des reçus, des factures et des rapports PDF.
* Consulter les statistiques et l'historique des opérations.
* Sécuriser les données et assurer la sauvegarde de la base de données.

---

## 2. Périmètre du projet

Le projet couvre la gestion administrative et commerciale d'une pharmacie. Il ne remplace pas un logiciel de prescription médicale ni les obligations réglementaires applicables à une pharmacie réelle.

| Inclus dans le projet | Hors périmètre initial |
| :--- | :--- |
| CRUD des médicaments avec photos | Diagnostic médical |
| Gestion des achats et fournisseurs | Prescription automatique |
| Gestion des ventes et clients | Consultation médicale |
| Gestion des stocks, lots et péremptions | Fabrication industrielle de médicaments |
| Gestion des utilisateurs et des droits | Connexion obligatoire à un système national |
| Rapports, factures et statistiques | Comptabilité générale complète |
| Sauvegarde et sécurité | Application mobile native |

> *Note : Les fonctions hors périmètre pourront être ajoutées ultérieurement si le projet évolue.*

---

## 3. Identification des acteurs

L'application devra proposer plusieurs profils d'utilisateurs, avec des autorisations différentes.

| Acteur | Responsabilités |
| :--- | :--- |
| **Administrateur** | Gérer les utilisateurs, les paramètres, les médicaments et consulter toutes les opérations autorisées. |
| **Pharmacien responsable** | Contrôler les médicaments, les lots, les péremptions, les achats et les ventes selon ses permissions. |
| **Gestionnaire de stock** | Gérer les fournisseurs, les commandes, les réceptions et les inventaires autorisés. |
| **Caissier** | Enregistrer les ventes, les paiements et imprimer les reçus. |
| **Responsable de gestion** | Consulter les statistiques, les recettes et les rapports autorisés. |

> *Note : Un même utilisateur pourra cumuler plusieurs fonctions uniquement si l'administrateur lui accorde les permissions correspondantes.*

---

## 4. Description détaillée des modules fonctionnels

### 4.1. Module A — Authentification et gestion des utilisateurs
L'application devra comporter une page de connexion sécurisée.

**Fonctionnalités requises :**
* Connexion et déconnexion.
* Création et modification des comptes par les personnes autorisées.
* Gestion des rôles et des permissions.
* Modification du mot de passe et procédure de réinitialisation sécurisée.
* Activation ou désactivation d'un compte.
* Protection des pages contre les utilisateurs non autorisés.
* Enregistrement de l'auteur et de la date des opérations importantes.

Les mots de passe devront être gérés par le système d'authentification Django, sans stockage en clair.

### 4.2. Module B — Gestion des médicaments
Ce module constitue une fonctionnalité centrale du système.

**Informations à enregistrer pour chaque médicament :**

| Champ | Type ou règle |
| :--- | :--- |
| **Identifiant** | Clé primaire automatique |
| **Nom commercial** | Texte obligatoire |
| **Dénomination générique** | Texte facultatif ou obligatoire selon la politique retenue |
| **Catégorie** | Relation avec la table Catégorie |
| **Forme pharmaceutique** | Comprimé, sirop, gélule, etc. |
| **Dosage** | Texte, par exemple 500 mg |
| **Laboratoire** | Nom du fabricant |
| **Code-barres** | Valeur unique lorsqu'elle est renseignée |
| **Photo** | Image facultative |
| **Prix d'achat** | Montant décimal positif |
| **Prix de vente** | Montant décimal positif |
| **Seuil d'alerte** | Quantité minimale souhaitée |
| **Statut** | Actif ou archivé |
| **Date de création** | Automatique |

**Opérations CRUD :**
* **Create :** ajouter un médicament.
* **Read :** afficher la liste et les détails.
* **Update :** modifier les informations.
* **Delete :** supprimer uniquement si cela ne compromet pas l'historique ; sinon, archiver.

Les listes devront proposer une recherche par nom ou code-barres, un filtrage par catégorie, un tri et une pagination.

### 4.3. Module C — Gestion des catégories
Une catégorie regroupe les médicaments ayant une classification commune (exemples pédagogiques : antalgiques, vitamines, antiseptiques et autres catégories appropriées).

**Fonctionnalités :**
* Ajouter une catégorie.
* Afficher les catégories.
* Modifier une catégorie.
* Rechercher une catégorie.
* Empêcher la suppression d'une catégorie utilisée par des médicaments.

### 4.4. Module D — Gestion des fournisseurs
Chaque fournisseur devra disposer d'une fiche comprenant :
* Identifiant.
* Nom ou raison sociale.
* Adresse.
* Téléphone.
* Adresse e-mail.
* Numéro fiscal ou identifiant professionnel, si applicable.
* Contact principal.
* Statut actif ou inactif.

**Fonctionnalités :**
* CRUD complet des fournisseurs.
* Recherche par nom et téléphone.
* Consultation de l'historique des achats.
* Consultation des montants des commandes et des réceptions.
* Désactivation d'un fournisseur sans effacer les anciennes opérations.

### 4.5. Module E — Gestion des clients
L'application pourra conserver les informations nécessaires à la gestion commerciale :
* Nom du client, si nécessaire.
* Téléphone et coordonnées facultatives.
* Historique des ventes autorisées.
* Statut du compte.

Une vente comptoir pourra être effectuée pour un client non identifié, lorsque la réglementation le permet. Les données personnelles devront être limitées au strict nécessaire et protégées contre les accès non autorisés.

### 4.6. Module F — Gestion des achats
Ce module gère l'approvisionnement de la pharmacie.

**Fonctionnalités :**
1. Sélectionner un fournisseur.
2. Créer une commande d'achat.
3. Ajouter plusieurs médicaments à la commande.
4. Indiquer les quantités et les prix d'achat.
5. Calculer automatiquement le montant total.
6. Enregistrer la commande en brouillon.
7. Valider la commande.
8. Réceptionner tout ou partie des marchandises.
9. Consulter l'historique des achats.
10. Générer un bon de commande ou un document de réception.

> *Règle importante : Une commande et une réception devront être distinguées : la création d'une commande ne doit pas augmenter automatiquement le stock. Le stock augmente lors de la validation de la réception effective.*

**Statuts possibles d'une commande :**
* Brouillon.
* Commandée.
* Partiellement réceptionnée.
* Entièrement réceptionnée.
* Annulée.

Toute modification du stock devra être associée à un mouvement traçable.

### 4.7. Module G — Gestion des stocks
Le stock doit être calculé à partir des entrées, des sorties et des corrections autorisées.

**Fonctionnalités :**
* Consulter le stock disponible.
* Enregistrer les réceptions d'achat.
* Déduire les quantités vendues.
* Enregistrer les retours et les corrections d'inventaire autorisées.
* Consulter l'historique des mouvements.
* Détecter les ruptures de stock.
* Détecter les stocks inférieurs au seuil d'alerte.
* Réaliser un inventaire physique.
* Signaler les produits périmés et ceux dont la date de péremption approche.

**Gestion des lots :** Chaque lot devra comporter un numéro de lot, une date de péremption et une quantité reçue. Une vente devra être rattachée au lot réellement délivré.  
La méthode **FEFO** (*First Expired, First Out*) sera privilégiée : les lots dont la date de péremption est la plus proche sont utilisés en priorité, sous réserve qu'ils soient encore valides et délivrables. Un médicament périmé ou bloqué ne devra pas être proposé à la vente.

### 4.8. Module H — Gestion des ventes
Le module de vente devra proposer une interface de caisse simple et rapide.

**Déroulement d'une vente :**
1. Rechercher un médicament ou scanner son code-barres.
2. Sélectionner le lot approprié.
3. Saisir la quantité.
4. Vérifier le prix de vente autorisé.
5. Calculer le sous-total de chaque ligne.
6. Calculer le total général.
7. Choisir le mode de paiement.
8. Confirmer la vente.
9. Enregistrer la sortie de stock.
10. Générer le reçu.

Les lignes de vente devront conserver le prix appliqué au moment de la transaction, afin que les anciennes ventes ne changent pas lorsqu'un prix de médicament est modifié.

**Règles de gestion obligatoires :**
* Refuser une quantité nulle ou négative.
* Refuser une quantité supérieure au stock disponible.
* Ne pas vendre un lot périmé ou bloqué.
* Empêcher la validation en double d'une même vente.
* Enregistrer l'utilisateur ayant réalisé la transaction.
* Effectuer la validation de la vente et la sortie de stock dans une transaction atomique.

Les modes de paiement pourront inclure les espèces, le mobile money et les autres moyens autorisés par la pharmacie. Un paiement électronique ne devra être considéré comme confirmé qu'après vérification fiable de son statut.

### 4.9. Module I — Retours et annulations
Les retours ne devront pas être traités comme une simple suppression de vente.

**Fonctionnalités :**
* Enregistrer la vente d'origine.
* Identifier le médicament, le lot et la quantité retournée.
* Enregistrer le motif du retour.
* Enregistrer l'utilisateur responsable.
* Appliquer la procédure de remboursement autorisée.
* Réintégrer le stock uniquement lorsque le produit est éligible à la remise en stock.
* Conserver une trace de la transaction initiale.

Une vente validée ne sera pas supprimée silencieusement. Une annulation ou une correction devra être réalisée par une opération compensatoire traçable.

### 4.10. Module J — Tableau de bord
Le tableau de bord présentera les indicateurs essentiels (calculés à partir des données réelles, et non saisis manuellement) :
* **Médicaments actifs :** Nombre
* **Ventes du jour :** Montant
* **Stocks faibles :** Nombre
* **Péremptions proches :** Nombre

Le tableau de bord devra aussi présenter :
* Les ventes sur une période sélectionnée.
* Les achats sur une période sélectionnée.
* Les produits les plus vendus.
* Les alertes de stock.
* Les lots périmés ou proches de la péremption.
* Les statistiques accessibles selon le rôle de l'utilisateur.

> *Note comptable : Le chiffre d'affaires devra être distingué des encaissements et des bénéfices. La marge commerciale ne devra pas être présentée comme un bénéfice net si les autres charges ne sont pas prises en compte.*

### 4.11. Module K — Factures, reçus et rapports
Le système devra générer des documents PDF avec **ReportLab**.

**Documents prévus :**
* Reçu de vente.
* Facture lorsque requise.
* Bon de commande.
* Bon de réception.
* Rapport de stock.
* Rapport des ventes.
* Rapport des achats.
* Liste des produits proches de la péremption.

Chaque document devra comporter les informations nécessaires, telles que le numéro du document, la date, les lignes, les quantités, les prix, le total et les informations de la pharmacie. Les mentions légales, fiscales et comptables seront adaptées aux règles applicables à Madagascar ou au territoire d'exploitation.

---

## 5. Règles de gestion générales

Les règles suivantes constituent des exigences essentielles du projet.

| Code | Règle |
| :--- | :--- |
| **RG01** | Chaque médicament possède un identifiant unique. |
| **RG02** | Le code-barres, lorsqu'il est renseigné, ne peut pas être dupliqué. |
| **RG03** | Les prix et les quantités doivent être validés côté serveur. |
| **RG04** | Une commande ne modifie pas le stock avant la réception. |
| **RG05** | Une réception validée augmente le stock une seule fois. |
| **RG06** | Une vente validée diminue le stock une seule fois. |
| **RG07** | Le stock ne peut pas devenir négatif. |
| **RG08** | Les lots périmés ou bloqués sont exclus de la vente. |
| **RG09** | Les opérations importantes conservent leur auteur, leur date et leur historique. |
| **RG10** | Les ventes et les achats validés ne sont pas supprimés sans traçabilité. |
| **RG11** | Les utilisateurs ne peuvent accéder qu'aux fonctions autorisées. |
| **RG12** | Les documents historiques conservent les prix appliqués au moment de l'opération. |

---

## 6. Modèle conceptuel de données

Le système devra s'appuyer sur une base relationnelle.

### Principales entités et relations
* **CATEGORIE** (`id`, `nom`, `description`) — *Une catégorie regroupe plusieurs médicaments.*
* **MEDICAMENT** (`id`, `nom`, `dosage`, `forme`, `photo`, `prix_achat`, `prix_vente`) — *Un médicament peut avoir plusieurs lots.*
* **LOT_STOCK** (`id`, `medicament_id`, `numero_lot`, `date_peremption`, `quantite`)
* `FOURNISSEUR` $\rightarrow$ `ACHAT` $\rightarrow$ `LIGNE_ACHAT` $\rightarrow$ `MEDICAMENT / LOT_STOCK`
* `CLIENT` $\rightarrow$ `VENTE` $\rightarrow$ `LIGNE_VENTE` $\rightarrow$ `MEDICAMENT / LOT_STOCK`
* `UTILISATEUR` $\rightarrow$ commandes, réceptions, ventes, corrections et journal d'audit

*(Schéma fonctionnel simplifié. Les clés étrangères, les contraintes et les relations détaillées seront définies lors de la conception Django.)*

### 6.1. Tables principales à prévoir

| Table | Rôle |
| :--- | :--- |
| `Categorie` | Classification des médicaments |
| `Medicament` | Informations générales sur les produits |
| `Fournisseur` | Coordonnées des fournisseurs |
| `Client` | Informations clients nécessaires |
| `LotStock` | Lots, péremption et quantités |
| `CommandeAchat` | En-tête d'une commande |
| `LigneAchat` | Médicaments et quantités commandées |
| `ReceptionAchat` | Réception réelle des marchandises |
| `MouvementStock` | Historique des entrées et sorties |
| `Vente` | En-tête d'une transaction |
| `LigneVente` | Médicaments, lots, quantités et prix appliqués |
| `Paiement` | Paiements et statuts |
| `RetourVente` | Retours et corrections |
| `Utilisateur` | Comptes, rôles et permissions |
| `JournalAudit` | Traçabilité des opérations sensibles |

> *Note : Les modèles pourront être complétés par des tables de lignes de réception, de remboursement ou de paiement partiel selon les besoins retenus.*

---

## 7. Architecture technique

L'application utilisera l'architecture **MVT** (*Model-View-Template*) de Django :
* **Model :** représente les données, les relations et les règles métier.
* **View :** traite les requêtes, vérifie les permissions et exécute les opérations.
* **Template :** affiche les pages HTML et les résultats.
* **URLconf :** associe les adresses web aux vues.
* **Forms :** valide les données saisies par les utilisateurs.
* **Admin :** permet à l'administrateur d'accéder aux données autorisées.

### Structure prévisionnelle
```text
PharmaGest/
├── manage.py
├── config/
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── utilisateurs/
├── medicaments/
├── fournisseurs/
├── clients/
├── achats/
├── stock/
├── ventes/
├── rapports/
├── templates/
├── static/
│   ├── css/
│   ├── js/
│   └── images/
├── media/
└── requirements.txt
```
*(La liste des applications est indicative et pourra être adaptée pour éviter de multiplier inutilement les modules.)*

### Technologies retenues

| Composant | Choix |
| :--- | :--- |
| **Langage** | Python |
| **Framework serveur** | Django |
| **Base de développement** | SQLite |
| **Base de production recommandée** | PostgreSQL |
| **Interface** | HTML5, CSS3, Bootstrap |
| **Gestion des photos** | Pillow et stockage média |
| **Documents PDF** | ReportLab |
| **Tests** | Django TestCase |
| **Gestion de versions** | Git |

---

## 8. Exigences non fonctionnelles

### 8.1. Sécurité
* Protection CSRF des formulaires.
* Validation serveur des données.
* Contrôle des permissions sur chaque vue.
* Vérification du type et de la taille des fichiers image.
* Protection contre les accès directs aux fonctions interdites.
* Utilisation de HTTPS en production.
* Conservation des secrets dans des variables d'environnement.
* Sauvegardes protégées et testées.
* Journalisation des opérations sensibles.
* Prévention des doubles ventes et des doubles réceptions.

### 8.2. Performance et fiabilité
* Recherche et pagination pour les listes volumineuses.
* Utilisation de transactions de base de données pour les ventes et réceptions.
* Vérification de la disponibilité du stock au moment de la validation.
* Gestion des erreurs avec des messages compréhensibles.
* Sauvegarde et restauration testées avant la mise en production.

### 8.3. Ergonomie
* Interface en français.
* Menu de navigation clair.
* Formulaires avec messages d'erreur.
* Confirmation avant les opérations sensibles.
* Interface adaptée aux ordinateurs, tablettes et téléphones (Responsive).
* Alertes visuelles pour les ruptures et les péremptions.

---

## 9. Tests et critères de validation

Le projet sera considéré comme fonctionnel lorsque les scénarios suivants auront été vérifiés :

| Test | Résultat attendu |
| :--- | :--- |
| Ajouter un médicament avec photo | Médicament enregistré et photo affichée |
| Modifier un médicament | Informations mises à jour |
| Supprimer ou archiver un médicament | Historique protégé |
| Réceptionner un achat de 20 unités | Stock augmenté de 20 une seule fois |
| Vendre 3 unités | Stock diminué de 3 une seule fois |
| Vendre plus que le stock disponible | Vente refusée |
| Vendre un lot périmé | Vente refusée |
| Tenter un accès sans permission | Accès interdit |
| Générer un reçu PDF | Document lisible avec les bons totaux |
| Enregistrer deux validations simultanées | Aucune sortie de stock en double ni stock négatif |
| Restaurer une sauvegarde | Données récupérées correctement |

Les tests automatisés devront couvrir les modèles, les formulaires, les permissions, les calculs et les opérations de stock.

---

## 10. Planning prévisionnel

Voici un planning pédagogique estimatif sur huit semaines, à adapter au niveau de l'équipe et à la disponibilité des développeurs.

| Semaine | Travaux |
| :---: | :--- |
| **1** | Analyse, installation et architecture du projet |
| **2** | Modèles, base de données et administration |
| **3** | CRUD médicaments, catégories et photos |
| **4** | Authentification, utilisateurs et permissions |
| **5** | Fournisseurs, achats, lots et stocks |
| **6** | Ventes, caisse, paiements et retours |
| **7** | Tableau de bord, PDF et rapports |
| **8** | Tests, sécurité, documentation et déploiement |

---

## 11. Livrables attendus

À la fin du projet, les livrables devront comprendre :
1. Le code source complet du projet Django.
2. La base de données et les migrations.
3. Les modèles et leurs relations.
4. Les pages HTML, CSS et Bootstrap.
5. Les formulaires CRUD avec photos.
6. Les modules d'achats, de ventes et de stock.
7. La gestion des utilisateurs et des permissions.
8. Les rapports PDF et le tableau de bord.
9. Un jeu de données fictives pour les tests.
10. Les tests automatisés.
11. Un manuel d'installation et de configuration.
12. Un guide d'utilisation.
13. Un dossier de conception comprenant le MCD, le MLD et les diagrammes UML utiles.

---

## 12. Sécurité réglementaire et exploitation réelle

Pour une utilisation réelle en pharmacie, le responsable du projet devra faire vérifier les exigences locales relatives à la délivrance des médicaments, à la traçabilité des lots, aux factures, aux données personnelles, aux paiements et à la conservation des documents.

Le logiciel ne devra pas considérer qu'un médicament est autorisé à la vente uniquement parce qu'il figure dans la base de données. Les règles de délivrance, les prescriptions nécessaires et les contrôles professionnels devront être respectés.

---

## Annexe : Illustrations et maquettes indicatives (Pages 20 à 29)

Le document original inclut des captures d'écran de référence illustrant les interfaces attendues pour le projet :
1. **Tableau de bord :** Nombre de médicaments, ventes du jour, alertes de stock, péremptions et statistiques.
2. **Gestion des médicaments :** Liste des médicaments avec photos, catégories, prix, quantités et boutons Ajouter, Modifier et Supprimer.
3. **Interface de vente et caisse :** Recherche de produits, panier, calcul automatique du total, paiement et impression du reçu.
4. **Gestion des stocks et achats :** Lots, dates de péremption, fournisseurs, réceptions et alertes de rupture.
5. **Graphiques statistiques et rapports :** Visualisation du chiffre d'affaires, répartition par catégorie, top des ventes et évolution mensuelle.