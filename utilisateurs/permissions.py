"""Permissions applicatives basées sur les rôles métier.

Un utilisateur peut cumuler plusieurs rôles (exigence du cahier des charges).
Les superutilisateurs et le rôle Administrateur disposent de tous les droits.
"""
from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

# Codes de rôles (synchronisés avec la table Role)
ADMIN = "ADMIN"
PHARMACIEN = "PHARMACIEN"
GESTION_STOCK = "GESTION_STOCK"
CAISSIER = "CAISSIER"
RESPONSABLE_GESTION = "RESPONSABLE_GESTION"

TOUS_LES_ROLES = (ADMIN, PHARMACIEN, GESTION_STOCK, CAISSIER, RESPONSABLE_GESTION)

# Matrice des autorisations
ADMIN_SEUL = (ADMIN,)
GESTION_MEDICAMENTS = (ADMIN, PHARMACIEN)
GESTION_STOCK_ROLES = (ADMIN, PHARMACIEN, GESTION_STOCK)
GESTION_ACHATS_ROLES = (ADMIN, PHARMACIEN, GESTION_STOCK)
VENTES_ROLES = (ADMIN, PHARMACIEN, CAISSIER)
LECTURE_GESTION = (ADMIN, PHARMACIEN, RESPONSABLE_GESTION)
LECTURE_MEDICAMENTS = TOUS_LES_ROLES

# Rôles hérités pour les imports historiques
GESTION_ACHATS = GESTION_ACHATS_ROLES
VENTES = VENTES_ROLES


class RoleRequisMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restreint une vue aux utilisateurs authentifiés possédant un rôle autorisé.

    ``roles_autorises`` vide signifie : tout utilisateur connecté.
    Un superutilisateur passe toujours.
    """

    roles_autorises = ()

    def test_func(self):
        utilisateur = self.request.user
        if not utilisateur.is_authenticated:
            return False
        if utilisateur.is_superuser:
            return True
        if not self.roles_autorises:
            return True
        return utilisateur.a_role(*self.roles_autorises)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied(
                "Votre profil ne vous autorise pas à accéder à cette fonction."
            )
        return super().handle_no_permission()


class AdminRequisMixin(RoleRequisMixin):
    roles_autorises = ADMIN_SEUL
