# Guide d'utilisation — PharmaGest

Ce guide décrit les parcours quotidiens de PharmaGest par rôle. Les libellés
des menus peuvent évoluer légèrement selon la version de l'interface, mais les
règles et les contrôles décrits ici sont ceux appliqués par le serveur.

> **À lire d'abord.** PharmaGest est un outil de gestion. Il ne remplace ni
> l'ordonnance, ni le conseil pharmaceutique, ni les obligations réglementaires.
> Les données de démonstration sont fictives.

---

## 1. Se connecter et se repérer

1. Ouvrir l'adresse de l'application dans un navigateur.
2. Saisir l'identifiant et le mot de passe fournis par l'administrateur.
3. En cas d'oubli, utiliser le lien de réinitialisation (un e-mail est envoyé
   si la messagerie est configurée) ou contacter l'administrateur.
4. Après connexion, le tableau de bord affiche les indicateurs autorisés pour
   votre rôle.

La session expire après 8 heures. Utilisez **Déconnexion** en quittant un
poste partagé.

### Comptes de démonstration

| Identifiant | Mot de passe | Rôle |
| --- | --- | --- |
| `admin` | `PharmaGest2026!` | Administrateur |
| `pharmacien` | `PharmaGest2026!` | Pharmacien responsable |
| `stock` | `PharmaGest2026!` | Gestionnaire de stock |
| `caissier` | `PharmaGest2026!` | Caissier |
| `gestion` | `PharmaGest2026!` | Responsable de gestion |

Ces comptes sont créés par `manage.py donnees_demo`. Changez leur mot de passe
dès que l'application quitte le cadre de la démonstration.

### Matrice des accès

| Module / action | Admin | Pharmacien | Gestion stock | Caissier | Resp. gestion |
| --- | :---: | :---: | :---: | :---: | :---: |
| Tableau de bord | ✔ | ✔ | ✔ | ✔ | ✔ |
| Consulter les médicaments | ✔ | ✔ | ✔ | ✔ | ✔ |
| Créer/modifier/archiver un médicament, gérer les catégories | ✔ | ✔ | — | — | — |
| Fournisseurs | ✔ | ✔ | ✔ | — | — |
| Clients | ✔ | ✔ | — | ✔ | — |
| Achats, réceptions | ✔ | ✔ | ✔ | — | — |
| Stock, lots, inventaires | ✔ | ✔ | ✔ | — | — |
| Caisse, ventes, paiements, retours | ✔ | ✔ | — | ✔ | — |
| Rapports détaillés et PDF | ✔ | ✔ | — | — | ✔ |
| Utilisateurs, paramètres, sauvegardes, audit | ✔ | — | — | — | — |

Un administrateur (rôle `ADMIN` ou superutilisateur) passe toujours. Un
utilisateur peut cumuler plusieurs rôles si l'administrateur le décide. Si un
bouton ou un menu n'apparaît pas, c'est que votre rôle ne l'autorise pas :
contacter l'administrateur plutôt que de partager un compte.

---

## 2. Administrateur

### 2.1 Gérer les utilisateurs et les rôles

1. Ouvrir **Utilisateurs**.
2. **Créer un utilisateur** : renseigner identifiant, prénom, nom, e-mail,
   téléphone, mot de passe et rôles.
3. Pour modifier : ouvrir la fiche, changer les informations ou les rôles.
4. Pour désactiver un départ : utiliser l'action **Activer/Désactiver**.
   Ne supprimez pas un compte ayant réalisé des opérations : l'historique
   doit rester lisible.
5. En cas de compromission : changer immédiatement le mot de passe, puis
   désactiver le compte si nécessaire.

Un compte désactivé ne peut plus se connecter mais ses traces sont conservées.
Les mots de passe sont hachés par Django ; personne, pas même l'administrateur,
ne peut les lire en clair.

### 2.2 Paramétrer la pharmacie

Menu **Paramètres** :

- nom, adresse, téléphone, e-mail, NIF, devise ;
- seuil d'alerte de péremption (30 jours par défaut) ;
- mentions légales imprimées sur les PDF ;
- logo.

Ces informations apparaissent sur les reçus, factures et rapports. Faites
valider les mentions fiscales et légales avant exploitation réelle.

