"""Contexte d'affichage : rôles et droits du menu."""
from utilisateurs.permissions import (
    ADMIN,
    ADMIN_SEUL,
    CAISSIER,
    GESTION_ACHATS_ROLES,
    GESTION_MEDICAMENTS,
    GESTION_STOCK_ROLES,
    PHARMACIEN,
    RESPONSABLE_GESTION,
    TOUS_LES_ROLES,
    VENTES_ROLES,
)


def roles_utilisateur(request):
    utilisateur = getattr(request, "user", None)
    contexte = {
        "est_connecte": bool(utilisateur and utilisateur.is_authenticated),
        "est_admin": False,
        "peut_medicaments": False,
        "peut_stock": False,
        "peut_achats": False,
        "peut_ventes": False,
        "peut_rapports": False,
        "peut_utilisateurs": False,
        "peut_parametres": False,
        "codes_roles": [],
    }
    if not utilisateur or not utilisateur.is_authenticated:
        return contexte

    if utilisateur.is_superuser:
        codes = set(TOUS_LES_ROLES) | {"SUPERUTILISATEUR"}
        est_admin = True
    else:
        codes = utilisateur.codes_roles
        est_admin = ADMIN in codes

    def autorise(roles):
        return est_admin or bool(codes.intersection(roles))

    contexte.update(
        {
            "est_admin": est_admin,
            "peut_medicaments": autorise(GESTION_MEDICAMENTS),
            "peut_stock": autorise(GESTION_STOCK_ROLES),
            "peut_achats": autorise(GESTION_ACHATS_ROLES),
            "peut_ventes": autorise(VENTES_ROLES),
            "peut_rapports": autorise(
                (ADMIN, PHARMACIEN, RESPONSABLE_GESTION)
            ),
            "peut_utilisateurs": autorise(ADMIN_SEUL),
            "peut_parametres": autorise(ADMIN_SEUL),
            "codes_roles": sorted(codes),
        }
    )
    return contexte
