from django.urls import path

from utilisateurs import views

app_name = "utilisateurs"

urlpatterns = [
    path("connexion/", views.ConnexionView.as_view(), name="connexion"),
    path("deconnexion/", views.DeconnexionView.as_view(), name="deconnexion"),
    path("profil/", views.ProfilView.as_view(), name="profil"),
    path("mot-de-passe/", views.MotDePasseView.as_view(), name="mot_de_passe"),
    path(
        "mot-de-passe/reinitialiser/",
        views.ReinitialisationView.as_view(),
        name="reinitialiser_mot_de_passe",
    ),
    path(
        "mot-de-passe/reinitialisation/envoyee/",
        views.ReinitialisationEnvoyeeView.as_view(),
        name="reinitialisation_envoyee",
    ),
    path(
        "mot-de-passe/reinitialisation/<uidb64>/<token>/",
        views.ReinitialisationConfirmationView.as_view(),
        name="reinitialisation_confirm",
    ),
    path(
        "mot-de-passe/reinitialisation/terminee/",
        views.ReinitialisationTermineeView.as_view(),
        name="reinitialisation_terminee",
    ),
    path("utilisateurs/", views.ListeUtilisateursView.as_view(), name="liste"),
    path("utilisateurs/creer/", views.CreationUtilisateurView.as_view(), name="creer"),
    path("utilisateurs/<int:pk>/", views.DetailUtilisateurView.as_view(), name="detail"),
    path(
        "utilisateurs/<int:pk>/modifier/",
        views.ModificationUtilisateurView.as_view(),
        name="modifier",
    ),
    path(
        "utilisateurs/<int:pk>/activer/",
        views.BasculerUtilisateurView.as_view(),
        name="basculer",
    ),
]
