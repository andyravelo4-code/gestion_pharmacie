"""Formulaires de caisse, de retour et d'annulation."""
import uuid

from django import forms

from clients.models import Client
from core.forms import FormulaireStyle
from ventes.models import Paiement, RetourVente


class FormulaireValidationVente(FormulaireStyle):
    client = forms.ModelChoiceField(
        label="Client",
        queryset=Client.objects.none(),
        required=False,
        empty_label="Client de passage (non identifié)",
    )
    mode_paiement = forms.ChoiceField(
        label="Mode de paiement",
        choices=Paiement.Mode.choices,
        initial=Paiement.Mode.ESPECES,
    )
    reference_paiement = forms.CharField(
        label="Référence de transaction",
        required=False,
        max_length=100,
        help_text="Obligatoire pour mobile money, carte, virement ou chèque.",
    )
    montant_recu = forms.DecimalField(
        label="Montant reçu en espèces",
        required=False,
        min_value=0,
        max_digits=14,
        decimal_places=2,
        help_text="Facultatif. Doit couvrir le total pour un paiement en espèces.",
    )
    paiement_confirme = forms.BooleanField(
        label="Paiement électronique vérifié et confirmé",
        required=False,
        help_text="À cocher uniquement après vérification fiable du statut de la transaction.",
    )
    notes = forms.CharField(
        label="Notes (facultatif)",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    cle_idempotence = forms.UUIDField(widget=forms.HiddenInput(), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["client"].queryset = Client.objects.filter(actif=True).order_by("nom", "telephone")
        self.fields["cle_idempotence"].initial = uuid.uuid4()
        self.fields["mode_paiement"].widget.attrs.update({"id": "id_mode_paiement"})
        self.fields["reference_paiement"].widget.attrs.update({"id": "id_reference_paiement"})
        self.fields["paiement_confirme"].widget.attrs.update({"id": "id_paiement_confirme"})

    def clean(self):
        donnees = super().clean()
        mode = donnees.get("mode_paiement")
        reference = (donnees.get("reference_paiement") or "").strip()
        if mode and mode != Paiement.Mode.ESPECES:
            if not reference:
                self.add_error(
                    "reference_paiement",
                    "Une référence de transaction est obligatoire pour ce mode de paiement.",
                )
            if not donnees.get("paiement_confirme"):
                self.add_error(
                    "paiement_confirme",
                    "Le paiement doit être vérifié et confirmé avant la validation.",
                )
        return donnees


class FormulaireRetourVente(FormulaireStyle):
    motif = forms.CharField(
        label="Motif du retour",
        max_length=255,
        widget=forms.TextInput(attrs={"placeholder": "Ex. : produit non conforme, erreur de délivrance…"}),
    )
    mode_remboursement = forms.ChoiceField(
        label="Mode de remboursement",
        choices=RetourVente.ModeRemboursement.choices,
        initial=RetourVente.ModeRemboursement.ESPECES,
    )
    notes = forms.CharField(
        label="Notes complémentaires",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )


class FormulaireAnnulationVente(FormulaireStyle):
    motif = forms.CharField(
        label="Motif de l'annulation",
        max_length=255,
        widget=forms.TextInput(attrs={"placeholder": "Ex. : erreur de saisie, demande du client…"}),
    )
    remise_en_stock = forms.BooleanField(
        label="Remettre les produits en stock (si les lots sont encore valides)",
        required=False,
        initial=True,
    )
