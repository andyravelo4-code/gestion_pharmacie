"""Vues des clients."""
from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from clients.forms import FormulaireClient
from clients.models import Client
from core.models import JournalAudit
from core.utils import journaliser
from utilisateurs.permissions import RoleRequisMixin, VENTES_ROLES
from ventes.models import Vente

MODULE_CLIENTS = "Clients"


class ClientListView(RoleRequisMixin, ListView):
    model = Client
    template_name = "clients/client_liste.html"
    context_object_name = "clients"
    paginate_by = 15
    roles_autorises = VENTES_ROLES

    def get_queryset(self):
        queryset = Client.objects.annotate(nombre_ventes_annote=Count("ventes"))
        recherche = (self.request.GET.get("q") or "").strip()
        if recherche:
            queryset = queryset.filter(
                Q(nom__icontains=recherche)
                | Q(telephone__icontains=recherche)
                | Q(email__icontains=recherche)
            )
        filtre = (self.request.GET.get("actif") or "").strip()
        if filtre == "1":
            queryset = queryset.filter(actif=True)
        elif filtre == "0":
            queryset = queryset.filter(actif=False)
        return queryset.order_by("nom", "telephone")

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte.update(
            {
                "recherche": (self.request.GET.get("q") or "").strip(),
                "actif_selectionne": (self.request.GET.get("actif") or "").strip(),
            }
        )
        return contexte


class ClientDetailView(RoleRequisMixin, DetailView):
    model = Client
    template_name = "clients/client_detail.html"
    context_object_name = "client"
    roles_autorises = VENTES_ROLES

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        client = self.object
        ventes = client.ventes.select_related("utilisateur").order_by("-date_vente")
        contexte.update(
            {
                "ventes": ventes[:25],
                "nombre_ventes": ventes.count(),
                "total_achete": ventes.filter(statut=Vente.Statut.VALIDEE).aggregate(
                    total=Sum("montant_total")
                )["total"]
                or 0,
            }
        )
        return contexte


class ClientCreateView(RoleRequisMixin, CreateView):
    model = Client
    form_class = FormulaireClient
    template_name = "clients/client_form.html"
    roles_autorises = VENTES_ROLES

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte["titre_formulaire"] = "Nouveau client"
        contexte["bouton_libelle"] = "Créer le client"
        return contexte

    def form_valid(self, form):
        reponse = super().form_valid(form)
        journaliser(
            self.request,
            JournalAudit.Action.CREATION,
            MODULE_CLIENTS,
            f"Création du client {self.object.nom_affichage}",
            objet=self.object,
        )
        messages.success(
            self.request, f"Le client « {self.object.nom_affichage} » a été créé."
        )
        return reponse

    def get_success_url(self):
        return reverse("clients:detail", args=[self.object.pk])


class ClientUpdateView(RoleRequisMixin, UpdateView):
    model = Client
    form_class = FormulaireClient
    template_name = "clients/client_form.html"
    roles_autorises = VENTES_ROLES

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte["titre_formulaire"] = f"Modifier — {self.object.nom_affichage}"
        contexte["bouton_libelle"] = "Enregistrer les modifications"
        return contexte

    def form_valid(self, form):
        reponse = super().form_valid(form)
        journaliser(
            self.request,
            JournalAudit.Action.MODIFICATION,
            MODULE_CLIENTS,
            f"Modification du client {self.object.nom_affichage}",
            objet=self.object,
        )
        messages.success(
            self.request, f"Le client « {self.object.nom_affichage} » a été mis à jour."
        )
        return reponse

    def get_success_url(self):
        return reverse("clients:detail", args=[self.object.pk])


class ClientBasculerView(RoleRequisMixin, View):
    """Active ou désactive un compte client (POST uniquement)."""

    roles_autorises = VENTES_ROLES

    def post(self, request, pk, *args, **kwargs):
        client = get_object_or_404(Client, pk=pk)
        if client.actif:
            client.desactiver()
            journaliser(
                request,
                JournalAudit.Action.MODIFICATION,
                MODULE_CLIENTS,
                f"Désactivation du client {client.nom_affichage}",
                objet=client,
            )
            messages.warning(
                request,
                f"Le compte de « {client.nom_affichage} » a été désactivé. "
                "Son historique de ventes est conservé.",
            )
        else:
            client.reactiver()
            journaliser(
                request,
                JournalAudit.Action.MODIFICATION,
                MODULE_CLIENTS,
                f"Réactivation du client {client.nom_affichage}",
                objet=client,
            )
            messages.success(
                request, f"Le compte de « {client.nom_affichage} » a été réactivé."
            )
        return redirect("clients:detail", pk=client.pk)

    def get(self, request, *args, **kwargs):
        return redirect("clients:liste")
