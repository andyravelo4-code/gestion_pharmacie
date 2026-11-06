"""Caisse, ventes, paiements, retours et annulations."""
import uuid
from decimal import Decimal

from django.contrib import messages
from django.db.models import Prefetch, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, ListView

from clients.models import Client
from core.exceptions import OperationRefusee
from core.models import JournalAudit
from core.utils import journaliser
from medicaments.models import Medicament
from stock.models import LotStock
from utilisateurs.permissions import (
    ADMIN,
    CAISSIER,
    PHARMACIEN,
    RESPONSABLE_GESTION,
    RoleRequisMixin,
    VENTES_ROLES,
)
from ventes.forms import (
    FormulaireAnnulationVente,
    FormulaireRetourVente,
    FormulaireValidationVente,
)
from ventes.models import LigneVente, Paiement, RetourVente, Vente
from ventes.panier import (
    ajouter_lot,
    ajouter_medicament_fefo,
    detail_panier,
    lignes_pour_service,
    lire_panier,
    modifier_lot,
    retirer_lot,
    vider_panier,
)
from ventes.services import annuler_vente, confirmer_paiement, creer_retour, creer_vente

ROLES_LECTURE_VENTES = VENTES_ROLES + (RESPONSABLE_GESTION,)
ROLES_RETOUR = (ADMIN, PHARMACIEN, CAISSIER)
ROLES_ANNULATION = (ADMIN, PHARMACIEN)
ROLES_PAIEMENT = (ADMIN, PHARMACIEN)


def _produits_caisse(q=""):
    """Médicaments actifs avec leurs lots délivrables triés FEFO."""
    lots_fefo = (
        LotStock.objects.filter(
            bloque=False,
            quantite__gt=0,
            date_peremption__gte=timezone.localdate(),
        )
        .select_related("fournisseur")
        .order_by("date_peremption", "pk")
    )
    medicaments = Medicament.objects.filter(statut=Medicament.Statut.ACTIF).select_related("categorie")
    if q:
        medicaments = medicaments.filter(
            Q(nom__icontains=q)
            | Q(denomination_generique__icontains=q)
            | Q(code_barres__iexact=q)
            | Q(laboratoire__icontains=q)
        )
    else:
        medicaments = medicaments.filter(lots__in=lots_fefo)
    medicaments = (
        medicaments.prefetch_related(Prefetch("lots", queryset=lots_fefo, to_attr="lots_disponibles"))
        .distinct()
        .order_by("nom")[:30]
    )
    resultats = []
    for medicament in medicaments:
        lots = list(medicament.lots_disponibles)
        if not lots:
            continue
        medicament.stock_affiche = sum(lot.quantite for lot in lots)
        medicament.premier_lot = lots[0]
        resultats.append(medicament)
    return resultats


def _contexte_caisse(request, q=""):
    detail = detail_panier(request)
    form = FormulaireValidationVente(
        initial={"cle_idempotence": str(uuid.uuid4())}
    )
    return {
        "q": q,
        "produits": _produits_caisse(q),
        "panier": detail,
        "form": form,
        "clients": Client.objects.filter(actif=True).order_by("nom"),
        "ventes_jour": Vente.objects.filter(
            statut=Vente.Statut.VALIDEE, date_vente__date=timezone.localdate()
        ).count(),
    }


class CaisseView(RoleRequisMixin, View):
    roles_autorises = VENTES_ROLES

    def get(self, request, *args, **kwargs):
        q = request.GET.get("q", "").strip()
        return render(request, "ventes/caisse.html", _contexte_caisse(request, q))


class PanierAjouterView(RoleRequisMixin, View):
    roles_autorises = VENTES_ROLES
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        lot_id = request.POST.get("lot")
        medicament_id = request.POST.get("medicament")
        quantite = request.POST.get("quantite") or 1
        try:
            quantite = int(quantite)
        except (TypeError, ValueError):
            messages.error(request, "La quantité saisie est invalide.")
            return redirect("ventes:caisse")
        try:
            if lot_id:
                lot = get_object_or_404(LotStock.objects.select_related("medicament"), pk=lot_id)
                ajouter_lot(request, lot, quantite)
                messages.success(
                    request,
                    f"{quantite} × {lot.medicament} (lot {lot.numero_lot}) ajouté(s) au panier.",
                )
            elif medicament_id:
                medicament = get_object_or_404(Medicament, pk=medicament_id)
                ajoute, demandee = ajouter_medicament_fefo(request, medicament, quantite)
                if ajoute < demandee:
                    messages.warning(
                        request,
                        f"Seulement {ajoute} unité(s) de {medicament} ont pu être ajoutées "
                        f"sur {demandee} demandée(s) (stock disponible).",
                    )
                else:
                    messages.success(request, f"{ajoute} × {medicament} ajouté(s) au panier (FEFO).")
            else:
                messages.error(request, "Aucun produit ou lot sélectionné.")
        except OperationRefusee as erreur:
            messages.error(request, str(erreur))
        return redirect("ventes:caisse")


