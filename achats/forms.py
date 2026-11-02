"""Formulaires des achats : commandes, lignes et réceptions."""
from django import forms
from django.db.models import F, Q
from django.utils import timezone

from achats.models import CommandeAchat, LigneAchat
from core.forms import FormulaireModeleStyle, FormulaireStyle
from fournisseurs.models import Fournisseur
from medicaments.models import Medicament


class FiltreCommandesForm(FormulaireStyle):
    """Recherche et filtres de la liste des commandes d'achat."""

    q = forms.CharField(
        label="Recherche",
        required=False,
        widget=forms.TextInput(
            attrs={"placeholder": "Numéro de commande ou fournisseur", "autocomplete": "off"}
        ),
    )
    statut = forms.ChoiceField(
        label="Statut",
        required=False,
        choices=(("", "Tous les statuts"),) + tuple(CommandeAchat.Statut.choices),
    )
    fournisseur = forms.ModelChoiceField(
        label="Fournisseur",
        required=False,
        queryset=Fournisseur.objects.order_by("nom"),
        empty_label="Tous les fournisseurs",
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


class FiltreReceptionsForm(FormulaireStyle):
    """Recherche et filtres de la liste des réceptions."""

    q = forms.CharField(
        label="Recherche",
        required=False,
        widget=forms.TextInput(
            attrs={
                "placeholder": "N° de réception, commande ou fournisseur",
                "autocomplete": "off",
            }
        ),
    )
    fournisseur = forms.ModelChoiceField(
        label="Fournisseur",
        required=False,
        queryset=Fournisseur.objects.order_by("nom"),
        empty_label="Tous les fournisseurs",
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


class FormulaireCommandeAchat(FormulaireModeleStyle):
    """Création et modification de l'en-tête d'une commande."""

    class Meta:
        model = CommandeAchat
        fields = ["fournisseur", "notes"]
        widgets = {
            "notes": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Conditions, références ou remarques…"}
            )
        }


class FormulaireLigneAchat(FormulaireModeleStyle):
    """Ajout ou modification d'une ligne de commande en brouillon."""

    prix_achat_unitaire = forms.DecimalField(
        label="Prix d'achat unitaire",
        required=False,
        min_value=0,
        max_digits=12,
        decimal_places=2,
        help_text="Laisser vide pour reprendre le prix d'achat du médicament.",
    )

    class Meta:
        model = LigneAchat
        fields = ["medicament", "quantite_commandee", "prix_achat_unitaire"]

    def __init__(self, *args, commande=None, **kwargs):
        self.commande = commande
        super().__init__(*args, **kwargs)
        medicaments = Medicament.objects.filter(statut=Medicament.Statut.ACTIF)
        if self.instance and self.instance.pk and self.instance.medicament_id:
            medicaments = Medicament.objects.filter(
                Q(pk=self.instance.medicament_id)
                | Q(statut=Medicament.Statut.ACTIF)
            )
        self.fields["medicament"].queryset = medicaments.order_by("nom", "dosage")

    def clean(self):
        donnees = super().clean()
        medicament = donnees.get("medicament")
        prix = donnees.get("prix_achat_unitaire")

        if medicament and prix is None:
            prix = medicament.prix_achat
            donnees["prix_achat_unitaire"] = prix
            self.instance.prix_achat_unitaire = prix

        if medicament and self.commande is not None:
            doublons = LigneAchat.objects.filter(
                commande=self.commande, medicament=medicament
            )
            if self.instance and self.instance.pk:
                doublons = doublons.exclude(pk=self.instance.pk)
            if doublons.exists():
                self.add_error(
                    "medicament",
                    "Ce médicament figure déjà dans la commande. "
                    "Modifiez la ligne existante plutôt que d'en créer une nouvelle.",
                )
        return donnees


class FormulaireReception(FormulaireStyle):
    """Saisie d'une réception, ligne par ligne, avec contrôles métier.

    Les champs sont construits dynamiquement à partir des lignes restantes.
    """

    def __init__(self, *args, commande=None, **kwargs):
        self.commande = commande
        self.lignes = []
        if commande is not None:
            self.lignes = list(
                commande.lignes.select_related("medicament")
                .filter(quantite_recue__lt=F("quantite_commandee"))
                .order_by("pk")
            )
        super().__init__(*args, **kwargs)
        aujourdhui = timezone.localdate()
        for ligne in self.lignes:
            prefixe = ligne.pk
            restante = ligne.quantite_restante
            self.fields[f"quantite_{prefixe}"] = forms.IntegerField(
                label="Quantité reçue",
                required=False,
                min_value=0,
                max_value=restante,
                initial=0,
                widget=forms.NumberInput(
                    attrs={"min": 0, "max": restante, "class": "form-control qte-input"}
                ),
            )
            self.fields[f"numero_lot_{prefixe}"] = forms.CharField(
                label="Numéro de lot",
                required=False,
                max_length=80,
                widget=forms.TextInput(attrs={"class": "form-control"}),
            )
            self.fields[f"date_peremption_{prefixe}"] = forms.DateField(
                label="Date de péremption",
                required=False,
                widget=forms.DateInput(
                    attrs={"type": "date", "min": aujourdhui.isoformat(), "class": "form-control"}
                ),
            )
            self.fields[f"prix_unitaire_{prefixe}"] = forms.DecimalField(
                label="Prix unitaire",
                required=False,
                min_value=0,
                max_digits=12,
                decimal_places=2,
                initial=ligne.prix_achat_unitaire,
                widget=forms.NumberInput(
                    attrs={"step": "0.01", "min": 0, "class": "form-control"}
                ),
            )
        self.styliser()

    def champs_lignes(self):
        """Associe chaque ligne restante à ses champs de formulaire."""
        resultat = []
        for ligne in self.lignes:
            resultat.append(
                {
                    "ligne": ligne,
                    "quantite": self[f"quantite_{ligne.pk}"],
                    "numero_lot": self[f"numero_lot_{ligne.pk}"],
                    "date_peremption": self[f"date_peremption_{ligne.pk}"],
                    "prix_unitaire": self[f"prix_unitaire_{ligne.pk}"],
                }
            )
        return resultat

    def clean(self):
        donnees = super().clean()
        aujourdhui = timezone.localdate()
        au_moins_une_quantite = False

        for ligne in self.lignes:
            quantite = donnees.get(f"quantite_{ligne.pk}") or 0
            if quantite <= 0:
                continue
            au_moins_une_quantite = True
            if quantite > ligne.quantite_restante:
                self.add_error(
                    f"quantite_{ligne.pk}",
                    f"La quantité ne peut pas dépasser le restant dû ({ligne.quantite_restante}).",
                )
            if not (donnees.get(f"numero_lot_{ligne.pk}") or "").strip():
                self.add_error(
                    f"numero_lot_{ligne.pk}",
                    "Le numéro de lot est obligatoire dès qu'une quantité est reçue.",
                )
            date_peremption = donnees.get(f"date_peremption_{ligne.pk}")
            if not date_peremption:
                self.add_error(
                    f"date_peremption_{ligne.pk}",
                    "La date de péremption est obligatoire dès qu'une quantité est reçue.",
                )
            elif date_peremption < aujourdhui:
                self.add_error(
                    f"date_peremption_{ligne.pk}",
                    "La date de péremption doit être future.",
                )

        if not self.lignes:
            raise forms.ValidationError("Cette commande n'a plus de ligne à réceptionner.")
        if not au_moins_une_quantite and not self.errors:
            raise forms.ValidationError("Veuillez saisir au moins une quantité reçue.")
        return donnees

    def donnees_reception(self):
        """Construit la liste de dictionnaires attendue par le service."""
        resultat = []
        for ligne in self.lignes:
            quantite = self.cleaned_data.get(f"quantite_{ligne.pk}") or 0
            if quantite <= 0:
                continue
            prix = self.cleaned_data.get(f"prix_unitaire_{ligne.pk}")
            if prix is None:
                prix = ligne.prix_achat_unitaire
            resultat.append(
                {
                    "ligne_achat": ligne,
                    "quantite": quantite,
                    "numero_lot": self.cleaned_data.get(
                        f"numero_lot_{ligne.pk}", ""
                    ).strip(),
                    "date_peremption": self.cleaned_data.get(
                        f"date_peremption_{ligne.pk}"
                    ),
                    "prix_unitaire": prix,
                }
            )
        return resultat
