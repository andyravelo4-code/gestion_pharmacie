"""Vues de stock : tableau de bord, lots, mouvements, alertes et inventaires."""
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import (
    Count,
    DecimalField,
    F,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import DetailView, ListView

from core.exceptions import OperationRefusee
from core.models import JournalAudit, ParametrePharmacie
from core.utils import journaliser
from medicaments.models import Medicament
from stock.forms import (
    ETATS_LOT,
    ETATS_STOCK,
    FormulaireBlocageLot,
    FormulaireInventaire,
    FormulaireInventaireLignes,
    FiltreLotsForm,
    FiltreMouvementsForm,
    FiltreStockForm,
)
from stock.models import Inventaire, LigneInventaire, LotStock, MouvementStock
from stock.services import creer_inventaire, valider_inventaire
from utilisateurs.permissions import GESTION_STOCK_ROLES, RoleRequisMixin

CHAMP_MONTANT = DecimalField(max_digits=16, decimal_places=2)


def _aujourdhui():
    return timezone.localdate()


def _seuil_peremption():
    return ParametrePharmacie.get_solo().seuil_jours


def medicaments_avec_stock():
    """Médicaments annotés du stock physique, disponible et de sa valeur.

    Chaque agrégat est calculé par sous-requête corrélée : pas de jointure
    multiplicative ni de requête par ligne.
    """
    aujourdhui = _aujourdhui()

    def total_lots(expression, filtre=Q(), champ=None):
        sous_requete = (
            LotStock.objects.filter(medicament=OuterRef("pk"))
            .filter(filtre)
            .values("medicament")
            .annotate(total=expression)
            .values("total")[:1]
        )
        return Subquery(sous_requete, output_field=champ) if champ else Subquery(sous_requete)

    return Medicament.objects.annotate(
        stock_physique_annote=Coalesce(
            total_lots(Sum("quantite")), Value(0)
        ),
        stock_disponible_annote=Coalesce(
            total_lots(
                Sum("quantite"),
                Q(
                    bloque=False,
                    date_peremption__gte=aujourdhui,
                    quantite__gt=0,
                ),
            ),
            Value(0),
        ),
        valeur_stock_annote=Coalesce(
            total_lots(
                Sum(
                    F("quantite") * F("prix_achat"),
                    output_field=CHAMP_MONTANT,
                ),
                Q(quantite__gt=0),
                CHAMP_MONTANT,
            ),
            Value(Decimal("0")),
            output_field=CHAMP_MONTANT,
        ),
    )


def _lire_filtre(form, request, nom, defaut=""):
    """Retourne la valeur nettoyée d'un filtre, ou la valeur brute si invalide."""
    if form.is_valid():
        return form.cleaned_data.get(nom) or defaut
    return (request.GET.get(nom) or defaut).strip()


class StockRolesMixin(RoleRequisMixin):
    roles_autorises = GESTION_STOCK_ROLES


class TableauStockView(StockRolesMixin, View):
    template_name = "stock/tableau.html"

    def get(self, request):
        aujourdhui = _aujourdhui()
        seuil_jours = _seuil_peremption()
        limite_peremption = aujourdhui + timedelta(days=seuil_jours)

        form = FiltreStockForm(request.GET or None)
        q = _lire_filtre(form, request, "q")
        etat = _lire_filtre(form, request, "etat")

        meds_actifs = medicaments_avec_stock().filter(statut=Medicament.Statut.ACTIF)
        rupture = meds_actifs.filter(stock_disponible_annote__lte=0)
        sous_seuil = meds_actifs.filter(
            stock_disponible_annote__gt=0,
            stock_disponible_annote__lte=F("seuil_alerte"),
        )

        medicaments = meds_actifs
        if q:
            medicaments = medicaments.filter(
                Q(nom__icontains=q)
                | Q(denomination_generique__icontains=q)
                | Q(code_barres__icontains=q)
                | Q(laboratoire__icontains=q)
            )
        if etat == "rupture":
            medicaments = medicaments.filter(stock_disponible_annote__lte=0)
        elif etat == "faible":
            medicaments = medicaments.filter(
                stock_disponible_annote__gt=0,
                stock_disponible_annote__lte=F("seuil_alerte"),
            )
        elif etat == "ok":
            medicaments = medicaments.filter(stock_disponible_annote__gt=F("seuil_alerte"))
        medicaments = medicaments.order_by("nom", "dosage")

        stats_lots = LotStock.objects.aggregate(
            valeur=Coalesce(
                Sum(
                    F("quantite") * F("prix_achat"),
                    filter=Q(quantite__gt=0),
                    output_field=CHAMP_MONTANT,
                ),
                Value(Decimal("0")),
                output_field=CHAMP_MONTANT,
            ),
            lots_actifs=Count("id", filter=Q(quantite__gt=0)),
            perimes=Count(
                "id", filter=Q(date_peremption__lt=aujourdhui, quantite__gt=0)
            ),
            proches=Count(
                "id",
                filter=Q(
                    date_peremption__gte=aujourdhui,
                    date_peremption__lte=limite_peremption,
                    quantite__gt=0,
                ),
            ),
        )

        page_obj = Paginator(medicaments, 15).get_page(request.GET.get("page"))

        contexte = {
            "page_obj": page_obj,
            "form": form,
            "q": q,
            "etat": etat,
            "etats_stock": ETATS_STOCK,
            "cartes": {
                "valeur_stock": stats_lots["valeur"],
                "nombre_lots": stats_lots["lots_actifs"],
                "ruptures": rupture.count(),
                "sous_seuil": sous_seuil.count(),
                "perimes": stats_lots["perimes"],
                "proches_peremption": stats_lots["proches"],
            },
            "seuil_jours": seuil_jours,
        }
        return render(request, self.template_name, contexte)


class LotsView(StockRolesMixin, View):
    template_name = "stock/lots.html"

    def get(self, request):
        aujourdhui = _aujourdhui()
        limite_peremption = aujourdhui + timedelta(days=_seuil_peremption())
        form = FiltreLotsForm(request.GET or None)
        q = _lire_filtre(form, request, "q")
        etat = _lire_filtre(form, request, "etat")
        tri = _lire_filtre(form, request, "tri", "peremption")

        lots = LotStock.objects.select_related("medicament", "fournisseur")
        if q:
            lots = lots.filter(
                Q(medicament__nom__icontains=q)
                | Q(medicament__denomination_generique__icontains=q)
                | Q(numero_lot__icontains=q)
                | Q(fournisseur__nom__icontains=q)
            )
        if etat == "delivrable":
            lots = lots.filter(
                bloque=False, date_peremption__gte=aujourdhui, quantite__gt=0
            )
        elif etat == "expire":
            lots = lots.filter(date_peremption__lt=aujourdhui)
        elif etat == "proche":
            lots = lots.filter(
                date_peremption__gte=aujourdhui,
                date_peremption__lte=limite_peremption,
                quantite__gt=0,
            )
        elif etat == "bloque":
            lots = lots.filter(bloque=True)
        elif etat == "epuise":
            lots = lots.filter(quantite=0)

        ordres = {
            "peremption": ("date_peremption", "medicament__nom"),
            "peremption_desc": ("-date_peremption", "medicament__nom"),
            "medicament": ("medicament__nom", "date_peremption"),
            "quantite_desc": ("-quantite", "date_peremption"),
        }
        lots = lots.order_by(*ordres.get(tri, ordres["peremption"]))
        page_obj = Paginator(lots, 20).get_page(request.GET.get("page"))

        return render(
            request,
            self.template_name,
            {
                "page_obj": page_obj,
                "form": form,
                "q": q,
                "etat": etat,
                "tri": tri,
                "etats_lot": ETATS_LOT,
                "aujourdhui": aujourdhui,
                "seuil_jours": _seuil_peremption(),
            },
        )


class LotDetailView(StockRolesMixin, DetailView):
    model = LotStock
    template_name = "stock/lot_detail.html"
    context_object_name = "lot"

    def get_queryset(self):
        return LotStock.objects.select_related("medicament", "fournisseur")

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        lot = self.object
        contexte["mouvements"] = lot.mouvements.select_related("utilisateur").order_by(
            "-date", "-id"
        )
        contexte["lignes_vente"] = lot.lignes_vente.select_related(
            "vente", "vente__client", "medicament"
        ).order_by("-vente__date_vente")
        contexte["formulaire_blocage"] = FormulaireBlocageLot()
        contexte["aujourdhui"] = _aujourdhui()
        return contexte


class BloquerLotView(StockRolesMixin, View):
    """Bloque ou débloque un lot (POST uniquement)."""

    http_method_names = ["post"]

    def post(self, request, pk):
        lot = get_object_or_404(
            LotStock.objects.select_related("medicament"), pk=pk
        )
        suivant = request.POST.get("suivant") or lot.get_absolute_url()
        if not url_has_allowed_host_and_scheme(
            suivant,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            suivant = lot.get_absolute_url()

        if lot.bloque:
            lot.debloquer()
            journaliser(
                request,
                JournalAudit.Action.MODIFICATION,
                "Stock",
                f"Déblocage du lot {lot.numero_lot} — {lot.medicament}",
                objet=lot,
            )
            messages.success(
                request,
                f"Le lot {lot.numero_lot} de {lot.medicament} est de nouveau délivrable.",
            )
            return redirect(suivant)

        formulaire = FormulaireBlocageLot(request.POST)
        if not formulaire.is_valid():
            messages.error(
                request,
                "Le motif est obligatoire pour bloquer un lot.",
            )
            return redirect(f"{lot.get_absolute_url()}#blocage")

        motif = formulaire.cleaned_data["motif"].strip()
        lot.bloquer(motif)
        journaliser(
            request,
            JournalAudit.Action.MODIFICATION,
            "Stock",
            f"Blocage du lot {lot.numero_lot} — {lot.medicament}",
            objet=lot,
            details=motif,
        )
        messages.success(
            request,
            f"Le lot {lot.numero_lot} de {lot.medicament} a été bloqué.",
        )
        return redirect(suivant)


class MouvementsView(StockRolesMixin, View):
    template_name = "stock/mouvements.html"

    def get(self, request):
        form = FiltreMouvementsForm(request.GET or None)
        mouvements = MouvementStock.objects.select_related(
            "medicament", "lot", "utilisateur"
        )
        if form.is_valid():
            q = form.cleaned_data.get("q") or ""
            type_mouvement = form.cleaned_data.get("type") or ""
            debut = form.cleaned_data.get("date_debut")
            fin = form.cleaned_data.get("date_fin")
        else:
            q = (request.GET.get("q") or "").strip()
            type_mouvement = request.GET.get("type") or ""
            debut = fin = None

        if q:
            mouvements = mouvements.filter(
                Q(medicament__nom__icontains=q)
                | Q(medicament__denomination_generique__icontains=q)
                | Q(lot__numero_lot__icontains=q)
                | Q(reference__icontains=q)
            )
        if type_mouvement:
            mouvements = mouvements.filter(type_mouvement=type_mouvement)
        if debut:
            mouvements = mouvements.filter(date__date__gte=debut)
        if fin:
            mouvements = mouvements.filter(date__date__lte=fin)

        page_obj = Paginator(mouvements, 30).get_page(request.GET.get("page"))
        return render(
            request,
            self.template_name,
            {
                "page_obj": page_obj,
                "form": form,
                "types_mouvement": MouvementStock.Type.choices,
            },
        )


class AlertesView(StockRolesMixin, View):
    template_name = "stock/alertes.html"

    def get(self, request):
        aujourdhui = _aujourdhui()
        seuil_jours = _seuil_peremption()
        limite = aujourdhui + timedelta(days=seuil_jours)

        meds_actifs = medicaments_avec_stock().filter(statut=Medicament.Statut.ACTIF)
        ruptures = meds_actifs.filter(stock_disponible_annote__lte=0).order_by(
            "nom", "dosage"
        )
        sous_seuil = meds_actifs.filter(
            stock_disponible_annote__gt=0,
            stock_disponible_annote__lte=F("seuil_alerte"),
        ).order_by("stock_disponible_annote", "nom")

        lots = LotStock.objects.select_related("medicament", "fournisseur")
        proches = lots.filter(
            quantite__gt=0,
            date_peremption__gte=aujourdhui,
            date_peremption__lte=limite,
        ).order_by("date_peremption")
        perimes = lots.filter(
            quantite__gt=0, date_peremption__lt=aujourdhui
        ).order_by("date_peremption")

        return render(
            request,
            self.template_name,
            {
                "ruptures": ruptures,
                "sous_seuil": sous_seuil,
                "lots_proches": proches,
                "lots_perimes": perimes,
                "seuil_jours": seuil_jours,
                "aujourdhui": aujourdhui,
            },
        )


class InventairesView(StockRolesMixin, ListView):
    model = Inventaire
    template_name = "stock/inventaires.html"
    context_object_name = "inventaires"
    paginate_by = 15

    def get_queryset(self):
        return (
            Inventaire.objects.select_related("utilisateur")
            .annotate(nombre_lignes=Count("lignes"))
            .order_by("-date_creation")
        )


class InventaireCreerView(StockRolesMixin, View):
    template_name = "stock/inventaire_form.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {"form": FormulaireInventaire()},
        )

    def post(self, request):
        form = FormulaireInventaire(request.POST)
        if form.is_valid():
            inventaire = creer_inventaire(
                utilisateur=request.user,
                notes=form.cleaned_data.get("notes", ""),
            )
            journaliser(
                request,
                JournalAudit.Action.CREATION,
                "Stock",
                f"Création de l'inventaire {inventaire.numero}",
                objet=inventaire,
            )
            messages.success(
                request,
                f"L'inventaire {inventaire.numero} a été créé. Saisissez les quantités comptées.",
            )
            return redirect("stock:inventaire_detail", pk=inventaire.pk)
        return render(request, self.template_name, {"form": form})


class InventaireDetailView(StockRolesMixin, View):
    template_name = "stock/inventaire_detail.html"

    def _contexte(self, request, inventaire, form=None):
        lignes = list(
            LigneInventaire.objects.select_related("lot__medicament")
            .filter(inventaire=inventaire)
            .order_by("lot__medicament__nom", "lot__date_peremption")
        )
        if form is None:
            form = FormulaireInventaireLignes(lignes=lignes)
        return {
            "inventaire": inventaire,
            "lignes": lignes,
            "form": form,
            "champs_lignes": form.champs_lignes(),
            "est_modifiable": inventaire.est_modifiable,
        }

    def get(self, request, pk):
        inventaire = get_object_or_404(
            Inventaire.objects.select_related("utilisateur"), pk=pk
        )
        return render(
            request, self.template_name, self._contexte(request, inventaire)
        )

    def post(self, request, pk):
        inventaire = get_object_or_404(
            Inventaire.objects.select_related("utilisateur"), pk=pk
        )
        if not inventaire.est_modifiable:
            messages.error(
                request,
                "Cet inventaire a déjà été validé : les quantités ne sont plus modifiables.",
            )
            return redirect("stock:inventaire_detail", pk=inventaire.pk)

        lignes = list(
            LigneInventaire.objects.select_related("lot__medicament")
            .filter(inventaire=inventaire)
            .order_by("lot__medicament__nom", "lot__date_peremption")
        )
        form = FormulaireInventaireLignes(request.POST, lignes=lignes)
        if form.is_valid():
            quantites = form.quantites()
            for ligne in lignes:
                if ligne.pk in quantites:
                    ligne.quantite_comptee = quantites[ligne.pk]
                    ligne.save(update_fields=["quantite_comptee"])
            journaliser(
                request,
                JournalAudit.Action.MODIFICATION,
                "Stock",
                f"Enregistrement du comptage de l'inventaire {inventaire.numero}",
                objet=inventaire,
            )
            messages.success(
                request, "Les quantités comptées ont été enregistrées."
            )
            return redirect("stock:inventaire_detail", pk=inventaire.pk)

        messages.error(request, "Veuillez corriger les quantités saisies.")
        return render(
            request, self.template_name, self._contexte(request, inventaire, form)
        )


class InventaireValiderView(StockRolesMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        inventaire = get_object_or_404(Inventaire, pk=pk)
        try:
            valider_inventaire(inventaire, utilisateur=request.user)
        except OperationRefusee as erreur:
            # OperationRefusee et ses sous-classes portent un message lisible.
            messages.error(request, str(erreur))
        else:
            journaliser(
                request,
                JournalAudit.Action.VALIDATION,
                "Stock",
                f"Validation de l'inventaire {inventaire.numero}",
                objet=inventaire,
            )
            messages.success(
                request,
                f"L'inventaire {inventaire.numero} a été validé : les écarts ont été appliqués.",
            )
        return redirect("stock:inventaire_detail", pk=inventaire.pk)
