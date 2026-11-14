"""Test de fumée : rendu de toutes les pages et de tous les PDF.

Ce test utilise le jeu de données fictif complet afin de détecter les erreurs
de template, d'URL ou de contexte qui ne apparaissent pas dans les tests
unitaires ciblés.
"""
import shutil
import tempfile
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from achats.models import CommandeAchat, LigneAchat, ReceptionAchat
from clients.models import Client
from fournisseurs.models import Fournisseur
from medicaments.models import Categorie, Medicament
from stock.models import Inventaire, LotStock
from utilisateurs.models import Utilisateur
from ventes.models import Vente

MEDIA_TEMPS = tempfile.mkdtemp(prefix="pharmagest-smoke-")


@override_settings(MEDIA_ROOT=MEDIA_TEMPS)
class SmokePagesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("donnees_demo", verbosity=0, stdout=StringIO())
        cls.admin = Utilisateur.objects.get(username="admin")
        cls.medicament = Medicament.objects.first()
        cls.categorie = Categorie.objects.first()
        cls.fournisseur = Fournisseur.objects.first()
        cls.client_obj = Client.objects.first()
        cls.lot = LotStock.objects.first()
        cls.inventaire = Inventaire.objects.first()
        cls.commande_brouillon = CommandeAchat.objects.filter(
            statut=CommandeAchat.Statut.BROUILLON
        ).first()
        cls.commande_receptionnable = CommandeAchat.objects.filter(
            statut__in=[
                CommandeAchat.Statut.COMMANDEE,
                CommandeAchat.Statut.PARTIELLEMENT_RECEPTIONNEE,
            ]
        ).first()
        cls.ligne = LigneAchat.objects.filter(
            commande=cls.commande_brouillon
        ).first()
        cls.reception = ReceptionAchat.objects.first()
        cls.vente = Vente.objects.filter(statut=Vente.Statut.VALIDEE).first()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_TEMPS, ignore_errors=True)

    def setUp(self):
        self.client.force_login(self.admin)

    def verifier(self, nom, args=None):
        url = reverse(nom, args=args)
        response = self.client.get(url, follow=False)
        self.assertEqual(
            response.status_code,
            200,
            f"{nom} ({url}) a répondu {response.status_code} : "
            f"{response.content[:400]!r}",
        )
        return response

    def test_pages_sans_objet(self):
        pages = [
            "utilisateurs:profil",
            "utilisateurs:mot_de_passe",
            "utilisateurs:reinitialiser_mot_de_passe",
            "utilisateurs:reinitialisation_envoyee",
            "utilisateurs:reinitialisation_terminee",
            "utilisateurs:liste",
            "utilisateurs:creer",
            "medicaments:liste",
            "medicaments:creer",
            "medicaments:categories",
            "medicaments:categorie_creer",
            "fournisseurs:liste",
            "fournisseurs:creer",
            "clients:liste",
            "clients:creer",
            "stock:tableau",
            "stock:lots",
            "stock:mouvements",
            "stock:alertes",
            "stock:inventaires",
            "stock:inventaire_creer",
            "achats:liste",
            "achats:creer",
            "achats:receptions",
            "ventes:caisse",
            "ventes:liste",
            "ventes:retours",
            "ventes:paiements",
            "rapports:tableau_bord",
            "rapports:ventes",
            "rapports:achats",
            "rapports:stock",
            "rapports:peremptions",
            "rapports:journal",
            "core:parametres",
            "core:sauvegardes",
        ]
        for nom in pages:
            with self.subTest(page=nom):
                self.verifier(nom)

    def test_pages_avec_objet(self):
        cas = [
            ("utilisateurs:detail", self.admin.pk),
            ("utilisateurs:modifier", self.admin.pk),
            ("medicaments:detail", self.medicament.pk),
            ("medicaments:modifier", self.medicament.pk),
            ("medicaments:supprimer", self.medicament.pk),
            ("medicaments:archiver", self.medicament.pk),
            ("medicaments:categorie_modifier", self.categorie.pk),
            ("medicaments:categorie_supprimer", self.categorie.pk),
            ("fournisseurs:detail", self.fournisseur.pk),
            ("fournisseurs:modifier", self.fournisseur.pk),
            ("clients:detail", self.client_obj.pk),
            ("clients:modifier", self.client_obj.pk),
            ("stock:lot_detail", self.lot.pk),
            ("stock:inventaire_detail", self.inventaire.pk),
            ("achats:detail", self.commande_brouillon.pk),
            ("achats:modifier", self.commande_brouillon.pk),
            ("achats:ajouter_ligne", self.commande_brouillon.pk),
            ("achats:modifier_ligne", self.ligne.pk),
            ("achats:receptionner", self.commande_receptionnable.pk),
            ("achats:reception_detail", self.reception.pk),
            ("ventes:detail", self.vente.pk),
            ("ventes:retour", self.vente.pk),
            ("ventes:annuler", self.vente.pk),
        ]
        for nom, pk in cas:
            with self.subTest(page=nom, pk=pk):
                self.verifier(nom, [pk])

    def test_pdf(self):
        cas = [
            ("rapports:pdf_ventes", None),
            ("rapports:pdf_achats", None),
            ("rapports:pdf_stock", None),
            ("rapports:pdf_peremptions", None),
            ("rapports:recu_vente", self.vente.pk),
            ("rapports:facture_vente", self.vente.pk),
            ("rapports:bon_commande", self.commande_brouillon.pk),
            ("rapports:bon_reception", self.reception.pk),
        ]
        for nom, pk in cas:
            with self.subTest(pdf=nom):
                response = self.verifier(nom, [pk] if pk else None)
                self.assertEqual(
                    response["Content-Type"],
                    "application/pdf",
                    f"{nom} n'a pas renvoyé un PDF.",
                )
                self.assertTrue(response.content.startswith(b"%PDF"))
