"""Vues des fournisseurs."""
from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from achats.models import CommandeAchat
from core.models import JournalAudit
from core.utils import journaliser
from fournisseurs.forms import FormulaireFournisseur
from fournisseurs.models import Fournisseur
from utilisateurs.permissions import GESTION_STOCK_ROLES, RoleRequisMixin

MODULE_FOURNISSEURS = "Fournisseurs"


class FournisseurListView(RoleRequisMixin, ListView):
    model = Fournisseur
    template_name = "fournisseurs/fournisseur_liste.html"
    context_object_name = "fournisseurs"
    paginate_by = 15
    roles_autorises = GESTION_STOCK_ROLES

    def get_queryset(self):
        queryset = Fournisseur.objects.annotate(
            nombre_commandes_annote=Count("commandes")
        )
        recherche = (self.request.GET.get("q") or "").strip()
        if recherche:
            queryset = queryset.filter(
                Q(nom__icontains=recherche) | Q(telephone__icontains=recherche)
            )
        filtre = (self.request.GET.get("actif") or "").strip()
        if filtre == "1":
            queryset = queryset.filter(actif=True)
        elif filtre == "0":
            queryset = queryset.filter(actif=False)
        return queryset.order_by("nom")

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte.update(
            {
                "recherche": (self.request.GET.get("q") or "").strip(),
                "actif_selectionne": (self.request.GET.get("actif") or "").strip(),
            }
        )
        return contexte


class FournisseurDetailView(RoleRequisMixin, DetailView):
    model = Fournisseur
    template_name = "fournisseurs/fournisseur_detail.html"
    context_object_name = "fournisseur"
    roles_autorises = GESTION_STOCK_ROLES

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        fournisseur = self.object
        commandes = (
            CommandeAchat.objects.filter(fournisseur=fournisseur)
            .prefetch_related("lignes")
            .order_by("-date_creation")[:20]
        )
        contexte.update(
            {
                "commandes": commandes,
                "nombre_commandes": fournisseur.commandes.count(),
                "total_achats": fournisseur.montant_total_achats,
                "lots": fournisseur.lots.select_related("medicament").order_by(
                    "-date_reception"
                )[:15],
            }
        )
        return contexte


class FournisseurCreateView(RoleRequisMixin, CreateView):
    model = Fournisseur
    form_class = FormulaireFournisseur
    template_name = "fournisseurs/fournisseur_form.html"
    roles_autorises = GESTION_STOCK_ROLES

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte["titre_formulaire"] = "Nouveau fournisseur"
        contexte["bouton_libelle"] = "Créer le fournisseur"
        return contexte

    def form_valid(self, form):
        reponse = super().form_valid(form)
        journaliser(
            self.request,
            JournalAudit.Action.CREATION,
            MODULE_FOURNISSEURS,
            f"Création du fournisseur {self.object.nom}",
            objet=self.object,
        )
        messages.success(
            self.request, f"Le fournisseur « {self.object.nom} » a été créé."
        )
        return reponse

    def get_success_url(self):
        return reverse("fournisseurs:detail", args=[self.object.pk])


class FournisseurUpdateView(RoleRequisMixin, UpdateView):
    model = Fournisseur
    form_class = FormulaireFournisseur
    template_name = "fournisseurs/fournisseur_form.html"
    roles_autorises = GESTION_STOCK_ROLES

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
            MODULE_FOURNISSEURS,
            f"Modification du fournisseur {self.object.nom}",
            objet=self.object,
        )
        messages.success(
            self.request, f"Le fournisseur « {self.object.nom} » a été mis à jour."
        )
        return reponse

    def get_success_url(self):
        return reverse("fournisseurs:detail", args=[self.object.pk])


class FournisseurBasculerView(RoleRequisMixin, View):
    """Désactive ou réactive un fournisseur (POST uniquement).

    Aucune suppression n'est proposée : les commandes et lots passés sont conservés.
    """

    roles_autorises = GESTION_STOCK_ROLES

    def post(self, request, pk, *args, **kwargs):
        fournisseur = get_object_or_404(Fournisseur, pk=pk)
        if fournisseur.actif:
            fournisseur.desactiver()
            journaliser(
                request,
                JournalAudit.Action.MODIFICATION,
                MODULE_FOURNISSEURS,
                f"Désactivation du fournisseur {fournisseur.nom}",
                objet=fournisseur,
            )
            messages.warning(
                request,
                f"Le fournisseur « {fournisseur.nom} » a été désactivé. "
                "Son historique de commandes reste intact.",
            )
        else:
            fournisseur.reactiver()
            journaliser(
                request,
                JournalAudit.Action.MODIFICATION,
                MODULE_FOURNISSEURS,
                f"Réactivation du fournisseur {fournisseur.nom}",
                objet=fournisseur,
            )
            messages.success(
                request, f"Le fournisseur « {fournisseur.nom} » a été réactivé."
            )
        return redirect("fournisseurs:detail", pk=fournisseur.pk)

    def get(self, request, *args, **kwargs):
        return redirect("fournisseurs:liste")
