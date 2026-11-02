"""Vues des achats : commandes, lignes, validation, annulation et réceptions."""
from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, DecimalField, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, UpdateView

from achats.forms import (
    FiltreCommandesForm,
    FiltreReceptionsForm,
    FormulaireCommandeAchat,
    FormulaireLigneAchat,
    FormulaireReception,
)
from achats.models import CommandeAchat, LigneAchat, ReceptionAchat
from achats.services import annuler_commande, receptionner_commande, valider_commande
from core.exceptions import OperationRefusee
from core.models import JournalAudit
from core.utils import journaliser
from utilisateurs.permissions import GESTION_ACHATS_ROLES, RoleRequisMixin

CHAMP_MONTANT = DecimalField(max_digits=16, decimal_places=2)


class AchatsRolesMixin(RoleRequisMixin):
    roles_autorises = GESTION_ACHATS_ROLES


def _expression_total_lignes():
    return Sum(
        F("lignes__quantite_commandee") * F("lignes__prix_achat_unitaire"),
        output_field=CHAMP_MONTANT,
    )


def _expression_total_reception():
    return Sum(
        F("lignes__quantite") * F("lignes__prix_unitaire"),
        output_field=CHAMP_MONTANT,
    )


def _filtre(form, champ, defaut=""):
    if form.is_valid():
        valeur = form.cleaned_data.get(champ)
        return valeur if valeur not in (None, "") else defaut
    return defaut


class CommandesView(AchatsRolesMixin, View):
    template_name = "achats/liste.html"

    def get(self, request):
        form = FiltreCommandesForm(request.GET or None)
        q = _filtre(form, "q")
        statut = _filtre(form, "statut")
        fournisseur = _filtre(form, "fournisseur")
        date_debut = _filtre(form, "date_debut")
        date_fin = _filtre(form, "date_fin")

        commandes = (
            CommandeAchat.objects.select_related("fournisseur", "utilisateur")
            .annotate(
                nombre_lignes=Count("lignes", distinct=True),
                total_annote=Coalesce(
                    _expression_total_lignes(),
                    Value(Decimal("0")),
                    output_field=CHAMP_MONTANT,
                ),
            )
            .order_by("-date_creation")
        )
        if q:
            commandes = commandes.filter(
                Q(numero__icontains=q)
                | Q(fournisseur__nom__icontains=q)
                | Q(notes__icontains=q)
            )
        if statut:
            commandes = commandes.filter(statut=statut)
        if fournisseur:
            commandes = commandes.filter(fournisseur=fournisseur)
        if date_debut:
            commandes = commandes.filter(date_creation__date__gte=date_debut)
        if date_fin:
            commandes = commandes.filter(date_creation__date__lte=date_fin)

        totaux = commandes.aggregate(
            montant=Coalesce(
                _expression_total_lignes(),
                Value(Decimal("0")),
                output_field=CHAMP_MONTANT,
            ),
            nombre=Count("pk", distinct=True),
        )
        page_obj = Paginator(commandes, 15).get_page(request.GET.get("page"))

        return render(
            request,
            self.template_name,
            {
                "page_obj": page_obj,
                "form": form,
                "totaux": totaux,
                "statuts": CommandeAchat.Statut.choices,
            },
        )


class CommandeCreerView(AchatsRolesMixin, View):
    template_name = "achats/commande_form.html"

    def get(self, request):
        return render(request, self.template_name, {"form": FormulaireCommandeAchat()})

    def post(self, request):
        form = FormulaireCommandeAchat(request.POST)
        if form.is_valid():
            commande = form.save(commit=False)
            commande.utilisateur = request.user
            commande.save()
            journaliser(
                request,
                JournalAudit.Action.CREATION,
                "Achats",
                f"Création de la commande {commande.numero} — {commande.fournisseur}",
                objet=commande,
            )
            messages.success(
                request,
                f"La commande {commande.numero} a été créée en brouillon. Ajoutez des lignes.",
            )
            return redirect("achats:detail", pk=commande.pk)
        return render(request, self.template_name, {"form": form})


class CommandeDetailView(AchatsRolesMixin, DetailView):
    model = CommandeAchat
    template_name = "achats/detail.html"
    context_object_name = "commande"

    def get_queryset(self):
        return (
            CommandeAchat.objects.select_related("fournisseur", "utilisateur")
            .annotate(
                total_annote=Coalesce(
                    _expression_total_lignes(),
                    Value(Decimal("0")),
                    output_field=CHAMP_MONTANT,
                )
            )
        )

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        commande = self.object
        lignes = list(
            commande.lignes.select_related("medicament").order_by("pk")
        )
        receptions = (
            commande.receptions.select_related("utilisateur")
            .annotate(
                nombre_lignes=Count("lignes", distinct=True),
                total_annote=Coalesce(
                    _expression_total_reception(),
                    Value(Decimal("0")),
                    output_field=CHAMP_MONTANT,
                ),
            )
            .order_by("-date_reception")
        )
        contexte.update(
            {
                "lignes": lignes,
                "receptions": receptions,
                "quantite_commandee_totale": sum(
                    ligne.quantite_commandee for ligne in lignes
                ),
                "quantite_recue_totale": sum(ligne.quantite_recue for ligne in lignes),
            }
        )
        return contexte


