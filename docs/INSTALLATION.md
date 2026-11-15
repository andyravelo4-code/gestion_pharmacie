# Manuel d’installation et de configuration — PharmaGest

Ce manuel décrit l’installation complète de **PharmaGest** en développement
(SQLite) puis en production (PostgreSQL, Gunicorn, Nginx, HTTPS). Il complète
le [`README.md`](../README.md), qui présente le projet et ses fonctionnalités.

---

## 1. Prérequis

| Élément | Version conseillée | Remarque |
| --- | --- | --- |
| Python | 3.12 ou supérieur | Testé avec Python 3.14 |
| pip / venv | fournis avec Python | `python3 -m venv` |
| SQLite | inclus avec Python | Développement |
| PostgreSQL | 14 ou supérieur | Production |
| Git | 2.x | Récupération du code |
| Système | Linux, macOS ou Windows | Les commandes Windows sont indiquées |

Dépendances Python principales :

- `Django>=5.2,<6`
- `Pillow>=10.0` (photos des médicaments et logo)
- `reportlab>=4.0` (reçus, factures, rapports PDF)

En production, ajouter :

- `psycopg[binary]>=3.1` (pilote PostgreSQL) ;
- `gunicorn>=21.2` (serveur WSGI).

---

## 2. Installation en développement

### 2.1 Récupérer le projet

```bash
git clone https://github.com/andyravelo4-code/gestion_pharmacie.git pharma_gest
cd pharma_gest
```

### 2.2 Créer l’environnement virtuel

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

Sous Windows :

```powershell
python -m venv .venv
.venv\Scripts\pip install --upgrade pip
.venv\Scripts\pip install -r requirements.txt
```

### 2.3 Configurer les variables d’environnement

```bash
cp .env.example .env
```

> **Important :** `config/settings.py` lit les variables avec `os.environ`.
> Django ne charge pas automatiquement `.env`. Dans un shell Bash :

```bash
set -a
. ./.env
set +a
```

Sans fichier `.env`, les valeurs de développement par défaut sont utilisées :
SQLite, `DEBUG=True`, hôtes `localhost` et `127.0.0.1`.

#### Variables principales

| Variable | Défaut | Rôle |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | clé de développement | Clé secrète Django ; à remplacer en production |
| `DJANGO_DEBUG` | `True` | `False` en production |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,[::1]` | Domaines autorisés, séparés par des virgules |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | vide | Origines HTTPS de confiance pour les POST |
| `DJANGO_SECURE_SSL_REDIRECT` | `True` | Redirection HTTPS si `DEBUG=False` |
| `DJANGO_SECURE_HSTS_SECONDS` | `31536000` | Durée HSTS en production |
| `DATABASE_ENGINE` | `sqlite` | `sqlite` ou `postgresql` |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD` | `pharmagest`, `pharmagest`, vide | Connexion PostgreSQL |
| `DB_HOST`, `DB_PORT` | `localhost`, `5432` | Connexion PostgreSQL |
| `DJANGO_EMAIL_BACKEND` | console | Backend e-mail de développement |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS` | vides / `587` / `True` | SMTP de production |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | vides | Identifiants SMTP |
| `DEFAULT_FROM_EMAIL` | `PharmaGest <noreply@pharmagest.local>` | Expéditeur |

Générer une clé secrète solide :

```bash
.venv/bin/python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
```

### 2.4 Initialiser la base de données

```bash
.venv/bin/python manage.py migrate
```

Les migrations créent le schéma complet : utilisateurs et rôles, catalogue,
fournisseurs, clients, lots, mouvements, inventaires, achats, ventes, paiements,
retours, paramètres et journal d’audit.

### 2.5 Charger les données fictives

```bash
.venv/bin/python manage.py donnees_demo
```

La commande crée un jeu de démonstration cohérent (comptes, médicaments, lots,
achats, ventes, retours, inventaire). Elle refuse de s’exécuter si la base
contient déjà des données métier.

Pour repartir de zéro sur une base de **développement uniquement** :

```bash
.venv/bin/python manage.py donnees_demo --reinitialiser
```

> `--reinitialiser` exécute un `flush` : toutes les données sont supprimées.
> Ne jamais l’utiliser sur une base de production.

### 2.6 Lancer le serveur

```bash
.venv/bin/python manage.py runserver
```

Ouvrir <http://127.0.0.1:8000/>. L’administration Django est disponible sur
`/admin/`.

### 2.7 Vérifier l’installation

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py test
```

Résultat attendu : `System check identified no issues` et une suite de tests
au vert (110 tests au moment de la rédaction).

---

## 3. Comptes de démonstration

Créés par `donnees_demo`, mot de passe commun **`PharmaGest2026!`** :

| Identifiant | Rôle |
| --- | --- |
| `admin` | Administrateur / superutilisateur |
| `pharmacien` | Pharmacien responsable |
| `stock` | Gestionnaire de stock |
| `caissier` | Caissier |
| `gestion` | Responsable de gestion |

Ces comptes sont fictifs. Les supprimer ou changer leurs mots de passe avant
toute utilisation réelle.

---

## 4. Installation en production (PostgreSQL)

### 4.1 Dépendances supplémentaires

Décommenter dans `requirements.txt` :

```text
psycopg[binary]>=3.1
gunicorn>=21.2
```

Puis :

```bash
.venv/bin/pip install -r requirements.txt
```

