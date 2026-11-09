"""Routage de l'application rapports."""
from django.urls import path

from . import views

app_name = "rapports"

urlpatterns = [
    path("", views.TableauBordView.as_view(), name="tableau_bord"),
    path("rapports/ventes/", views.RapportVentesView.as_view(), name="ventes"),
    path("rapports/achats/", views.RapportAchatsView.as_view(), name="achats"),
    path("rapports/stock/", views.RapportStockView.as_view(), name="stock"),
    path(
        "rapports/peremptions/",
        views.RapportPeremptionsView.as_view(),
        name="peremptions",
    ),
    path("rapports/journal/", views.JournalAuditView.as_view(), name="journal"),
    path("pdf/ventes/", views.PdfVentesView.as_view(), name="pdf_ventes"),
    path("pdf/achats/", views.PdfAchatsView.as_view(), name="pdf_achats"),
    path("pdf/stock/", views.PdfStockView.as_view(), name="pdf_stock"),
    path(
        "pdf/peremptions/",
        views.PdfPeremptionsView.as_view(),
        name="pdf_peremptions",
    ),
    path(
        "pdf/ventes/<int:pk>/recu/",
        views.RecuVenteView.as_view(),
        name="recu_vente",
    ),
    path(
        "pdf/ventes/<int:pk>/facture/",
        views.FactureVenteView.as_view(),
        name="facture_vente",
    ),
    path(
        "pdf/commandes/<int:pk>/",
        views.BonCommandeView.as_view(),
        name="bon_commande",
    ),
    path(
        "pdf/receptions/<int:pk>/",
        views.BonReceptionView.as_view(),
        name="bon_reception",
    ),
]