class CommandeModifierView(AchatsRolesMixin, UpdateView):
    model = CommandeAchat
    form_class = FormulaireCommandeAchat
    template_name = "achats/commande_form.html"
    context_object_name = "commande"

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.est_modifiable:
            messages.error(
                request,
                "Seule une commande en brouillon peut être modifiée.",
            )
            return redirect("achats:detail", pk=self.object.pk)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        reponse = super().form_valid(form)
        journaliser(
            self.request,
            JournalAudit.Action.MODIFICATION,
            "Achats",
            f"Modification de la commande {self.object.numero}",
            objet=self.object,
        )
        messages.success(self.request, "La commande a été mise à jour.")
        return reponse

    def get_success_url(self):
        return reverse("achats:detail", args=[self.object.pk])


class LigneAjouterView(AchatsRolesMixin, View):
    template_name = "achats/ligne_form.html"

    def _commande(self, pk):
        return get_object_or_404(
            CommandeAchat.objects.select_related("fournisseur"), pk=pk
        )

    def _contexte(self, commande, form):
        return {
            "commande": commande,
            "form": form,
            "titre": "Ajouter une ligne",
        }

    def get(self, request, pk):
        commande = self._commande(pk)
        if not commande.est_modifiable:
            messages.error(
                request, "Les lignes ne sont modifiables qu'en brouillon."
            )
            return redirect("achats:detail", pk=commande.pk)
        form = FormulaireLigneAchat(commande=commande)
        return render(request, self.template_name, self._contexte(commande, form))

    def post(self, request, pk):
        commande = self._commande(pk)
        if not commande.est_modifiable:
            messages.error(
                request, "Les lignes ne sont modifiables qu'en brouillon."
            )
            return redirect("achats:detail", pk=commande.pk)
        form = FormulaireLigneAchat(request.POST, commande=commande)
        if form.is_valid():
            ligne = form.save(commit=False)
            ligne.commande = commande
            ligne.save()
            journaliser(
                request,
                JournalAudit.Action.CREATION,
                "Achats",
                f"Ajout de {ligne.medicament} à la commande {commande.numero}",
                objet=commande,
                details=f"Quantité : {ligne.quantite_commandee}",
            )
            messages.success(request, "La ligne a été ajoutée à la commande.")
            return redirect("achats:detail", pk=commande.pk)
        return render(request, self.template_name, self._contexte(commande, form))


class LigneModifierView(AchatsRolesMixin, View):
    template_name = "achats/ligne_form.html"

    def _ligne(self, pk):
        return get_object_or_404(
            LigneAchat.objects.select_related("commande__fournisseur", "medicament"),
            pk=pk,
        )

    def _contexte(self, ligne, form):
        return {
            "commande": ligne.commande,
            "form": form,
            "titre": "Modifier une ligne",
            "ligne": ligne,
        }

    def get(self, request, pk):
        ligne = self._ligne(pk)
        if not ligne.commande.est_modifiable:
            messages.error(
                request, "Les lignes ne sont modifiables qu'en brouillon."
            )
            return redirect("achats:detail", pk=ligne.commande_id)
        form = FormulaireLigneAchat(instance=ligne, commande=ligne.commande)
        return render(request, self.template_name, self._contexte(ligne, form))

    def post(self, request, pk):
        ligne = self._ligne(pk)
        if not ligne.commande.est_modifiable:
            messages.error(
                request, "Les lignes ne sont modifiables qu'en brouillon."
            )
            return redirect("achats:detail", pk=ligne.commande_id)
        form = FormulaireLigneAchat(
            request.POST, instance=ligne, commande=ligne.commande
        )
        if form.is_valid():
            ligne = form.save()
            journaliser(
                request,
                JournalAudit.Action.MODIFICATION,
                "Achats",
                f"Modification de la ligne {ligne.medicament} "
                f"de la commande {ligne.commande.numero}",
                objet=ligne.commande,
            )
            messages.success(request, "La ligne a été modifiée.")
            return redirect("achats:detail", pk=ligne.commande_id)
        return render(request, self.template_name, self._contexte(ligne, form))


