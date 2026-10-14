"""Mixins de formulaires Bootstrap et formulaires transverses."""
from django import forms

from core.models import ParametrePharmacie


class FormulaireStyleMixin:
    """Ajoute automatiquement les classes Bootstrap aux widgets."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.styliser()

    def styliser(self):
        for nom, champ in self.fields.items():
            widget = champ.widget
            if isinstance(widget, forms.CheckboxInput):
                classe = "form-check-input"
            elif isinstance(widget, forms.CheckboxSelectMultiple):
                classe = "form-check-input"
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                classe = "form-select"
            else:
                classe = "form-control"
            classes = widget.attrs.get("class", "").split()
            if classe not in classes:
                classes.append(classe)
            widget.attrs["class"] = " ".join(classes).strip()
            if isinstance(widget, forms.DateInput):
                widget.attrs.setdefault("type", "date")
                widget.input_type = "date"


class FormulaireModeleStyle(FormulaireStyleMixin, forms.ModelForm):
    """ModelForm stylisé."""


class FormulaireStyle(FormulaireStyleMixin, forms.Form):
    """Form simple stylisé."""


class FormulaireParametre(FormulaireModeleStyle):
    class Meta:
        model = ParametrePharmacie
        fields = [
            "nom",
            "adresse",
            "telephone",
            "email",
            "numero_fiscal",
            "devise",
            "seuil_peremption_jours",
            "mentions_legales",
            "logo",
        ]
        widgets = {
            "adresse": forms.TextInput(),
            "mentions_legales": forms.Textarea(attrs={"rows": 4}),
        }
