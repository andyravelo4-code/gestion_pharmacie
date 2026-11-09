"""Vues des rapports, du tableau de bord et des documents PDF."""
import re
from urllib.parse import urlencode

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.generic import TemplateView, View

from achats.models import CommandeAchat
from core.models import JournalAudit, ParametrePharmacie
from utilisateurs.models import Utilisateur
from utilisateurs.permissions import (
    ADMIN,
    AdminRequisMixin,
    GESTION_STOCK_ROLES,
    LECTURE_GESTION,
    RoleRequisMixin,
    VENTES_ROLES,
)
from ventes.models import Vente

from . import pdf, services
from .forms import (
    FormulaireJournal,
    FormulairePeremptions,
    FormulairePeriode,
    FormulaireStock,
)

# Un reçu ou une facture est accessible aux profils ventes et rapports.
RECU_FACTURE_ROLES = tuple(sorted(set(VENTES_ROLES) | set(LECTURE_GESTION)))


# ---------------------------------------------------------------------------
# Aides
# ---------------------------------------------------------------------------
def _periode_et_formulaire(request, jours_defaut=30):
    """Lit la période depuis la requête et construit le formulaire associé."""
    debut, fin = services.resoudre_periode(
        request.GET.get("debut"), request.GET.get("fin"), jours_defaut
    )
    formulaire = FormulairePeriode(
        request.GET if request.GET else None,
        initial={"debut": debut, "fin": fin},
    )
    if formulaire.is_bound and formulaire.is_valid():
        debut_choisi = formulaire.cleaned_data.get("debut")
        fin_choisie = formulaire.cleaned_data.get("fin")
        debut, fin = services.normaliser_periode(
            debut_choisi or debut, fin_choisie or fin, jours_defaut
        )
    return formulaire, debut, fin


def _requete_pdf(debut, fin, **extra):
    parametres = {"debut": debut.isoformat(), "fin": fin.isoformat()}
    parametres.update({cle: valeur for cle, valeur in extra.items() if valeur})
    return urlencode(parametres)


def _reponse_pdf(contenu, nom_fichier):
    nom_fichier = re.sub(r"[^A-Za-z0-9_.-]+", "_", nom_fichier)
    if not nom_fichier.lower().endswith(".pdf"):
        nom_fichier += ".pdf"
    reponse = HttpResponse(contenu, content_type="application/pdf")
    reponse["Content-Disposition"] = f'attachment; filename="{nom_fichier}"'
    reponse["Content-Length"] = str(len(contenu))
    return reponse


def _utilisateur_peut_rapports(utilisateur):
    return (
        utilisateur.is_authenticated
        and (utilisateur.is_superuser or utilisateur.a_role(*LECTURE_GESTION))
    )


def _utilisateur_est_admin(utilisateur):
    return (
        utilisateur.is_authenticated
        and (utilisateur.is_superuser or utilisateur.a_role(ADMIN))
    )


# ---------------------------------------------------------------------------
# Tableau de bord
# ---------------------------------------------------------------------------
class TableauBordView(LoginRequiredMixin, TemplateView):
    template_name = "rapports/tableau_bord.html"

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        aujourd_hui = timezone.localdate()
        formulaire, debut, fin = _periode_et_formulaire(self.request)
        indicateurs = services.indicateurs_tableau_bord(debut, fin)

        contexte.update(indicateurs)
        contexte.update(
            {
                "filtre": formulaire,
                "debut": debut,
                "fin": fin,
                "aujourd_hui": aujourd_hui,
                "libelle_periode": services.libelle_periode(debut, fin),
                "pdf_query": _requete_pdf(debut, fin),
                "peut_rapports_utilisateur": _utilisateur_peut_rapports(
                    self.request.user
                ),
                "est_admin_utilisateur": _utilisateur_est_admin(self.request.user),
            }
        )

        if contexte["peut_rapports_utilisateur"]:
            contexte["graphique_mensuel"] = services.evolution_mensuelle(6)
            contexte["graphique_categories"] = services.repartition_categories(debut, fin)
            contexte["top_produits"] = services.top_produits(debut, fin, 5)
            contexte["dernieres_ventes"] = (
                Vente.objects.filter(date_vente__date__range=(debut, fin))
                .select_related("client", "utilisateur")
                .prefetch_related("lignes", "retours")
                .order_by("-date_vente")[:8]
            )
            contexte["alertes_stock"] = services.alertes_stock(10)
            contexte["lots_perimes"] = indicateurs["peremptions"]["perimes"][:8]
            contexte["lots_proches"] = indicateurs["peremptions"]["proches"][:8]
            contexte["repartition_paiements"] = services.repartition_paiements(
                debut, fin
            )

        if contexte["est_admin_utilisateur"]:
            contexte["activites_audit"] = JournalAudit.objects.select_related(
                "utilisateur"
            ).order_by("-date")[:8]

        return contexte


