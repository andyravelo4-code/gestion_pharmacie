"""Paramétrage, sauvegardes et pages d'erreur."""
import shutil
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import TemplateView, UpdateView

from core.forms import FormulaireParametre
from core.models import JournalAudit, ParametrePharmacie
from core.utils import journaliser
from utilisateurs.permissions import AdminRequisMixin


class ParametresView(AdminRequisMixin, UpdateView):
    model = ParametrePharmacie
    form_class = FormulaireParametre
    template_name = "core/parametres.html"
    success_url = reverse_lazy("core:parametres")

    def get_object(self, queryset=None):
        return ParametrePharmacie.get_solo()

    def form_valid(self, form):
        reponse = super().form_valid(form)
        journaliser(
            self.request,
            JournalAudit.Action.PARAMETRE,
            "Paramètres",
            "Mise à jour des paramètres de la pharmacie",
            objet=self.object,
        )
        messages.success(self.request, "Les paramètres de la pharmacie ont été enregistrés.")
        return reponse


def _liste_sauvegardes():
    dossier = Path(settings.BACKUP_DIR)
    dossier.mkdir(parents=True, exist_ok=True)
    fichiers = sorted(
        (f for f in dossier.glob("*") if f.is_file()),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    return [
        {
            "nom": f.name,
            "taille": f.stat().st_size,
            "date": datetime.fromtimestamp(f.stat().st_mtime),
        }
        for f in fichiers
    ]


def creer_fichier_sauvegarde():
    """Crée une sauvegarde cohérente de la base SQLite (ou via pg_dump)."""
    dossier = Path(settings.BACKUP_DIR)
    dossier.mkdir(parents=True, exist_ok=True)
    horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
    moteur = settings.DATABASES["default"]["ENGINE"]

    if "sqlite3" in moteur:
        destination = dossier / f"pharmagest_{horodatage}.sqlite3"
        source = settings.DATABASES["default"]["NAME"]
        connexion = sqlite3.connect(source)
        try:
            cible = sqlite3.connect(destination)
            try:
                connexion.backup(cible)
            finally:
                cible.close()
        finally:
            connexion.close()
        return destination

    destination = dossier / f"pharmagest_{horodatage}.sql"
    db = settings.DATABASES["default"]
    commande = [
        "pg_dump",
        "-h", db.get("HOST", "localhost"),
        "-p", str(db.get("PORT", "5432")),
        "-U", db.get("USER", ""),
        "-d", db.get("NAME", ""),
        "-f", str(destination),
    ]
    subprocess.run(commande, check=True)
    return destination


class SauvegardesView(AdminRequisMixin, TemplateView):
    template_name = "core/sauvegardes.html"

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte["sauvegardes"] = _liste_sauvegardes()
        contexte["dossier"] = str(settings.BACKUP_DIR)
        return contexte

    def post(self, request, *args, **kwargs):
        try:
            fichier = creer_fichier_sauvegarde()
        except Exception as erreur:  # pragma: no cover - dépend de l'environnement
            messages.error(request, f"La sauvegarde a échoué : {erreur}")
        else:
            journaliser(
                request,
                JournalAudit.Action.SAUVEGARDE,
                "Sauvegarde",
                f"Sauvegarde de la base créée : {fichier.name}",
            )
            messages.success(request, f"Sauvegarde créée : {fichier.name}")
        return redirect("core:sauvegardes")


class TelechargerSauvegardeView(AdminRequisMixin, TemplateView):
    def get(self, request, nom, *args, **kwargs):
        dossier = Path(settings.BACKUP_DIR).resolve()
        fichier = (dossier / nom).resolve()
        if dossier not in fichier.parents or not fichier.is_file():
            raise Http404("Sauvegarde introuvable.")
        journaliser(
            request,
            JournalAudit.Action.SAUVEGARDE,
            "Sauvegarde",
            f"Téléchargement de la sauvegarde {fichier.name}",
        )
        return FileResponse(open(fichier, "rb"), as_attachment=True, filename=fichier.name)


def erreur_403(request, exception=None):
    return render(request, "403.html", status=403)


def erreur_404(request, exception=None):
    return render(request, "404.html", status=404)


def erreur_500(request):
    return render(request, "500.html", status=500)
