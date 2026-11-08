"""Tests des règles de vente, FEFO, idempotence, retours et permissions."""
import uuid
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from medicaments.models import Categorie, Medicament
from stock.models import LotStock, MouvementStock
from stock.services import receptionner_lot
from utilisateurs.models import Role, Utilisateur
from ventes.models import LigneVente, Paiement, RetourVente, Vente
from ventes.panier import detail_panier
from ventes.services import annuler_vente, creer_retour, creer_vente

MDP = "MotDePasseTest2026!"


def creer_role(code):
    role, _ = Role.objects.get_or_create(code=code, defaults={"nom": code, "ordre": 10})
    return role


def creer_utilisateur(username, code_role):
    user = Utilisateur.objects.create_user(username=username, password=MDP, email=f"{username}@test.mg")
    user.roles.add(creer_role(code_role))
    return user


class BaseVenteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.caissier = creer_utilisateur("caissier", "CAISSIER")
        cls.pharmacien = creer_utilisateur("pharmacien", "PHARMACIEN")
        cls.sans_role = Utilisateur.objects.create_user(username="sansrole", password=MDP)
        cls.categorie = Categorie.objects.create(nom="Antalgiques")
        cls.medicament = Medicament.objects.create(
            nom="Paracétamol",
            denomination_generique="Paracétamol",
            categorie=cls.categorie,
            forme="Comprimé",
            dosage="500 mg",
            prix_achat=Decimal("100"),
            prix_vente=Decimal("250"),
            seuil_alerte=5,
        )

    def creer_lot(self, numero, jours, quantite, medicament=None, prix=Decimal("100")):
        return receptionner_lot(
            medicament=medicament or self.medicament,
            numero_lot=numero,
            date_peremption=timezone.localdate() + timedelta(days=jours),
            quantite=quantite,
            prix_achat=prix,
            utilisateur=self.pharmacien,
        )

    def vendre(self, lot, quantite, utilisateur=None, **kwargs):
        return creer_vente(
            utilisateur=utilisateur or self.caissier,
            lignes=[{"lot": lot, "quantite": quantite}],
            **kwargs,
        )


