"""Tests de l'application rapports : accès, calculs, filtres et PDF."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from achats.models import CommandeAchat, LigneAchat
from achats.services import receptionner_commande, valider_commande
from core.models import JournalAudit, ParametrePharmacie
from fournisseurs.models import Fournisseur
from medicaments.models import Categorie, Medicament
from stock.models import LotStock
from utilisateurs.models import Role, Utilisateur
from ventes.models import Paiement, Vente
from ventes.services import creer_retour, creer_vente


class DonneesRapportsTest(TestCase):
    """Jeu de données minimal commun aux tests."""

    @classmethod
    def setUpTestData(cls):
        cls.role_admin, _ = Role.objects.get_or_create(
            code="ADMIN", defaults={"nom": "Administrateur"}
        )
        cls.role_pharmacien, _ = Role.objects.get_or_create(
            code="PHARMACIEN", defaults={"nom": "Pharmacien"}
        )
        cls.role_caissier, _ = Role.objects.get_or_create(
            code="CAISSIER", defaults={"nom": "Caissier"}
        )
        cls.role_responsable, _ = Role.objects.get_or_create(
            code="RESPONSABLE_GESTION", defaults={"nom": "Responsable de gestion"}
        )
        cls.role_stock, _ = Role.objects.get_or_create(
            code="GESTION_STOCK", defaults={"nom": "Gestionnaire de stock"}
        )

        cls.admin = Utilisateur.objects.create_user(
            username="admin_test", password="motdepasse123", first_name="Alice", last_name="Admin"
        )
        cls.admin.roles.add(cls.role_admin)
        cls.pharmacien = Utilisateur.objects.create_user(
            username="pharma_test",
            password="motdepasse123",
            first_name="Paul",
            last_name="Pharmacien",
        )
        cls.pharmacien.roles.add(cls.role_pharmacien)
        cls.caissier = Utilisateur.objects.create_user(
            username="caisse_test",
            password="motdepasse123",
            first_name="Céline",
            last_name="Caissier",
        )
        cls.caissier.roles.add(cls.role_caissier)
        cls.responsable = Utilisateur.objects.create_user(
            username="gestion_test",
            password="motdepasse123",
            first_name="Rina",
            last_name="Responsable",
        )
        cls.responsable.roles.add(cls.role_responsable)
        cls.gestionnaire_stock = Utilisateur.objects.create_user(
            username="stock_test",
            password="motdepasse123",
            first_name="Sylvain",
            last_name="Stock",
        )
        cls.gestionnaire_stock.roles.add(cls.role_stock)

        parametres = ParametrePharmacie.get_solo()
        parametres.nom = "Pharmacie Test"
        parametres.adresse = "12 rue des Fleurs"
        parametres.telephone = "034 00 000 00"
        parametres.email = "contact@pharmacie-test.mg"
        parametres.numero_fiscal = "NIF-TEST-001"
        parametres.devise = "Ar"
        parametres.seuil_peremption_jours = 30
        parametres.mentions_legales = "Document de test PharmaGest."
        parametres.save()

        cls.categorie = Categorie.objects.create(nom="Antalgiques")
        cls.categorie_autre = Categorie.objects.create(nom="Antibiotiques")

        aujourd_hui = timezone.localdate()

        cls.med_vente = Medicament.objects.create(
            nom="Paracétamol",
            denomination_generique="Paracétamol",
            categorie=cls.categorie,
            forme=Medicament.Forme.COMPRIME,
            dosage="500 mg",
            prix_achat=Decimal("100.00"),
            prix_vente=Decimal("200.00"),
            seuil_alerte=10,
        )
        cls.lot_vente = LotStock.objects.create(
            medicament=cls.med_vente,
            numero_lot="LOT-VENTE",
            date_peremption=aujourd_hui + timedelta(days=365),
            quantite=100,
            quantite_initiale=100,
            prix_achat=Decimal("100.00"),
        )

        cls.med_faible = Medicament.objects.create(
            nom="Amoxicilline",
            categorie=cls.categorie_autre,
            forme=Medicament.Forme.GELULE,
            dosage="1 g",
            prix_achat=Decimal("150.00"),
            prix_vente=Decimal("300.00"),
            seuil_alerte=10,
        )
        LotStock.objects.create(
            medicament=cls.med_faible,
            numero_lot="LOT-FAIBLE",
            date_peremption=aujourd_hui + timedelta(days=120),
            quantite=5,
            quantite_initiale=5,
            prix_achat=Decimal("150.00"),
        )

        cls.med_rupture = Medicament.objects.create(
            nom="Ibuprofène",
            categorie=cls.categorie,
            forme=Medicament.Forme.COMPRIME,
            dosage="400 mg",
            prix_achat=Decimal("80.00"),
            prix_vente=Decimal("150.00"),
            seuil_alerte=10,
        )

        cls.med_peremption = Medicament.objects.create(
            nom="Vitamine C",
            categorie=cls.categorie_autre,
            forme=Medicament.Forme.COMPRIME,
            dosage="1000 mg",
            prix_achat=Decimal("50.00"),
            prix_vente=Decimal("120.00"),
            seuil_alerte=5,
        )
        LotStock.objects.create(
            medicament=cls.med_peremption,
            numero_lot="LOT-PROCHE",
            date_peremption=aujourd_hui + timedelta(days=10),
            quantite=20,
            quantite_initiale=20,
            prix_achat=Decimal("50.00"),
        )
        LotStock.objects.create(
            medicament=cls.med_peremption,
            numero_lot="LOT-PERIME",
            date_peremption=aujourd_hui - timedelta(days=5),
            quantite=3,
            quantite_initiale=3,
            prix_achat=Decimal("50.00"),
        )

        cls.med_archive = Medicament.objects.create(
            nom="Médicament archivé",
            categorie=cls.categorie,
            forme=Medicament.Forme.AUTRE,
            dosage="—",
            prix_achat=Decimal("10.00"),
            prix_vente=Decimal("20.00"),
            seuil_alerte=5,
            statut=Medicament.Statut.ARCHIVE,
        )

        # Vente du jour via le service métier (stock réellement décrémenté).
        cls.vente, _ = creer_vente(
            utilisateur=cls.caissier,
            lignes=[{"lot": cls.lot_vente, "quantite": 2}],
            mode_paiement=Paiement.Mode.ESPECES,
            montant_recu=Decimal("500.00"),
        )
        creer_retour(
            vente=cls.vente,
            lignes=[
                {
                    "ligne_vente": cls.vente.lignes.first(),
                    "quantite": 1,
                    "remise_en_stock": False,
                }
            ],
            utilisateur=cls.caissier,
            motif="Test de retour",
        )

        # Commande et réception du jour.
        cls.fournisseur = Fournisseur.objects.create(
            nom="Fournisseur Test",
            telephone="020 00 000 00",
            email="fournisseur@test.mg",
            numero_fiscal="F-TEST",
        )
        cls.commande = CommandeAchat.objects.create(
            fournisseur=cls.fournisseur, utilisateur=cls.gestionnaire_stock
        )
        cls.ligne_commande = LigneAchat.objects.create(
            commande=cls.commande,
            medicament=cls.med_vente,
            quantite_commandee=10,
            prix_achat_unitaire=Decimal("80.00"),
        )
        valider_commande(cls.commande, cls.gestionnaire_stock)
        cls.reception = receptionner_commande(
            cls.commande,
            [
                {
                    "ligne_achat": cls.ligne_commande,
                    "quantite": 10,
                    "numero_lot": "LOT-RECEPTION",
                    "date_peremption": aujourd_hui + timedelta(days=200),
                    "prix_unitaire": Decimal("80.00"),
                }
            ],
            utilisateur=cls.gestionnaire_stock,
        )
        cls.commande.refresh_from_db()

        JournalAudit.objects.create(
            utilisateur=cls.caissier,
            action=JournalAudit.Action.VENTE,
            module="Ventes",
            objet_id=str(cls.vente.pk),
            description="Vente de test enregistrée",
        )
        JournalAudit.objects.create(
            utilisateur=cls.admin,
            action=JournalAudit.Action.CREATION,
            module="Stock",
            description="Création d'un lot de test",
        )


class TableauBordTests(DonneesRapportsTest):
    def test_tableau_bord_accessible_utilisateur_connecte(self):
        self.client.force_login(self.caissier)
        reponse = self.client.get(reverse("rapports:tableau_bord"))
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Tableau de bord")

    def test_tableau_bord_refuse_anonyme(self):
        reponse = self.client.get(reverse("rapports:tableau_bord"))
        self.assertEqual(reponse.status_code, 302)
        self.assertIn("connexion", reponse.url)

    def test_indicateurs_calcules(self):
        self.client.force_login(self.admin)
        reponse = self.client.get(reverse("rapports:tableau_bord"))
        contexte = reponse.context

        self.assertEqual(contexte["medicaments_actifs"], 4)
        self.assertEqual(contexte["ventes_jour_brut"], Decimal("400.00"))
        self.assertEqual(contexte["ventes_jour_net"], Decimal("200.00"))
        self.assertEqual(contexte["stocks_faibles"], 1)
        self.assertEqual(contexte["ruptures"], 1)
        self.assertEqual(contexte["peremptions_proches"], 1)
        self.assertEqual(contexte["ca_periode"], Decimal("400.00"))
        self.assertEqual(contexte["retours_periode"], Decimal("200.00"))
        self.assertEqual(contexte["ca_periode_net"], Decimal("200.00"))
        self.assertEqual(contexte["encaissements_periode"], Decimal("400.00"))
        self.assertGreaterEqual(len(contexte["top_produits"]), 1)
        self.assertIn("graphique_mensuel", contexte)
        self.assertIn("graphique_categories", contexte)

    def test_blocs_detailles_masques_pour_caissier(self):
        self.client.force_login(self.caissier)
        reponse = self.client.get(reverse("rapports:tableau_bord"))
        self.assertEqual(reponse.status_code, 200)
        self.assertNotContains(reponse, "graphique-mensuel")
        self.assertNotContains(reponse, "Top 5 des produits vendus")

    def test_blocs_detailles_affiches_pour_rapports(self):
        self.client.force_login(self.responsable)
        reponse = self.client.get(reverse("rapports:tableau_bord"))
        self.assertContains(reponse, "graphique-mensuel")
        self.assertContains(reponse, "Top 5 des produits vendus")


class AccesRapportsTests(DonneesRapportsTest):
    def test_rapports_refuses_au_caissier(self):
        self.client.force_login(self.caissier)
        for nom in ("ventes", "achats", "stock", "peremptions", "pdf_ventes", "pdf_stock"):
            with self.subTest(url=nom):
                reponse = self.client.get(reverse(f"rapports:{nom}"))
                self.assertEqual(reponse.status_code, 403)

    def test_journal_reserve_admin(self):
        self.client.force_login(self.caissier)
        self.assertEqual(
            self.client.get(reverse("rapports:journal")).status_code, 403
        )
        self.client.force_login(self.pharmacien)
        self.assertEqual(
            self.client.get(reverse("rapports:journal")).status_code, 403
        )
        self.client.force_login(self.admin)
        reponse = self.client.get(reverse("rapports:journal"))
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Journal d'audit")

    def test_rapports_accessibles_profils_lecture(self):
        for utilisateur in (self.admin, self.pharmacien, self.responsable):
            self.client.force_login(utilisateur)
            for nom in ("ventes", "achats", "stock", "peremptions"):
                with self.subTest(utilisateur=utilisateur.username, url=nom):
                    reponse = self.client.get(reverse(f"rapports:{nom}"))
                    self.assertEqual(reponse.status_code, 200)

    def test_pdf_rapports_autorises_et_interdits(self):
        self.client.force_login(self.responsable)
        for nom in ("pdf_ventes", "pdf_achats", "pdf_stock", "pdf_peremptions"):
            with self.subTest(url=nom):
                reponse = self.client.get(reverse(f"rapports:{nom}"))
                self.assertEqual(reponse.status_code, 200)
                self.assertEqual(reponse["Content-Type"], "application/pdf")

        self.client.force_login(self.gestionnaire_stock)
        self.assertEqual(
            self.client.get(reverse("rapports:pdf_ventes")).status_code, 403
        )


class FiltresRapportsTests(DonneesRapportsTest):
    def test_filtre_periode_ventes(self):
        self.client.force_login(self.admin)
        aujourd_hui = timezone.localdate()
        reponse = self.client.get(
            reverse("rapports:ventes"),
            {
                "debut": (aujourd_hui - timedelta(days=10)).isoformat(),
                "fin": aujourd_hui.isoformat(),
            },
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.context["totaux"]["brut"], Decimal("400.00"))
        self.assertContains(reponse, "Télécharger le PDF")

    def test_filtre_stock_rupture(self):
        self.client.force_login(self.admin)
        reponse = self.client.get(reverse("rapports:stock"), {"etat": "rupture"})
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.context["nb_lignes"], 1)

    def test_filtre_peremptions_horizon(self):
        self.client.force_login(self.admin)
        reponse = self.client.get(reverse("rapports:peremptions"), {"jours": 5})
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(len(reponse.context["proches"]), 0)
        self.assertEqual(len(reponse.context["perimes"]), 1)

        reponse = self.client.get(reverse("rapports:peremptions"), {"jours": 30})
        self.assertEqual(len(reponse.context["proches"]), 1)

    def test_filtre_journal_action_et_recherche(self):
        self.client.force_login(self.admin)
        reponse = self.client.get(reverse("rapports:journal"), {"action": "VENTE"})
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.context["page_obj"].paginator.count, 1)

        reponse = self.client.get(
            reverse("rapports:journal"), {"q": "Création d'un lot"}
        )
        self.assertEqual(reponse.context["page_obj"].paginator.count, 1)


class PdfDocumentsTests(DonneesRapportsTest):
    def _verifier_pdf(self, reponse):
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse["Content-Type"], "application/pdf")
        self.assertIn("attachment;", reponse["Content-Disposition"])
        self.assertIn(".pdf", reponse["Content-Disposition"])
        contenu = reponse.content
        self.assertTrue(contenu.startswith(b"%PDF"))
        self.assertGreater(len(contenu), 1200)
        return contenu

    def test_recu_et_facture_vente(self):
        self.client.force_login(self.caissier)
        recu = self.client.get(
            reverse("rapports:recu_vente", args=[self.vente.pk])
        )
        contenu = self._verifier_pdf(recu)
        self.assertIn(b"Pharmacie Test", contenu)
        self.assertIn(b"400,00", contenu)

        facture = self.client.get(
            reverse("rapports:facture_vente", args=[self.vente.pk])
        )
        contenu_facture = self._verifier_pdf(facture)
        self.assertIn(b"FACTURE", contenu_facture)

    def test_pdf_rapports_ventes_stock_peremptions_achats(self):
        self.client.force_login(self.admin)
        for nom, motif in (
            ("pdf_ventes", b"RAPPORT DES VENTES"),
            ("pdf_stock", b"RAPPORT DE STOCK"),
            ("pdf_peremptions", b"P\xc3\xa9remptions"),
            ("pdf_achats", b"RAPPORT DES ACHATS"),
        ):
            with self.subTest(url=nom):
                reponse = self.client.get(reverse(f"rapports:{nom}"))
                contenu = self._verifier_pdf(reponse)
                self.assertIn(b"Pharmacie Test", contenu)

    def test_pdf_ventes_respecte_filtres(self):
        self.client.force_login(self.admin)
        aujourd_hui = timezone.localdate()
        reponse = self.client.get(
            reverse("rapports:pdf_ventes"),
            {
                "debut": (aujourd_hui - timedelta(days=2)).isoformat(),
                "fin": aujourd_hui.isoformat(),
            },
        )
        self._verifier_pdf(reponse)

    def test_bon_commande_et_bon_reception(self):
        self.client.force_login(self.gestionnaire_stock)
        commande = self.client.get(
            reverse("rapports:bon_commande", args=[self.commande.pk])
        )
        self._verifier_pdf(commande)
        reception = self.client.get(
            reverse("rapports:bon_reception", args=[self.reception.pk])
        )
        self._verifier_pdf(reception)

    def test_bons_achats_refuses_au_caissier(self):
        self.client.force_login(self.caissier)
        self.assertEqual(
            self.client.get(
                reverse("rapports:bon_commande", args=[self.commande.pk])
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                reverse("rapports:bon_reception", args=[self.reception.pk])
            ).status_code,
            403,
        )
