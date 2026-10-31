"""Achats : commandes fournisseurs et réceptions effectives."""
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from core.utils import generer_numero
from fournisseurs.models import Fournisseur
from medicaments.models import Medicament


class CommandeAchat(models.Model):
    class Statut(models.TextChoices):
        BROUILLON = "BROUILLON", "Brouillon"
        COMMANDEE = "COMMANDEE", "Commandée"
        PARTIELLEMENT_RECEPTIONNEE = "PARTIELLEMENT_RECEPTIONNEE", "Partiellement réceptionnée"
        RECEPTIONNEE = "RECEPTIONNEE", "Entièrement réceptionnée"
        ANNULEE = "ANNULEE", "Annulée"

    numero = models.CharField("Numéro", max_length=40, unique=True, blank=True)
    fournisseur = models.ForeignKey(
        Fournisseur,
        verbose_name="Fournisseur",
        on_delete=models.PROTECT,
        related_name="commandes",
    )
    statut = models.CharField(
        "Statut", max_length=30, choices=Statut.choices, default=Statut.BROUILLON, db_index=True
    )
    date_creation = models.DateTimeField("Date de création", auto_now_add=True)
    date_commande = models.DateTimeField("Date de validation", null=True, blank=True)
    date_modification = models.DateTimeField("Date de modification", auto_now=True)
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Créé par",
        on_delete=models.SET_NULL,
        null=True,
        related_name="commandes_achat",
    )
    notes = models.TextField("Notes", blank=True)

    class Meta:
        verbose_name = "commande d'achat"
        verbose_name_plural = "commandes d'achat"
        ordering = ["-date_creation"]
        indexes = [models.Index(fields=["statut"]), models.Index(fields=["date_creation"])]

    def __str__(self):
        return f"{self.numero} — {self.fournisseur}"

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = generer_numero("CMD", CommandeAchat)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("achats:detail", args=[self.pk])

    @property
    def montant_total(self):
        return sum((ligne.sous_total for ligne in self.lignes.all()), Decimal("0"))

    @property
    def montant_receptionne(self):
        total = sum(
            (
                ligne.prix_achat_unitaire * ligne.quantite_recue
                for ligne in self.lignes.all()
            ),
            Decimal("0"),
        )
        return total

    @property
    def quantite_totale_commandee(self):
        return sum((ligne.quantite_commandee for ligne in self.lignes.all()), 0)

    @property
    def quantite_totale_recue(self):
        return sum((ligne.quantite_recue for ligne in self.lignes.all()), 0)

    @property
    def est_modifiable(self):
        return self.statut == self.Statut.BROUILLON

    @property
    def peut_etre_receptionnee(self):
        return self.statut in {
            self.Statut.COMMANDEE,
            self.Statut.PARTIELLEMENT_RECEPTIONNEE,
        }

    @property
    def peut_etre_annulee(self):
        return self.statut in {self.Statut.BROUILLON, self.Statut.COMMANDEE}

    def recalculer_statut(self, sauvegarder=True):
        """Met à jour le statut à partir des quantités réellement reçues."""
        if self.statut in {self.Statut.BROUILLON, self.Statut.ANNULEE}:
            return self.statut
        lignes = list(self.lignes.all())
        if not lignes:
            nouveau = self.Statut.COMMANDEE
        elif all(ligne.quantite_recue >= ligne.quantite_commandee for ligne in lignes):
            nouveau = self.Statut.RECEPTIONNEE
        elif any(ligne.quantite_recue > 0 for ligne in lignes):
            nouveau = self.Statut.PARTIELLEMENT_RECEPTIONNEE
        else:
            nouveau = self.Statut.COMMANDEE
        if nouveau != self.statut:
            self.statut = nouveau
            if sauvegarder:
                self.save(update_fields=["statut", "date_modification"])
        return self.statut


class LigneAchat(models.Model):
    commande = models.ForeignKey(
        CommandeAchat, verbose_name="Commande", on_delete=models.CASCADE, related_name="lignes"
    )
    medicament = models.ForeignKey(
        Medicament, verbose_name="Médicament", on_delete=models.PROTECT, related_name="lignes_achat"
    )
    quantite_commandee = models.PositiveIntegerField(
        "Quantité commandée", validators=[MinValueValidator(1)]
    )
    quantite_recue = models.PositiveIntegerField("Quantité reçue", default=0)
    prix_achat_unitaire = models.DecimalField(
        "Prix d'achat unitaire",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )

    class Meta:
        verbose_name = "ligne de commande"
        verbose_name_plural = "lignes de commande"
        constraints = [
            models.UniqueConstraint(
                fields=["commande", "medicament"], name="medicament_unique_par_commande"
            )
        ]

    def __str__(self):
        return f"{self.medicament} × {self.quantite_commandee}"

    @property
    def sous_total(self):
        return self.quantite_commandee * self.prix_achat_unitaire

    @property
    def quantite_restante(self):
        return max(self.quantite_commandee - self.quantite_recue, 0)


class ReceptionAchat(models.Model):
    numero = models.CharField("Numéro", max_length=40, unique=True, blank=True)
    commande = models.ForeignKey(
        CommandeAchat,
        verbose_name="Commande",
        on_delete=models.PROTECT,
        related_name="receptions",
    )
    date_reception = models.DateTimeField("Date de réception", default=timezone.now)
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Réceptionné par",
        on_delete=models.SET_NULL,
        null=True,
        related_name="receptions_achat",
    )
    notes = models.TextField("Notes", blank=True)

    class Meta:
        verbose_name = "réception d'achat"
        verbose_name_plural = "réceptions d'achat"
        ordering = ["-date_reception"]

    def __str__(self):
        return f"{self.numero} — {self.commande}"

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = generer_numero("REC", ReceptionAchat)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("achats:reception_detail", args=[self.pk])

    @property
    def montant_total(self):
        return sum((ligne.sous_total for ligne in self.lignes.all()), Decimal("0"))

    @property
    def quantite_totale(self):
        return sum((ligne.quantite for ligne in self.lignes.all()), 0)


class LigneReception(models.Model):
    reception = models.ForeignKey(
        ReceptionAchat, verbose_name="Réception", on_delete=models.CASCADE, related_name="lignes"
    )
    ligne_achat = models.ForeignKey(
        LigneAchat,
        verbose_name="Ligne de commande",
        on_delete=models.PROTECT,
        related_name="lignes_reception",
    )
    lot = models.ForeignKey(
        "stock.LotStock",
        verbose_name="Lot créé",
        on_delete=models.PROTECT,
        related_name="lignes_reception",
    )
    quantite = models.PositiveIntegerField("Quantité reçue", validators=[MinValueValidator(1)])
    numero_lot = models.CharField("Numéro de lot", max_length=80)
    date_peremption = models.DateField("Date de péremption")
    prix_unitaire = models.DecimalField(
        "Prix unitaire", max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0"))]
    )

    class Meta:
        verbose_name = "ligne de réception"
        verbose_name_plural = "lignes de réception"
        constraints = [
            models.UniqueConstraint(
                fields=["reception", "ligne_achat"], name="ligne_achat_unique_par_reception"
            )
        ]

    def __str__(self):
        return f"{self.ligne_achat.medicament} × {self.quantite}"

    @property
    def sous_total(self):
        return self.quantite * self.prix_unitaire
