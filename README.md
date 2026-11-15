# PharmaGest

Application web de gestion d'une pharmacie développée avec **Django 5.2**.
Elle couvre les médicaments, les fournisseurs, les clients, les achats, les
stocks par lots, la caisse, les retours, les rapports PDF et la traçabilité des
opérations.

> **Données de démonstration fictives.** Les comptes, produits, prix et clients
> fournis par `donnees_demo` servent uniquement au développement et aux
> démonstrations. Ils ne constituent ni une base réglementaire ni un avis
> pharmaceutique. Voir la section [Avertissement réglementaire](#avertissement-réglementaire).

---

## Sommaire

- [Fonctionnalités](#fonctionnalités)
- [Architecture](#architecture)
- [Prérequis](#prérequis)
- [Installation pas à pas](#installation-pas-à-pas)
- [Comptes de démonstration](#comptes-de-démonstration)
- [Tests et vérifications](#tests-et-vérifications)
- [Sauvegarde et restauration](#sauvegarde-et-restauration)
- [Déploiement en production](#déploiement-en-production)
- [Avertissement réglementaire](#avertissement-réglementaire)
- [Documentation](#documentation)

---

## Fonctionnalités

### Authentification, utilisateurs et rôles

- Connexion, déconnexion, changement et réinitialisation de mot de passe.
- Cinq rôles cumulables : `ADMIN`, `PHARMACIEN`, `GESTION_STOCK`,
  `CAISSIER`, `RESPONSABLE_GESTION`.
- Création, modification, activation/désactivation des comptes par
  l'administrateur.
- Contrôle des permissions côté serveur sur chaque vue.
- Journal d'audit : connexions, créations, modifications, validations,
  annulations, réceptions, ventes, retours, sauvegardes.

### Médicaments et catégories

- Fiche médicament : nom commercial, DCI, catégorie, forme, dosage,
  laboratoire, code-barres unique, photo, prix d'achat/vente, seuil d'alerte,
  statut actif/archivé.
- CRUD avec recherche, filtres, tri et pagination.
- Archives au lieu de suppressions lorsque l'historique doit être conservé.
- Catégories protégées contre la suppression si elles contiennent des
  médicaments.

### Fournisseurs et clients

- Fiches fournisseur (raison sociale, adresse, contacts, NIF, statut) et
  historique des achats.
- Fiches client limitées aux données commerciales nécessaires ; vente
  anonyme possible.
- Désactivation sans suppression des opérations passées.

### Achats et réceptions

- Commandes d'achat avec lignes, quantités et prix.
- Statuts : brouillon, commandée, partiellement réceptionnée, entièrement
  réceptionnée, annulée.
- **Une commande ne modifie jamais le stock** : seule la réception effective
  crée les lots et les mouvements d'entrée.
- Réception totale ou partielle, numéro de lot et date de péremption
  obligatoires.

### Stocks, lots et inventaires

- Suivi par lot : quantité, quantité initiale, péremption, fournisseur,
  prix d'achat, blocage/déblocage.
- Mouvements signés et historisés : entrée, sortie, retour, correction,
  perte.
- Stock disponible calculé à partir des lots non périmés, non bloqués et non
  vides.
- Alertes de rupture, de stock faible et de péremption proche.
- Inventaires avec quantités théoriques/comptées, écarts et validation
  atomique.
- Stratégie **FEFO** (*First Expired, First Out*) pour la délivrance.

### Caisse, ventes, paiements, retours

- Recherche d'un médicament ou scan du code-barres, panier, quantités,
  total calculé côté serveur.
- Prix figé sur chaque ligne de vente.
- Modes de paiement : espèces, mobile money, carte, virement, chèque.
- Les paiements électroniques exigent une référence et une confirmation
  explicite après vérification.
- Reçu et facture PDF.
- Retours partiels avec motif, remboursement et remise en stock contrôlée.
- Annulation par opération compensatoire traçable, jamais par suppression
  silencieuse.

### Tableau de bord, rapports et PDF

- Indicateurs : médicaments actifs, ventes du jour, stocks faibles,
  péremptions proches.
- Ventes, achats, état du stock, produits les plus vendus, mouvements,
  journal d'audit.
- Rapports PDF (ventes, achats, stock, péremptions), reçus, factures, bons de
  commande et de réception, générés avec **ReportLab**.
- Accès aux rapports détaillés selon le rôle.

### Exploitation

- Paramètres de la pharmacie : nom, adresse, contacts, NIF, devise, seuil de
  péremption, mentions légales, logo.
- Sauvegardes depuis l'interface (administrateur) et en ligne de commande.
- Commande de jeu de données fictives pour les démonstrations.
- Interface responsive en français, actifs statiques locaux (aucun CDN).

---

## Architecture

Architecture **MVT** de Django, avec une couche `services` explicite pour les
opérations sensibles (stock, achats, ventes).

```text
pharma_gest/
├── manage.py
├── requirements.txt
├── .env.example
├── config/
│   ├── settings.py          # configuration par variables d'environnement
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── core/                    # paramètres pharmacie, audit, sauvegardes
│   ├── models.py            # ParametrePharmacie, JournalAudit
│   ├── utils.py             # numéros, montants, journalisation
│   ├── views.py             # paramètres et sauvegardes
│   └── management/commands/ # donnees_demo, sauvegarde_db, restaurer_db
├── utilisateurs/            # Utilisateur, Role, permissions, signaux
├── medicaments/             # Categorie, Medicament
├── fournisseurs/            # Fournisseur
├── clients/                 # Client
├── stock/                   # LotStock, MouvementStock, Inventaire
│   └── services.py          # mouvements, réceptions, inventaires
├── achats/                  # CommandeAchat, LigneAchat, réceptions
│   └── services.py          # validation, annulation, réception
├── ventes/                  # Vente, LigneVente, Paiement, RetourVente
│   └── services.py          # FEFO, vente, retour, annulation, paiement
├── rapports/                # tableau de bord, rapports et PDF
├── templates/               # gabarits HTML globaux
├── static/                  # CSS, JS, Bootstrap et Chart.js locaux
├── docs/                    # SPEC_INTERNE, CONCEPTION, GUIDE_UTILISATION
├── media/                   # photos et logos (non versionné)
├── backups/                 # sauvegardes (non versionné)
└── logs/                    # journal technique (non versionné)
```

Principes structurants :

- **Modèles figés** : les règles métier vivent dans les services et les
  modèles, pas dans les templates.
- **Transactions atomiques** et verrouillage (`select_for_update`) pour les
  ventes, réceptions et validations d'inventaire.
- **Traçabilité** : chaque mouvement de stock conserve l'auteur, la date, la
  référence et le motif.
- **Permissions** : mixins `RoleRequisMixin` / `AdminRequisMixin` et contrôle
  systématique côté serveur.
- **Configuration** : secrets et paramètres lus dans l'environnement.

---

## Prérequis

- Python **3.12 ou supérieur** (testé avec Python 3.14).
- `pip` et l'outil `venv`.
- SQLite (inclus avec Python) pour le développement.
- PostgreSQL 14+ et `psycopg` pour une production relationnelle.
- Linux/macOS, ou Windows avec les commandes adaptées.

Dépendances principales : Django `>=5.2,<6`, Pillow, ReportLab. Voir
`requirements.txt`.

---

## Installation pas à pas

### 1. Récupérer le projet et créer l'environnement virtuel

```bash
git clone <url-du-depot> pharma_gest
cd pharma_gest
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

Sous Windows, remplacer `.venv/bin/` par `.venv\Scripts\`.

### 2. Configurer l'environnement

```bash
cp .env.example .env
```

Adapter au minimum `DJANGO_SECRET_KEY`, `DJANGO_DEBUG` et
`DJANGO_ALLOWED_HOSTS`. **Django ne lit pas automatiquement le fichier
`.env`** : `config/settings.py` utilise `os.environ`. Dans un shell Bash :

```bash
set -a
. ./.env
set +a
```

Sans fichier `.env`, les valeurs de développement par défaut de
`config/settings.py` sont utilisées (SQLite, `DEBUG=True`).

### 3. Appliquer les migrations

```bash
.venv/bin/python manage.py migrate
```

### 4. Charger le jeu de démonstration (facultatif mais recommandé)

```bash
.venv/bin/python manage.py donnees_demo
```

Sur une base déjà remplie, la commande refuse de s'exécuter. Pour une base de
**développement uniquement**, on peut repartir de zéro avec :

```bash
.venv/bin/python manage.py donnees_demo --reinitialiser
```

> `--reinitialiser` exécute un `flush` : **toutes les données** sont
> supprimées. Ne jamais l'utiliser sur une base de production.

### 5. Lancer le serveur de développement

```bash
.venv/bin/python manage.py runserver
```

Ouvrir <http://127.0.0.1:8000/>. L'administration Django reste accessible sur
`/admin/`.

### 6. Vérifier l'installation

```bash
.venv/bin/python manage.py check
```

---

## Comptes de démonstration

Créés par `donnees_demo`, avec le mot de passe commun **`PharmaGest2026!`** :

| Identifiant | Rôle | Usage |
| --- | --- | --- |
| `admin` | Administrateur (superutilisateur) | Utilisateurs, paramètres, sauvegardes, toutes opérations |
| `pharmacien` | Pharmacien responsable | Médicaments, lots, achats, ventes, rapports |
| `stock` | Gestionnaire de stock | Fournisseurs, commandes, réceptions, inventaires |
| `caissier` | Caissier | Caisse, ventes, paiements, reçus |
| `gestion` | Responsable de gestion | Consultation des statistiques et rapports |

Tous ces comptes sont fictifs. Changez ou supprimez-les avant toute
utilisation réelle.

Le jeu de démonstration contient notamment : 6 catégories, 20 médicaments
(dont 3 archivés), 3 fournisseurs, 4 clients, 42 lots (dont 3 proches de la
péremption et 2 périmés), 4 commandes d'achat à des statuts différents,
30 ventes réparties sur 60 jours (dont 3 le jour même), 2 retours/annulations,
un inventaire en cours et des alertes de stock.

---

## Tests et vérifications

```bash
# Vérification de la configuration Django
.venv/bin/python manage.py check

# Vérification renforcée avant production
.venv/bin/python manage.py check --deploy

# Toute la suite de tests
.venv/bin/python manage.py test

# Une application en particulier
.venv/bin/python manage.py test ventes
.venv/bin/python manage.py test stock
.venv/bin/python manage.py test core
```

Les tests couvrent les modèles, les services (FEFO, stock négatif, retours),
les permissions, les formulaires, les vues et la génération PDF. Le test de
fumée `core/test_smoke.py` rend toutes les pages HTML et tous les PDF à partir
du jeu de démonstration. Dernier résultat connu : **110 tests, OK**. Les tests
utilisent une base dédiée et ne touchent pas `db.sqlite3`.

---

## Sauvegarde et restauration

### Sauvegarde en ligne de commande

```bash
# Sauvegarde horodatée dans backups/
.venv/bin/python manage.py sauvegarde_db

# Emplacement explicite
.venv/bin/python manage.py sauvegarde_db --sortie /chemin/ma_sauvegarde.sqlite3
```

- **SQLite** : la commande utilise l'API de sauvegarde en ligne de `sqlite3`.
  Le fichier est cohérent même si l'application tourne, puis contrôlé avec
  `PRAGMA integrity_check`.
- **PostgreSQL** : la commande utilise `pg_dump` s'il est installé et produit
  un fichier `.sql`.
- Les fichiers sont créés avec des permissions restreintes (`0600`).

Une sauvegarde de la base **ne contient pas** les photos et logos de
`media/` : sauvegardez également ce dossier (et vérifiez la cohérence des
deux sauvegardes).

### Restauration SQLite

> Arrêtez le serveur web avant de restaurer une base de production.

```bash
# 1. Sauvegarder la base active (fortement recommandé)
.venv/bin/python manage.py sauvegarde_db

# 2. Restaurer une sauvegarde
.venv/bin/python manage.py restaurer_db backups/pharmagest_20261117_120000.sqlite3

# 3. Si une base existe déjà, la commande exige --force
.venv/bin/python manage.py restaurer_db backups/pharmagest_20261117_120000.sqlite3 --force
```

La commande :

1. vérifie que le fichier est une base SQLite valide et qu'il contient les
   tables PharmaGest (`utilisateurs_utilisateur` ou `django_migrations`) ;
2. contrôle l'intégrité SQLite et la présence de migrations ;
3. refuse d'écraser la base existante sans `--force` ;
4. crée automatiquement une sauvegarde de sécurité
   `backups/avant_restauration_*.sqlite3` avant remplacement ;
5. ferme les connexions Django, remplace le fichier de façon atomique et
   supprime les anciens fichiers `-wal`, `-shm`, `-journal`.

Après restauration : redémarrer le serveur, exécuter
`.venv/bin/python manage.py check` et, si la sauvegarde provient d'une version
antérieure, `.venv/bin/python manage.py migrate`.

### Restauration PostgreSQL

La restauration automatique n'est pas implémentée pour PostgreSQL. Utiliser
les outils natifs, par exemple :

```bash
pg_restore --clean --if-exists -d pharmagest sauvegarde.dump   # format custom
psql -d pharmagest -f sauvegarde.sql                           # format plain
```

Toujours sauvegarder la base active et tester la restauration sur une base
de recette avant d'intervenir en production.

### Bonnes pratiques

- Sauvegarde quotidienne automatique (cron/systemd timer) + sauvegarde avant
  chaque mise à jour.
- Copie hors site ou stockage chiffré ; durée de conservation définie.
- Test de restauration périodique (au moins trimestriel).
- Protection des fichiers : données de santé et données personnelles.
- Journalisation et surveillance des échecs de sauvegarde.

---

## Déploiement en production

### 1. Variables d'environnement

Dans `.env` ou dans l'unité systemd :

```dotenv
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=<clé aléatoire longue et unique>
DJANGO_ALLOWED_HOSTS=pharmacie.example.mg,www.pharmacie.example.mg
DJANGO_CSRF_TRUSTED_ORIGINS=https://pharmacie.example.mg,https://www.pharmacie.example.mg
DJANGO_SECURE_SSL_REDIRECT=True
DJANGO_SECURE_HSTS_SECONDS=31536000

DATABASE_ENGINE=postgresql
DB_NAME=pharmagest
DB_USER=pharmagest
DB_PASSWORD=<mot de passe fort>
DB_HOST=127.0.0.1
DB_PORT=5432

DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.example.mg
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=notifications@example.mg
EMAIL_HOST_PASSWORD=<secret>
DEFAULT_FROM_EMAIL=PharmaGest <noreply@example.mg>
```

Générer une clé :

```bash
.venv/bin/python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
```

Ne jamais versionner `.env`. En production, `DEBUG=False` active aussi les
cookies sécurisés, HSTS, `X-Frame-Options: DENY` et la redirection HTTPS.

### 2. Base PostgreSQL

```bash
sudo -u postgres psql
CREATE USER pharmagest WITH PASSWORD 'mot-de-passe-fort';
CREATE DATABASE pharmagest OWNER pharmagest;
\q
```

Installer le pilote et appliquer les migrations :

```bash
.venv/bin/pip install "psycopg[binary]>=3.1"
set -a; . ./.env; set +a
.venv/bin/python manage.py migrate
.venv/bin/python manage.py check --deploy
```

Restreindre les droits du compte applicatif au strict nécessaire et activer
les sauvegardes managées si l'hébergeur le propose.

### 3. Fichiers statiques et médias

```bash
.venv/bin/python manage.py collectstatic --noinput
```

- `staticfiles/` est servi par Nginx (ou le CDN), pas par Django.
- `media/` doit être servi par Nginx avec un en-tête `X-Content-Type-Options:
  nosniff` et sans exécution de scripts.
- Vérifier les droits d'écriture de l'utilisateur du service sur `media/`,
  `backups/` et `logs/`.

### 4. Serveur WSGI (Gunicorn)

```bash
.venv/bin/pip install "gunicorn>=21.2"
set -a; . ./.env; set +a
.venv/bin/gunicorn config.wsgi:application \
  --bind 127.0.0.1:8000 \
  --workers 3 \
  --timeout 60 \
  --access-logfile - \
  --error-logfile -
```

Exemple d'unité systemd (`/etc/systemd/system/pharmagest.service`) :

```ini
[Unit]
Description=PharmaGest (Gunicorn)
After=network.target postgresql.service

[Service]
User=pharmagest
Group=pharmagest
WorkingDirectory=/srv/pharmagest
EnvironmentFile=/srv/pharmagest/.env
ExecStart=/srv/pharmagest/.venv/bin/gunicorn config.wsgi:application \
  --bind 127.0.0.1:8000 --workers 3 --timeout 60
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now pharmagest
```

### 5. HTTPS et reverse proxy

Placer Nginx (ou Caddy/Traefik) devant Gunicorn, terminer TLS, rediriger
HTTP vers HTTPS, puis adapter :

- `DJANGO_ALLOWED_HOSTS` et `DJANGO_CSRF_TRUSTED_ORIGINS` ;
- `DJANGO_SECURE_SSL_REDIRECT=True` ;
- HSTS uniquement lorsque HTTPS est stable sur tous les sous-domaines.

Exemple Nginx (extrait) :

```nginx
server {
    listen 443 ssl http2;
    server_name pharmacie.example.mg;

    client_max_body_size 10m;

    location /static/ {
        alias /srv/pharmagest/staticfiles/;
        expires 30d;
    }

    location /media/ {
        alias /srv/pharmagest/media/;
        add_header X-Content-Type-Options nosniff;
    }

    location / {
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_pass http://127.0.0.1:8000;
    }
}
```

Utiliser un certificat renouvelé automatiquement (Let's Encrypt/Certbot ou
certificat de l'hébergeur).

### 6. Sauvegardes et exploitation

Exemple de cron quotidien à 02 h 30 :

```cron
30 2 * * * cd /srv/pharmagest && set -a && . ./.env && set +a && .venv/bin/python manage.py sauvegarde_db >> logs/sauvegarde.log 2>&1
```

Ajouter la copie de `media/`, la rotation des journaux, la supervision des
erreurs et un test de restauration. Prévoir une procédure de retour arrière
lors des mises à jour (sauvegarde + migrations testées en recette).

### 7. Durcissement

- Restreindre `/admin/` par IP ou VPN ; imposer des mots de passe forts.
- Désactiver les comptes de démonstration ; supprimer `donnees_demo` de la
  base de production.
- Servir uniquement en HTTPS ; désactiver le listage des répertoires.
- Mettre à jour Django, Pillow, ReportLab et le système.
- Limiter les privilèges PostgreSQL et les accès réseau.
- Vérifier `manage.py check --deploy` avant chaque mise en production.
- Définir une politique de conservation des données et des journaux.

---

## Avertissement réglementaire

PharmaGest est un **outil de gestion interne**, pas un dispositif médical ni
un logiciel de prescription. Il ne doit pas servir à établir un diagnostic, à
décider d'une délivrance ou à remplacer le jugement d'un professionnel de
santé.

Avant toute exploitation réelle à Madagascar, le responsable de la pharmacie
doit faire valider par un professionnel habilité et, si nécessaire, par un
juriste :

- le respect du Code de la santé publique et de la réglementation
  pharmaceutique malgache (délivrance, prescription, stupéfiants, chaîne du
  froid, traçabilité des lots, pharmacovigilance) ;
- les mentions légales, fiscales et comptables des reçus, factures et
  rapports (NIF, TVA, numérotation, conservation des pièces) ;
- la protection des données personnelles, notamment la loi malgache sur la
  protection des données à caractère personnel (à vérifier dans sa version en
  vigueur), les durées de conservation, les droits des personnes et la
  sécurité des données de santé ;
- les obligations de conservation et d'archivage des documents.

Les paramètres `mentions_legales` et les informations de la pharmacie sont
modifiables dans l'interface d'administration ; les valeurs livrées sont des
exemples à adapter. Les sauvegardes contiennent des données sensibles :
elles doivent être chiffrées, accessibles uniquement aux personnes autorisées
et testées régulièrement.

---

## Documentation

- [`docs/INSTALLATION.md`](docs/INSTALLATION.md) — manuel d'installation et de
  configuration (développement, PostgreSQL, Gunicorn, Nginx, HTTPS, sauvegardes).
- [`docs/GUIDE_UTILISATION.md`](docs/GUIDE_UTILISATION.md) — guide par rôle et
  parcours métier.
- [`docs/CONCEPTION.md`](docs/CONCEPTION.md) — dossier de conception : MCD,
  MLD, cas d'utilisation, séquences, règles, sécurité et tests.
- [`docs/LIVRABLES.md`](docs/LIVRABLES.md) — checklist des 13 livrables du
  cahier des charges et de leur emplacement.
- [`docs/SPEC_INTERNE.md`](docs/SPEC_INTERNE.md) — conventions internes de
  développement (contrat d'URL, modèles, services).
- [`docs/CREDITS_IMAGES.md`](docs/CREDITS_IMAGES.md) — crédits, auteurs et
  licences des photos de médicaments utilisées pour la démonstration.
- [`base_de_donnees/README.md`](base_de_donnees/README.md) — export SQL de
  démonstration et procédure de restauration.
- [`cahier_des_charges_pharmagest.md`](cahier_des_charges_pharmagest.md) —
  cahier des charges initial.