### 2.3 Sauvegardes

Menu **Sauvegardes** :

1. Cliquer sur **Créer une sauvegarde** : un fichier horodaté est produit
   dans le dossier `backups/`.
2. Télécharger la sauvegarde et la conserver hors du serveur.
3. Vérifier régulièrement qu'une restauration fonctionne (voir
   `README.md`, section « Sauvegarde et restauration »).

Une sauvegarde de base ne contient pas les photos de `media/` : prévoir aussi
la sauvegarde de ce dossier.

### 2.4 Journal d'audit

Le journal conserve les connexions, créations, modifications, validations,
annulations, réceptions, ventes, retours et sauvegardes, avec l'auteur et la
date. Il permet d'enquêter sur une anomalie. Ne modifiez pas les données
directement en base : toute correction doit passer par une opération traçable.

---

## 3. Pharmacien responsable

### 3.1 Créer et tenir le catalogue des médicaments

1. **Médicaments → Ajouter**.
2. Renseigner le nom commercial, la DCI, la catégorie, la forme, le dosage,
   le laboratoire, le code-barres, les prix d'achat et de vente, le seuil
   d'alerte et éventuellement une photo.
3. Vérifier le prix de vente : il sera figé sur chaque ligne de vente au
   moment de la transaction. Une modification ultérieure ne change pas les
   ventes passées.
4. Enregistrer.

Bonnes pratiques :

- un code-barres ne peut pas être dupliqué (RG02) ;
- les photos acceptées sont JPEG, PNG, WebP ou GIF, dans la limite de taille
  configurée ;
- utilisez la recherche par nom/code-barres, les filtres de catégorie et la
  pagination pour retrouver un produit.

### 3.2 Archiver plutôt que supprimer

Si un médicament a déjà des lots, des achats ou des ventes, la suppression est
bloquée : utilisez **Archiver**. Un médicament archivé :

- reste visible dans l'historique et les rapports ;
- n'est plus proposé à la vente ;
- ne déclenche plus d'alerte de stock actif ;
- peut être réactivé si nécessaire.

### 3.3 Catégories

**Médicaments → Catégories** permet d'ajouter, modifier et supprimer une
catégorie. Une catégorie utilisée par au moins un médicament ne peut pas être
supprimée : déplacez d'abord les médicaments concernés.

### 3.4 Fournisseurs et clients

- **Fournisseurs** : raison sociale, adresse, téléphone, e-mail, NIF, contact.
  Un fournisseur inactif reste dans l'historique des achats.
- **Clients** : ne conservez que les données commerciales nécessaires (nom,
  téléphone, e-mail, adresse, notes). Une vente au comptoir peut rester
  anonyme.

### 3.5 Superviser les stocks et les péremptions

Consulter **Stock → Alertes** :

- **Rupture** : stock disponible à zéro ;
- **Stock faible** : stock disponible inférieur ou égal au seuil du
  médicament ;
- **Péremption proche** : lots dont la date est dans le seuil configuré
  (30 jours par défaut) ;
- **Périmé** : lot dont la date est dépassée, avec quantité éventuellement
  positive : il ne doit jamais être vendu.

Un lot périmé ou bloqué doit être retiré de la zone de vente. Il peut être
bloqué dans PharmaGest avec un motif (contrôle qualité, rappel, destruction).
La sortie physique définitive doit être enregistrée selon la procédure de la
pharmacie (perte/destruction), pas par suppression silencieuse.

---

## 4. Gestionnaire de stock

### 4.1 Fournisseurs

Créer et tenir à jour les fiches fournisseurs. L'historique des commandes et
les montants d'achat sont consultables depuis la fiche. Désactivez un
fournisseur au lieu de le supprimer.

### 4.2 Commander : de la commande à la réception

**Règle essentielle (RG04) : une commande ne modifie pas le stock.** Le stock
n'augmente qu'à la réception effective (RG05).

1. **Achats → Nouvelle commande**.
2. Choisir le fournisseur.
3. Ajouter les lignes : médicament, quantité commandée, prix d'achat
   unitaire. Le total se calcule côté serveur.
