"""Vues des médicaments et des catégories."""
from django.contrib import messages
from django.db.models import Count, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from core.models import JournalAudit
from core.utils import journaliser
from medicaments.forms import FormulaireCategorie, FormulaireMedicament
from medicaments.models import Categorie, Medicament
from utilisateurs.permissions import GESTION_MEDICAMENTS, RoleRequisMixin

MODULE_MEDICAMENTS = "Médicaments"
MODULE_CATEGORIES = "Catégories"

TRIS_MEDICAMENTS = {
    "nom": "nom",
    "-nom": "-nom",
    "prix_vente": "prix_vente",
    "-prix_vente": "-prix_vente",
    "date_creation": "date_creation",
    "-date_creation": "-date_creation",
}


class MedicamentListView(RoleRequisMixin, ListView):
    """Catalogue consultable par tout utilisateur connecté."""

    model = Medicament
    template_name = "medicaments/medicament_liste.html"
    context_object_name = "medicaments"
    paginate_by = 12
    roles_autorises = ()

    def get_queryset(self):
        aujourdhui = timezone.localdate()
        queryset = (
            Medicament.objects.select_related("categorie")
            .annotate(
                stock_physique=Coalesce(Sum("lots__quantite"), Value(0)),
                stock_disponible_annote=Coalesce(
                    Sum(
                        "lots__quantite",
                        filter=Q(
                            lots__bloque=False,
                            lots__date_peremption__gte=aujourdhui,
                            lots__quantite__gt=0,
                        ),
                    ),
                    Value(0),
                ),
            )
        )

        recherche = (self.request.GET.get("q") or "").strip()
        if recherche:
            queryset = queryset.filter(
                Q(nom__icontains=recherche)
                | Q(denomination_generique__icontains=recherche)
                | Q(code_barres__icontains=recherche)
                | Q(laboratoire__icontains=recherche)
            )

        categorie = (self.request.GET.get("categorie") or "").strip()
        if categorie.isdigit():
            queryset = queryset.filter(categorie_id=int(categorie))

        statut = (self.request.GET.get("statut") or "").strip()
        if statut in {Medicament.Statut.ACTIF, Medicament.Statut.ARCHIVE}:
            queryset = queryset.filter(statut=statut)

        if self.request.GET.get("alerte") in {"1", "oui", "true"}:
            queryset = queryset.filter(
                statut=Medicament.Statut.ACTIF,
                stock_disponible_annote__lte=F("seuil_alerte"),
            )
        if self.request.GET.get("rupture") in {"1", "oui", "true"}:
            queryset = queryset.filter(stock_disponible_annote__lte=0)

        tri = (self.request.GET.get("tri") or "nom").strip()
        queryset = queryset.order_by(TRIS_MEDICAMENTS.get(tri, "nom"), "nom")
        return queryset

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte.update(
            {
                "categories": Categorie.objects.all(),
                "recherche": (self.request.GET.get("q") or "").strip(),
                "categorie_selectionnee": (self.request.GET.get("categorie") or "").strip(),
                "statut_selectionne": (self.request.GET.get("statut") or "").strip(),
                "alerte_selectionnee": self.request.GET.get("alerte") in {"1", "oui", "true"},
                "rupture_selectionnee": self.request.GET.get("rupture") in {"1", "oui", "true"},
                "tri_selectionne": (self.request.GET.get("tri") or "nom").strip(),
                "tris": [
                    ("nom", "Nom (A → Z)"),
                    ("-nom", "Nom (Z → A)"),
                    ("prix_vente", "Prix de vente croissant"),
                    ("-prix_vente", "Prix de vente décroissant"),
                    ("-date_creation", "Ajout le plus récent"),
                    ("date_creation", "Ajout le plus ancien"),
                ],
            }
        )
        return contexte


class MedicamentDetailView(RoleRequisMixin, DetailView):
    """Fiche complète d'un médicament (lecture ouverte aux connectés)."""

    model = Medicament
    template_name = "medicaments/medicament_detail.html"
    context_object_name = "medicament"
    roles_autorises = ()

    def get_queryset(self):
        return Medicament.objects.select_related("categorie")

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        medicament = self.object
        contexte.update(
            {
                "lots": medicament.lots.select_related("fournisseur").order_by(
                    "date_peremption", "numero_lot"
                ),
                "mouvements": medicament.mouvements.select_related(
                    "lot", "utilisateur"
                ).order_by("-date", "-id")[:10],
                "lignes_vente": medicament.lignes_vente.select_related(
                    "vente", "lot"
                ).order_by("-vente__date_vente", "-pk")[:10],
                "stock_total": medicament.stock_total(),
                "stock_disponible": medicament.stock_disponible(),
            }
        )
        return contexte


