"""Formulaires de filtres des rapports (GET uniquement)."""
from django import forms

from core.forms import FormulaireStyle
from core.models import JournalAudit
from utilisateurs.models import Utilisateur


class FormulairePeriode(FormulaireStyle):
    debut = forms.DateField(
        label="Du",
        required=False,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    fin = forms.DateField(
        label="Au",
        required=False,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )


class FormulaireStock(FormulaireStyle):
    ETATS = (
        ("", "Tous les états"),
        ("rupture", "Rupture"),
        ("faible", "Stock faible"),
        ("normal", "Stock normal"),
    )

    q = forms.CharField(
        label="Recherche",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Nom, DCI, catégorie…"}),
    )
    etat = forms.ChoiceField(label="État", required=False, choices=ETATS)


class FormulairePeremptions(FormulaireStyle):
    jours = forms.IntegerField(
        label="Horizon (jours)",
        required=False,
        min_value=1,
        max_value=3650,
        initial=30,
        widget=forms.NumberInput(attrs={"min": 1, "max": 3650}),
    )


class FormulaireJournal(FormulaireStyle):
    utilisateur = forms.ModelChoiceField(
        label="Utilisateur",
        required=False,
        queryset=Utilisateur.objects.none(),
        empty_label="Tous les utilisateurs",
    )
    module = forms.ChoiceField(label="Module", required=False, choices=())
    action = forms.ChoiceField(
        label="Action",
        required=False,
        choices=(("", "Toutes les actions"),) + tuple(JournalAudit.Action.choices),
    )
    debut = forms.DateField(
        label="Du",
        required=False,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    fin = forms.DateField(
        label="Au",
        required=False,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    q = forms.CharField(
        label="Recherche",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Description, objet…"}),
    )

    def __init__(self, *args, utilisateurs=None, modules=None, **kwargs):
        super().__init__(*args, **kwargs)
        if utilisateurs is not None:
            self.fields["utilisateur"].queryset = utilisateurs
        choix_modules = [("", "Tous les modules")] + [
            (module, module) for module in (modules or [])
        ]
        self.fields["module"].choices = choix_modules
