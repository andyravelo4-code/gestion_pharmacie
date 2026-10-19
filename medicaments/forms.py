"""Formulaires des médicaments et des catégories."""
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from core.forms import FormulaireModeleStyle
from medicaments.models import Categorie, Medicament


class FormulaireCategorie(FormulaireModeleStyle):
    """Création / modification d'une catégorie."""

    class Meta:
        model = Categorie
        fields = ["nom", "description"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_nom(self):
        nom = (self.cleaned_data.get("nom") or "").strip()
        if not nom:
            raise ValidationError("Le nom de la catégorie est obligatoire.")
        doublon = Categorie.objects.filter(nom__iexact=nom)
        if self.instance and self.instance.pk:
            doublon = doublon.exclude(pk=self.instance.pk)
        if doublon.exists():
            raise ValidationError("Une catégorie porte déjà ce nom.")
        return nom


class FormulaireMedicament(FormulaireModeleStyle):
    """Création / modification d'un médicament (photo comprise)."""

    class Meta:
        model = Medicament
        fields = [
            "nom",
            "denomination_generique",
            "categorie",
            "forme",
            "dosage",
            "laboratoire",
            "code_barres",
            "photo",
            "prix_achat",
            "prix_vente",
            "seuil_alerte",
        ]
        widgets = {
            "nom": forms.TextInput(attrs={"placeholder": "Ex. : Paracétamol"}),
            "dosage": forms.TextInput(attrs={"placeholder": "Ex. : 500 mg"}),
            "code_barres": forms.TextInput(attrs={"placeholder": "Laisser vide si non renseigné"}),
            "photo": forms.ClearableFileInput(attrs={"accept": "image/*"}),
        }
        help_texts = {
            "code_barres": "Facultatif, mais unique lorsqu'il est renseigné.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categorie"].empty_label = "— Choisir une catégorie —"
        self.fields["prix_achat"].initial = Decimal("0")
        self.fields["prix_vente"].initial = Decimal("0")

    def clean_code_barres(self):
        code = (self.cleaned_data.get("code_barres") or "").strip()
        if not code:
            return None
        doublon = Medicament.objects.filter(code_barres=code)
        if self.instance and self.instance.pk:
            doublon = doublon.exclude(pk=self.instance.pk)
        if doublon.exists():
            raise ValidationError(
                "Ce code-barres est déjà utilisé par un autre médicament. "
                "Vérifiez la fiche existante avant de créer un doublon."
            )
        return code

    def clean_prix_vente(self):
        prix = self.cleaned_data.get("prix_vente")
        if prix is None:
            raise ValidationError("Le prix de vente est obligatoire.")
        if prix < 0:
            raise ValidationError("Le prix de vente ne peut pas être négatif.")
        return prix

    def clean_prix_achat(self):
        prix = self.cleaned_data.get("prix_achat")
        if prix is not None and prix < 0:
            raise ValidationError("Le prix d'achat ne peut pas être négatif.")
        return prix

    def clean_seuil_alerte(self):
        seuil = self.cleaned_data.get("seuil_alerte")
        if seuil is not None and seuil < 0:
            raise ValidationError("Le seuil d'alerte ne peut pas être négatif.")
        return seuil