4. Enregistrer en **brouillon** : la commande est modifiable.
5. **Valider** la commande : elle passe à « Commandée » et n'est plus
   modifiable comme un brouillon.
6. À la livraison : **Réceptionner**. Pour chaque ligne, saisir la quantité
   réellement reçue, le numéro de lot, la date de péremption et le prix
   unitaire.
7. Valider la réception.

Résultats :

- un lot est créé ou complété pour chaque ligne reçue ;
- un mouvement d'entrée est enregistré avec l'auteur et la référence ;
- les quantités reçues sont cumulées ;
- le statut devient « Partiellement réceptionnée » ou « Entièrement
  réceptionnée » selon les quantités ;
- une réception ne peut pas être rejouée pour augmenter le stock deux fois.

Une commande déjà partiellement reçue ne peut plus être annulée : le reliquat
doit être réceptionné ou traité selon la procédure interne. Une date de
péremption passée est refusée à la réception.

### 4.3 Consulter les lots et les mouvements

- **Stock → Lots** : médicament, numéro de lot, péremption, quantité,
  fournisseur, statut bloqué, valeur.
- **Stock → Mouvements** : historique signé (entrée, sortie, retour,
  correction, perte) avec référence, motif, auteur et date.
- Une fiche lot permet de bloquer/débloquer un lot avec un motif.

Le stock disponible exclut les lots périmés, bloqués ou vides. Le stock total
peut donc être supérieur au stock réellement vendable : c'est normal et visible
dans les écrans.

### 4.4 Inventaire physique

