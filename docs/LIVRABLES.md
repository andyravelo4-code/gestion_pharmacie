# Livrables — PharmaGest

Ce document fait le lien entre les **13 livrables du cahier des charges** et les
fichiers réellement présents dans le projet.

## Synthèse

| # | Livrable attendu | Statut | Emplacement principal |
| --- | --- | --- | --- |
| 1 | Code source complet du projet Django | ✅ Complet | Racine du dépôt, applications `core`, `utilisateurs`, `medicaments`, `fournisseurs`, `clients`, `stock`, `achats`, `ventes`, `rapports` |
| 2 | Base de données et migrations | ✅ Complet | `db.sqlite3` (local), `*/migrations/`, export `base_de_donnees/pharmagest_demo.sql.gz` |
| 3 | Modèles et relations | ✅ Complet | `*/models.py`, MCD/MLD dans `docs/CONCEPTION.md` |
| 4 | Pages HTML, CSS et Bootstrap | ✅ Complet | `templates/`, `*/templates/`, `static/css/app.css`, Bootstrap local dans `static/vendor/` |
| 5 | Formulaires CRUD avec photos | ✅ Complet | `*/forms.py`, `templates/medicaments/medicament_form.html`, `core/validators.py` |
| 6 | Modules achats, ventes et stock | ✅ Complet | `achats/`, `ventes/`, `stock/` (modèles, services, vues, templates, tests) |
| 7 | Gestion des utilisateurs et permissions | ✅ Complet | `utilisateurs/`, `utilisateurs/permissions.py`, `templates/utilisateurs/` |
| 8 | Rapports PDF et tableau de bord | ✅ Complet | `rapports/pdf.py`, `rapports/views.py`, `templates/rapports/` |
| 9 | Jeu de données fictives | ✅ Complet | Commande `core/management/commands/donnees_demo.py`, export `base_de_donnees/` |
| 10 | Tests automatisés | ✅ Complet | `*/tests.py`, `core/test_smoke.py` — 110 tests |
| 11 | Manuel d’installation et de configuration | ✅ Complet | `docs/INSTALLATION.md`, sections installation/déploiement du `README.md` |
| 12 | Guide d’utilisation | ✅ Complet | `docs/GUIDE_UTILISATION.md` |
| 13 | Dossier de conception : MCD, MLD, UML | ✅ Complet | `docs/CONCEPTION.md` |

---

## Détail des livrables

### 1. Code source complet

```text
pharma_gest/
├── manage.py
├── config/                 # réglages et routage racine
├── core/                   # paramètres, audit, sauvegardes, données démo
├── utilisateurs/           # Utilisateur, Role, permissions
├── medicaments/            # Categorie, Medicament
├── fournisseurs/           # Fournisseur
├── clients/                # Client
├── stock/                  # LotStock, MouvementStock, Inventaire
├── achats/                 # CommandeAchat, ReceptionAchat
├── ventes/                 # Vente, Paiement, RetourVente
├── rapports/               # tableaux de bord, rapports, PDF
├── templates/              # templates transverses
├── static/                 # CSS, JS, Bootstrap, Chart.js locaux
├── docs/                   # documentation
└── base_de_donnees/        # export SQL de démonstration
```

### 2. Base de données et migrations

- Migrations versionnées pour chaque application.
- Base SQLite de développement : `db.sqlite3` (non versionnée, recréée par les
  migrations).
- Export complet de démonstration :
  `base_de_donnees/pharmagest_demo.sql.gz`.
- Procédure de restauration : `base_de_donnees/README.md`.

```bash
.venv/bin/python manage.py migrate
.venv/bin/python manage.py donnees_demo
```

### 3. Modèles et relations

- Modèles Django dans les fichiers `models.py` de chaque application.
- Relations détaillées dans le MCD et le MLD de `docs/CONCEPTION.md`.
- Contraintes clés : unicité du code-barres, clé d’idempotence des ventes,
  montants en `DecimalField`, protections `PROTECT`/`SET_NULL`.