class VenteServiceTests(BaseVenteTests):
    def test_vente_diminue_stock_et_cree_un_seul_mouvement(self):
        lot = self.creer_lot("LOT-A", 20, 10)
        vente, creee = self.vendre(lot, 3)
        self.assertTrue(creee)
        lot.refresh_from_db()
        self.assertEqual(lot.quantite, 7)
        self.assertEqual(vente.lignes.count(), 1)
        self.assertEqual(vente.montant_total, Decimal("750.00"))
        self.assertEqual(
            MouvementStock.objects.filter(
                reference=vente.numero, type_mouvement=MouvementStock.Type.SORTIE
            ).count(),
            1,
        )
        mouvement = MouvementStock.objects.get(reference=vente.numero)
        self.assertEqual(mouvement.quantite, -3)
        paiement = vente.paiements.get()
        self.assertEqual(paiement.statut, Paiement.Statut.CONFIRME)

    def test_quantite_negative_refusee(self):
        lot = self.creer_lot("LOT-B", 20, 10)
        with self.assertRaises(Exception):
            self.vendre(lot, -2)
        self.assertFalse(Vente.objects.exists())

    def test_stock_insuffisant_refuse_sans_modification(self):
        lot = self.creer_lot("LOT-C", 20, 2)
        with self.assertRaises(Exception):
            self.vendre(lot, 3)
        lot.refresh_from_db()
        self.assertEqual(lot.quantite, 2)
        self.assertFalse(Vente.objects.exists())

    def test_lot_perime_refuse(self):
        lot = self.creer_lot("LOT-D", -5, 10)
        with self.assertRaises(Exception):
            self.vendre(lot, 1)
        self.assertFalse(Vente.objects.exists())
        lot.refresh_from_db()
        self.assertEqual(lot.quantite, 10)

    def test_lot_bloque_refuse(self):
        lot = self.creer_lot("LOT-E", 20, 10)
        lot.bloquer("Contrôle qualité")
        with self.assertRaises(Exception):
            self.vendre(lot, 1)
        lot.refresh_from_db()
        self.assertEqual(lot.quantite, 10)

    def test_prix_applique_est_fige(self):
        lot = self.creer_lot("LOT-F", 20, 10)
        vente, _ = self.vendre(lot, 2)
        self.medicament.prix_vente = Decimal("999")
        self.medicament.save(update_fields=["prix_vente"])
        vente.refresh_from_db()
        self.assertEqual(vente.lignes.get().prix_unitaire, Decimal("250"))
        self.assertEqual(vente.montant_total, Decimal("500.00"))

    def test_cle_idempotence_evite_double_vente(self):
        lot = self.creer_lot("LOT-G", 20, 10)
        cle = uuid.uuid4()
        vente1, creee1 = self.vendre(lot, 2, cle_idempotence=cle)
        vente2, creee2 = self.vendre(lot, 2, cle_idempotence=cle)
        self.assertTrue(creee1)
        self.assertFalse(creee2)
        self.assertEqual(vente1.pk, vente2.pk)
        lot.refresh_from_db()
        self.assertEqual(lot.quantite, 8)
        self.assertEqual(Vente.objects.count(), 1)
        self.assertEqual(MouvementStock.objects.filter(type_mouvement=MouvementStock.Type.SORTIE).count(), 1)

    def test_paiement_electronique_exige_reference_et_confirmation(self):
        lot = self.creer_lot("LOT-H", 20, 10)
        with self.assertRaises(Exception):
            self.vendre(lot, 1, mode_paiement=Paiement.Mode.MOBILE_MONEY)
        self.assertFalse(Vente.objects.exists())
        vente, _ = self.vendre(
            lot,
            1,
            mode_paiement=Paiement.Mode.MOBILE_MONEY,
            reference_paiement="MM-12345",
            paiement_confirme=True,
        )
        self.assertEqual(vente.paiements.get().statut, Paiement.Statut.CONFIRME)

    def test_especes_insuffisantes_refusees(self):
        lot = self.creer_lot("LOT-I", 20, 10)
        with self.assertRaises(Exception):
            self.vendre(lot, 2, montant_recu=Decimal("100"))
        lot.refresh_from_db()
        self.assertEqual(lot.quantite, 10)

    def test_medicament_archive_non_vendable(self):
        lot = self.creer_lot("LOT-J", 20, 10)
        self.medicament.archiver()
        with self.assertRaises(Exception):
            self.vendre(lot, 1)