class PanierModifierView(RoleRequisMixin, View):
    roles_autorises = VENTES_ROLES
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        lot_id = request.POST.get("lot")
        quantite = request.POST.get("quantite") or 0
        try:
            modifier_lot(request, lot_id, int(quantite))
            messages.success(request, "Quantité du panier mise à jour.")
        except (OperationRefusee, TypeError, ValueError) as erreur:
            messages.error(request, str(erreur))
        return redirect("ventes:caisse")


class PanierRetirerView(RoleRequisMixin, View):
    roles_autorises = VENTES_ROLES
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        retirer_lot(request, request.POST.get("lot"))
        messages.info(request, "Ligne retirée du panier.")
        return redirect("ventes:caisse")


class PanierViderView(RoleRequisMixin, View):
    roles_autorises = VENTES_ROLES
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        vider_panier(request)
        messages.info(request, "Le panier a été vidé.")
        return redirect("ventes:caisse")


class ValiderVenteView(RoleRequisMixin, View):
    roles_autorises = VENTES_ROLES
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        detail = detail_panier(request)
        if not detail["lignes"]:
            messages.error(request, "Le panier est vide.")
            return redirect("ventes:caisse")
        if detail["erreurs"]:
            for erreur in detail["erreurs"]:
                messages.error(request, erreur)
            messages.error(request, "Corrigez le panier avant de valider la vente.")
            return redirect("ventes:caisse")

        form = FormulaireValidationVente(request.POST)
        if not form.is_valid():
            for erreurs in form.errors.values():
                for erreur in erreurs:
                    messages.error(request, erreur)
            return redirect("ventes:caisse")

        donnees = form.cleaned_data
        try:
            vente, creee = creer_vente(
                utilisateur=request.user,
                lignes=lignes_pour_service(detail),
                client=donnees["client"],
                mode_paiement=donnees["mode_paiement"],
                reference_paiement=donnees["reference_paiement"],
                montant_recu=donnees["montant_recu"],
                paiement_confirme=donnees["paiement_confirme"],
                notes=donnees["notes"],
                cle_idempotence=donnees.get("cle_idempotence"),
            )
        except OperationRefusee as erreur:
            messages.error(request, str(erreur))
            return redirect("ventes:caisse")

        vider_panier(request)
        if creee:
            journaliser(
                request,
                JournalAudit.Action.VENTE,
                "Ventes",
                f"Vente {vente.numero} validée",
                objet=vente,
                details=(
                    f"{vente.nombre_articles} article(s), total {vente.montant_total}, "
                    f"paiement {vente.paiements.first().get_mode_display() if vente.paiements.exists() else '—'}"
                ),
            )
            messages.success(request, f"Vente {vente.numero} validée avec succès.")
        else:
            messages.info(request, "Cette vente avait déjà été enregistrée (double validation évitée).")
        return redirect(f"{vente.get_absolute_url()}?nouvelle=1")


class ListeVentesView(RoleRequisMixin, ListView):
    roles_autorises = ROLES_LECTURE_VENTES
    model = Vente
    template_name = "ventes/liste.html"
    paginate_by = 20
    context_object_name = "ventes"

    def get_queryset(self):
        qs = (
            Vente.objects.select_related("client", "utilisateur")
            .prefetch_related("lignes", "paiements")
            .order_by("-date_vente")
        )
        q = self.request.GET.get("q", "").strip()
        statut = self.request.GET.get("statut", "").strip()
        mode = self.request.GET.get("mode", "").strip()
        debut = self.request.GET.get("debut", "").strip()
        fin = self.request.GET.get("fin", "").strip()
        caissier = self.request.GET.get("caissier", "").strip()
        if q:
            qs = qs.filter(
                Q(numero__icontains=q)
                | Q(client__nom__icontains=q)
                | Q(client__telephone__icontains=q)
                | Q(lignes__medicament__nom__icontains=q)
            ).distinct()
        if statut:
            qs = qs.filter(statut=statut)
        if mode:
            qs = qs.filter(paiements__mode=mode, paiements__statut=Paiement.Statut.CONFIRME).distinct()
        if debut:
            qs = qs.filter(date_vente__date__gte=debut)
        if fin:
            qs = qs.filter(date_vente__date__lte=fin)
        if caissier:
            qs = qs.filter(utilisateur_id=caissier)
        return qs

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        filtre = self.get_queryset()
        contexte["nombre_total"] = filtre.count()
        contexte["montant_total"] = filtre.aggregate(total=Sum("montant_total"))["total"] or 0
        contexte["q"] = self.request.GET.get("q", "")
        contexte["statut_selectionne"] = self.request.GET.get("statut", "")
        contexte["mode_selectionne"] = self.request.GET.get("mode", "")
        contexte["debut"] = self.request.GET.get("debut", "")
        contexte["fin"] = self.request.GET.get("fin", "")
        contexte["caissier_selectionne"] = self.request.GET.get("caissier", "")
        contexte["modes"] = Paiement.Mode.choices
        from utilisateurs.models import Utilisateur

        contexte["caissiers"] = Utilisateur.objects.filter(ventes__isnull=False).distinct()
        return contexte