class LigneSupprimerView(AchatsRolesMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        ligne = get_object_or_404(
            LigneAchat.objects.select_related("commande", "medicament"), pk=pk
        )
        commande = ligne.commande
        if not commande.est_modifiable:
            messages.error(
                request, "Les lignes ne sont supprimables qu'en brouillon."
            )
            return redirect("achats:detail", pk=commande.pk)
        description = f"Suppression de {ligne.medicament} de la commande {commande.numero}"
        ligne.delete()
        journaliser(
            request,
            JournalAudit.Action.SUPPRESSION,
            "Achats",
            description,
            objet=commande,
        )
        messages.success(request, "La ligne a été supprimée.")
        return redirect("achats:detail", pk=commande.pk)


class CommandeValiderView(AchatsRolesMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        commande = get_object_or_404(CommandeAchat, pk=pk)
        try:
            valider_commande(commande, utilisateur=request.user)
        except OperationRefusee as erreur:
            messages.error(request, str(erreur))
        else:
            journaliser(
                request,
                JournalAudit.Action.VALIDATION,
                "Achats",
                f"Validation de la commande {commande.numero}",
                objet=commande,
            )
            messages.success(
                request,
                f"La commande {commande.numero} est maintenant commandée : "
                "le stock sera augmenté à la réception effective.",
            )
        return redirect("achats:detail", pk=commande.pk)


class CommandeAnnulerView(AchatsRolesMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        commande = get_object_or_404(CommandeAchat, pk=pk)
        try:
            annuler_commande(commande, utilisateur=request.user)
        except OperationRefusee as erreur:
            messages.error(request, str(erreur))
        else:
            journaliser(
                request,
                JournalAudit.Action.ANNULATION,
                "Achats",
                f"Annulation de la commande {commande.numero}",
                objet=commande,
            )
            messages.success(request, f"La commande {commande.numero} a été annulée.")
        return redirect("achats:detail", pk=commande.pk)


class CommandeReceptionnerView(AchatsRolesMixin, View):
    template_name = "achats/reception_form.html"

    def _commande(self, pk):
        return get_object_or_404(
            CommandeAchat.objects.select_related("fournisseur"), pk=pk
        )

    def _contexte(self, commande, form):
        return {
            "commande": commande,
            "form": form,
            "champs_lignes": form.champs_lignes(),
        }

    def get(self, request, pk):
        commande = self._commande(pk)
        if not commande.peut_etre_receptionnee:
            messages.error(
                request,
                "Cette commande ne peut pas être réceptionnée dans son statut actuel.",
            )
            return redirect("achats:detail", pk=commande.pk)
        form = FormulaireReception(commande=commande)
        return render(request, self.template_name, self._contexte(commande, form))

    def post(self, request, pk):
        commande = self._commande(pk)
        if not commande.peut_etre_receptionnee:
            messages.error(
                request,
                "Cette commande ne peut pas être réceptionnée dans son statut actuel.",
            )
            return redirect("achats:detail", pk=commande.pk)

        form = FormulaireReception(request.POST, commande=commande)
        if form.is_valid():
            try:
                reception = receptionner_commande(
                    commande,
                    form.donnees_reception(),
                    utilisateur=request.user,
                    notes=request.POST.get("notes", "").strip(),
                )
            except OperationRefusee as erreur:
                messages.error(request, str(erreur))
                return render(
                    request, self.template_name, self._contexte(commande, form)
                )
            journaliser(
                request,
                JournalAudit.Action.RECEPTION,
                "Achats",
                f"Réception {reception.numero} de la commande {commande.numero}",
                objet=reception,
            )
            messages.success(
                request,
                f"La réception {reception.numero} a été enregistrée : le stock a été augmenté.",
            )
            return redirect("achats:reception_detail", pk=reception.pk)
        return render(request, self.template_name, self._contexte(commande, form))


class ReceptionsView(AchatsRolesMixin, View):
    template_name = "achats/receptions.html"

    def get(self, request):
        form = FiltreReceptionsForm(request.GET or None)
        q = _filtre(form, "q")
        fournisseur = _filtre(form, "fournisseur")
        date_debut = _filtre(form, "date_debut")
        date_fin = _filtre(form, "date_fin")

        receptions = (
            ReceptionAchat.objects.select_related(
                "commande__fournisseur", "utilisateur"
            )
            .annotate(
                nombre_lignes=Count("lignes", distinct=True),
                total_annote=Coalesce(
                    _expression_total_reception(),
                    Value(Decimal("0")),
                    output_field=CHAMP_MONTANT,
                ),
            )
            .order_by("-date_reception")
        )
        if q:
            receptions = receptions.filter(
                Q(numero__icontains=q)
                | Q(commande__numero__icontains=q)
                | Q(commande__fournisseur__nom__icontains=q)
            )
        if fournisseur:
            receptions = receptions.filter(commande__fournisseur=fournisseur)
        if date_debut:
            receptions = receptions.filter(date_reception__date__gte=date_debut)
        if date_fin:
            receptions = receptions.filter(date_reception__date__lte=date_fin)

        page_obj = Paginator(receptions, 15).get_page(request.GET.get("page"))
        return render(
            request,
            self.template_name,
            {"page_obj": page_obj, "form": form},
        )


class ReceptionDetailView(AchatsRolesMixin, DetailView):
    model = ReceptionAchat
    template_name = "achats/reception_detail.html"
    context_object_name = "reception"

    def get_queryset(self):
        return ReceptionAchat.objects.select_related(
            "commande__fournisseur", "utilisateur"
        )

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        lignes = list(
            self.object.lignes.select_related(
                "ligne_achat__medicament", "lot"
            ).order_by("pk")
        )
        contexte["lignes"] = lignes
        contexte["quantite_totale"] = sum(ligne.quantite for ligne in lignes)
        contexte["montant_total"] = sum(
            (ligne.sous_total for ligne in lignes), Decimal("0")
        )
        return contexte