class RetourTests(BaseVenteTests):
    def test_retour_partiel_remet_en_stock_et_trace(self):
        lot = self.creer_lot("LOT-R1", 20, 10)
        vente, _ = self.vendre(lot, 3)
        ligne = vente.lignes.get()
        retour = creer_retour(
            vente=vente,
            lignes=[{"ligne_vente": ligne, "quantite": 2, "remise_en_stock": True}],
            utilisateur=self.pharmacien,
            motif="Erreur de délivrance",
        )
        lot.refresh_from_db()
        self.assertEqual(lot.quantite, 9)  # 10 - 3 + 2
        self.assertEqual(retour.montant_rembourse, Decimal("500.00"))
        self.assertEqual(retour.lignes.count(), 1)
        self.assertTrue(
            MouvementStock.objects.filter(
                type_mouvement=MouvementStock.Type.RETOUR, reference=retour.numero, quantite=2
            ).exists()
        )
        vente.refresh_from_db()
        self.assertEqual(vente.statut, Vente.Statut.VALIDEE)
        self.assertEqual(ligne.quantite_retournable, 1)

    def test_retour_complet_annule_la_vente_sans_la_supprimer(self):
        lot = self.creer_lot("LOT-R2", 20, 10)
        vente, _ = self.vendre(lot, 2)
        creer_retour(
            vente=vente,
            lignes=[{"ligne_vente": vente.lignes.get(), "quantite": 2, "remise_en_stock": True}],
            utilisateur=self.pharmacien,
            motif="Retour complet",
        )
        vente.refresh_from_db()
        self.assertEqual(vente.statut, Vente.Statut.ANNULEE)
        self.assertTrue(Vente.objects.filter(pk=vente.pk).exists())
        lot.refresh_from_db()
        self.assertEqual(lot.quantite, 10)

    def test_quantite_retour_superieure_refusee(self):
        lot = self.creer_lot("LOT-R3", 20, 10)
        vente, _ = self.vendre(lot, 2)
        with self.assertRaises(Exception):
            creer_retour(
                vente=vente,
                lignes=[{"ligne_vente": vente.lignes.get(), "quantite": 3, "remise_en_stock": True}],
                utilisateur=self.pharmacien,
                motif="Trop",
            )
        lot.refresh_from_db()
        self.assertEqual(lot.quantite, 8)

    def test_lot_perime_non_remis_en_stock(self):
        lot = self.creer_lot("LOT-R4", 20, 10)
        vente, _ = self.vendre(lot, 2)
        lot.date_peremption = timezone.localdate() - timedelta(days=1)
        lot.save(update_fields=["date_peremption"])
        with self.assertRaises(Exception):
            creer_retour(
                vente=vente,
                lignes=[{"ligne_vente": vente.lignes.get(), "quantite": 1, "remise_en_stock": True}],
                utilisateur=self.pharmacien,
                motif="Périmé",
            )

    def test_retour_sans_remise_en_stock_ne_modifie_pas_le_stock(self):
        lot = self.creer_lot("LOT-R5", 20, 10)
        vente, _ = self.vendre(lot, 2)
        creer_retour(
            vente=vente,
            lignes=[{"ligne_vente": vente.lignes.get(), "quantite": 1, "remise_en_stock": False}],
            utilisateur=self.pharmacien,
            motif="Produit non conforme",
        )
        lot.refresh_from_db()
        self.assertEqual(lot.quantite, 8)
        self.assertFalse(
            MouvementStock.objects.filter(type_mouvement=MouvementStock.Type.RETOUR).exists()
        )

    def test_annulation_par_operation_compensatoire(self):
        lot = self.creer_lot("LOT-R6", 20, 10)
        vente, _ = self.vendre(lot, 4)
        retour = annuler_vente(
            vente=vente, utilisateur=self.pharmacien, motif="Annulation", remise_en_stock=True
        )
        self.assertEqual(retour.type_retour, RetourVente.Type.ANNULATION)
        vente.refresh_from_db()
        lot.refresh_from_db()
        self.assertEqual(vente.statut, Vente.Statut.ANNULEE)
        self.assertEqual(lot.quantite, 10)
        self.assertEqual(Vente.objects.count(), 1)

    def test_motif_obligatoire(self):
        lot = self.creer_lot("LOT-R7", 20, 10)
        vente, _ = self.vendre(lot, 1)
        with self.assertRaises(Exception):
            creer_retour(
                vente=vente,
                lignes=[{"ligne_vente": vente.lignes.get(), "quantite": 1, "remise_en_stock": True}],
                utilisateur=self.pharmacien,
                motif="   ",
            )


class PanierTests(BaseVenteTests):
    def test_panier_recalcule_le_prix_cote_serveur(self):
        lot = self.creer_lot("LOT-P1", 20, 10)
        session = self.client.session
        session["pharmagest_panier"] = {str(lot.pk): 2}
        session.save()
        self.client.force_login(self.caissier)
        self.medicament.prix_vente = Decimal("300")
        self.medicament.save(update_fields=["prix_vente"])
        request = self.client.get(reverse("ventes:caisse")).wsgi_request
        detail = detail_panier(request)
        self.assertEqual(detail["total"], Decimal("600.00"))

    def test_panier_signale_stock_insuffisant(self):
        lot = self.creer_lot("LOT-P2", 20, 2)
        session = self.client.session
        session["pharmagest_panier"] = {str(lot.pk): 5}
        session.save()
        self.client.force_login(self.caissier)
        request = self.client.get(reverse("ventes:caisse")).wsgi_request
        detail = detail_panier(request)
        self.assertTrue(detail["erreurs"])

    def test_ajout_fefo_repartit_sur_les_lots_les_plus_proches(self):
        lot_tard = self.creer_lot("LOT-FEFO-TARD", 200, 10)
        lot_proche = self.creer_lot("LOT-FEFO-PROCHE", 10, 2)
        self.client.force_login(self.caissier)
        reponse = self.client.post(
            reverse("ventes:panier_ajouter"),
            {"medicament": self.medicament.pk, "quantite": 5},
        )
        self.assertEqual(reponse.status_code, 302)
        panier = self.client.session.get("pharmagest_panier")
        self.assertEqual(panier[str(lot_proche.pk)], 2)
        self.assertEqual(panier[str(lot_tard.pk)], 3)


