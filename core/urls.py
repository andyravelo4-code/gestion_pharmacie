from django.urls import path

from core import views

app_name = "core"

urlpatterns = [
    path("parametres/", views.ParametresView.as_view(), name="parametres"),
    path("sauvegardes/", views.SauvegardesView.as_view(), name="sauvegardes"),
    path("sauvegardes/<str:nom>/", views.TelechargerSauvegardeView.as_view(), name="telecharger_sauvegarde"),
]
