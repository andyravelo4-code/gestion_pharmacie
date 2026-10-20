"""Tests des vues et formulaires des médicaments et catégories."""
import shutil
import tempfile
from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from core.models import JournalAudit
from medicaments.models import Categorie, Medicament
from stock.models import LotStock
from utilisateurs.models import Role, Utilisateur
from utilisateurs.permissions import ADMIN, CAISSIER, PHARMACIEN

MEDIA_TEST_ROOT = tempfile.mkdtemp(prefix="pharmagest-medicaments-tests-")


def creer_utilisateur(nom, code_role):
    role, _ = Role.objects.get_or_create(code=code_role, defaults={"nom": code_role})
    utilisateur = Utilisateur.objects.create(username=nom, first_name=nom.title())
    utilisateur.roles.add(role)
    return utilisateur


def image_test(nom="photo.png"):
    tampon = BytesIO()
    Image.new("RGB", (24, 24), (15, 122, 90)).save(tampon, format="PNG")
    return SimpleUploadedFile(nom, tampon.getvalue(), content_type="image/png")


def donnees_medicament(categorie, **extra):
    donnees = {
        "nom": "Paracétamol",
        "denomination_generique": "Paracétamol",
        "categorie": categorie.pk,
        "forme": Medicament.Forme.COMPRIME,
        "dosage": "500 mg",
        "laboratoire": "Laboratoire Test",
        "code_barres": "3600000000017",
        "prix_achat": "100.00",
        "prix_vente": "150.00",
        "seuil_alerte": "10",
    }
    donnees.update(extra)
    return donnees


class BaseMedicamentsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.categorie = Categorie.objects.create(nom="Antalgiques")
        cls.categorie2 = Categorie.objects.create(nom="Vitamines")
        cls.utilisateur_admin = creer_utilisateur("admin_med", ADMIN)
        cls.utilisateur_pharmacien = creer_utilisateur("pharmacien_med", PHARMACIEN)
        cls.utilisateur_caissier = creer_utilisateur("caissier_med", CAISSIER)


class MedicamentPermissionsTests(BaseMedicamentsTest):
    def test_liste_accessible_au_caissier(self):
        self.client.force_login(self.utilisateur_caissier)
        reponse = self.client.get(reverse("medicaments:liste"))
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Catalogue des médicaments")

    def test_detail_accessible_a_tout_connecte(self):
        medicament = Medicament.objects.create(
            nom="Ibuprofène", categorie=self.categorie, forme=Medicament.Forme.COMPRIME,
            dosage="400 mg", prix_vente=Decimal("200"),
        )
        self.client.force_login(self.utilisateur_caissier)
        reponse = self.client.get(reverse("medicaments:detail", args=[medicament.pk]))
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Ibuprofène")

    def test_anonyme_redirige_vers_connexion(self):
        reponse = self.client.get(reverse("medicaments:liste"))
        self.assertEqual(reponse.status_code, 302)
        self.assertIn(reverse("utilisateurs:connexion"), reponse.url)

    def test_caissier_ne_peut_pas_creer(self):
        self.client.force_login(self.utilisateur_caissier)
        reponse = self.client.get(reverse("medicaments:creer"))
        self.assertEqual(reponse.status_code, 403)
        reponse = self.client.post(
            reverse("medicaments:creer"), donnees_medicament(self.categorie)
        )
        self.assertEqual(reponse.status_code, 403)
        self.assertEqual(Medicament.objects.count(), 0)

    def test_caissier_ne_peut_pas_acceder_aux_categories(self):
        self.client.force_login(self.utilisateur_caissier)
        self.assertEqual(
            self.client.get(reverse("medicaments:categories")).status_code, 403
        )

    def test_pharmacien_autorise(self):
        self.client.force_login(self.utilisateur_pharmacien)
        self.assertEqual(
            self.client.get(reverse("medicaments:creer")).status_code, 200
        )
        self.assertEqual(
            self.client.get(reverse("medicaments:categories")).status_code, 200
        )