# ---------------------------------------------------------------------------
# Rapports HTML
# ---------------------------------------------------------------------------
class RapportVentesView(RoleRequisMixin, TemplateView):
    roles_autorises = LECTURE_GESTION
    template_name = "rapports/ventes.html"

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        formulaire, debut, fin = _periode_et_formulaire(self.request)
        totaux = services.totaux_ventes(debut, fin)
        ventes = (
            Vente.objects.filter(date_vente__date__range=(debut, fin))
            .select_related("client", "utilisateur")
            .prefetch_related("lignes", "paiements", "retours")
            .order_by("-date_vente")
        )
        paginator = Paginator(ventes, 20)
        page_obj = paginator.get_page(self.request.GET.get("page"))

        contexte.update(
            {
                "filtre": formulaire,
                "debut": debut,
                "fin": fin,
                "libelle_periode": services.libelle_periode(debut, fin),
                "totaux": totaux,
                "page_obj": page_obj,
                "top_produits": services.top_produits(debut, fin, 5),
                "modes_paiement": services.repartition_paiements(debut, fin),
                "pdf_query": _requete_pdf(debut, fin),
            }
        )
        return contexte


class RapportAchatsView(RoleRequisMixin, TemplateView):
    roles_autorises = LECTURE_GESTION
    template_name = "rapports/achats.html"

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        formulaire, debut, fin = _periode_et_formulaire(self.request)
        statistiques = services.statistiques_achats(debut, fin)
        commandes = Paginator(statistiques["commandes"], 15).get_page(
            self.request.GET.get("page_commandes")
        )
        receptions = Paginator(statistiques["receptions"], 15).get_page(
            self.request.GET.get("page_receptions")
        )

        contexte.update(statistiques)
        contexte.update(
            {
                "filtre": formulaire,
                "debut": debut,
                "fin": fin,
                "libelle_periode": services.libelle_periode(debut, fin),
                "page_commandes": commandes,
                "page_receptions": receptions,
                "pdf_query": _requete_pdf(debut, fin),
            }
        )
        return contexte


class RapportStockView(RoleRequisMixin, TemplateView):
    roles_autorises = LECTURE_GESTION
    template_name = "rapports/stock.html"

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        formulaire = FormulaireStock(self.request.GET if self.request.GET else None)
        recherche = ""
        etat = ""
        if formulaire.is_bound and formulaire.is_valid():
            recherche = formulaire.cleaned_data.get("q") or ""
            etat = formulaire.cleaned_data.get("etat") or ""
        resultat = services.etat_stock(recherche=recherche, etat=etat)
        page_obj = Paginator(resultat["lignes"], 40).get_page(
            self.request.GET.get("page")
        )
        contexte.update(
            {
                "filtre": formulaire,
                "recherche": recherche,
                "etat": etat,
                "page_obj": page_obj,
                "totaux": resultat["totaux"],
                "nb_lignes": len(resultat["lignes"]),
                "pdf_query": urlencode(
                    {
                        cle: valeur
                        for cle, valeur in {"q": recherche, "etat": etat}.items()
                        if valeur
                    }
                ),
            }
        )
        return contexte


