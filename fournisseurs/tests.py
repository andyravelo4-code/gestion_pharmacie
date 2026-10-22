"""Tests des vues et formulaires des fournisseurs."""
from django.test import TestCase
from django.urls import reverse

from achats.models import CommandeAchat
from core.models import JournalAudit
from fournisseurs.models import Fournisseur
from utilisateurs.models import Role, Utilisateur
from utilisateurs.permissions import ADMIN, CAISSIER, GESTION_STOCK


def creer_utilisateur(nom, code_role):
    role, _ = Role.objects.get_or_create(code=code_role, defaults={"nom": code_role})
    utilisateur = Utilisateur.objects.create(username=nom, first_name=nom.title())
    utilisateur.roles.add(role)
    return utilisateur


class BaseFournisseursTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.utilisateur_admin = creer_utilisateur("admin_four", ADMIN)
        cls.utilisateur_stock = creer_utilisateur("stock_four", GESTION_STOCK)
        cls.utilisateur_caissier = creer_utilisateur("caissier_four", CAISSIER)


class FournisseurPermissionsTests(BaseFournisseursTest):
    def test_anonyme_redirige(self):
        reponse = self.client.get(reverse("fournisseurs:liste"))
        self.assertEqual(reponse.status_code, 302)
        self.assertIn(reverse("utilisateurs:connexion"), reponse.url)

    def test_gestionnaire_stock_autorise(self):
        self.client.force_login(self.utilisateur_stock)
        self.assertEqual(
            self.client.get(reverse("fournisseurs:liste")).status_code, 200
        )
        self.assertEqual(
            self.client.get(reverse("fournisseurs:creer")).status_code, 200
        )

    def test_caissier_interdit(self):
        self.client.force_login(self.utilisateur_caissier)
        self.assertEqual(
            self.client.get(reverse("fournisseurs:liste")).status_code, 403
        )
        reponse = self.client.post(
            reverse("fournisseurs:creer"), {"nom": "Interdit"}
        )
        self.assertEqual(reponse.status_code, 403)
        self.assertFalse(Fournisseur.objects.filter(nom="Interdit").exists())


class FournisseurCrudTests(BaseFournisseursTest):
    def setUp(self):
        self.client.force_login(self.utilisateur_stock)
        self.fournisseur = Fournisseur.objects.create(
            nom="Pharma Distribution",
            telephone="034 11 222 33",
            email="contact@pharmadist.mg",
            adresse="Antananarivo",
            numero_fiscal="NIF-001",
            contact_principal="M. Rakoto",
        )

    def test_creation_fournisseur(self):
        reponse = self.client.post(
            reverse("fournisseurs:creer"),
            {
                "nom": "Grossiste Santé",
                "adresse": "Toamasina",
                "telephone": "033 44 555 66",
                "email": "contact@grossiste.mg",
                "numero_fiscal": "NIF-002",
                "contact_principal": "Mme Rasoa",
            },
        )
        fournisseur = Fournisseur.objects.get(nom="Grossiste Santé")
        self.assertRedirects(
            reponse, reverse("fournisseurs:detail", args=[fournisseur.pk])
        )
        self.assertTrue(fournisseur.actif)
        self.assertTrue(
            JournalAudit.objects.filter(
                action=JournalAudit.Action.CREATION, module="Fournisseurs"
            ).exists()
        )

    def test_nom_duplique_refuse(self):
        reponse = self.client.post(
            reverse("fournisseurs:creer"),
            {"nom": self.fournisseur.nom, "adresse": "", "telephone": "", "email": ""},
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "porte déjà cette raison sociale")
        self.assertEqual(
            Fournisseur.objects.filter(nom=self.fournisseur.nom).count(), 1
        )

    def test_modification_fournisseur(self):
        reponse = self.client.post(
            reverse("fournisseurs:modifier", args=[self.fournisseur.pk]),
            {
                "nom": "Pharma Distribution Plus",
                "adresse": "Antananarivo",
                "telephone": "034 11 222 33",
                "email": "contact@pharmadist.mg",
                "numero_fiscal": "NIF-001",
                "contact_principal": "M. Rakoto",
            },
        )
        self.assertRedirects(
            reponse, reverse("fournisseurs:detail", args=[self.fournisseur.pk])
        )
        self.fournisseur.refresh_from_db()
        self.assertEqual(self.fournisseur.nom, "Pharma Distribution Plus")
        self.assertTrue(
            JournalAudit.objects.filter(
                action=JournalAudit.Action.MODIFICATION, module="Fournisseurs"
            ).exists()
        )

    def test_recherche_et_filtre_liste(self):
        Fournisseur.objects.create(nom="Autre Fournisseur", telephone="032 00 000 01")
        inactif = Fournisseur.objects.create(nom="Inactif SARL", actif=False)

        reponse = self.client.get(reverse("fournisseurs:liste"), {"q": "distribution"})
        noms = [f.nom for f in reponse.context["fournisseurs"]]
        self.assertEqual(noms, ["Pharma Distribution"])

        reponse = self.client.get(reverse("fournisseurs:liste"), {"q": "032"})
        noms = [f.nom for f in reponse.context["fournisseurs"]]
        self.assertEqual(noms, ["Autre Fournisseur"])

        reponse = self.client.get(reverse("fournisseurs:liste"), {"actif": "0"})
        noms = [f.nom for f in reponse.context["fournisseurs"]]
        self.assertEqual(noms, [inactif.nom])

    def test_desactivation_conserve_historique(self):
        commande = CommandeAchat.objects.create(
            fournisseur=self.fournisseur, utilisateur=self.utilisateur_admin
        )
        reponse = self.client.post(
            reverse("fournisseurs:basculer", args=[self.fournisseur.pk]), follow=True
        )
        self.fournisseur.refresh_from_db()
        self.assertFalse(self.fournisseur.actif)
        self.assertTrue(CommandeAchat.objects.filter(pk=commande.pk).exists())
        self.assertContains(reponse, "désactivé")
        self.assertContains(reponse, commande.numero)
        self.assertContains(reponse, "Inactif")

    def test_basculer_en_get_ne_modifie_pas(self):
        reponse = self.client.get(
            reverse("fournisseurs:basculer", args=[self.fournisseur.pk])
        )
        self.assertEqual(reponse.status_code, 302)
        self.fournisseur.refresh_from_db()
        self.assertTrue(self.fournisseur.actif)

    def test_reactivation(self):
        self.fournisseur.desactiver()
        self.client.post(
            reverse("fournisseurs:basculer", args=[self.fournisseur.pk])
        )
        self.fournisseur.refresh_from_db()
        self.assertTrue(self.fournisseur.actif)
        self.assertTrue(
            JournalAudit.objects.filter(
                action=JournalAudit.Action.MODIFICATION, module="Fournisseurs"
            ).exists()
        )

    def test_detail_affiche_commandes_et_total(self):
        CommandeAchat.objects.create(
            fournisseur=self.fournisseur, utilisateur=self.utilisateur_admin
        )
        reponse = self.client.get(
            reverse("fournisseurs:detail", args=[self.fournisseur.pk])
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Historique des commandes")
        self.assertContains(reponse, self.fournisseur.nom)
        self.assertEqual(reponse.context["nombre_commandes"], 1)

    def test_404_detail(self):
        reponse = self.client.get(reverse("fournisseurs:detail", args=[999999]))
        self.assertEqual(reponse.status_code, 404)
