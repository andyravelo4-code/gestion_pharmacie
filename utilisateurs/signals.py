"""Signaux : rôles par défaut et journalisation des connexions."""
from django.apps import apps
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import post_migrate
from django.dispatch import receiver

from core.models import JournalAudit
from core.utils import journaliser

ROLES_PAR_DEFAUT = [
    ("ADMIN", "Administrateur", "Gère les utilisateurs, les paramètres et toutes les opérations.", 10),
    ("PHARMACIEN", "Pharmacien responsable", "Contrôle les médicaments, lots, achats et ventes.", 20),
    ("GESTION_STOCK", "Gestionnaire de stock", "Gère fournisseurs, commandes, réceptions et inventaires.", 30),
    ("CAISSIER", "Caissier", "Enregistre les ventes, paiements et imprime les reçus.", 40),
    ("RESPONSABLE_GESTION", "Responsable de gestion", "Consulte statistiques, recettes et rapports.", 50),
]


@receiver(post_migrate)
def creer_roles_par_defaut(sender, **kwargs):
    """Garantit la présence des cinq rôles du cahier des charges."""
    if getattr(sender, "name", "") != "utilisateurs":
        return
    Role = apps.get_model("utilisateurs", "Role")
    for code, nom, description, ordre in ROLES_PAR_DEFAUT:
        Role.objects.get_or_create(
            code=code,
            defaults={"nom": nom, "description": description, "ordre": ordre},
        )


@receiver(user_logged_in)
def journaliser_connexion(sender, request, user, **kwargs):
    journaliser(
        request,
        JournalAudit.Action.CONNEXION,
        "Authentification",
        f"Connexion de {user.nom_complet}",
        objet=user,
    )


@receiver(user_logged_out)
def journaliser_deconnexion(sender, request, user, **kwargs):
    if user is not None:
        journaliser(
            request,
            JournalAudit.Action.DECONNEXION,
            "Authentification",
            f"Déconnexion de {user.nom_complet}",
            objet=user,
        )


@receiver(user_login_failed)
def journaliser_echec_connexion(sender, credentials, request, **kwargs):
    identifiant = credentials.get("username", "inconnu") if credentials else "inconnu"
    journaliser(
        request,
        JournalAudit.Action.CONNEXION,
        "Authentification",
        f"Échec de connexion pour « {identifiant} »",
        details="Identifiants invalides ou compte désactivé.",
    )
