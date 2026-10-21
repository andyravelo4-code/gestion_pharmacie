"""Formulaires des fournisseurs."""
from django import forms
from django.core.exceptions import ValidationError

from core.forms import FormulaireModeleStyle
from fournisseurs.models import Fournisseur


class FormulaireFournisseur(FormulaireModeleStyle):
    """Création / modification d'un fournisseur.

    Le statut actif/inactif est géré par l'action dédiée ``basculer`` :
    il n'est pas modifiable directement dans le formulaire.
    """

    class Meta:
        model = Fournisseur
        fields = [
            "nom",
            "adresse",
            "telephone",
            "email",
            "numero_fiscal",
            "contact_principal",
        ]
        widgets = {
            "adresse": forms.TextInput(attrs={"placeholder": "Rue, quartier, ville"}),
            "telephone": forms.TextInput(attrs={"placeholder": "Ex. : 034 00 000 00"}),
        }

    def clean_nom(self):
        nom = (self.cleaned_data.get("nom") or "").strip()
        if not nom:
            raise ValidationError("La raison sociale est obligatoire.")
        doublon = Fournisseur.objects.filter(nom__iexact=nom)
        if self.instance and self.instance.pk:
            doublon = doublon.exclude(pk=self.instance.pk)
        if doublon.exists():
            raise ValidationError("Un fournisseur porte déjà cette raison sociale.")
        return nom