class RapportPeremptionsView(RoleRequisMixin, TemplateView):
    roles_autorises = LECTURE_GESTION
    template_name = "rapports/peremptions.html"

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        seuil = ParametrePharmacie.get_solo().seuil_jours
        formulaire = FormulairePeremptions(
            self.request.GET if self.request.GET else None,
            initial={"jours": seuil},
        )
        jours = seuil
        if formulaire.is_bound and formulaire.is_valid():
            jours = formulaire.cleaned_data.get("jours") or seuil
        donnees = services.lots_peremption(jours)
        contexte.update(donnees)
        contexte.update(
            {
                "filtre": formulaire,
                "pdf_query": urlencode({"jours": donnees["jours"]}),
            }
        )
        return contexte


class JournalAuditView(AdminRequisMixin, TemplateView):
    template_name = "rapports/journal.html"

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        modules = list(
            JournalAudit.objects.order_by("module")
            .values_list("module", flat=True)
            .distinct()
        )
        utilisateurs = Utilisateur.objects.order_by(
            "last_name", "first_name", "username"
        )
        formulaire = FormulaireJournal(
            self.request.GET if self.request.GET else None,
            utilisateurs=utilisateurs,
            modules=modules,
        )
        entrees = JournalAudit.objects.select_related("utilisateur").order_by("-date")

        if formulaire.is_bound and formulaire.is_valid():
            donnees = formulaire.cleaned_data
            if donnees.get("utilisateur"):
                entrees = entrees.filter(utilisateur=donnees["utilisateur"])
            if donnees.get("module"):
                entrees = entrees.filter(module=donnees["module"])
            if donnees.get("action"):
                entrees = entrees.filter(action=donnees["action"])
            debut = donnees.get("debut")
            fin = donnees.get("fin")
            if debut and fin and debut > fin:
                debut, fin = fin, debut
            if debut:
                entrees = entrees.filter(date__date__gte=debut)
            if fin:
                entrees = entrees.filter(date__date__lte=fin)
            recherche = (donnees.get("q") or "").strip()
            if recherche:
                entrees = entrees.filter(
                    Q(description__icontains=recherche)
                    | Q(details__icontains=recherche)
                    | Q(objet_id__icontains=recherche)
                )

        page_obj = Paginator(entrees, 30).get_page(self.request.GET.get("page"))
        contexte.update(
            {
                "filtre": formulaire,
                "page_obj": page_obj,
                "modules": modules,
                "actions": JournalAudit.Action.choices,
                "pdf_query": self.request.GET.urlencode(),
            }
        )
        return contexte


# ---------------------------------------------------------------------------
# PDF : rapports
# ---------------------------------------------------------------------------
class PdfVentesView(RoleRequisMixin, View):
    roles_autorises = LECTURE_GESTION

    def get(self, request, *args, **kwargs):
        _, debut, fin = _periode_et_formulaire(request)
        totaux = services.totaux_ventes(debut, fin)
        ventes = list(
            Vente.objects.filter(date_vente__date__range=(debut, fin))
            .select_related("client", "utilisateur")
            .prefetch_related("lignes", "retours", "paiements")
            .order_by("-date_vente")
        )
        contenu = pdf.rapport_ventes_pdf(
            debut,
            fin,
            totaux,
            ventes,
            services.top_produits(debut, fin, 5),
            services.repartition_paiements(debut, fin),
            pharmacie=ParametrePharmacie.get_solo(),
        )
        return _reponse_pdf(
            contenu,
            f"rapport_ventes_{debut:%Y%m%d}_{fin:%Y%m%d}.pdf",
        )


class PdfAchatsView(RoleRequisMixin, View):
    roles_autorises = LECTURE_GESTION

    def get(self, request, *args, **kwargs):
        _, debut, fin = _periode_et_formulaire(request)
        statistiques = services.statistiques_achats(debut, fin)
        contenu = pdf.rapport_achats_pdf(
            debut,
            fin,
            statistiques,
            pharmacie=ParametrePharmacie.get_solo(),
        )
        return _reponse_pdf(
            contenu,
            f"rapport_achats_{debut:%Y%m%d}_{fin:%Y%m%d}.pdf",
        )