class DetailVenteView(RoleRequisMixin, DetailView):
    roles_autorises = ROLES_LECTURE_VENTES
    model = Vente
    template_name = "ventes/detail.html"
    context_object_name = "vente"

    def get_queryset(self):
        return (
            Vente.objects.select_related("client", "utilisateur")
            .prefetch_related(
                "lignes__medicament",
                "lignes__lot",
                "paiements__confirme_par",
                "retours__lignes__ligne_vente__medicament",
            )
        )

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        utilisateur = self.request.user
        contexte["peut_annuler"] = (
            self.object.statut == Vente.Statut.VALIDEE
            and self.object.peut_etre_retournee
            and (utilisateur.is_superuser or utilisateur.a_role(*ROLES_ANNULATION))
        )
        contexte["peut_retourner"] = (
            self.object.statut == Vente.Statut.VALIDEE
            and self.object.peut_etre_retournee
            and (utilisateur.is_superuser or utilisateur.a_role(*ROLES_RETOUR))
        )
        contexte["nouvelle"] = self.request.GET.get("nouvelle") == "1"
        return contexte


class RetourVenteView(RoleRequisMixin, View):
    roles_autorises = ROLES_RETOUR

    def get_vente(self, pk):
        return get_object_or_404(
            Vente.objects.select_related("client").prefetch_related(
                "lignes__medicament", "lignes__lot", "lignes__lignes_retour"
            ),
            pk=pk,
        )

    def get(self, request, pk, *args, **kwargs):
        vente = self.get_vente(pk)
        if vente.statut == Vente.Statut.ANNULEE:
            messages.info(request, "Cette vente est déjà annulée.")
            return redirect("ventes:detail", pk=vente.pk)
        return render(
            request,
            "ventes/retour.html",
            {
                "vente": vente,
                "form": FormulaireRetourVente(),
                "lignes": vente.lignes.all(),
            },
        )

    def post(self, request, pk, *args, **kwargs):
        vente = self.get_vente(pk)
        if vente.statut == Vente.Statut.ANNULEE:
            messages.error(request, "Une vente annulée ne peut pas faire l'objet d'un nouveau retour.")
            return redirect("ventes:detail", pk=vente.pk)
        form = FormulaireRetourVente(request.POST)
        lignes = []
        if form.is_valid():
            for ligne in vente.lignes.all():
                try:
                    quantite = int(request.POST.get(f"quantite_{ligne.pk}") or 0)
                except (TypeError, ValueError):
                    quantite = 0
                if quantite <= 0:
                    continue
                lignes.append(
                    {
                        "ligne_vente": ligne,
                        "quantite": quantite,
                        "remise_en_stock": request.POST.get(f"remise_{ligne.pk}") == "on",
                    }
                )
            if not lignes:
                messages.error(request, "Indiquez au moins une quantité à retourner.")
                return render(
                    request,
                    "ventes/retour.html",
                    {"vente": vente, "form": form, "lignes": vente.lignes.all()},
                )
            try:
                retour = creer_retour(
                    vente=vente,
                    lignes=lignes,
                    utilisateur=request.user,
                    motif=form.cleaned_data["motif"],
                    mode_remboursement=form.cleaned_data["mode_remboursement"],
                    notes=form.cleaned_data["notes"],
                )
            except OperationRefusee as erreur:
                messages.error(request, str(erreur))
            else:
                journaliser(
                    request,
                    JournalAudit.Action.RETOUR,
                    "Retours",
                    f"Retour {retour.numero} enregistré sur la vente {vente.numero}",
                    objet=retour,
                    details=f"Montant : {retour.montant_rembourse} — Motif : {retour.motif}",
                )
                messages.success(
                    request,
                    f"Retour {retour.numero} enregistré. Montant remboursé : {retour.montant_rembourse}.",
                )
                return redirect("ventes:detail", pk=vente.pk)
        return render(
            request,
            "ventes/retour.html",
            {"vente": vente, "form": form, "lignes": vente.lignes.all()},
        )


