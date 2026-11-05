"""Ventes, paiements, retours et annulations."""
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from clients.models import Client
from core.utils import generer_numero
from medicaments.models import Medicament
from stock.models import LotStock


class Vente(models.Model):
    class Statut(models.TextChoices):
        VALIDEE = "VALIDEE", "Validée"
        ANNULEE = "ANNULEE", "Annulée"

    numero = models.CharField("Numéro", max_length=40, unique=True, blank=True)
    client = models.ForeignKey(
        Client,
        verbose_name="Client",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ventes",
    )
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Caissier",
        on_delete=models.SET_NULL,
        null=True,
        related_name="ventes",
    )
    date_vente = models.DateTimeField("Date de vente", auto_now_add=True, db_index=True)
    statut = models.CharField(
        "Statut", max_length=10, choices=Statut.choices, default=Statut.VALIDEE, db_index=True
    )
    montant_total = models.DecimalField(
        "Montant total (prix appliqués)", max_digits=14, decimal_places=2, default=Decimal("0")
    )
    cle_idempotence = models.UUIDField(
        "Clé d'idempotence", null=True, blank=True, unique=True, editable=False
    )
    notes = models.TextField("Notes", blank=True)

    class Meta:
        verbose_name = "vente"
        verbose_name_plural = "ventes"
        ordering = ["-date_vente"]
        indexes = [models.Index(fields=["date_vente"]), models.Index(fields=["statut"])]

    def __str__(self):
        return f"{self.numero} — {self.montant_total}"

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = generer_numero("VTE", Vente)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("ventes:detail", args=[self.pk])

    @property
    def est_annulee(self):
        return self.statut == self.Statut.ANNULEE

    @property
    def montant_paye(self):
        return sum(
            (paiement.montant for paiement in self.paiements.filter(statut=Paiement.Statut.CONFIRME)),
            Decimal("0"),
        )

    @property
    def montant_retourne(self):
        return sum((retour.montant_rembourse for retour in self.retours.all()), Decimal("0"))

    @property
    def montant_net(self):
        return self.montant_total - self.montant_retourne

    @property
    def reste_a_payer(self):
        return max(self.montant_total - self.montant_paye, Decimal("0"))

    @property
    def nombre_articles(self):
        return sum((ligne.quantite for ligne in self.lignes.all()), 0)

    @property
    def peut_etre_retournee(self):
        return any(ligne.quantite_retournable > 0 for ligne in self.lignes.all())


class LigneVente(models.Model):
    vente = models.ForeignKey(
        Vente, verbose_name="Vente", on_delete=models.PROTECT, related_name="lignes"
    )
    medicament = models.ForeignKey(
        Medicament, verbose_name="Médicament", on_delete=models.PROTECT, related_name="lignes_vente"
    )
    lot = models.ForeignKey(
        LotStock, verbose_name="Lot délivré", on_delete=models.PROTECT, related_name="lignes_vente"
    )
    quantite = models.PositiveIntegerField("Quantité", validators=[MinValueValidator(1)])
    prix_unitaire = models.DecimalField(
        "Prix appliqué",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Prix figé au moment de la vente (RG12).",
    )
    sous_total = models.DecimalField("Sous-total", max_digits=14, decimal_places=2)

    class Meta:
        verbose_name = "ligne de vente"
        verbose_name_plural = "lignes de vente"
        ordering = ["pk"]
        constraints = [
            models.UniqueConstraint(fields=["vente", "lot"], name="lot_unique_par_vente")
        ]

    def __str__(self):
        return f"{self.medicament} × {self.quantite}"

    def save(self, *args, **kwargs):
        self.sous_total = self.quantite * self.prix_unitaire
        super().save(*args, **kwargs)

    @property
    def quantite_retournee(self):
        return (
            self.lignes_retour.aggregate(total=models.Sum("quantite"))["total"] or 0
        )

    @property
    def quantite_retournable(self):
        return max(self.quantite - self.quantite_retournee, 0)

    @property
    def montant_retourne(self):
        return sum((ligne.sous_total for ligne in self.lignes_retour.all()), Decimal("0"))


