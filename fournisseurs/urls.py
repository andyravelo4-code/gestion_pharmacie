"""Routage des fournisseurs."""
from django.urls import path

from fournisseurs import views

app_name = "fournisseurs"

urlpatterns = [
    path("", views.FournisseurListView.as_view(), name="liste"),
    path("ajouter/", views.FournisseurCreateView.as_view(), name="creer"),
    path("<int:pk>/", views.FournisseurDetailView.as_view(), name="detail"),
    path("<int:pk>/modifier/", views.FournisseurUpdateView.as_view(), name="modifier"),
    path("<int:pk>/activer/", views.FournisseurBasculerView.as_view(), name="basculer"),
]
