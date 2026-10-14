"""Modèles transverses : paramètres de la pharmacie et journal d'audit."""
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class ParametrePharmacie(models.Model):
    """Paramètres généraux (ligne unique) utilisés notamment dans les PDF."""

    nom = models.CharField("Nom de la pharmacie", max_length=150, default="Pharmacie PharmaGest")
    adresse = models.CharField("Adresse", max_length=255, blank=True)
    telephone = models.CharField("Téléphone", max_length=40, blank=True)
    email = models.EmailField("E-mail", blank=True)
    numero_fiscal = models.CharField("NIF / Numéro fiscal", max_length=60, blank=True)
    devise = models.CharField("Devise", max_length=10, default="Ar")
    seuil_peremption_jours = models.PositiveIntegerField(
        "Seuil d'alerte péremption (jours)", default=30, validators=[MinValueValidator(1)]
    )
    mentions_legales = models.TextField(
        "Mentions légales",
        blank=True,
        default="Document généré par PharmaGest. Les mentions fiscales et légales doivent être "
        "adaptées à la réglementation en vigueur.",
    )
    logo = models.ImageField("Logo", upload_to="pharmacie/", blank=True, null=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "paramètres de la pharmacie"
        verbose_name_plural = "paramètres de la pharmacie"

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        """Retourne l'unique ligne de paramètres, sans erreur avant migration."""
        try:
            obj, _ = cls.objects.get_or_create(pk=1)
            return obj
        except Exception:  # pragma: no cover - base non migrée
            return cls()

    @property
    def seuil_jours(self):
        return self.seuil_peremption_jours or 30


class JournalAudit(models.Model):
    """Trace des opérations sensibles (RG09)."""

    class Action(models.TextChoices):
        CONNEXION = "CONNEXION", "Connexion"
        DECONNEXION = "DECONNEXION", "Déconnexion"
        CREATION = "CREATION", "Création"
        MODIFICATION = "MODIFICATION", "Modification"
        SUPPRESSION = "SUPPRESSION", "Suppression"
        ARCHIVAGE = "ARCHIVAGE", "Archivage"
        VALIDATION = "VALIDATION", "Validation"
        ANNULATION = "ANNULATION", "Annulation"
        RECEPTION = "RECEPTION", "Réception"
        VENTE = "VENTE", "Vente"
        RETOUR = "RETOUR", "Retour"
        CORRECTION = "CORRECTION", "Correction de stock"
        PAIEMENT = "PAIEMENT", "Paiement"
        SAUVEGARDE = "SAUVEGARDE", "Sauvegarde"
        PARAMETRE = "PARAMETRE", "Paramétrage"

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Utilisateur",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="journal_actions",
    )
    action = models.CharField("Action", max_length=20, choices=Action.choices)
    module = models.CharField("Module", max_length=50)
    objet_id = models.CharField("Identifiant de l'objet", max_length=50, blank=True)
    description = models.CharField("Description", max_length=255)
    details = models.TextField("Détails", blank=True)
    adresse_ip = models.GenericIPAddressField("Adresse IP", null=True, blank=True)
    date = models.DateTimeField("Date", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "entrée du journal d'audit"
        verbose_name_plural = "journal d'audit"
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["module", "action"]),
        ]

    def __str__(self):
        utilisateur = self.utilisateur.nom_complet if self.utilisateur else "Système"
        return f"{self.date:%d/%m/%Y %H:%M} — {utilisateur} — {self.description}"