class MedicamentCreateView(RoleRequisMixin, CreateView):
    model = Medicament
    form_class = FormulaireMedicament
    template_name = "medicaments/medicament_form.html"
    roles_autorises = GESTION_MEDICAMENTS

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte["titre_formulaire"] = "Nouveau médicament"
        contexte["bouton_libelle"] = "Créer le médicament"
        return contexte

    def form_valid(self, form):
        reponse = super().form_valid(form)
        journaliser(
            self.request,
            JournalAudit.Action.CREATION,
            MODULE_MEDICAMENTS,
            f"Création du médicament {self.object}",
            objet=self.object,
        )
        messages.success(
            self.request, f"Le médicament « {self.object} » a été créé."
        )
        return reponse

    def get_success_url(self):
        return reverse("medicaments:detail", args=[self.object.pk])


class MedicamentUpdateView(RoleRequisMixin, UpdateView):
    model = Medicament
    form_class = FormulaireMedicament
    template_name = "medicaments/medicament_form.html"
    roles_autorises = GESTION_MEDICAMENTS

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte["titre_formulaire"] = f"Modifier — {self.object}"
        contexte["bouton_libelle"] = "Enregistrer les modifications"
        return contexte

    def form_valid(self, form):
        reponse = super().form_valid(form)
        journaliser(
            self.request,
            JournalAudit.Action.MODIFICATION,
            MODULE_MEDICAMENTS,
            f"Modification du médicament {self.object}",
            objet=self.object,
        )
        messages.success(
            self.request, f"Le médicament « {self.object} » a été mis à jour."
        )
        return reponse

    def get_success_url(self):
        return reverse("medicaments:detail", args=[self.object.pk])


class MedicamentDeleteView(RoleRequisMixin, DeleteView):
    """Supprime un médicament vierge d'historique, sinon l'archive."""

    model = Medicament
    template_name = "medicaments/medicament_confirm_delete.html"
    context_object_name = "medicament"
    roles_autorises = GESTION_MEDICAMENTS
    success_url = reverse_lazy("medicaments:liste")

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte["historique_sensible"] = self.object.historique_sensible()
        return contexte

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        medicament = self.object
        if medicament.historique_sensible():
            medicament.archiver()
            journaliser(
                request,
                JournalAudit.Action.ARCHIVAGE,
                MODULE_MEDICAMENTS,
                f"Archivage du médicament {medicament} (historique conservé)",
                objet=medicament,
            )
            messages.warning(
                request,
                f"« {medicament} » est référencé dans des opérations passées : "
                "il a été archivé au lieu d'être supprimé afin de préserver l'historique.",
            )
            return redirect("medicaments:detail", pk=medicament.pk)

        identifiant = medicament.pk
        libelle = str(medicament)
        medicament.delete()
        journaliser(
            request,
            JournalAudit.Action.SUPPRESSION,
            MODULE_MEDICAMENTS,
            f"Suppression du médicament {libelle}",
            objet_id=identifiant,
        )
        messages.success(request, f"Le médicament « {libelle} » a été supprimé.")
        return redirect("medicaments:liste")


class MedicamentArchiverView(RoleRequisMixin, View):
    """Archive ou réactive un médicament après confirmation (POST)."""

    roles_autorises = GESTION_MEDICAMENTS
    template_name = "medicaments/medicament_archiver.html"

    def get_medicament(self):
        return get_object_or_404(Medicament, pk=self.kwargs["pk"])

    def get(self, request, *args, **kwargs):
        medicament = self.get_medicament()
        return self.render_confirmation(request, medicament)

    def render_confirmation(self, request, medicament):
        return render(
            request,
            self.template_name,
            {
                "medicament": medicament,
                "va_archiver": medicament.est_actif,
            },
        )

    def post(self, request, *args, **kwargs):
        medicament = self.get_medicament()
        if medicament.est_actif:
            medicament.archiver()
            journaliser(
                request,
                JournalAudit.Action.ARCHIVAGE,
                MODULE_MEDICAMENTS,
                f"Archivage du médicament {medicament}",
                objet=medicament,
            )
            messages.success(
                request,
                f"Le médicament « {medicament} » a été archivé. "
                "Il reste consultable mais n'est plus proposé à la vente.",
            )
        else:
            medicament.reactiver()
            journaliser(
                request,
                JournalAudit.Action.MODIFICATION,
                MODULE_MEDICAMENTS,
                f"Réactivation du médicament {medicament}",
                objet=medicament,
            )
            messages.success(
                request, f"Le médicament « {medicament} » a été réactivé."
            )
        return redirect("medicaments:detail", pk=medicament.pk)