class Paiement(models.Model):
    class Mode(models.TextChoices):
        ESPECES = "ESPECES", "Espèces"
        MOBILE_MONEY = "MOBILE_MONEY", "Mobile money"
        CARTE = "CARTE", "Carte bancaire"
        VIREMENT = "VIREMENT", "Virement"
        CHEQUE = "CHEQUE", "Chèque"

    class Statut(models.TextChoices):
        EN_ATTENTE = "EN_ATTENTE", "En attente de vérification"
        CONFIRME = "CONFIRME", "Confirmé"
        ECHOUE = "ECHOUE", "Échoué"
        REMBOURSE = "REMBOURSE", "Remboursé"

    MODES_ELECTRONIQUES = {Mode.MOBILE_MONEY, Mode.CARTE, Mode.VIREMENT}

    vente = models.ForeignKey(
        Vente, verbose_name="Vente", on_delete=models.PROTECT, related_name="paiements"
    )
    montant = models.DecimalField(
        "Montant", max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0"))]
    )
    mode = models.CharField("Mode de paiement", max_length=20, choices=Mode.choices)
    statut = models.CharField(
        "Statut", max_length=15, choices=Statut.choices, default=Statut.EN_ATTENTE
    )
    reference = models.CharField("Référence / transaction", max_length=100, blank=True)
    montant_recu = models.DecimalField(
        "Montant reçu", max_digits=14, decimal_places=2, null=True, blank=True
    )
    date_paiement = models.DateTimeField("Date", auto_now_add=True)
    confirme_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Confirmé par",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="paiements_confirmes",
    )
    date_confirmation = models.DateTimeField("Date de confirmation", null=True, blank=True)

    class Meta:
        verbose_name = "paiement"
        verbose_name_plural = "paiements"
        ordering = ["-date_paiement"]

    def __str__(self):
        return f"{self.vente.numero} — {self.montant} ({self.get_mode_display()})"

    @property
    def est_confirme(self):
        return self.statut == self.Statut.CONFIRME

    @property
    def est_electronique(self):
        return self.mode in self.MODES_ELECTRONIQUES

    def confirmer(self, utilisateur=None):
        if self.statut == self.Statut.CONFIRME:
            return self
        self.statut = self.Statut.CONFIRME
        self.confirme_par = utilisateur
        self.date_confirmation = timezone.now()
        self.save(update_fields=["statut", "confirme_par", "date_confirmation"])
        return self


class RetourVente(models.Model):
    class Type(models.TextChoices):
        RETOUR = "RETOUR", "Retour de produit"
        ANNULATION = "ANNULATION", "Annulation de vente"

    class ModeRemboursement(models.TextChoices):
        ESPECES = "ESPECES", "Espèces"
        MOBILE_MONEY = "MOBILE_MONEY", "Mobile money"
        AVOIR = "AVOIR", "Avoir client"
        AUCUN = "AUCUN", "Aucun remboursement"

    numero = models.CharField("Numéro", max_length=40, unique=True, blank=True)
    vente = models.ForeignKey(
        Vente, verbose_name="Vente d'origine", on_delete=models.PROTECT, related_name="retours"
    )
    type_retour = models.CharField(
        "Type", max_length=15, choices=Type.choices, default=Type.RETOUR
    )
    date_retour = models.DateTimeField("Date du retour", auto_now_add=True)
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Enregistré par",
        on_delete=models.SET_NULL,
        null=True,
        related_name="retours_vente",
    )
    motif = models.CharField("Motif", max_length=255)
    montant_rembourse = models.DecimalField(
        "Montant remboursé", max_digits=14, decimal_places=2, default=Decimal("0")
    )
    mode_remboursement = models.CharField(
        "Mode de remboursement",
        max_length=20,
        choices=ModeRemboursement.choices,
        default=ModeRemboursement.ESPECES,
    )
    notes = models.TextField("Notes", blank=True)

    class Meta:
        verbose_name = "retour de vente"
        verbose_name_plural = "retours de vente"
        ordering = ["-date_retour"]

    def __str__(self):
        return f"{self.numero} — {self.vente.numero}"

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = generer_numero("RET", RetourVente)
        super().save(*args, **kwargs)

    @property
    def quantite_totale(self):
        return sum((ligne.quantite for ligne in self.lignes.all()), 0)


class LigneRetour(models.Model):
    retour = models.ForeignKey(
        RetourVente, verbose_name="Retour", on_delete=models.CASCADE, related_name="lignes"
    )
    ligne_vente = models.ForeignKey(
        LigneVente,
        verbose_name="Ligne de vente",
        on_delete=models.PROTECT,
        related_name="lignes_retour",
    )
    quantite = models.PositiveIntegerField("Quantité retournée", validators=[MinValueValidator(1)])
    prix_unitaire = models.DecimalField("Prix appliqué", max_digits=12, decimal_places=2)
    remise_en_stock = models.BooleanField("Remise en stock", default=False)

    class Meta:
        verbose_name = "ligne de retour"
        verbose_name_plural = "lignes de retour"
        constraints = [
            models.UniqueConstraint(
                fields=["retour", "ligne_vente"], name="ligne_vente_unique_par_retour"
            )
        ]

    def __str__(self):
        return f"{self.ligne_vente.medicament} × {self.quantite}"

    @property
    def sous_total(self):
        return self.quantite * self.prix_unitaire
