"""Tests des comptes, rôles, permissions et sécurité d'authentification."""
import uuid

from django.test import TestCase
from django.urls import reverse

from core.models import JournalAudit
from utilisateurs.models import Role, Utilisateur

MOT_DE_PASSE = "MotDePasseTest2026!"


def creer_role(code, nom):
    role, _ = Role.objects.get_or_create(code=code, defaults={"nom": nom, "ordre": 10})
    return role


def creer_utilisateur(username, code_role, **extra):
    utilisateur = Utilisateur.objects.create_user(
        username=username,
        password=MOT_DE_PASSE,
        first_name=username.capitalize(),
        last_name="Test",
        email=f"{username}@pharmagest.test",
        **extra,
    )
    utilisateur.roles.add(creer_role(code_role, code_role))
    return utilisateur


class AuthentificationTests(TestCase):
    def setUp(self):
        self.utilisateur = creer_utilisateur("pharmacien", "PHARMACIEN")

    def test_connexion_et_redirection(self):
        reponse = self.client.post(
            reverse("utilisateurs:connexion"),
            {"username": "pharmacien", "password": MOT_DE_PASSE},
        )
        self.assertRedirects(reponse, reverse("rapports:tableau_bord"))
        self.assertTrue(JournalAudit.objects.filter(action=JournalAudit.Action.CONNEXION).exists())

    def test_mauvais_mot_de_passe_refuse(self):
        reponse = self.client.post(
            reverse("utilisateurs:connexion"),
            {"username": "pharmacien", "password": "incorrect"},
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "incorrect")

    def test_compte_desactive_refuse(self):
        self.utilisateur.is_active = False
        self.utilisateur.save(update_fields=["is_active"])
        reponse = self.client.post(
            reverse("utilisateurs:connexion"),
            {"username": "pharmacien", "password": MOT_DE_PASSE},
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(reponse.wsgi_request.user.is_authenticated)

    def test_pages_protegees(self):
        reponse = self.client.get(reverse("ventes:caisse"))
        self.assertEqual(reponse.status_code, 302)
        self.assertIn(reverse("utilisateurs:connexion"), reponse.url)

    def test_profil_modifiable(self):
        self.client.force_login(self.utilisateur)
        reponse = self.client.post(
            reverse("utilisateurs:profil"),
            {
                "first_name": "Nouveau",
                "last_name": "Nom",
                "email": "nouveau@pharmagest.test",
                "telephone": "0340000000",
                "adresse": "Antananarivo",
            },
        )
        self.assertRedirects(reponse, reverse("utilisateurs:profil"))
        self.utilisateur.refresh_from_db()
        self.assertEqual(self.utilisateur.first_name, "Nouveau")

    def test_changement_mot_de_passe(self):
        self.client.force_login(self.utilisateur)
        reponse = self.client.post(
            reverse("utilisateurs:mot_de_passe"),
            {
                "old_password": MOT_DE_PASSE,
                "new_password1": "NouveauMotDePasse2026!",
                "new_password2": "NouveauMotDePasse2026!",
            },
        )
        self.assertRedirects(reponse, reverse("utilisateurs:profil"))
        self.utilisateur.refresh_from_db()
        self.assertTrue(self.utilisateur.check_password("NouveauMotDePasse2026!"))


class GestionUtilisateursTests(TestCase):
    def setUp(self):
        self.admin = creer_utilisateur("admin", "ADMIN")
        self.caissier = creer_utilisateur("caissier", "CAISSIER")
        self.pharmacien = creer_utilisateur("pharmacien", "PHARMACIEN")

    def test_liste_reservee_admin(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("utilisateurs:liste")).status_code, 200)
        self.client.force_login(self.caissier)
        self.assertEqual(self.client.get(reverse("utilisateurs:liste")).status_code, 403)

    def test_creation_compte_avec_roles_cumules(self):
        self.client.force_login(self.admin)
        role_caissier = creer_role("CAISSIER", "Caissier")
        role_stock = creer_role("GESTION_STOCK", "Gestionnaire de stock")
        reponse = self.client.post(
            reverse("utilisateurs:creer"),
            {
                "username": "nouveau",
                "first_name": "Nouveau",
                "last_name": "Compte",
                "email": "nouveau@pharmagest.test",
                "telephone": "",
                "adresse": "",
                "is_active": "on",
                "roles": [role_caissier.pk, role_stock.pk],
                "password1": "CompteTest2026!",
                "password2": "CompteTest2026!",
            },
        )
        self.assertEqual(reponse.status_code, 302, reponse.context)
        compte = Utilisateur.objects.get(username="nouveau")
        self.assertEqual(compte.roles.count(), 2)
        self.assertTrue(compte.a_role("CAISSIER"))
        self.assertTrue(compte.a_role("GESTION_STOCK"))

    def test_mot_de_passe_non_conforme_refuse(self):
        self.client.force_login(self.admin)
        role = creer_role("CAISSIER", "Caissier")
        reponse = self.client.post(
            reverse("utilisateurs:creer"),
            {
                "username": "faible",
                "is_active": "on",
                "roles": [role.pk],
                "password1": "12345678",
                "password2": "12345678",
            },
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(Utilisateur.objects.filter(username="faible").exists())

    def test_desactivation_et_reactivation(self):
        self.client.force_login(self.admin)
        reponse = self.client.post(reverse("utilisateurs:basculer", args=[self.caissier.pk]))
        self.assertRedirects(reponse, reverse("utilisateurs:detail", args=[self.caissier.pk]))
        self.caissier.refresh_from_db()
        self.assertFalse(self.caissier.is_active)
        self.client.post(reverse("utilisateurs:basculer", args=[self.caissier.pk]))
        self.caissier.refresh_from_db()
        self.assertTrue(self.caissier.is_active)

    def test_auto_desactivation_interdite(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("utilisateurs:basculer", args=[self.admin.pk]))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_dernier_admin_protege(self):
        self.client.force_login(self.admin)
        reponse = self.client.post(reverse("utilisateurs:basculer", args=[self.caissier.pk]))
        self.assertEqual(reponse.status_code, 302)
        # Le seul administrateur ne peut pas être désactivé.
        self.client.post(reverse("utilisateurs:basculer", args=[self.admin.pk]))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_audit_connexion_et_action(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("utilisateurs:basculer", args=[self.caissier.pk]))
        self.assertTrue(
            JournalAudit.objects.filter(module="Utilisateurs", action=JournalAudit.Action.MODIFICATION).exists()
        )
