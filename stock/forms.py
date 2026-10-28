"""Formulaires des écrans de stock, lots, mouvements et inventaires."""
from django import forms

from core.forms import FormulaireModeleStyle, FormulaireStyle
from stock.models import Inventaire, MouvementStock

ETATS_STOCK = (
    ("", "Tous les états"),
    ("rupture", "En rupture"),
    ("faible", "Sous le seuil"),
    ("ok", "Stock suffisant"),
)

ETATS_LOT = (
    ("", "Tous les lots"),
    ("delivrable", "Délivrables"),
    ("expire", "Périmés"),
    ("proche", "Péremption proche"),
    ("bloque", "Bloqués"),
    ("epuise", "Épuisés"),
)

TRIS_LOT = (
    ("peremption", "Péremption la plus proche"),
    ("peremption_desc", "Péremption la plus lointaine"),
    ("medicament", "Médicament (A → Z)"),
    ("quantite_desc", "Quantité décroissante"),
)


class FiltreStockForm(FormulaireStyle):
    """Recherche et filtre du tableau de stock."""

    q = forms.CharField(
        label="Recherche",
        required=False,
        widget=forms.TextInput(
            attrs={"placeholder": "Nom, DCI ou code-barres", "autocomplete": "off"}
        ),
    )
    etat = forms.ChoiceField(label="État", required=False, choices=ETATS_STOCK)


class FiltreLotsForm(FormulaireStyle):
    """Recherche, filtres et tri de la liste des lots."""

    q = forms.CharField(
        label="Recherche",
        required=False,
        widget=forms.TextInput(
            attrs={"placeholder": "Médicament, numéro de lot ou fournisseur", "autocomplete": "off"}
        ),
    )
    etat = forms.ChoiceField(label="État du lot", required=False, choices=ETATS_LOT)
    tri = forms.ChoiceField(label="Tri", required=False, choices=TRIS_LOT)


class FiltreMouvementsForm(FormulaireStyle):
    """Filtres de l'historique des mouvements de stock."""

    q = forms.CharField(
        label="Recherche",
        required=False,
        widget=forms.TextInput(
            attrs={"placeholder": "Médicament, lot ou référence", "autocomplete": "off"}
        ),
    )
    type = forms.ChoiceField(
        label="Type",
        required=False,
        choices=(("", "Tous les types"),) + tuple(MouvementStock.Type.choices),
    )
    date_debut = forms.DateField(
        label="Du", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    date_fin = forms.DateField(
        label="Au", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )

    def clean(self):
        donnees = super().clean()
        debut = donnees.get("date_debut")
        fin = donnees.get("date_fin")
        if debut and fin and debut > fin:
            raise forms.ValidationError(
                "La date de début doit être antérieure ou égale à la date de fin."
            )
        return donnees


class FormulaireBlocageLot(FormulaireStyle):
    """Motif obligatoire pour bloquer un lot."""

    motif = forms.CharField(
        label="Motif du blocage",
        max_length=255,
        widget=forms.Textarea(
            attrs={"rows": 2, "placeholder": "Ex. : lot suspecté non conforme, rappel fournisseur…"}
        ),
    )


class FormulaireInventaire(FormulaireModeleStyle):
    """Création d'un inventaire (snapshot des lots existants)."""

    class Meta:
        model = Inventaire
        fields = ["notes"]
        widgets = {
            "notes": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Précisez le périmètre ou les observations du comptage…",
                }
            )
        }


class FormulaireInventaireLignes(FormulaireStyle):
    """Saisie des quantités comptées pour un inventaire en cours."""

    def __init__(self, *args, lignes=None, **kwargs):
        self.lignes = list(lignes or [])
        super().__init__(*args, **kwargs)
        for ligne in self.lignes:
            self.fields[f"quantite_{ligne.pk}"] = forms.IntegerField(
                label="Quantité comptée",
                min_value=0,
                required=True,
                initial=ligne.quantite_comptee,
                widget=forms.NumberInput(attrs={"min": 0, "class": "form-control qte-input"}),
            )
        self.styliser()

    def champs_lignes(self):
        """Associe chaque ligne d'inventaire à son champ de saisie."""
        return [
            (ligne, self[f"quantite_{ligne.pk}"])
            for ligne in self.lignes
        ]

    def quantites(self):
        """Retourne ``{ligne_pk: quantite_comptee}`` après validation."""
        return {
            ligne.pk: self.cleaned_data.get(f"quantite_{ligne.pk}")
            for ligne in self.lignes
            if f"quantite_{ligne.pk}" in self.cleaned_data
        }
