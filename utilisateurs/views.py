"""Authentification, gestion des comptes et permissions."""
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from core.models import JournalAudit
from core.utils import journaliser
from utilisateurs.forms import (
    FormulaireConnexion,
    FormulaireMotDePasse,
    FormulaireNouveauMotDePasse,
    FormulaireProfil,
    FormulaireReinitialisation,
    FormulaireUtilisateur,
)
from utilisateurs.models import Role, Utilisateur
from utilisateurs.permissions import ADMIN, AdminRequisMixin


class ConnexionView(auth_views.LoginView):
    template_name = "registration/login.html"
    authentication_form = FormulaireConnexion
    redirect_authenticated_user = True


class DeconnexionView(auth_views.LogoutView):
    next_page = reverse_lazy("utilisateurs:connexion")
    http_method_names = ["post", "options"]


class ProfilView(LoginRequiredMixin, UpdateView):
    model = Utilisateur
    form_class = FormulaireProfil
    template_name = "utilisateurs/profil.html"
    success_url = reverse_lazy("utilisateurs:profil")

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        reponse = super().form_valid(form)
        journaliser(
            self.request,
            JournalAudit.Action.MODIFICATION,
            "Profil",
            "Mise à jour de son profil",
            objet=self.object,
        )
        messages.success(self.request, "Votre profil a été mis à jour.")
        return reponse

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte["actions_recentes"] = JournalAudit.objects.filter(
            utilisateur=self.request.user
        )[:12]
        return contexte


class MotDePasseView(auth_views.PasswordChangeView):
    form_class = FormulaireMotDePasse
    template_name = "registration/password_change_form.html"
    success_url = reverse_lazy("utilisateurs:profil")

    def form_valid(self, form):
        reponse = super().form_valid(form)
        journaliser(
            self.request,
            JournalAudit.Action.MODIFICATION,
            "Authentification",
            "Changement de mot de passe",
            objet=self.request.user,
        )
        messages.success(self.request, "Votre mot de passe a été modifié avec succès.")
        return reponse


class ReinitialisationView(auth_views.PasswordResetView):
    form_class = FormulaireReinitialisation
    template_name = "registration/password_reset_form.html"
    email_template_name = "registration/password_reset_email.txt"
    subject_template_name = "registration/password_reset_subject.txt"
    success_url = reverse_lazy("utilisateurs:reinitialisation_envoyee")

    def form_valid(self, form):
        reponse = super().form_valid(form)
        journaliser(
            self.request,
            JournalAudit.Action.PARAMETRE,
            "Authentification",
            "Demande de réinitialisation de mot de passe",
            details=f"Adresse concernée : {form.cleaned_data.get('email', '')}",
        )
        return reponse


class ReinitialisationEnvoyeeView(auth_views.PasswordResetDoneView):
    template_name = "registration/password_reset_done.html"


class ReinitialisationConfirmationView(auth_views.PasswordResetConfirmView):
    form_class = FormulaireNouveauMotDePasse
    template_name = "registration/password_reset_confirm.html"
    success_url = reverse_lazy("utilisateurs:reinitialisation_terminee")

    def form_valid(self, form):
        reponse = super().form_valid(form)
        journaliser(
            self.request,
            JournalAudit.Action.MODIFICATION,
            "Authentification",
            f"Réinitialisation du mot de passe de {form.user.nom_complet}",
            objet=form.user,
        )
        return reponse


class ReinitialisationTermineeView(auth_views.PasswordResetCompleteView):
    template_name = "registration/password_reset_complete.html"


# --------------------------------------------------------------------------
# Gestion des utilisateurs (administrateur)
# --------------------------------------------------------------------------
class ListeUtilisateursView(AdminRequisMixin, ListView):
    model = Utilisateur
    template_name = "utilisateurs/liste.html"
    paginate_by = 15
    context_object_name = "utilisateurs"

    def get_queryset(self):
        qs = Utilisateur.objects.prefetch_related("roles").distinct()
        q = self.request.GET.get("q", "").strip()
        role = self.request.GET.get("role", "").strip()
        statut = self.request.GET.get("statut", "").strip()
        if q:
            qs = qs.filter(
                Q(username__icontains=q)
                | Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(email__icontains=q)
                | Q(telephone__icontains=q)
            )
        if role:
            qs = qs.filter(roles__code=role)
        if statut == "actif":
            qs = qs.filter(is_active=True)
        elif statut == "inactif":
            qs = qs.filter(is_active=False)
        return qs.order_by("last_name", "first_name", "username")

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte["roles"] = Role.objects.all()
        contexte["q"] = self.request.GET.get("q", "")
        contexte["role_selectionne"] = self.request.GET.get("role", "")
        contexte["statut_selectionne"] = self.request.GET.get("statut", "")
        return contexte


