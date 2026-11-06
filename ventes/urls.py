from django.urls import path

from ventes import views

app_name = "ventes"

urlpatterns = [
    path("caisse/", views.CaisseView.as_view(), name="caisse"),
    path("panier/ajouter/", views.PanierAjouterView.as_view(), name="panier_ajouter"),
    path("panier/modifier/", views.PanierModifierView.as_view(), name="panier_modifier"),
    path("panier/retirer/", views.PanierRetirerView.as_view(), name="panier_retirer"),
    path("panier/vider/", views.PanierViderView.as_view(), name="panier_vider"),
    path("valider/", views.ValiderVenteView.as_view(), name="valider"),
    path("", views.ListeVentesView.as_view(), name="liste"),
    path("<int:pk>/", views.DetailVenteView.as_view(), name="detail"),
    path("<int:pk>/retour/", views.RetourVenteView.as_view(), name="retour"),
    path("<int:pk>/annuler/", views.AnnulerVenteView.as_view(), name="annuler"),
    path("retours/", views.ListeRetoursView.as_view(), name="retours"),
    path("paiements/", views.PaiementsView.as_view(), name="paiements"),
    path(
        "paiements/<int:pk>/confirmer/",
        views.ConfirmerPaiementView.as_view(),
        name="confirmer_paiement",
    ),
]
