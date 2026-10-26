"""Lots, mouvements de stock et inventaires."""
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from medicaments.models import Medicament


class LotStock(models.Model):
    """Lot physique d'un médicament, avec date de péremption (FEFO)."""

    medicament = models.ForeignKey(
        Medicament,
        verbose_name="Médicament",
        on_delete=models.PROTECT,
        related_name="lots",
    )
    numero_lot = models.CharField("Numéro de lot", max_length=80)
    date_peremption = models.DateField("Date de péremption", db_index=True)
    quantite = models.PositiveIntegerField("Quantité en stock", default=0)
    quantite_initiale = models.PositiveIntegerField("Quantité reçue initialement", default=0)
    prix_achat = models.DecimalField(
        "Prix d'achat unitaire", max_digits=12, decimal_places=2, default=Decimal("0")
    )
    fournisseur = models.ForeignKey(
        "fournisseurs.Fournisseur",
        verbose_name="Fournisseur",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lots",
    )
    bloque = models.BooleanField("Lot bloqué", default=False)
    motif_blocage = models.CharField("Motif du blocage", max_length=255, blank=True)
    date_reception = models.DateTimeField("Date de réception", default=timezone.now)
    date_creation = models.DateTimeField("Date de création", auto_now_add=True)
    date_modification = models.DateTimeField("Date de modification", auto_now=True)

    class Meta:
        verbose_name = "lot de stock"
        verbose_name_plural = "lots de stock"
        ordering = ["date_peremption", "medicament__nom"]
        constraints = [
            models.UniqueConstraint(
                fields=["medicament", "numero_lot", "date_peremption"],
                name="lot_unique_par_medicament_numero_peremption",
            )
        ]
        indexes = [
            models.Index(fields=["date_peremption"]),
            models.Index(fields=["bloque"]),
        ]

    def __str__(self):
        return f"{self.medicament} — lot {self.numero_lot} ({self.date_peremption:%d/%m/%Y})"

    def get_absolute_url(self):
        return reverse("stock:lot_detail", args=[self.pk])

    @property
    def est_perime(self):
        return self.date_peremption < timezone.localdate()

    @property
    def jours_avant_peremption(self):
        return (self.date_peremption - timezone.localdate()).days

    @property
    def est_delivrable(self):
        return not self.bloque and not self.est_perime and self.quantite > 0

    @property
    def valeur_stock(self):
        return self.quantite * self.prix_achat

    def bloquer(self, motif=""):
        self.bloque = True
        self.motif_blocage = motif
        self.save(update_fields=["bloque", "motif_blocage", "date_modification"])

    def debloquer(self):
        self.bloque = False
        self.motif_blocage = ""
        self.save(update_fields=["bloque", "motif_blocage", "date_modification"])

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.date_peremption and self.date_peremption < timezone.localdate():
            # Un lot périmé peut exister (historique), mais il ne sera jamais vendu.
            pass
        if self.quantite < 0:
            raise ValidationError({"quantite": "La quantité ne peut pas être négative."})


class MouvementStock(models.Model):
    """Historique signé des entrées et sorties de stock (RG09)."""

    class Type(models.TextChoices):
        ENTREE = "ENTREE", "Entrée (réception)"
        SORTIE = "SORTIE", "Sortie (vente)"
        RETOUR = "RETOUR", "Retour de vente"
        CORRECTION_POSITIVE = "CORRECTION_POSITIVE", "Correction positive"
        CORRECTION_NEGATIVE = "CORRECTION_NEGATIVE", "Correction négative"
        PERTE = "PERTE", "Perte / destruction"

    medicament = models.ForeignKey(
        Medicament,
        verbose_name="Médicament",
        on_delete=models.PROTECT,
        related_name="mouvements",
    )
    lot = models.ForeignKey(
        LotStock,
        verbose_name="Lot",
        on_delete=models.PROTECT,
        related_name="mouvements",
        null=True,
        blank=True,
    )
    type_mouvement = models.CharField("Type", max_length=25, choices=Type.choices)
    quantite = models.IntegerField(
        "Quantité signée", help_text="Positive pour une entrée, négative pour une sortie."
    )
    prix_unitaire = models.DecimalField(
        "Prix unitaire", max_digits=12, decimal_places=2, null=True, blank=True
    )
    reference = models.CharField("Référence du document", max_length=80, blank=True)
    motif = models.CharField("Motif / commentaire", max_length=255, blank=True)
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Auteur",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mouvements_stock",
    )
    date = models.DateTimeField("Date", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "mouvement de stock"
        verbose_name_plural = "mouvements de stock"
        ordering = ["-date", "-id"]
        indexes = [
            models.Index(fields=["type_mouvement"]),
            models.Index(fields=["reference"]),
        ]

    def __str__(self):
        signe = "+" if self.quantite >= 0 else ""
        return f"{self.date:%d/%m/%Y} — {self.medicament} : {signe}{self.quantite}"

    @property
    def est_entree(self):
        return self.quantite > 0


class Inventaire(models.Model):
    class Statut(models.TextChoices):
        EN_COURS = "EN_COURS", "En cours"
        VALIDE = "VALIDE", "Validé"
        ANNULE = "ANNULE", "Annulé"

    numero = models.CharField("Numéro", max_length=40, unique=True)
    date_creation = models.DateTimeField("Date de création", auto_now_add=True)
    date_validation = models.DateTimeField("Date de validation", null=True, blank=True)
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Responsable",
        on_delete=models.SET_NULL,
        null=True,
        related_name="inventaires",
    )
    statut = models.CharField("Statut", max_length=10, choices=Statut.choices, default=Statut.EN_COURS)
    notes = models.TextField("Notes", blank=True)

    class Meta:
        verbose_name = "inventaire"
        verbose_name_plural = "inventaires"
        ordering = ["-date_creation"]

    def __str__(self):
        return f"{self.numero} — {self.get_statut_display()}"

    @property
    def est_modifiable(self):
        return self.statut == self.Statut.EN_COURS


class LigneInventaire(models.Model):
    inventaire = models.ForeignKey(
        Inventaire, verbose_name="Inventaire", on_delete=models.CASCADE, related_name="lignes"
    )
    lot = models.ForeignKey(
        LotStock, verbose_name="Lot", on_delete=models.PROTECT, related_name="lignes_inventaire"
    )
    quantite_theorique = models.PositiveIntegerField("Quantité théorique", default=0)
    quantite_comptee = models.PositiveIntegerField("Quantité comptée", default=0)

    class Meta:
        verbose_name = "ligne d'inventaire"
        verbose_name_plural = "lignes d'inventaire"
        constraints = [
            models.UniqueConstraint(fields=["inventaire", "lot"], name="ligne_inventaire_unique")
        ]

    def __str__(self):
        return f"{self.lot} — écart {self.ecart:+d}"

    @property
    def ecart(self):
        return self.quantite_comptee - self.quantite_theorique