class DetailUtilisateurView(AdminRequisMixin, DetailView):
    model = Utilisateur
    template_name = "utilisateurs/detail.html"
    context_object_name = "compte"

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte["actions_recentes"] = JournalAudit.objects.filter(
            utilisateur=self.object
        ).select_related("utilisateur")[:20]
        contexte["nombre_ventes"] = self.object.ventes.count()
        return contexte


def _est_dernier_admin(utilisateur):
    """Vrai si retirer ce compte laisserait la pharmacie sans administrateur actif."""
    autres = Utilisateur.objects.filter(is_active=True, roles__code=ADMIN).exclude(pk=utilisateur.pk)
    return not autres.exists()


class CreationUtilisateurView(AdminRequisMixin, CreateView):
    model = Utilisateur
    form_class = FormulaireUtilisateur
    template_name = "utilisateurs/formulaire.html"

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte["titre_formulaire"] = "Nouvel utilisateur"
        contexte["bouton"] = "Créer le compte"
        return contexte

    def form_valid(self, form):
        reponse = super().form_valid(form)
        journaliser(
            self.request,
            JournalAudit.Action.CREATION,
            "Utilisateurs",
            f"Création du compte {self.object.username}",
            objet=self.object,
            details=f"Rôles : {', '.join(r.nom for r in self.object.roles.all())}",
        )
        messages.success(self.request, f"Le compte {self.object.username} a été créé.")
        return reponse

    def get_success_url(self):
        return reverse_lazy("utilisateurs:detail", args=[self.object.pk])


class ModificationUtilisateurView(AdminRequisMixin, UpdateView):
    model = Utilisateur
    form_class = FormulaireUtilisateur
    template_name = "utilisateurs/formulaire.html"

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte["titre_formulaire"] = f"Modifier {self.object.nom_complet}"
        contexte["bouton"] = "Enregistrer les modifications"
        return contexte

    def form_valid(self, form):
        object_modifie = form.save(commit=False)
        if object_modifie.pk == self.request.user.pk:
            if not form.cleaned_data.get("is_active"):
                form.add_error("is_active", "Vous ne pouvez pas désactiver votre propre compte.")
                return self.form_invalid(form)
            if not self.request.user.is_superuser and not form.cleaned_data["roles"].filter(
                code=ADMIN
            ).exists():
                form.add_error(
                    "roles",
                    "Vous ne pouvez pas retirer votre propre rôle administrateur.",
                )
                return self.form_invalid(form)
        if _est_dernier_admin(self.object) and self.object.is_active and self.object.roles.filter(
            code=ADMIN
        ).exists():
            if not self.request.user.is_superuser and (
                not form.cleaned_data.get("is_active")
                or not form.cleaned_data["roles"].filter(code=ADMIN).exists()
            ):
                form.add_error(
                    "roles",
                    "Impossible de retirer le dernier administrateur actif de la pharmacie.",
                )
                return self.form_invalid(form)

        reponse = super().form_valid(form)
        journaliser(
            self.request,
            JournalAudit.Action.MODIFICATION,
            "Utilisateurs",
            f"Modification du compte {self.object.username}",
            objet=self.object,
            details=f"Rôles : {', '.join(r.nom for r in self.object.roles.all())}",
        )
        messages.success(self.request, f"Le compte {self.object.username} a été mis à jour.")
        return reponse

    def get_success_url(self):
        return reverse_lazy("utilisateurs:detail", args=[self.object.pk])


class BasculerUtilisateurView(AdminRequisMixin, DetailView):
    """Active ou désactive un compte (jamais de suppression)."""

    http_method_names = ["post"]

    def post(self, request, pk, *args, **kwargs):
        compte = get_object_or_404(Utilisateur, pk=pk)
        if compte.pk == request.user.pk:
            messages.error(request, "Vous ne pouvez pas désactiver votre propre compte.")
            return redirect("utilisateurs:detail", pk=compte.pk)
        if compte.is_active and _est_dernier_admin(compte):
            messages.error(
                request,
                "Impossible de désactiver le dernier administrateur actif.",
            )
            return redirect("utilisateurs:detail", pk=compte.pk)
        compte.is_active = not compte.is_active
        compte.save(update_fields=["is_active"])
        action = "Activé" if compte.is_active else "Désactivé"
        journaliser(
            request,
            JournalAudit.Action.MODIFICATION,
            "Utilisateurs",
            f"Compte {compte.username} {action.lower()}",
            objet=compte,
        )
        messages.success(request, f"Le compte {compte.username} a été {action.lower()}.")
        return redirect("utilisateurs:detail", pk=compte.pk)