### 4. Pages HTML, CSS et Bootstrap

- Interface responsive en français.
- Bootstrap 5 et Bootstrap Icons servis **localement** (aucun CDN).
- Templates par module et templates transverses (`base.html`, messages,
  pagination, champs de formulaire).
- Graphiques du tableau de bord avec Chart.js local.

### 5. Formulaires CRUD avec photos

- CRUD médicaments et catégories.
- CRUD fournisseurs et clients (avec désactivation/archivage).
- Téléversement de photo pour les médicaments et le logo de la pharmacie.
- Validation serveur des images : type, taille maximale (3 Mo), traitement
  Pillow.

### 6. Modules achats, ventes et stock

- **Achats** : commandes, lignes, validation, réception totale/partielle,
  statuts, prix figés.
- **Ventes** : caisse, panier, FEFO, paiements, reçus, retours, annulations.
- **Stock** : lots, péremptions, blocage, mouvements signés, alertes,
  inventaires.
- Services transactionnels : `transaction.atomic()` et `select_for_update()`.

### 7. Utilisateurs et permissions

- Modèle `Utilisateur` personnalisé (`AUTH_USER_MODEL`).
- Rôles cumulables : `ADMIN`, `PHARMACIEN`, `GESTION_STOCK`, `CAISSIER`,
  `RESPONSABLE_GESTION`.
- Contrôle serveur par `RoleRequisMixin` / `AdminRequisMixin`.
- Authentification, profil, changement et réinitialisation de mot de passe.
- Journal d’audit des actions sensibles.

### 8. Rapports PDF et tableau de bord

- Tableau de bord : indicateurs, ventes, alertes, péremptions, graphiques.
- Rapports : ventes, achats, stock, péremptions, journal d’audit.
- PDF ReportLab : reçus, factures, bons de commande, bons de réception,
  rapports.
- En-tête `%PDF` vérifié par les tests.

### 9. Jeu de données fictives

```bash
.venv/bin/python manage.py donnees_demo
# ou, sur une base de développement :
.venv/bin/python manage.py donnees_demo --reinitialiser
```

Contenu : 5 comptes, 20 médicaments, 42 lots, 4 commandes, 30 ventes,
2 retours/annulations, 1 inventaire, 109 mouvements de stock.

### 10. Tests automatisés

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py test
```

Dernier résultat connu :

```text
Ran 110 tests
OK
```

Le test `core/test_smoke.py` charge le jeu de données et vérifie le rendu de
**toutes les pages HTML** et de **tous les PDF**.

### 11. Manuel d’installation et de configuration

- `docs/INSTALLATION.md` : installation développement, variables
  d’environnement, PostgreSQL, Gunicorn, Nginx, HTTPS, sauvegardes, dépannage,
  checklist.
- `README.md` : présentation, installation rapide, tests, déploiement.

### 12. Guide d’utilisation

`docs/GUIDE_UTILISATION.md` décrit les parcours par rôle :

- Administrateur : utilisateurs, paramètres, sauvegardes, audit.
- Pharmacien : catalogue, lots, achats, ventes.
- Gestionnaire de stock : fournisseurs, commandes, réceptions, inventaires.
- Caissier : caisse, paiements, reçus, retours, annulations.
- Responsable de gestion : tableaux de bord et rapports.

### 13. Dossier de conception

`docs/CONCEPTION.md` contient :

- architecture logicielle et couche services ;
- acteurs, rôles et cas d’utilisation UML ;
- MCD Mermaid ;
- MLD détaillé table par table ;
- diagrammes de séquence (vente FEFO, réception, retour/annulation) ;
- diagrammes d’état (commande, vente, lot) ;
- exports PNG des 8 diagrammes dans `docs/diagrammes/` (galerie en §9) ;
- correspondance RG01–RG12 ;
- sécurité, transactions et stratégie de tests.

---

## Vérifications finales

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py test
```

Tous les livrables ci-dessus sont présents dans le dépôt Git
`andyravelo4-code/gestion_pharmacie`.
