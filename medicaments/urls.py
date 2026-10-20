"""Routage de l'application médicaments."""
from django.urls import path

from medicaments import views

app_name = "medicaments"

urlpatterns = [
    path("", views.MedicamentListView.as_view(), name="liste"),
    path("ajouter/", views.MedicamentCreateView.as_view(), name="creer"),
    path("categories/", views.CategorieListView.as_view(), name="categories"),
    path("categories/ajouter/", views.CategorieCreateView.as_view(), name="categorie_creer"),
    path(
        "categories/<int:pk>/modifier/",
        views.CategorieUpdateView.as_view(),
        name="categorie_modifier",
    ),
    path(
        "categories/<int:pk>/supprimer/",
        views.CategorieDeleteView.as_view(),
        name="categorie_supprimer",
    ),
    path("<int:pk>/", views.MedicamentDetailView.as_view(), name="detail"),
    path("<int:pk>/modifier/", views.MedicamentUpdateView.as_view(), name="modifier"),
    path("<int:pk>/supprimer/", views.MedicamentDeleteView.as_view(), name="supprimer"),
    path("<int:pk>/archiver/", views.MedicamentArchiverView.as_view(), name="archiver"),
]
