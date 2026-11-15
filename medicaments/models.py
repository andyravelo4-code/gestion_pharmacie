"""Modèles des médicaments et des catégories."""
import uuid
from decimal import Decimal

from django.contrib.staticfiles import finders
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone

from core.validators import ValiderImage


def chemin_photo(instance, filename):
    """Range les photos par année/mois avec un nom unique."""
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    return f"medicaments/{timezone.now():%Y/%m}/{uuid.uuid4().hex}.{extension}"


class Categorie(models.Model):
    nom = models.CharField("Nom", max_length=120, unique=True)
    description = models.TextField("Description", blank=True)
    date_creation = models.DateTimeField("Date de création", auto_now_add=True)
    date_modification = models.DateTimeField("Date de modification", auto_now=True)

    class Meta:
        verbose_name = "catégorie"
        verbose_name_plural = "catégories"
        ordering = ["nom"]

    def __str__(self):
        return self.nom

    @property
    def nombre_medicaments(self):
        return self.medicaments.count()

    def peut_etre_supprimee(self):
        return not self.medicaments.exists()


class Medicament(models.Model):
    class Forme(models.TextChoices):
        COMPRIME = "Comprimé", "Comprimé"
        GELULE = "Gélule", "Gélule"
        SIROP = "Sirop", "Sirop"
        SUSPENSION = "Suspension", "Suspension"
        INJECTABLE = "Injectable", "Injectable"
        POMMADE = "Pommade", "Pommade"
        CREME = "Crème", "Crème"
        GOUTTES = "Gouttes", "Gouttes"
        SUPPOSITOIRE = "Suppositoire", "Suppositoire"
        AUTRE = "Autre", "Autre"

    class Statut(models.TextChoices):
        ACTIF = "ACTIF", "Actif"
        ARCHIVE = "ARCHIVE", "Archivé"

    nom = models.CharField("Nom commercial", max_length=150)
    denomination_generique = models.CharField("Dénomination générique (DCI)", max_length=150, blank=True)
    categorie = models.ForeignKey(
        Categorie,
        verbose_name="Catégorie",
        on_delete=models.PROTECT,
        related_name="medicaments",
    )
    forme = models.CharField("Forme pharmaceutique", max_length=50, choices=Forme.choices)
    dosage = models.CharField("Dosage", max_length=80, help_text="Ex. : 500 mg")
    laboratoire = models.CharField("Laboratoire", max_length=150, blank=True)
    code_barres = models.CharField(
        "Code-barres", max_length=80, unique=True, null=True, blank=True
    )
    photo = models.ImageField(
        "Photo",
        upload_to=chemin_photo,
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(["jpg", "jpeg", "png", "webp", "gif"]),
            ValiderImage(),
        ],
    )
    prix_achat = models.DecimalField(
        "Prix d'achat",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    prix_vente = models.DecimalField(
        "Prix de vente",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    seuil_alerte = models.PositiveIntegerField(
        "Seuil d'alerte", default=10, validators=[MinValueValidator(0)]
    )
    statut = models.CharField("Statut", max_length=10, choices=Statut.choices, default=Statut.ACTIF)
    date_creation = models.DateTimeField("Date de création", auto_now_add=True)
    date_modification = models.DateTimeField("Date de modification", auto_now=True)

    class Meta:
        verbose_name = "médicament"
        verbose_name_plural = "médicaments"
        ordering = ["nom"]
        indexes = [
            models.Index(fields=["nom"]),
            models.Index(fields=["code_barres"]),
            models.Index(fields=["statut"]),
        ]

    def __str__(self):
        return f"{self.nom} {self.dosage}".strip()

    def get_absolute_url(self):
        return reverse("medicaments:detail", args=[self.pk])

    @property
    def photo_url(self):
        """URL d'affichage de la photo, avec repli sur les visuels livrés.

        Le dossier ``media/`` n'est pas versionné : une base restaurée peut
        référencer une photo absente du disque. On retombe alors sur le visuel
        de démonstration stocké dans ``static/img/medicaments/demo/`` afin de
        ne jamais afficher une image cassée.
        """
        if self.photo:
            try:
                if self.photo.storage.exists(self.photo.name):
                    return self.photo.url
            except (OSError, ValueError):
                pass
        nom = (
            self.photo.name.rsplit("/", 1)[-1]
            if self.photo
            else f"medicament_{self.pk or 0:02d}.jpg"
        )
        chemin = f"img/medicaments/demo/{nom}"
        if finders.find(chemin):
            return static(chemin)
        return ""

    @property
    def est_actif(self):
        return self.statut == self.Statut.ACTIF

    @property
    def marge_unitaire(self):
        return self.prix_vente - self.prix_achat

    def stock_total(self):
        """Stock physique, tous lots confondus."""
        return self.lots.aggregate(total=models.Sum("quantite"))["total"] or 0

    def stock_disponible(self):
        """Stock délivrable : lots non périmés, non bloqués et non vides (FEFO)."""
        return (
            self.lots.filter(
                bloque=False,
                date_peremption__gte=timezone.localdate(),
                quantite__gt=0,
            ).aggregate(total=models.Sum("quantite"))["total"]
            or 0
        )

    @property
    def est_en_alerte(self):
        return self.est_actif and self.stock_disponible() <= self.seuil_alerte

    @property
    def est_en_rupture(self):
        return self.stock_disponible() <= 0

    def archiver(self):
        self.statut = self.Statut.ARCHIVE
        self.save(update_fields=["statut", "date_modification"])

    def reactiver(self):
        self.statut = self.Statut.ACTIF
        self.save(update_fields=["statut", "date_modification"])

    def historique_sensible(self):
        """Vrai si le médicament est référencé dans des opérations passées."""
        return (
            self.lignes_achat.exists()
            or self.lignes_vente.exists()
            or self.lots.exists()
            or self.mouvements.exists()
        )
