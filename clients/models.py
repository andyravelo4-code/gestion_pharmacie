"""Clients (données limitées au nécessaire commercial)."""
from django.db import models
from django.urls import reverse


class Client(models.Model):
    nom = models.CharField("Nom du client", max_length=150, blank=True)
    telephone = models.CharField("Téléphone", max_length=40, blank=True)
    email = models.EmailField("E-mail", blank=True)
    adresse = models.CharField("Adresse", max_length=255, blank=True)
    notes = models.CharField("Notes", max_length=255, blank=True)
    actif = models.BooleanField("Compte actif", default=True)
    date_creation = models.DateTimeField("Date de création", auto_now_add=True)
    date_modification = models.DateTimeField("Date de modification", auto_now=True)

    class Meta:
        verbose_name = "client"
        verbose_name_plural = "clients"
        ordering = ["nom", "telephone"]
        indexes = [models.Index(fields=["nom"]), models.Index(fields=["telephone"])]

    def __str__(self):
        if self.nom:
            return self.nom
        return self.telephone or f"Client #{self.pk}"

    def get_absolute_url(self):
        return reverse("clients:detail", args=[self.pk])

    @property
    def nom_affichage(self):
        return self.nom or self.telephone or "Client non identifié"

    def desactiver(self):
        self.actif = False
        self.save(update_fields=["actif", "date_modification"])

    def reactiver(self):
        self.actif = True
        self.save(update_fields=["actif", "date_modification"])