# ---------------------------------------------------------------------------
# Catégories
# ---------------------------------------------------------------------------


class CategorieListView(RoleRequisMixin, ListView):
    model = Categorie
    template_name = "medicaments/categorie_liste.html"
    context_object_name = "categories"
    paginate_by = 20
    roles_autorises = GESTION_MEDICAMENTS

    def get_queryset(self):
        queryset = Categorie.objects.annotate(
            nombre_medicaments_annote=Count("medicaments")
        )
        recherche = (self.request.GET.get("q") or "").strip()
        if recherche:
            queryset = queryset.filter(nom__icontains=recherche)
        return queryset.order_by("nom")

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte["recherche"] = (self.request.GET.get("q") or "").strip()
        return contexte


class CategorieCreateView(RoleRequisMixin, CreateView):
    model = Categorie
    form_class = FormulaireCategorie
    template_name = "medicaments/categorie_form.html"
    roles_autorises = GESTION_MEDICAMENTS
    success_url = reverse_lazy("medicaments:categories")

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte["titre_formulaire"] = "Nouvelle catégorie"
        contexte["bouton_libelle"] = "Créer la catégorie"
        return contexte

    def form_valid(self, form):
        reponse = super().form_valid(form)
        journaliser(
            self.request,
            JournalAudit.Action.CREATION,
            MODULE_CATEGORIES,
            f"Création de la catégorie {self.object.nom}",
            objet=self.object,
        )
        messages.success(
            self.request, f"La catégorie « {self.object.nom} » a été créée."
        )
        return reponse


class CategorieUpdateView(RoleRequisMixin, UpdateView):
    model = Categorie
    form_class = FormulaireCategorie
    template_name = "medicaments/categorie_form.html"
    roles_autorises = GESTION_MEDICAMENTS
    success_url = reverse_lazy("medicaments:categories")

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte["titre_formulaire"] = f"Modifier — {self.object.nom}"
        contexte["bouton_libelle"] = "Enregistrer les modifications"
        return contexte

    def form_valid(self, form):
        reponse = super().form_valid(form)
        journaliser(
            self.request,
            JournalAudit.Action.MODIFICATION,
            MODULE_CATEGORIES,
            f"Modification de la catégorie {self.object.nom}",
            objet=self.object,
        )
        messages.success(
            self.request, f"La catégorie « {self.object.nom} » a été mise à jour."
        )
        return reponse


class CategorieDeleteView(RoleRequisMixin, DeleteView):
    model = Categorie
    template_name = "medicaments/categorie_confirm_delete.html"
    context_object_name = "categorie"
    roles_autorises = GESTION_MEDICAMENTS
    success_url = reverse_lazy("medicaments:categories")

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte["nombre_medicaments"] = self.object.medicaments.count()
        contexte["suppression_possible"] = self.object.peut_etre_supprimee()
        return contexte

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        categorie = self.object
        if not categorie.peut_etre_supprimee():
            nombre = categorie.medicaments.count()
            messages.error(
                request,
                f"La catégorie « {categorie.nom} » ne peut pas être supprimée : "
                f"{nombre} médicament{'s' if nombre > 1 else ''} y "
                f"{'sont' if nombre > 1 else 'est'} encore rattaché{'s' if nombre > 1 else ''}. "
                "Modifiez d'abord ces fiches.",
            )
            return redirect("medicaments:categories")

        identifiant = categorie.pk
        libelle = categorie.nom
        categorie.delete()
        journaliser(
            request,
            JournalAudit.Action.SUPPRESSION,
            MODULE_CATEGORIES,
            f"Suppression de la catégorie {libelle}",
            objet_id=identifiant,
        )
        messages.success(request, f"La catégorie « {libelle} » a été supprimée.")
        return redirect("medicaments:categories")