@override_settings(MEDIA_ROOT=MEDIA_TEST_ROOT)
class MedicamentCrudTests(BaseMedicamentsTest):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_TEST_ROOT, ignore_errors=True)

    def setUp(self):
        self.client.force_login(self.utilisateur_pharmacien)

    def test_creation_avec_photo(self):
        donnees = donnees_medicament(self.categorie)
        donnees["photo"] = image_test()
        reponse = self.client.post(reverse("medicaments:creer"), donnees)
        medicament = Medicament.objects.get(nom="Paracétamol")
        self.assertRedirects(
            reponse, reverse("medicaments:detail", args=[medicament.pk])
        )
        self.assertTrue(medicament.photo)
        self.assertTrue(medicament.photo.name.startswith("medicaments/"))
        self.assertTrue(
            JournalAudit.objects.filter(
                action=JournalAudit.Action.CREATION, module="Médicaments"
            ).exists()
        )

    def test_code_barres_duplique_refuse(self):
        Medicament.objects.create(
            nom="Premier", categorie=self.categorie, forme=Medicament.Forme.COMPRIME,
            dosage="500 mg", code_barres="DUP-001", prix_vente=Decimal("100"),
        )
        reponse = self.client.post(
            reverse("medicaments:creer"),
            donnees_medicament(self.categorie, nom="Second", code_barres="DUP-001"),
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "déjà utilisé")
        self.assertEqual(Medicament.objects.filter(nom="Second").count(), 0)

    def test_code_barres_vide_normalise_en_null(self):
        donnees = donnees_medicament(self.categorie, code_barres="   ")
        reponse = self.client.post(reverse("medicaments:creer"), donnees)
        self.assertEqual(reponse.status_code, 302)
        medicament = Medicament.objects.get(nom="Paracétamol")
        self.assertIsNone(medicament.code_barres)

    def test_prix_vente_negatif_refuse(self):
        donnees = donnees_medicament(self.categorie, prix_vente="-10")
        reponse = self.client.post(reverse("medicaments:creer"), donnees)
        self.assertEqual(reponse.status_code, 200)
        self.assertIn("prix_vente", reponse.context["form"].errors)
        self.assertEqual(Medicament.objects.count(), 0)

    def test_modification_medicament(self):
        medicament = Medicament.objects.create(
            nom="Ancien nom", categorie=self.categorie, forme=Medicament.Forme.SIROP,
            dosage="100 ml", prix_vente=Decimal("500"),
        )
        donnees = donnees_medicament(
            self.categorie2, nom="Nouveau nom", dosage="125 ml"
        )
        reponse = self.client.post(
            reverse("medicaments:modifier", args=[medicament.pk]), donnees
        )
        self.assertRedirects(
            reponse, reverse("medicaments:detail", args=[medicament.pk])
        )
        medicament.refresh_from_db()
        self.assertEqual(medicament.nom, "Nouveau nom")
        self.assertEqual(medicament.categorie, self.categorie2)
        self.assertTrue(
            JournalAudit.objects.filter(
                action=JournalAudit.Action.MODIFICATION, module="Médicaments"
            ).exists()
        )

    def test_page_confirmation_archivage_si_historique(self):
        medicament = Medicament.objects.create(
            nom="Utilisé", categorie=self.categorie, forme=Medicament.Forme.COMPRIME,
            dosage="500 mg", prix_vente=Decimal("100"),
        )
        LotStock.objects.create(
            medicament=medicament, numero_lot="LOT-1",
            date_peremption=timezone.localdate() + timedelta(days=365), quantite=5,
        )
        reponse = self.client.get(
            reverse("medicaments:supprimer", args=[medicament.pk])
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(reponse.context["historique_sensible"])
        self.assertContains(reponse, "sera <strong>archivé</strong>", html=False)

    def test_archivage_medicament_utilise_au_lieu_de_suppression(self):
        medicament = Medicament.objects.create(
            nom="Utilisé", categorie=self.categorie, forme=Medicament.Forme.COMPRIME,
            dosage="500 mg", prix_vente=Decimal("100"),
        )
        lot = LotStock.objects.create(
            medicament=medicament, numero_lot="LOT-1",
            date_peremption=timezone.localdate() + timedelta(days=365), quantite=5,
        )
        reponse = self.client.post(
            reverse("medicaments:supprimer", args=[medicament.pk]), follow=True
        )
        medicament.refresh_from_db()
        self.assertEqual(medicament.statut, Medicament.Statut.ARCHIVE)
        self.assertTrue(LotStock.objects.filter(pk=lot.pk).exists())
        self.assertContains(reponse, "archivé au lieu d&#x27;être supprimé")
        self.assertTrue(
            JournalAudit.objects.filter(
                action=JournalAudit.Action.ARCHIVAGE, module="Médicaments"
            ).exists()
        )

    def test_suppression_medicament_sans_historique(self):
        medicament = Medicament.objects.create(
            nom="Sans historique", categorie=self.categorie,
            forme=Medicament.Forme.COMPRIME, dosage="100 mg",
            prix_vente=Decimal("50"),
        )
        reponse = self.client.post(
            reverse("medicaments:supprimer", args=[medicament.pk]), follow=True
        )
        self.assertFalse(Medicament.objects.filter(nom="Sans historique").exists())
        self.assertContains(reponse, "a été supprimé")
        self.assertTrue(
            JournalAudit.objects.filter(
                action=JournalAudit.Action.SUPPRESSION, module="Médicaments"
            ).exists()
        )

    def test_action_archiver_puis_reactiver(self):
        medicament = Medicament.objects.create(
            nom="À archiver", categorie=self.categorie, forme=Medicament.Forme.GELULE,
            dosage="250 mg", prix_vente=Decimal("300"),
        )
        reponse = self.client.get(reverse("medicaments:archiver", args=[medicament.pk]))
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Confirmer l'archivage")

        self.client.post(reverse("medicaments:archiver", args=[medicament.pk]))
        medicament.refresh_from_db()
        self.assertEqual(medicament.statut, Medicament.Statut.ARCHIVE)

        self.client.post(reverse("medicaments:archiver", args=[medicament.pk]))
        medicament.refresh_from_db()
        self.assertEqual(medicament.statut, Medicament.Statut.ACTIF)
        self.assertTrue(
            JournalAudit.objects.filter(module="Médicaments").count() >= 2
        )

    def test_recherche_et_filtres_liste(self):
        Medicament.objects.create(
            nom="Doliprane", categorie=self.categorie, forme=Medicament.Forme.COMPRIME,
            dosage="500 mg", code_barres="AAA-1", prix_vente=Decimal("100"),
        )
        Medicament.objects.create(
            nom="Vitamine C", categorie=self.categorie2, forme=Medicament.Forme.COMPRIME,
            dosage="1000 mg", prix_vente=Decimal("200"),
        )
        archive = Medicament.objects.create(
            nom="Ancien produit", categorie=self.categorie,
            forme=Medicament.Forme.AUTRE, dosage="—", prix_vente=Decimal("10"),
            statut=Medicament.Statut.ARCHIVE,
        )

        reponse = self.client.get(reverse("medicaments:liste"), {"q": "dolip"})
        noms = [m.nom for m in reponse.context["medicaments"]]
        self.assertEqual(noms, ["Doliprane"])

        reponse = self.client.get(
            reverse("medicaments:liste"), {"categorie": self.categorie2.pk}
        )
        noms = [m.nom for m in reponse.context["medicaments"]]
        self.assertEqual(noms, ["Vitamine C"])

        reponse = self.client.get(
            reverse("medicaments:liste"), {"statut": Medicament.Statut.ARCHIVE}
        )
        noms = [m.nom for m in reponse.context["medicaments"]]
        self.assertEqual(noms, [archive.nom])

        reponse = self.client.get(reverse("medicaments:liste"), {"alerte": "1"})
        noms = [m.nom for m in reponse.context["medicaments"]]
        self.assertIn("Doliprane", noms)
        self.assertIn("Vitamine C", noms)
        self.assertNotIn(archive.nom, noms)

    def test_tri_par_prix(self):
        Medicament.objects.create(
            nom="B", categorie=self.categorie, forme=Medicament.Forme.COMPRIME,
            dosage="1", prix_vente=Decimal("200"),
        )
        Medicament.objects.create(
            nom="A", categorie=self.categorie, forme=Medicament.Forme.COMPRIME,
            dosage="1", prix_vente=Decimal("100"),
        )
        reponse = self.client.get(reverse("medicaments:liste"), {"tri": "prix_vente"})
        prix = [m.prix_vente for m in reponse.context["medicaments"]]
        self.assertEqual(prix, sorted(prix))


class CategorieTests(BaseMedicamentsTest):
    def setUp(self):
        self.client.force_login(self.utilisateur_pharmacien)

    def test_liste_categories_et_recherche(self):
        Categorie.objects.create(nom="Antibiotiques")
        reponse = self.client.get(reverse("medicaments:categories"), {"q": "anti"})
        noms = [c.nom for c in reponse.context["categories"]]
        self.assertEqual(noms, ["Antibiotiques"])

    def test_creation_categorie(self):
        reponse = self.client.post(
            reverse("medicaments:categorie_creer"),
            {"nom": "Dermatologie", "description": "Soins de la peau"},
        )
        self.assertRedirects(reponse, reverse("medicaments:categories"))
        self.assertTrue(Categorie.objects.filter(nom="Dermatologie").exists())
        self.assertTrue(
            JournalAudit.objects.filter(
                action=JournalAudit.Action.CREATION, module="Catégories"
            ).exists()
        )

    def test_nom_categorie_duplique_refuse(self):
        reponse = self.client.post(
            reverse("medicaments:categorie_creer"),
            {"nom": self.categorie.nom, "description": ""},
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "porte déjà ce nom")
        self.assertEqual(Categorie.objects.filter(nom="Antalgiques").count(), 1)

    def test_modification_categorie(self):
        reponse = self.client.post(
            reverse("medicaments:categorie_modifier", args=[self.categorie.pk]),
            {"nom": "Douleur", "description": "Antalgiques"},
        )
        self.assertRedirects(reponse, reverse("medicaments:categories"))
        self.categorie.refresh_from_db()
        self.assertEqual(self.categorie.nom, "Douleur")

    def test_protection_categorie_utilisee(self):
        Medicament.objects.create(
            nom="Produit lié", categorie=self.categorie,
            forme=Medicament.Forme.COMPRIME, dosage="500 mg",
            prix_vente=Decimal("100"),
        )
        reponse = self.client.get(
            reverse("medicaments:categorie_supprimer", args=[self.categorie.pk])
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(reponse.context["suppression_possible"])
        self.assertContains(reponse, "Suppression impossible")

        reponse = self.client.post(
            reverse("medicaments:categorie_supprimer", args=[self.categorie.pk]),
            follow=True,
        )
        self.assertTrue(Categorie.objects.filter(pk=self.categorie.pk).exists())
        self.assertContains(reponse, "ne peut pas être supprimée")

    def test_suppression_categorie_non_utilisee(self):
        categorie = Categorie.objects.create(nom="Sans médicament")
        reponse = self.client.post(
            reverse("medicaments:categorie_supprimer", args=[categorie.pk]),
            follow=True,
        )
        self.assertFalse(Categorie.objects.filter(pk=categorie.pk).exists())
        self.assertContains(reponse, "a été supprimée")
