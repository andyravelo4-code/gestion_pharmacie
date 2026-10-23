"""Formulaires des clients."""
from django import forms

from core.forms import FormulaireModeleStyle
from clients.models import Client


class FormulaireClient(FormulaireModeleStyle):
    """Création / modification d'un client.

    Le statut du compte est géré par l'action dédiée ``basculer``.
    """

    class Meta:
        model = Client
        fields = ["nom", "telephone", "email", "adresse", "notes"]
        widgets = {
            "nom": forms.TextInput(attrs={"placeholder": "Facultatif pour un client de passage"}),
            "telephone": forms.TextInput(attrs={"placeholder": "Ex. : 034 00 000 00"}),
            "notes": forms.TextInput(attrs={"placeholder": "Information utile au suivi commercial"}),
        }
