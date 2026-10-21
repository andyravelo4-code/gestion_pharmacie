"""Fournisseurs."""
from django.db import models
from django.urls import reverse


class Fournisseur(models.Model):
    nom = models.CharField("Raison sociale", max_length=180, unique=True)
    adresse = models.CharField("Adresse", max_length=255, blank=True)
    telephone = models.CharField("Téléphone", max_length=40, blank=True)
    email = models.EmailField("E-mail", blank=True)
    numero_fiscal = models.CharField("Numéro fiscal / identifiant professionnel", max_length=80, blank=True)
    contact_principal = models.CharField("Contact principal", max_length=150, blank=True)
    actif = models.BooleanField("Actif", default=True)
    date_creation = models.DateTimeField("Date de création", auto_now_add=True)
    date_modification = models.DateTimeField("Date de modification", auto_now=True)

    class Meta:
        verbose_name = "fournisseur"
        verbose_name_plural = "fournisseurs"
        ordering = ["nom"]
        indexes = [models.Index(fields=["nom"]), models.Index(fields=["telephone"])]

    def __str__(self):
        return self.nom

    def get_absolute_url(self):
        return reverse("fournisseurs:detail", args=[self.pk])

    @property
    def nombre_commandes(self):
        return self.commandes.count()

    @property
    def montant_total_achats(self):
        from achats.models import LigneAchat

        total = LigneAchat.objects.filter(
            commande__fournisseur=self,
            commande__statut__in=[
                "COMMANDEE",
                "PARTIELLEMENT_RECEPTIONNEE",
                "RECEPTIONNEE",
            ],
        ).aggregate(
            total=models.Sum(
                models.F("quantite_commandee") * models.F("prix_achat_unitaire"),
                output_field=models.DecimalField(max_digits=14, decimal_places=2),
            )
        )["total"]
        return total or 0

    def desactiver(self):
        self.actif = False
        self.save(update_fields=["actif", "date_modification"])

    def reactiver(self):
        self.actif = True
        self.save(update_fields=["actif", "date_modification"])
