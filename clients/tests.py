"""Tests des vues et formulaires des clients."""
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from clients.models import Client
from core.models import JournalAudit
from utilisateurs.models import Role, Utilisateur
from utilisateurs.permissions import ADMIN, CAISSIER, GESTION_STOCK, PHARMACIEN
from ventes.models import Vente


def creer_utilisateur(nom, code_role):
    role, _ = Role.objects.get_or_create(code=code_role, defaults={"nom": code_role})
    utilisateur = Utilisateur.objects.create(username=nom, first_name=nom.title())
    utilisateur.roles.add(role)
    return utilisateur


class BaseClientsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.utilisateur_admin = creer_utilisateur("admin_cli", ADMIN)
        cls.utilisateur_caissier = creer_utilisateur("caissier_cli", CAISSIER)
        cls.utilisateur_pharmacien = creer_utilisateur("pharmacien_cli", PHARMACIEN)
        cls.utilisateur_stock = creer_utilisateur("stock_cli", GESTION_STOCK)


class ClientPermissionsTests(BaseClientsTest):
    def test_anonyme_redirige(self):
        reponse = self.client.get(reverse("clients:liste"))
        self.assertEqual(reponse.status_code, 302)
        self.assertIn(reverse("utilisateurs:connexion"), reponse.url)

    def test_caissier_autorise(self):
        self.client.force_login(self.utilisateur_caissier)
        self.assertEqual(self.client.get(reverse("clients:liste")).status_code, 200)
        self.assertEqual(self.client.get(reverse("clients:creer")).status_code, 200)

    def test_gestionnaire_stock_interdit(self):
        self.client.force_login(self.utilisateur_stock)
        self.assertEqual(self.client.get(reverse("clients:liste")).status_code, 403)
        self.assertEqual(self.client.get(reverse("clients:creer")).status_code, 403)

    def test_pharmacien_autorise(self):
        self.client.force_login(self.utilisateur_pharmacien)
        self.assertEqual(self.client.get(reverse("clients:liste")).status_code, 200)


class ClientCrudTests(BaseClientsTest):
    def setUp(self):
        self.client.force_login(self.utilisateur_caissier)
        self.client_obj = Client.objects.create(
            nom="Rakoto Jean",
            telephone="034 55 666 77",
            email="rakoto@example.mg",
            adresse="Antananarivo",
        )

    def test_creation_client(self):
        reponse = self.client.post(
            reverse("clients:creer"),
            {
                "nom": "Rasoa Marie",
                "telephone": "033 11 222 33",
                "email": "rasoa@example.mg",
                "adresse": "Antsirabe",
                "notes": "Cliente fidèle",
            },
        )
        client = Client.objects.get(nom="Rasoa Marie")
        self.assertRedirects(reponse, reverse("clients:detail", args=[client.pk]))
        self.assertTrue(client.actif)
        self.assertTrue(
            JournalAudit.objects.filter(
                action=JournalAudit.Action.CREATION, module="Clients"
            ).exists()
        )

    def test_creation_client_non_identifie_possible(self):
        reponse = self.client.post(
            reverse("clients:creer"),
            {"nom": "", "telephone": "", "email": "", "adresse": "", "notes": ""},
        )
        self.assertEqual(reponse.status_code, 302)
        self.assertTrue(Client.objects.filter(nom="", telephone="").exists())

    def test_modification_client(self):
        reponse = self.client.post(
            reverse("clients:modifier", args=[self.client_obj.pk]),
            {
                "nom": "Rakoto Jean Pierre",
                "telephone": "034 55 666 77",
                "email": "jp.rakoto@example.mg",
                "adresse": "Antananarivo",
                "notes": "",
            },
        )
        self.assertRedirects(
            reponse, reverse("clients:detail", args=[self.client_obj.pk])
        )
        self.client_obj.refresh_from_db()
        self.assertEqual(self.client_obj.nom, "Rakoto Jean Pierre")
        self.assertTrue(
            JournalAudit.objects.filter(
                action=JournalAudit.Action.MODIFICATION, module="Clients"
            ).exists()
        )

    def test_recherche_et_filtre_liste(self):
        Client.objects.create(nom="Autre Personne", telephone="032 00 000 01")
        inactif = Client.objects.create(nom="Inactif", actif=False)

        for terme, attendu in [
            ("rakoto", ["Rakoto Jean"]),
            ("666 77", ["Rakoto Jean"]),
            ("rakoto@example", ["Rakoto Jean"]),
        ]:
            reponse = self.client.get(reverse("clients:liste"), {"q": terme})
            noms = [c.nom for c in reponse.context["clients"]]
            self.assertEqual(noms, attendu)

        reponse = self.client.get(reverse("clients:liste"), {"actif": "0"})
        noms = [c.nom for c in reponse.context["clients"]]
        self.assertEqual(noms, [inactif.nom])

    def test_nombre_ventes_annote(self):
        Vente.objects.create(
            client=self.client_obj, utilisateur=self.utilisateur_caissier,
            montant_total=Decimal("5000"),
        )
        reponse = self.client.get(reverse("clients:liste"))
        client = next(
            c for c in reponse.context["clients"] if c.pk == self.client_obj.pk
        )
        self.assertEqual(client.nombre_ventes_annote, 1)

    def test_desactivation_conserve_historique_ventes(self):
        vente = Vente.objects.create(
            client=self.client_obj, utilisateur=self.utilisateur_caissier,
            montant_total=Decimal("12000"),
        )
        reponse = self.client.post(
            reverse("clients:basculer", args=[self.client_obj.pk]), follow=True
        )
        self.client_obj.refresh_from_db()
        self.assertFalse(self.client_obj.actif)
        self.assertTrue(Vente.objects.filter(pk=vente.pk).exists())
        self.assertContains(reponse, "désactivé")
        self.assertContains(reponse, vente.numero)
        self.assertContains(reponse, "Compte inactif")
        self.assertEqual(reponse.context["total_achete"], Decimal("12000"))

    def test_basculer_en_get_ne_modifie_pas(self):
        reponse = self.client.get(
            reverse("clients:basculer", args=[self.client_obj.pk])
        )
        self.assertEqual(reponse.status_code, 302)
        self.client_obj.refresh_from_db()
        self.assertTrue(self.client_obj.actif)

    def test_reactivation_client(self):
        self.client_obj.desactiver()
        self.client.post(reverse("clients:basculer", args=[self.client_obj.pk]))
        self.client_obj.refresh_from_db()
        self.assertTrue(self.client_obj.actif)
        self.assertTrue(
            JournalAudit.objects.filter(
                action=JournalAudit.Action.MODIFICATION, module="Clients"
            ).exists()
        )

    def test_detail_client(self):
        Vente.objects.create(
            client=self.client_obj, utilisateur=self.utilisateur_caissier,
            montant_total=Decimal("3000"),
        )
        reponse = self.client.get(
            reverse("clients:detail", args=[self.client_obj.pk])
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Historique des ventes")
        self.assertContains(reponse, self.client_obj.nom)
        self.assertEqual(reponse.context["nombre_ventes"], 1)
        self.assertEqual(reponse.context["total_achete"], Decimal("3000"))

    def test_404_detail(self):
        reponse = self.client.get(reverse("clients:detail", args=[999999]))
        self.assertEqual(reponse.status_code, 404)