class VenteVuesTests(BaseVenteTests):
    def test_caisse_accessible_au_caissier(self):
        self.client.force_login(self.caissier)
        reponse = self.client.get(reverse("ventes:caisse"))
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Caisse")

    def test_caisse_interdite_sans_role(self):
        self.client.force_login(self.sans_role)
        self.assertEqual(self.client.get(reverse("ventes:caisse")).status_code, 403)

    def test_validation_vente_depuis_la_caisse(self):
        lot = self.creer_lot("LOT-V1", 20, 10)
        self.client.force_login(self.caissier)
        session = self.client.session
        session["pharmagest_panier"] = {str(lot.pk): 2}
        session.save()
        reponse = self.client.post(
            reverse("ventes:valider"),
            {
                "client": "",
                "mode_paiement": "ESPECES",
                "montant_recu": "600",
                "reference_paiement": "",
                "notes": "",
                "cle_idempotence": str(uuid.uuid4()),
            },
        )
        vente = Vente.objects.get()
        self.assertRedirects(reponse, f"{vente.get_absolute_url()}?nouvelle=1")
        lot.refresh_from_db()
        self.assertEqual(lot.quantite, 8)
        self.assertIn(self.client.session.get("pharmagest_panier"), (None, {}))

    def test_double_clic_ne_cree_pas_deux_ventes(self):
        lot = self.creer_lot("LOT-V2", 20, 10)
        self.client.force_login(self.caissier)
        session = self.client.session
        session["pharmagest_panier"] = {str(lot.pk): 1}
        session.save()
        donnees = {
            "mode_paiement": "ESPECES",
            "montant_recu": "250",
            "cle_idempotence": str(uuid.uuid4()),
        }
        self.client.post(reverse("ventes:valider"), donnees)
        self.client.post(reverse("ventes:valider"), donnees)
        self.assertEqual(Vente.objects.count(), 1)
        lot.refresh_from_db()
        self.assertEqual(lot.quantite, 9)

    def test_annulation_interdite_au_caissier(self):
        lot = self.creer_lot("LOT-V3", 20, 10)
        vente, _ = self.vendre(lot, 1)
        self.client.force_login(self.caissier)
        reponse = self.client.get(reverse("ventes:annuler", args=[vente.pk]))
        self.assertEqual(reponse.status_code, 403)
        self.client.force_login(self.pharmacien)
        self.assertEqual(self.client.get(reverse("ventes:annuler", args=[vente.pk])).status_code, 200)

    def test_retour_interdit_sans_role(self):
        lot = self.creer_lot("LOT-V4", 20, 10)
        vente, _ = self.vendre(lot, 1)
        self.client.force_login(self.sans_role)
        self.assertEqual(self.client.get(reverse("ventes:retour", args=[vente.pk])).status_code, 403)

    def test_detail_vente_affiche_les_prix_historiques(self):
        lot = self.creer_lot("LOT-V5", 20, 10)
        vente, _ = self.vendre(lot, 2)
        self.medicament.prix_vente = Decimal("999")
        self.medicament.save(update_fields=["prix_vente"])
        self.client.force_login(self.pharmacien)
        reponse = self.client.get(reverse("ventes:detail", args=[vente.pk]))
        self.assertContains(reponse, "250,00")
        self.assertNotContains(reponse, "999,00")
