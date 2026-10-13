"""
Configuration Django du projet PharmaGest.

Les valeurs sensibles sont lues dans l'environnement (voir .env.example).
En développement, des valeurs par défaut sûres sont utilisées.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def charger_fichier_env(chemin):
    """Charge un fichier .env simple (KEY=VALUE) sans dépendance externe."""
    chemin = Path(chemin)
    if not chemin.is_file():
        return
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, valeur = ligne.split("=", 1)
        cle = cle.strip()
        valeur = valeur.strip().strip("'\"")
        if cle and cle not in os.environ:
            os.environ[cle] = valeur


charger_fichier_env(BASE_DIR / ".env")


def env_bool(name, default=False):
    """Lit une variable d'environnement booléenne."""
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "oui", "yes", "on"}


def env_list(name, default=""):
    """Lit une liste séparée par des virgules."""
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# --------------------------------------------------------------------------
# Sécurité
# --------------------------------------------------------------------------
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-pharmagest-cle-a-remplacer-en-production-2026",
)
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]")
INTERNAL_IPS = ["127.0.0.1", "[::1]"]
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

# --------------------------------------------------------------------------
# Applications
# --------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # Applications PharmaGest
    "core.apps.CoreConfig",
    "utilisateurs.apps.UtilisateursConfig",
    "medicaments.apps.MedicamentsConfig",
    "fournisseurs.apps.FournisseursConfig",
    "clients.apps.ClientsConfig",
    "stock.apps.StockConfig",
    "achats.apps.AchatsConfig",
    "ventes.apps.VentesConfig",
    "rapports.apps.RapportsConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.pharmacie",
                "utilisateurs.context_processors.roles_utilisateur",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --------------------------------------------------------------------------
# Base de données (SQLite en développement, PostgreSQL en production)
# --------------------------------------------------------------------------
if os.environ.get("DATABASE_ENGINE") == "postgresql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "pharmagest"),
            "USER": os.environ.get("DB_USER", "pharmagest"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# --------------------------------------------------------------------------
# Authentification
# --------------------------------------------------------------------------
AUTH_USER_MODEL = "utilisateurs.Utilisateur"
LOGIN_URL = "utilisateurs:connexion"
LOGIN_REDIRECT_URL = "rapports:tableau_bord"
LOGOUT_REDIRECT_URL = "utilisateurs:connexion"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

SESSION_COOKIE_AGE = 8 * 3600  # 8 heures
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # nécessaire pour certains formulaires AJAX
LANGUAGE_COOKIE_NAME = "pharmagest_langue"

# --------------------------------------------------------------------------
# Internationalisation
# --------------------------------------------------------------------------
LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Indian/Antananarivo"
USE_I18N = True
USE_TZ = True

# --------------------------------------------------------------------------
# Fichiers statiques et médias
# --------------------------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Téléversements : limite globale et validation des images
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
MAX_IMAGE_SIZE = 3 * 1024 * 1024  # 3 Mo (validé côté serveur)

# --------------------------------------------------------------------------
# E-mails (réinitialisation de mot de passe)
# --------------------------------------------------------------------------
EMAIL_BACKEND = os.environ.get(
    "DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "PharmaGest <noreply@pharmagest.local>")

# --------------------------------------------------------------------------
# Sauvegardes
# --------------------------------------------------------------------------
BACKUP_DIR = BASE_DIR / "backups"

# --------------------------------------------------------------------------
# Sécurité de production
# --------------------------------------------------------------------------
if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    X_FRAME_OPTIONS = "DENY"

# Journalisation technique
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
        "fichier": {
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "logs" / "pharmagest.log",
            "encoding": "utf-8",
        },
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO"},
        "pharmagest": {"handlers": ["console", "fichier"], "level": "INFO", "propagate": False},
    },
}
(BASE_DIR / "logs").mkdir(exist_ok=True)
