"""Utilisateurs et rôles métier de PharmaGest."""
from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.Model):
    """Rôle métier ; un utilisateur peut en cumuler plusieurs."""

    code = models.CharField("Code", max_length=30, unique=True)
    nom = models.CharField("Nom du rôle", max_length=100)
    description = models.TextField("Description", blank=True)
    ordre = models.PositiveSmallIntegerField("Ordre d'affichage", default=0)

    class Meta:
        verbose_name = "rôle"
        verbose_name_plural = "rôles"
        ordering = ["ordre", "nom"]

    def __str__(self):
        return self.nom


class Utilisateur(AbstractUser):
    """Utilisateur personnalisé avec rôles cumulables et statut d'activation."""

    telephone = models.CharField("Téléphone", max_length=40, blank=True)
    adresse = models.CharField("Adresse", max_length=255, blank=True)
    roles = models.ManyToManyField(
        Role,
        verbose_name="Rôles",
        related_name="utilisateurs",
        blank=True,
    )
    date_creation = models.DateTimeField("Date de création", auto_now_add=True)

    class Meta:
        verbose_name = "utilisateur"
        verbose_name_plural = "utilisateurs"
        ordering = ["last_name", "first_name", "username"]

    def __str__(self):
        return self.nom_complet

    @property
    def nom_complet(self):
        complet = self.get_full_name().strip()
        return complet or self.username

    @property
    def codes_roles(self):
        if self.is_superuser:
            return {"ADMIN"}
        if not hasattr(self, "_codes_roles_cache"):
            self._codes_roles_cache = set(self.roles.values_list("code", flat=True))
        return self._codes_roles_cache

    def a_role(self, *codes):
        """Vrai si l'utilisateur possède au moins un des rôles demandés."""
        if not self.is_authenticated:
            return False
        if self.is_superuser or "ADMIN" in self.codes_roles:
            return True
        return bool(self.codes_roles.intersection(set(codes)))

    def role_principal(self):
        role = self.roles.order_by("ordre").first()
        return role.nom if role else "Aucun rôle"

    role_principal.short_description = "Rôle principal"