class PdfStockView(RoleRequisMixin, View):
    roles_autorises = LECTURE_GESTION

    def get(self, request, *args, **kwargs):
        formulaire = FormulaireStock(request.GET if request.GET else None)
        recherche = ""
        etat = ""
        if formulaire.is_bound and formulaire.is_valid():
            recherche = formulaire.cleaned_data.get("q") or ""
            etat = formulaire.cleaned_data.get("etat") or ""
        resultat = services.etat_stock(recherche=recherche, etat=etat)
        contenu = pdf.rapport_stock_pdf(
            resultat["lignes"],
            resultat["totaux"],
            pharmacie=ParametrePharmacie.get_solo(),
            recherche=recherche,
            etat=etat,
        )
        suffixe = timezone.localdate().strftime("%Y%m%d")
        return _reponse_pdf(contenu, f"rapport_stock_{suffixe}.pdf")


class PdfPeremptionsView(RoleRequisMixin, View):
    roles_autorises = LECTURE_GESTION

    def get(self, request, *args, **kwargs):
        seuil = ParametrePharmacie.get_solo().seuil_jours
        jours = services.resoudre_jours(request.GET.get("jours"), seuil)
        donnees = services.lots_peremption(jours)
        contenu = pdf.rapport_peremptions_pdf(
            donnees,
            pharmacie=ParametrePharmacie.get_solo(),
        )
        suffixe = timezone.localdate().strftime("%Y%m%d")
        return _reponse_pdf(contenu, f"rapport_peremptions_{suffixe}.pdf")


# ---------------------------------------------------------------------------
# PDF : documents de vente et d'achat
# ---------------------------------------------------------------------------
class RecuVenteView(RoleRequisMixin, View):
    roles_autorises = RECU_FACTURE_ROLES

    def get(self, request, pk, *args, **kwargs):
        vente = get_object_or_404(
            Vente.objects.select_related("client", "utilisateur").prefetch_related(
                "lignes__medicament", "lignes__lot", "paiements"
            ),
            pk=pk,
        )
        contenu = pdf.document_vente_pdf(
            vente, ParametrePharmacie.get_solo(), facture=False
        )
        return _reponse_pdf(contenu, f"recu_{vente.numero}.pdf")


class FactureVenteView(RoleRequisMixin, View):
    roles_autorises = RECU_FACTURE_ROLES

    def get(self, request, pk, *args, **kwargs):
        vente = get_object_or_404(
            Vente.objects.select_related("client", "utilisateur").prefetch_related(
                "lignes__medicament", "lignes__lot", "paiements"
            ),
            pk=pk,
        )
        contenu = pdf.document_vente_pdf(
            vente, ParametrePharmacie.get_solo(), facture=True
        )
        return _reponse_pdf(contenu, f"facture_{vente.numero}.pdf")


class BonCommandeView(RoleRequisMixin, View):
    roles_autorises = GESTION_STOCK_ROLES

    def get(self, request, pk, *args, **kwargs):
        commande = get_object_or_404(
            CommandeAchat.objects.select_related(
                "fournisseur", "utilisateur"
            ).prefetch_related("lignes__medicament"),
            pk=pk,
        )
        contenu = pdf.bon_commande_pdf(
            commande, ParametrePharmacie.get_solo()
        )
        return _reponse_pdf(contenu, f"bon_commande_{commande.numero}.pdf")


class BonReceptionView(RoleRequisMixin, View):
    roles_autorises = GESTION_STOCK_ROLES

    def get(self, request, pk, *args, **kwargs):
        from achats.models import ReceptionAchat

        reception = get_object_or_404(
            ReceptionAchat.objects.select_related(
                "commande__fournisseur", "utilisateur"
            ).prefetch_related("lignes__ligne_achat__medicament", "lignes__lot"),
            pk=pk,
        )
        contenu = pdf.bon_reception_pdf(
            reception, ParametrePharmacie.get_solo()
        )
        return _reponse_pdf(contenu, f"bon_reception_{reception.numero}.pdf")