1. **Stock → Inventaires → Nouvel inventaire**.
2. Choisir les lots à compter (ou tout le stock selon l'interface).
3. Le système enregistre la quantité théorique de chaque lot.
4. Saisir les quantités réellement comptées.
5. Valider l'inventaire.

La validation :

- vérifie que le stock n'a pas changé depuis le comptage ;
- applique un mouvement de correction positive ou négative pour chaque écart ;
- conserve l'auteur, la date et le numéro d'inventaire ;
- ne peut s'exécuter qu'une seule fois.

Si le stock a bougé entre-temps, la validation est refusée : recommencez le
comptage. Un inventaire en cours peut être consulté mais ne modifie pas le
stock tant qu'il n'est pas validé.

### 4.5 Alertes à traiter

Chaque jour :

1. ouvrir **Stock → Alertes** et le tableau de bord ;
2. traiter les ruptures et stocks faibles (commande de réassort) ;
3. isoler les lots périmés et les déclarer ;
4. vérifier les lots proches de la péremption et planifier leur écoulement
   prioritaire (FEFO) ;
5. contrôler les mouvements inhabituels dans le journal.

---

## 5. Caissier

### 5.1 Ouvrir la caisse et composer le panier

1. **Ventes → Caisse**.
2. Rechercher un médicament par nom ou code-barres.
3. Le système propose les lots délivrables selon la règle **FEFO** (le lot
   dont la péremption est la plus proche d'abord). Un lot périmé, bloqué ou
   vide n'est jamais proposé.
4. Saisir la quantité (1 à 5 en démonstration, selon le stock réel).
5. Ajouter au panier. Répéter pour plusieurs produits.
6. Vérifier les lignes, les prix et le total. Les prix affichés proviennent du
   serveur et sont figés au moment de la validation (RG12).
7. Modifier une quantité ou retirer une ligne si nécessaire ; vider le panier
   en cas d'erreur.

Le panier n'est pas une vente : le stock n'est décrémenté qu'à la validation.
Si le stock a changé entre l'ajout et la validation, la vente est refusée avec
un message clair.

### 5.2 Choisir le client

- Sélectionner un client existant, ou
- laisser le client vide pour une vente anonyme au comptoir, lorsque la
  réglementation locale le permet.
- Ne collectez pas de données de santé inutiles dans les notes client.

### 5.3 Payer en espèces

1. Choisir **Espèces**.
2. Saisir le montant reçu (facultatif s'il est égal au total).
3. Valider.

Le montant reçu doit être supérieur ou égal au total. La vente est enregistrée
avec un paiement confirmé, le stock est diminué une seule fois (RG06) et un
reçu est disponible.

### 5.4 Payer par mobile money ou carte

**Règle de sécurité : un paiement électronique n'est jamais considéré comme
confirmé sans vérification fiable.**

1. Choisir **Mobile money** ou **Carte**.
2. Saisir la **référence de transaction** fournie par le client ou le
   terminal (obligatoire).
3. Vérifier le paiement sur le canal fiable prévu par la pharmacie
   (application opérateur, relevé, terminal bancaire, appel au service).
4. Cocher la case de confirmation / utiliser l'action **Confirmer le
   paiement**.
5. Seulement alors, valider la vente.

Sans référence ou sans confirmation, le serveur refuse la vente. Si le
paiement s'avère invalide après coup, ne supprimez pas la vente : contactez le
responsable et appliquez la procédure de correction/annulation traçable.

### 5.5 Reçu et facture

Depuis le détail d'une vente :

- **Reçu** : document de caisse avec le numéro, la date, les lignes, les
  quantités, les prix, le total et les informations de la pharmacie ;
- **Facture** : document plus complet lorsque le client en a besoin (NIF,
  coordonnées, mentions légales).

Les PDF sont générés côté serveur avec ReportLab. Vérifiez le total et les
mentions avant de remettre le document. Les prix des documents historiques ne
changent pas lorsque le catalogue est modifié.

### 5.6 Retour de produit

1. Retrouver la vente d'origine (numéro, date, client).
2. Ouvrir **Retour**.
3. Sélectionner la ou les lignes, la quantité retournée (jamais supérieure à
   la quantité encore retournable).
4. Saisir un **motif obligatoire**.
5. Indiquer si le produit peut être **remis en stock** :
   - uniquement s'il est non ouvert, non périmé et que le lot n'est pas
     bloqué ;
   - sinon, le retour est enregistré sans remise en stock.
6. Choisir le mode de remboursement (espèces, mobile money, avoir, aucun).
7. Valider.

Le retour crée une opération compensatoire, conserve la vente d'origine et
peut remettre la quantité en stock via un mouvement de type `RETOUR`. Un lot
périmé ou bloqué ne peut pas être remis en stock.

### 5.7 Annulation d'une vente

Une vente validée n'est **jamais supprimée** (RG10). L'annulation :

- est enregistrée comme un retour de type `ANNULATION` ;
- remet les quantités en stock si demandé et si les lots sont éligibles ;
- passe la vente au statut « Annulée » ;
- conserve l'auteur, la date et le motif.

Utilisez l'annulation uniquement en cas d'erreur réelle (double saisie,
paiement refusé, client parti) et documentez le motif.

---

## 6. Responsable de gestion

### 6.1 Tableau de bord

Le tableau de bord calcule les indicateurs à partir des données réelles
(aucune saisie manuelle) :

- nombre de médicaments actifs ;
- montant des ventes du jour ;
- nombre de stocks faibles ;
- nombre de péremptions proches ;
- ventes et achats sur une période ;
- produits les plus vendus ;
- alertes et lots à surveiller.

Le chiffre d'affaires, les encaissements et la marge commerciale sont des
notions différentes. La marge affichée n'est pas un bénéfice net : les charges
(loyer, salaires, énergie, etc.) ne sont pas gérées par PharmaGest.

### 6.2 Rapports

- **Rapports → Ventes** : période, totaux, modes de paiement, produits.
- **Rapports → Achats** : commandes, réceptions, fournisseurs.
- **Rapports → Stock** : quantités, valeurs, seuils.
- **Rapports → Péremptions** : lots périmés et proches de la péremption.
- **Rapports → Journal** : opérations sensibles et auteurs.

Chaque rapport peut être exporté en PDF. Vérifiez la période et les filtres
avant diffusion. Les données personnelles ne doivent être communiquées
qu'aux personnes autorisées.

---

## 7. Règles métier expliquées

| Règle | Ce que cela change pour vous |
| --- | --- |
| **RG01** | Chaque médicament a un identifiant unique interne. |
| **RG02** | Un code-barres renseigné ne peut pas être attribué à deux médicaments. |
| **RG03** | Prix et quantités sont validés par le serveur ; un total affiché par le navigateur ne fait pas foi. |
| **RG04** | Créer ou valider une commande d'achat **ne modifie pas le stock**. Seule la réception le fait. |
| **RG05** | Une réception validée augmente le stock une seule fois, dans une transaction atomique. |
| **RG06** | Une vente validée diminue le stock une seule fois, dans une transaction atomique. |
| **RG07** | Le stock ne peut jamais devenir négatif : une quantité supérieure au disponible est refusée. |
| **RG08** | Les lots périmés ou bloqués ne sont jamais vendus ni remis en stock. |
| **RG09** | Les opérations importantes conservent auteur, date, référence et historique. |
| **RG10** | Une vente ou un achat validé n'est pas supprimé silencieusement ; on utilise un retour ou une annulation traçable. |
| **RG11** | Chaque page vérifie les permissions côté serveur ; masquer un bouton ne suffit pas. |
| **RG12** | Les lignes de vente et les documents conservent les prix appliqués au moment de l'opération. |

### Comprendre les alertes

| Alerte | Signification | Action recommandée |
| --- | --- | --- |
| Rupture | Stock disponible ≤ 0 | Commander ou transférer depuis un autre dépôt |
| Stock faible | Stock disponible ≤ seuil d'alerte | Planifier un réassort |
| Péremption proche | Lot valide dont la date est dans le seuil (30 j par défaut) | Écouler en priorité (FEFO), surveiller |
| Lot périmé | Date dépassée, quantité éventuellement > 0 | Retirer de la vente, bloquer, déclarer la destruction |
| Lot bloqué | Blocage manuel avec motif | Ne pas vendre ; lever le blocage après contrôle |
| Paiement en attente | Paiement électronique non confirmé | Vérifier la transaction avant toute validation |
| Inventaire en cours | Comptage non validé | Terminer et valider, ou annuler selon la procédure |

---

## 8. Bonnes pratiques et dépannage

### Sécurité au quotidien

- Un compte par personne, jamais de compte partagé.
- Mot de passe long et unique ; verrouiller la session en quittant le poste.
- Ne pas installer d'extension navigateur non maîtrisée sur le poste de
  caisse.
- Ne jamais désactiver les contrôles de permission pour « aller plus vite ».
- Signaler immédiatement un stock incohérent, un paiement douteux ou un accès
  suspect à l'administrateur.

### Messages fréquents

| Message | Cause probable | Solution |
| --- | --- | --- |
| « Stock insuffisant » | Quantité demandée supérieure au lot disponible | Réduire la quantité ou choisir un autre lot |
| « Lot périmé / bloqué » | Lot non délivrable | Choisir un lot valide ; ne pas forcer |
| « Référence obligatoire » | Paiement mobile/carte sans référence | Saisir la référence vérifiée |
| « Paiement non confirmé » | Case de vérification non cochée | Vérifier puis confirmer le paiement |
| « Commande déjà réceptionnée » | Double clic ou double soumission | Recharger la page ; ne pas recréer |
| « Inventaire modifié » | Stock changé depuis le comptage | Recommencer l'inventaire |
| Accès refusé (403) | Rôle insuffisant | Contacter l'administrateur |
| Session expirée | Plus de 8 heures d'inactivité | Se reconnecter |

### En cas d'incident

1. Ne pas modifier la base directement.
2. Noter l'heure, l'écran, le message et l'utilisateur concerné.
3. Prévenir l'administrateur ou le pharmacien responsable.
4. Si nécessaire, restaurer une sauvegarde **après** avoir sauvegardé l'état
   actuel et arrêté le serveur (voir `README.md`).

---

## 9. Aide-mémoire des parcours

```text
Réception d'achat :
  Fournisseur → Commande (brouillon) → Valider → Réceptionner
  → quantités + lots + péremptions → Stock augmenté une seule fois

Vente au comptoir :
  Caisse → rechercher → choisir lot FEFO → quantité → panier
  → client (ou anonyme) → mode de paiement → vérifier/confirmer
  → Valider → stock diminué une seule fois → reçu/facture

Retour :
  Vente d'origine → Retour → ligne + quantité + motif
  → remise en stock ? → remboursement → valider (trace conservée)

Inventaire :
  Stock → Inventaires → Nouvel inventaire → compter → Valider
  → corrections tracées (une seule fois)
```