### 4.2 Créer la base PostgreSQL

```bash
sudo -u postgres psql
```

```sql
CREATE DATABASE pharmagest;
CREATE USER pharmagest WITH ENCRYPTED PASSWORD 'mot-de-passe-solide';
GRANT ALL PRIVILEGES ON DATABASE pharmagest TO pharmagest;
ALTER DATABASE pharmagest OWNER TO pharmagest;
\q
```

Configurer `.env` :

```bash
DATABASE_ENGINE=postgresql
DB_NAME=pharmagest
DB_USER=pharmagest
DB_PASSWORD=mot-de-passe-solide
DB_HOST=localhost
DB_PORT=5432
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=pharmacie.example.mg,www.pharmacie.example.mg
DJANGO_CSRF_TRUSTED_ORIGINS=https://pharmacie.example.mg,https://www.pharmacie.example.mg
DJANGO_SECRET_KEY=<clé-générée>
```

### 4.3 Appliquer les migrations et les fichiers statiques

```bash
set -a; . ./.env; set +a
.venv/bin/python manage.py migrate
.venv/bin/python manage.py collectstatic --noinput
```

### 4.4 Lancer Gunicorn

```bash
.venv/bin/gunicorn config.wsgi:application \
  --bind 127.0.0.1:8000 \
  --workers 3 \
  --timeout 60
```

Exemple d’unité systemd `/etc/systemd/system/pharmagest.service` :

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
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now pharmagest
sudo systemctl status pharmagest
```

### 4.5 Nginx et HTTPS

Exemple de virtual host :

```nginx
server {
    listen 80;
    server_name pharmacie.example.mg www.pharmacie.example.mg;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name pharmacie.example.mg www.pharmacie.example.mg;

    ssl_certificate     /etc/letsencrypt/live/pharmacie.example.mg/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/pharmacie.example.mg/privkey.pem;

    client_max_body_size 10M;

    location /static/ {
        alias /srv/pharmagest/staticfiles/;
        expires 30d;
        access_log off;
    }

    location /media/ {
        alias /srv/pharmagest/media/;
        expires 7d;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

Avec `DEBUG=False`, PharmaGest active la redirection HTTPS, les cookies
sécurisés, HSTS et les en-têtes de sécurité. Vérifier la configuration :

```bash
.venv/bin/python manage.py check --deploy
```

Les avertissements de développement (`SECRET_KEY` de test, `DEBUG=True`) doivent
disparaître une fois les variables de production appliquées.

---

## 5. Sauvegarde et restauration

### 5.1 SQLite

```bash
.venv/bin/python manage.py sauvegarde_db
```

Le fichier est créé dans `backups/`. Restauration :

```bash
.venv/bin/python manage.py restaurer_db backups/pharmagest_AAAAMMJJ_HHMMSS.sqlite3 --force
```

> La restauration remplace la base courante. Sauvegarder la base actuelle avant
> toute restauration et ne jamais lancer la commande sur une base de production
> sans validation.

### 5.2 PostgreSQL

```bash
pg_dump -Fc -U pharmagest -h localhost pharmagest > sauvegarde_pharmagest.dump
pg_restore -U pharmagest -h localhost -d pharmagest --clean --if-exists sauvegarde_pharmagest.dump
```

### 5.3 Bonnes pratiques

- automatiser une sauvegarde quotidienne ;
- conserver les fichiers hors du serveur (stockage chiffré, disque externe) ;
- tester régulièrement une restauration ;
- sauvegarder aussi `media/` (photos et logo) et `.env` (dans un coffre-fort) ;
- ne jamais versionner les sauvegardes ni les secrets.

---

## 6. Dépannage

| Symptôme | Cause probable | Solution |
| --- | --- | --- |
| `ModuleNotFoundError: django` | environnement virtuel non activé | utiliser `.venv/bin/python` |
| `no such table` | migrations non appliquées | `manage.py migrate` |
| `CSRF verification failed` | origine HTTPS absente | renseigner `DJANGO_CSRF_TRUSTED_ORIGINS` |
| `DisallowedHost` | domaine absent | compléter `DJANGO_ALLOWED_HOSTS` |
| Page sans style | fichiers statiques non collectés | `collectstatic` + configuration Nginx |
| Photos non affichées | `MEDIA_ROOT`/Nginx mal configuré | vérifier `media/` et l’alias Nginx |
| E-mail de réinitialisation invisible | backend console | configurer SMTP en production |
| `database is locked` (SQLite) | accès concurrents | utiliser PostgreSQL en production |

---

## 7. Checklist de mise en service

- [ ] Python 3.12+ et environnement virtuel créés.
- [ ] `pip install -r requirements.txt` exécuté.
- [ ] `.env` renseigné (secret, hôtes, base, e-mail).
- [ ] `manage.py migrate` exécuté.
- [ ] `manage.py collectstatic` exécuté.
- [ ] `manage.py check` et `manage.py test` au vert.
- [ ] Comptes de démonstration supprimés ou mots de passe changés.
- [ ] HTTPS et HSTS actifs.
- [ ] Sauvegardes automatiques testées.
- [ ] Droits des dossiers `media/`, `backups/`, `logs/` vérifiés.
- [ ] Journal d’audit consulté après les premiers tests.
- [ ] Mentions légales et paramètres de la pharmacie personnalisés.
