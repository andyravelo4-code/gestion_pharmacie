"""Routage de l'application stock."""
from django.urls import path

from stock import views

app_name = "stock"

urlpatterns = [
    path("", views.TableauStockView.as_view(), name="tableau"),
    path("lots/", views.LotsView.as_view(), name="lots"),
    path("lots/<int:pk>/", views.LotDetailView.as_view(), name="lot_detail"),
    path("lots/<int:pk>/bloquer/", views.BloquerLotView.as_view(), name="bloquer_lot"),
    path("mouvements/", views.MouvementsView.as_view(), name="mouvements"),
    path("alertes/", views.AlertesView.as_view(), name="alertes"),
    path("inventaires/", views.InventairesView.as_view(), name="inventaires"),
    path(
        "inventaires/creer/",
        views.InventaireCreerView.as_view(),
        name="inventaire_creer",
    ),
    path(
        "inventaires/<int:pk>/",
        views.InventaireDetailView.as_view(),
        name="inventaire_detail",
    ),
    path(
        "inventaires/<int:pk>/valider/",
        views.InventaireValiderView.as_view(),
        name="inventaire_valider",
    ),
]
