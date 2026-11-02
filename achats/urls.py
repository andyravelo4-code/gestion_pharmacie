"""Routage de l'application achats."""
from django.urls import path

from achats import views

app_name = "achats"

urlpatterns = [
    path("", views.CommandesView.as_view(), name="liste"),
    path("creer/", views.CommandeCreerView.as_view(), name="creer"),
    path("<int:pk>/", views.CommandeDetailView.as_view(), name="detail"),
    path("<int:pk>/modifier/", views.CommandeModifierView.as_view(), name="modifier"),
    path("<int:pk>/lignes/ajouter/", views.LigneAjouterView.as_view(), name="ajouter_ligne"),
    path("lignes/<int:pk>/modifier/", views.LigneModifierView.as_view(), name="modifier_ligne"),
    path("lignes/<int:pk>/supprimer/", views.LigneSupprimerView.as_view(), name="supprimer_ligne"),
    path("<int:pk>/valider/", views.CommandeValiderView.as_view(), name="valider"),
    path("<int:pk>/annuler/", views.CommandeAnnulerView.as_view(), name="annuler"),
    path("<int:pk>/receptionner/", views.CommandeReceptionnerView.as_view(), name="receptionner"),
    path("receptions/", views.ReceptionsView.as_view(), name="receptions"),
    path(
        "receptions/<int:pk>/",
        views.ReceptionDetailView.as_view(),
        name="reception_detail",
    ),
]