class AnnulerVenteView(RoleRequisMixin, View):
    roles_autorises = ROLES_ANNULATION

    def get_vente(self, pk):
        return get_object_or_404(
            Vente.objects.prefetch_related("lignes__medicament", "lignes__lot"), pk=pk
        )

    def get(self, request, pk, *args, **kwargs):
        vente = self.get_vente(pk)
        return render(
            request,
            "ventes/annuler.html",
            {"vente": vente, "form": FormulaireAnnulationVente()},
        )

    def post(self, request, pk, *args, **kwargs):
        vente = self.get_vente(pk)
        form = FormulaireAnnulationVente(request.POST)
        if form.is_valid():
            try:
                retour = annuler_vente(
                    vente=vente,
                    utilisateur=request.user,
                    motif=form.cleaned_data["motif"],
                    remise_en_stock=form.cleaned_data["remise_en_stock"],
                )
            except OperationRefusee as erreur:
                messages.error(request, str(erreur))
            else:
                journaliser(
                    request,
                    JournalAudit.Action.ANNULATION,
                    "Ventes",
                    f"Vente {vente.numero} annulée",
                    objet=vente,
                    details=f"Retour compensatoire {retour.numero} — motif : {retour.motif}",
                )
                messages.success(
                    request,
                    f"La vente {vente.numero} a été annulée par l'opération compensatoire "
                    f"{retour.numero}. Aucune donnée n'a été supprimée.",
                )
                return redirect("ventes:detail", pk=vente.pk)
        return render(
            request,
            "ventes/annuler.html",
            {"vente": vente, "form": form},
        )


class ListeRetoursView(RoleRequisMixin, ListView):
    roles_autorises = ROLES_LECTURE_VENTES
    model = RetourVente
    template_name = "ventes/retours.html"
    paginate_by = 20
    context_object_name = "retours"

    def get_queryset(self):
        qs = RetourVente.objects.select_related("vente", "utilisateur").prefetch_related("lignes")
        q = self.request.GET.get("q", "").strip()
        type_retour = self.request.GET.get("type", "").strip()
        debut = self.request.GET.get("debut", "").strip()
        fin = self.request.GET.get("fin", "").strip()
        if q:
            qs = qs.filter(
                Q(numero__icontains=q)
                | Q(vente__numero__icontains=q)
                | Q(motif__icontains=q)
            )
        if type_retour:
            qs = qs.filter(type_retour=type_retour)
        if debut:
            qs = qs.filter(date_retour__date__gte=debut)
        if fin:
            qs = qs.filter(date_retour__date__lte=fin)
        return qs.order_by("-date_retour")

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte["q"] = self.request.GET.get("q", "")
        contexte["type_selectionne"] = self.request.GET.get("type", "")
        contexte["debut"] = self.request.GET.get("debut", "")
        contexte["fin"] = self.request.GET.get("fin", "")
        contexte["types"] = RetourVente.Type.choices
        contexte["montant_total"] = self.get_queryset().aggregate(total=Sum("montant_rembourse"))["total"] or 0
        return contexte


class PaiementsView(RoleRequisMixin, ListView):
    roles_autorises = ROLES_PAIEMENT
    model = Paiement
    template_name = "ventes/paiements.html"
    paginate_by = 25
    context_object_name = "paiements"

    def get_queryset(self):
        qs = Paiement.objects.select_related("vente", "confirme_par").order_by("-date_paiement")
        statut = self.request.GET.get("statut", "").strip()
        mode = self.request.GET.get("mode", "").strip()
        if statut:
            qs = qs.filter(statut=statut)
        if mode:
            qs = qs.filter(mode=mode)
        return qs

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte["statut_selectionne"] = self.request.GET.get("statut", "")
        contexte["mode_selectionne"] = self.request.GET.get("mode", "")
        contexte["statuts"] = Paiement.Statut.choices
        contexte["modes"] = Paiement.Mode.choices
        return contexte


class ConfirmerPaiementView(RoleRequisMixin, View):
    roles_autorises = ROLES_PAIEMENT
    http_method_names = ["post"]

    def post(self, request, pk, *args, **kwargs):
        paiement = get_object_or_404(Paiement, pk=pk)
        if paiement.statut == Paiement.Statut.CONFIRME:
            messages.info(request, "Ce paiement est déjà confirmé.")
        else:
            confirmer_paiement(paiement, request.user)
            journaliser(
                request,
                JournalAudit.Action.PAIEMENT,
                "Paiements",
                f"Paiement {paiement.pk} confirmé pour la vente {paiement.vente.numero}",
                objet=paiement,
                details=f"Montant : {paiement.montant} — Référence : {paiement.reference}",
            )
            messages.success(request, "Le paiement a été confirmé.")
        return redirect("ventes:paiements")
