"""Jeu de données fictives pour découvrir et tester PharmaGest.

La commande crée des données réalistes en passant par les modèles et les
services métier (stock, achats, ventes). Elle ne doit jamais être exécutée sur
une base contenant de vraies données sans le drapeau explicite
``--reinitialiser``.

Exemples :
    .venv/bin/python manage.py donnees_demo
    .venv/bin/python manage.py donnees_demo --reinitialiser
"""
from __future__ import annotations

import random
import textwrap
from datetime import datetime, time, timedelta
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageColor, ImageDraw, ImageFont

from achats.models import CommandeAchat, LigneAchat, LigneReception, ReceptionAchat
from achats.services import receptionner_commande, valider_commande
from clients.models import Client
from core.models import ParametrePharmacie
from fournisseurs.models import Fournisseur
from medicaments.models import Categorie, Medicament
from stock.models import Inventaire, LigneInventaire, LotStock, MouvementStock
from stock.services import creer_inventaire, receptionner_lot
from utilisateurs.models import Role, Utilisateur
from ventes.models import LigneVente, Paiement, RetourVente, Vente
from ventes.services import (
    annuler_vente,
    creer_retour,
    creer_vente,
    lots_fefo,
)

MOT_DE_PASSE = "PharmaGest2026!"
GRAINE = 20261117
NB_VENTES = 30

ROLES = [
    ("ADMIN", "Administrateur", "Gère les utilisateurs, les paramètres et toutes les opérations.", 10),
    ("PHARMACIEN", "Pharmacien responsable", "Contrôle les médicaments, lots, achats et ventes.", 20),
    ("GESTION_STOCK", "Gestionnaire de stock", "Gère fournisseurs, commandes, réceptions et inventaires.", 30),
    ("CAISSIER", "Caissier", "Enregistre les ventes, paiements et imprime les reçus.", 40),
    ("RESPONSABLE_GESTION", "Responsable de gestion", "Consulte statistiques, recettes et rapports.", 50),
]

UTILISATEURS = [
    {
        "username": "admin",
        "prenom": "Andrianina",
        "nom": "Rakotomalala",
        "email": "admin@pharmagest.mg",
        "telephone": "+261 34 00 000 01",
        "adresse": "Analakely, Antananarivo",
        "role": "ADMIN",
        "superuser": True,
    },
    {
        "username": "pharmacien",
        "prenom": "Fanja",
        "nom": "Razafindrakoto",
        "email": "pharmacien@pharmagest.mg",
        "telephone": "+261 34 00 000 02",
        "adresse": "Ambohipo, Antananarivo",
        "role": "PHARMACIEN",
        "superuser": False,
    },
    {
        "username": "stock",
        "prenom": "Hery",
        "nom": "Andriamihaja",
        "email": "stock@pharmagest.mg",
        "telephone": "+261 34 00 000 03",
        "adresse": "Ankadifotsy, Antananarivo",
        "role": "GESTION_STOCK",
        "superuser": False,
    },
    {
        "username": "caissier",
        "prenom": "Miora",
        "nom": "Rakotobe",
        "email": "caissier@pharmagest.mg",
        "telephone": "+261 34 00 000 04",
        "adresse": "Isotry, Antananarivo",
        "role": "CAISSIER",
        "superuser": False,
    },
    {
        "username": "gestion",
        "prenom": "Tojo",
        "nom": "Ramaroson",
        "email": "gestion@pharmagest.mg",
        "telephone": "+261 34 00 000 05",
        "adresse": "Ivandry, Antananarivo",
        "role": "RESPONSABLE_GESTION",
        "superuser": False,
    },
]

CATEGORIES = [
    ("Antalgiques", "Médicaments contre la douleur et la fièvre."),
    ("Antibiotiques", "Anti-infectieux bactériens sur prescription."),
    ("Anti-inflammatoires", "Médicaments contre l'inflammation et la douleur."),
    ("Vitamines", "Compléments vitaminiques et minéraux."),
    ("Antiseptiques", "Désinfection de la peau et des plaies."),
    ("Gastro-entérologie", "Troubles digestifs, acidité et vomissements."),
]

# 20 médicaments réalistes (prix indicatifs en ariary, données fictives).
MEDICAMENTS = [
    {
        "cle": "doliprane_500", "nom": "Doliprane", "dci": "Paracétamol",
        "categorie": "Antalgiques", "forme": "Comprimé", "dosage": "500 mg",
        "laboratoire": "Sanofi", "prix_achat": "350.00", "prix_vente": "700.00",
        "seuil": 15,
    },
    {
        "cle": "efferalgan_1g", "nom": "Efferalgan", "dci": "Paracétamol",
        "categorie": "Antalgiques", "forme": "Comprimé", "dosage": "1 g",
        "laboratoire": "UPSA", "prix_achat": "520.00", "prix_vente": "1000.00",
        "seuil": 12,
    },
    {
        "cle": "paracetamol_sirop", "nom": "Paracétamol pédiatrique", "dci": "Paracétamol",
        "categorie": "Antalgiques", "forme": "Sirop", "dosage": "120 mg/5 ml",
        "laboratoire": "Biopharma", "prix_achat": "900.00", "prix_vente": "1600.00",
        "seuil": 10,
    },
    {
        "cle": "doliprane_suppo", "nom": "Doliprane nourrisson", "dci": "Paracétamol",
        "categorie": "Antalgiques", "forme": "Suppositoire", "dosage": "150 mg",
        "laboratoire": "Sanofi", "prix_achat": "420.00", "prix_vente": "850.00",
        "seuil": 10,
    },
    {
        "cle": "augmentin_1g", "nom": "Augmentin", "dci": "Amoxicilline + acide clavulanique",
        "categorie": "Antibiotiques", "forme": "Comprimé", "dosage": "1 g",
        "laboratoire": "GSK", "prix_achat": "2200.00", "prix_vente": "3800.00",
        "seuil": 8,
    },
    {
        "cle": "amoxicilline_500", "nom": "Amoxicilline", "dci": "Amoxicilline",
        "categorie": "Antibiotiques", "forme": "Gélule", "dosage": "500 mg",
        "laboratoire": "Biopharma", "prix_achat": "250.00", "prix_vente": "500.00",
        "seuil": 15,
    },
    {
        "cle": "azithromycine_250", "nom": "Azithromycine", "dci": "Azithromycine",
        "categorie": "Antibiotiques", "forme": "Comprimé", "dosage": "250 mg",
        "laboratoire": "Pfizer", "prix_achat": "950.00", "prix_vente": "1700.00",
        "seuil": 6,
    },
    {
        "cle": "ciprofloxacine_500", "nom": "Ciprofloxacine", "dci": "Ciprofloxacine",
        "categorie": "Antibiotiques", "forme": "Comprimé", "dosage": "500 mg",
        "laboratoire": "Bayer", "prix_achat": "600.00", "prix_vente": "1200.00",
        "seuil": 8,
    },
    {
        "cle": "ibuprofene_400", "nom": "Ibuprofène", "dci": "Ibuprofène",
        "categorie": "Anti-inflammatoires", "forme": "Comprimé", "dosage": "400 mg",
        "laboratoire": "Mylan", "prix_achat": "400.00", "prix_vente": "800.00",
        "seuil": 12,
    },
    {
        "cle": "diclofenac_50", "nom": "Diclofénac", "dci": "Diclofénac sodique",
        "categorie": "Anti-inflammatoires", "forme": "Comprimé", "dosage": "50 mg",
        "laboratoire": "Novartis", "prix_achat": "320.00", "prix_vente": "650.00",
        "seuil": 10,
    },
    {
        "cle": "diclofenac_injectable", "nom": "Diclofénac injectable", "dci": "Diclofénac sodique",
        "categorie": "Anti-inflammatoires", "forme": "Injectable", "dosage": "75 mg/3 ml",
        "laboratoire": "Novartis", "prix_achat": "700.00", "prix_vente": "1500.00",
        "seuil": 5, "archive": True,
    },
    {
        "cle": "voltarene_emulgel", "nom": "Voltarène Emulgel", "dci": "Diclofénac diéthylamine",
        "categorie": "Anti-inflammatoires", "forme": "Crème", "dosage": "1 % — tube 50 g",
        "laboratoire": "Novartis", "prix_achat": "900.00", "prix_vente": "1900.00",
        "seuil": 6,
    },
    {
        "cle": "vitamine_c_500", "nom": "Vitamine C", "dci": "Acide ascorbique",
        "categorie": "Vitamines", "forme": "Comprimé", "dosage": "500 mg",
        "laboratoire": "Roche", "prix_achat": "150.00", "prix_vente": "350.00",
        "seuil": 15,
    },
    {
        "cle": "vitamine_b", "nom": "Vitamine B complexe", "dci": "Complexe vitaminique B",
        "categorie": "Vitamines", "forme": "Comprimé", "dosage": "B1-B6-B12",
        "laboratoire": "Sopharma", "prix_achat": "220.00", "prix_vente": "480.00",
        "seuil": 8,
    },
    {
        "cle": "betadine_10", "nom": "Bétadine dermique", "dci": "Povidone iodée",
        "categorie": "Antiseptiques", "forme": "Autre", "dosage": "10 % — flacon 125 ml",
        "laboratoire": "Meda Pharma", "prix_achat": "650.00", "prix_vente": "1300.00",
        "seuil": 10,
    },
    {
        "cle": "alcool_70", "nom": "Alcool éthylique", "dci": "Éthanol",
        "categorie": "Antiseptiques", "forme": "Autre", "dosage": "70° — flacon 500 ml",
        "laboratoire": "SOMAPHARM", "prix_achat": "250.00", "prix_vente": "600.00",
        "seuil": 12,
    },
    {
        "cle": "neomycine_pommade", "nom": "Néomycine pommade", "dci": "Néomycine",
        "categorie": "Antiseptiques", "forme": "Pommade", "dosage": "0,5 % — tube 30 g",
        "laboratoire": "Biogaran", "prix_achat": "380.00", "prix_vente": "850.00",
        "seuil": 8, "archive": True,
    },
    {
        "cle": "omeprazole_20", "nom": "Oméprazole", "dci": "Oméprazole",
        "categorie": "Gastro-entérologie", "forme": "Gélule", "dosage": "20 mg",
        "laboratoire": "AstraZeneca", "prix_achat": "480.00", "prix_vente": "1000.00",
        "seuil": 10,
    },
    {
        "cle": "smecta_3g", "nom": "Smecta", "dci": "Diosmectite",
        "categorie": "Gastro-entérologie", "forme": "Autre", "dosage": "3 g — sachet",
        "laboratoire": "Ipsen", "prix_achat": "300.00", "prix_vente": "650.00",
        "seuil": 8,
    },
    {
        "cle": "vogalene_15", "nom": "Vogalène", "dci": "Métopimazine",
        "categorie": "Gastro-entérologie", "forme": "Comprimé", "dosage": "15 mg",
        "laboratoire": "Teofarma", "prix_achat": "450.00", "prix_vente": "950.00",
        "seuil": 6, "archive": True,
    },
]

FOURNISSEURS = [
    {
        "nom": "SOAMADI Distribution",
        "adresse": "Lot II B 45, Ankorondrano, Antananarivo 101",
        "telephone": "+261 20 22 456 78",
        "email": "commandes@soamadi.mg",
        "numero_fiscal": "NIF 123 456 789",
        "contact_principal": "M. Rakotondrabe",
    },
    {
        "nom": "Laborex Madagascar",
        "adresse": "Zone Galaxy Andraharo, Antananarivo 101",
        "telephone": "+261 20 23 567 89",
        "email": "commandes@laborex.mg",
        "numero_fiscal": "NIF 234 567 890",
        "contact_principal": "Mme Rasoanaivo",
    },
    {
        "nom": "Office Pharmaceutique Malgache",
        "adresse": "Antsakaviro, Antananarivo 101",
        "telephone": "+261 20 22 678 90",
        "email": "ventes@opm.mg",
        "numero_fiscal": "NIF 345 678 901",
        "contact_principal": "Dr Andrianarisoa",
    },
]

CLIENTS = [
    {
        "nom": "Rakoto Jean",
        "telephone": "+261 34 12 345 67",
        "email": "jean.rakoto@example.mg",
        "adresse": "Analakely, Antananarivo",
        "notes": "Client fidèle — ordonnances chroniques.",
    },
    {
        "nom": "Rasoa Marie",
        "telephone": "+261 33 23 456 78",
        "email": "marie.rasoa@example.mg",
        "adresse": "Isotry, Antananarivo",
        "notes": "Préfère être contactée par téléphone.",
    },
    {
        "nom": "Cabinet médical Espoir",
        "telephone": "+261 20 22 111 22",
        "email": "contact@cabinet-espoir.mg",
        "adresse": "Ambohijatovo, Antananarivo",
        "notes": "Compte professionnel — factures mensuelles.",
    },
    {
        "nom": "Hery Randriamampionona",
        "telephone": "+261 32 34 567 89",
        "email": "hery.randria@example.mg",
        "adresse": "Ankadifotsy, Antananarivo",
        "notes": "",
    },
]

COULEURS_PHOTOS = [
    ("#0B6E4F", "#FFFFFF"),
    ("#1D4E89", "#FFFFFF"),
    ("#7A3E9D", "#FFFFFF"),
    ("#A63D40", "#FFFFFF"),
    ("#B5651D", "#FFFFFF"),
    ("#2A6F97", "#FFFFFF"),
    ("#3D5A40", "#FFFFFF"),
    ("#6B4E71", "#FFFFFF"),
    ("#8A5A44", "#FFFFFF"),
    ("#204E5B", "#FFFFFF"),
]

# Clés de médicaments utilisées pour scénariser les lots et les alertes.
SANS_LOT = {"azithromycine_250", "ciprofloxacine_500"}
STOCK_FAIBLE = {"vitamine_b", "doliprane_suppo"}
PEREMPTION_PROCHE = {
    "doliprane_500": 12,
    "ibuprofene_400": 21,
    "omeprazole_20": 27,
}
LOTS_PERIMES = {
    "amoxicilline_500": 20,
    "betadine_10": 45,
}


def _heure(jour, heure=10, minute=0):
    return timezone.make_aware(datetime.combine(jour, time(heure, minute)))


def _melange(couleur_a: str, couleur_b: str, proportion: float) -> tuple[int, int, int]:
    a = ImageColor.getrgb(couleur_a)
    b = ImageColor.getrgb(couleur_b)
    return tuple(int(a[i] + (b[i] - a[i]) * proportion) for i in range(3))


def _police(taille: int):
    chemins = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    ]
    for chemin in chemins:
        if Path(chemin).is_file():
            try:
                return ImageFont.truetype(chemin, taille)
            except OSError:
                continue
    try:
        return ImageFont.load_default(size=taille)
    except TypeError:  # Pillow ancien
        return ImageFont.load_default()


class Command(BaseCommand):
    help = (
        "Crée un jeu de données de démonstration fictif (utilisateurs, "
        "médicaments, lots, achats, ventes, retours, inventaire)."
    )
    # Cette commande ne dépend pas du routage : elle doit rester utilisable même
    # pendant que l'interface web est en cours de modification.
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument(
            "--reinitialiser",
            action="store_true",
            help=(
                "Vide la base (flush --noinput) avant de recréer les données de "
                "démonstration. À n'utiliser que sur une base de développement."
            ),
        )

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------
    def handle(self, *args, **options):
        self.hasard = random.Random(GRAINE)
        self.utilisateurs = {}
        self.medicaments = {}
        self.fournisseurs = []
        self.clients = []
        self.ventes = []

        if options["reinitialiser"]:
            self.stdout.write(
                self.style.WARNING(
                    "Réinitialisation explicite : toutes les données de la base vont "
                    "être supprimées (flush), puis remplacées par le jeu de démonstration."
                )
            )
            call_command("flush", interactive=False, verbosity=0)
        else:
            existantes = self._donnees_existantes()
            if existantes:
                raise CommandError(
                    "La base contient déjà des données métier "
                    f"({existantes}).\n"
                    "Pour ne pas écraser des données réelles, la commande s'arrête.\n"
                    "Sur une base de développement uniquement, relancez avec :\n"
                    "    .venv/bin/python manage.py donnees_demo --reinitialiser"
                )

        with transaction.atomic():
            self._creer_roles()
            self._creer_parametres()
            self._creer_utilisateurs()
            self._creer_categories()
            self._creer_medicaments()
            self._creer_fournisseurs()
            self._creer_clients()
            self._creer_lots_de_base()
            self._creer_commandes_achat()
            self._creer_ventes()
            self._creer_retour_et_annulation()
            self._creer_inventaire()

        self._afficher_resume()

    def _donnees_existantes(self) -> str:
        compteurs = []
        for libelle, modele in (
            ("médicament(s)", Medicament),
            ("vente(s)", Vente),
            ("commande(s) d'achat", CommandeAchat),
            ("lot(s) de stock", LotStock),
        ):
            nombre = modele.objects.count()
            if nombre:
                compteurs.append(f"{nombre} {libelle}")
        return ", ".join(compteurs)

    # ------------------------------------------------------------------
    # Utilisateurs, paramètres, référentiels
    # ------------------------------------------------------------------
    def _creer_roles(self):
        self.roles = {}
        for code, nom, description, ordre in ROLES:
            role, _ = Role.objects.get_or_create(
                code=code,
                defaults={"nom": nom, "description": description, "ordre": ordre},
            )
            self.roles[code] = role

    def _creer_parametres(self):
        parametres = ParametrePharmacie.get_solo()
        parametres.nom = "Pharmacie de la Place"
        parametres.adresse = "Lot II M 12 bis, Antananarivo 101, Madagascar"
        parametres.telephone = "+261 20 22 123 45"
        parametres.email = "contact@pharmacie-place.mg"
        parametres.numero_fiscal = "NIF 400 123 456"
        parametres.devise = "Ar"
        parametres.seuil_peremption_jours = 30
        parametres.mentions_legales = (
            "Document généré par PharmaGest. Les mentions légales, fiscales et "
            "comptables doivent être adaptées à la réglementation malgache en "
            "vigueur. Les données personnelles sont traitées de manière "
            "confidentielle et limitées au strict nécessaire."
        )
        parametres.save()

    def _creer_utilisateurs(self):
        for donnees in UTILISATEURS:
            utilisateur, _ = Utilisateur.objects.get_or_create(
                username=donnees["username"]
            )
            utilisateur.first_name = donnees["prenom"]
            utilisateur.last_name = donnees["nom"]
            utilisateur.email = donnees["email"]
            utilisateur.telephone = donnees["telephone"]
            utilisateur.adresse = donnees["adresse"]
            utilisateur.is_active = True
            utilisateur.is_staff = donnees["superuser"]
            utilisateur.is_superuser = donnees["superuser"]
            utilisateur.set_password(MOT_DE_PASSE)
            utilisateur.save()
            utilisateur.roles.set([self.roles[donnees["role"]]])
            self.utilisateurs[donnees["username"]] = utilisateur

    def _creer_categories(self):
        self.categories = {}
        for nom, description in CATEGORIES:
            categorie, _ = Categorie.objects.get_or_create(
                nom=nom, defaults={"description": description}
            )
            self.categories[nom] = categorie

    def _ean13(self, index: int) -> str:
        """Construit un EAN-13 fictif valide et unique (préfixe 200)."""
        base = f"200{index:09d}"
        somme = sum(
            int(chiffre) * (1 if position % 2 == 0 else 3)
            for position, chiffre in enumerate(base)
        )
        return base + str((10 - somme % 10) % 10)

    def _creer_medicaments(self):
        for index, donnees in enumerate(MEDICAMENTS, start=1):
            medicament = Medicament.objects.create(
                nom=donnees["nom"],
                denomination_generique=donnees["dci"],
                categorie=self.categories[donnees["categorie"]],
                forme=donnees["forme"],
                dosage=donnees["dosage"],
                laboratoire=donnees["laboratoire"],
                code_barres=self._ean13(index),
                prix_achat=Decimal(donnees["prix_achat"]),
                prix_vente=Decimal(donnees["prix_vente"]),
                seuil_alerte=donnees["seuil"],
                statut=(
                    Medicament.Statut.ARCHIVE
                    if donnees.get("archive")
                    else Medicament.Statut.ACTIF
                ),
            )
            self._creer_photo(medicament, index)
            self.medicaments[donnees["cle"]] = medicament

    def _creer_photo(self, medicament: Medicament, index: int):
        """Réutilise une photo réelle si elle existe, sinon en génère une.

        Les photos libres de droits téléchargées pour la démonstration sont
        conservées dans ``media/medicaments/demo/``. Leur présence évite de les
        écraser par une vignette synthétique lors d'un nouveau
        ``donnees_demo --reinitialiser``.
        """
        nom_fichier = f"medicaments/demo/medicament_{index:02d}.jpg"
        if default_storage.exists(nom_fichier):
            medicament.photo.name = nom_fichier
            medicament.save(update_fields=["photo"])
            return

        source = (
            Path(settings.BASE_DIR)
            / "static"
            / "img"
            / "medicaments"
            / "demo"
            / f"medicament_{index:02d}.jpg"
        )
        if source.is_file():
            chemin = default_storage.save(
                nom_fichier, ContentFile(source.read_bytes())
            )
            medicament.photo.name = chemin
            medicament.save(update_fields=["photo"])
            return

        fond, texte = COULEURS_PHOTOS[(index - 1) % len(COULEURS_PHOTOS)]
        taille = 480
        image = Image.new("RGB", (taille, taille), fond)
        dessin = ImageDraw.Draw(image)
        dessin.ellipse(
            [110, 70, taille - 110, taille - 200],
            fill=_melange(fond, "#FFFFFF", 0.16),
        )
        dessin.rectangle(
            [0, taille - 105, taille, taille],
            fill=_melange(fond, "#000000", 0.12),
        )

        mots = [mot for mot in medicament.nom.replace("-", " ").split() if mot]
        initiales = "".join(mot[0] for mot in mots[:2]).upper() or "PG"
        dessin.text(
            (taille / 2, 205),
            initiales,
            font=_police(150),
            fill=texte,
            anchor="mm",
        )

        nom = "\n".join(textwrap.wrap(medicament.nom, width=24)[:2])
        dessin.multiline_text(
            (taille / 2, taille - 62),
            nom,
            font=_police(26),
            fill=texte,
            anchor="mm",
            align="center",
            spacing=4,
        )
        dessin.text(
            (taille / 2, taille - 24),
            medicament.dosage[:34],
            font=_police(18),
            fill=_melange(texte, fond, 0.18),
            anchor="mm",
        )

        tampon = BytesIO()
        image.save(tampon, format="JPEG", quality=88, optimize=True)
        if default_storage.exists(nom_fichier):
            default_storage.delete(nom_fichier)
        chemin = default_storage.save(
            nom_fichier, ContentFile(tampon.getvalue())
        )
        medicament.photo.name = chemin
        medicament.save(update_fields=["photo"])

    def _creer_fournisseurs(self):
        for donnees in FOURNISSEURS:
            fournisseur, _ = Fournisseur.objects.get_or_create(
                nom=donnees["nom"], defaults=donnees
            )
            self.fournisseurs.append(fournisseur)

    def _creer_clients(self):
        for donnees in CLIENTS:
            client, _ = Client.objects.get_or_create(
                nom=donnees["nom"],
                telephone=donnees["telephone"],
                defaults=donnees,
            )
            self.clients.append(client)

    # ------------------------------------------------------------------
    # Lots et achats
    # ------------------------------------------------------------------
    def _date_ancienne(self, jours_min=30, jours_max=90):
        return _heure(
            timezone.localdate()
            - timedelta(days=self.hasard.randint(jours_min, jours_max)),
            heure=self.hasard.randint(8, 16),
            minute=self.hasard.randint(0, 59),
        )

    def _creer_lot(
        self,
        medicament,
        numero_lot,
        jours_peremption,
        quantite,
        fournisseur=None,
        reference="STOCK-INITIAL",
        date_reception=None,
    ):
        lot = receptionner_lot(
            medicament=medicament,
            numero_lot=numero_lot,
            date_peremption=timezone.localdate() + timedelta(days=jours_peremption),
            quantite=quantite,
            prix_achat=medicament.prix_achat,
            fournisseur=fournisseur,
            utilisateur=self.utilisateurs["stock"],
            reference=reference,
        )
        if date_reception is not None:
            LotStock.objects.filter(pk=lot.pk).update(date_reception=date_reception)
            MouvementStock.objects.filter(
                lot=lot, reference=reference, type_mouvement=MouvementStock.Type.ENTREE
            ).update(date=date_reception)
        return lot

    def _creer_lots_de_base(self):
        for cle, medicament in self.medicaments.items():
            fournisseur = self.hasard.choice(self.fournisseurs)
            date_reception = self._date_ancienne(45, 90)

            if medicament.statut == Medicament.Statut.ARCHIVE:
                self._creer_lot(
                    medicament,
                    f"LOT-DEMO-{medicament.pk:03d}-A",
                    jours_peremption=self.hasard.randint(150, 300),
                    quantite=self.hasard.randint(12, 24),
                    fournisseur=fournisseur,
                    date_reception=date_reception,
                )
                continue

            if cle in SANS_LOT:
                # Rupture volontaire pour alimenter les alertes de stock.
                continue

            if cle in STOCK_FAIBLE:
                self._creer_lot(
                    medicament,
                    f"LOT-DEMO-{medicament.pk:03d}-A",
                    jours_peremption=self.hasard.randint(180, 300),
                    quantite=self.hasard.randint(2, 4),
                    fournisseur=fournisseur,
                    date_reception=date_reception,
                )
                continue

            # Lot principal (péremption lointaine) et lot secondaire.
            self._creer_lot(
                medicament,
                f"LOT-DEMO-{medicament.pk:03d}-A",
                jours_peremption=self.hasard.randint(300, 540),
                quantite=self.hasard.randint(60, 120),
                fournisseur=fournisseur,
                date_reception=date_reception,
            )
            self._creer_lot(
                medicament,
                f"LOT-DEMO-{medicament.pk:03d}-B",
                jours_peremption=self.hasard.randint(150, 240),
                quantite=self.hasard.randint(30, 70),
                fournisseur=self.hasard.choice(self.fournisseurs),
                date_reception=self._date_ancienne(30, 60),
            )

        # Lots proches de la péremption (< 30 jours), encore valides et vendables.
        for cle, jours in PEREMPTION_PROCHE.items():
            medicament = self.medicaments[cle]
            self._creer_lot(
                medicament,
                f"LOT-PROCHE-{medicament.pk:03d}",
                jours_peremption=jours,
                quantite=40,
                fournisseur=self.hasard.choice(self.fournisseurs),
                date_reception=self._date_ancienne(10, 25),
            )

        # Lots déjà périmés, conservés avec une quantité positive : ils ne
        # doivent jamais être proposés à la vente (RG08).
        for cle, jours_perimes in LOTS_PERIMES.items():
            medicament = self.medicaments[cle]
            self._creer_lot(
                medicament,
                f"LOT-PERIME-{medicament.pk:03d}",
                jours_peremption=-jours_perimes,
                quantite=self.hasard.randint(8, 15),
                fournisseur=self.hasard.choice(self.fournisseurs),
                date_reception=self._date_ancienne(120, 200),
            )

    def _creer_commande(self, fournisseur, lignes, notes=""):
        commande = CommandeAchat.objects.create(
            fournisseur=fournisseur,
            utilisateur=self.utilisateurs["stock"],
            notes=notes,
        )
        lignes_creees = []
        for cle, quantite in lignes:
            lignes_creees.append(
                LigneAchat.objects.create(
                    commande=commande,
                    medicament=self.medicaments[cle],
                    quantite_commandee=quantite,
                    prix_achat_unitaire=self.medicaments[cle].prix_achat,
                )
            )
        return commande, lignes_creees

    def _receptionner(self, commande, lignes_creees, proportions, date_reception):
        lignes_reception = []
        for index, (ligne, proportion) in enumerate(zip(lignes_creees, proportions)):
            quantite = max(1, int(ligne.quantite_commandee * proportion))
            quantite = min(quantite, ligne.quantite_restante)
            if quantite <= 0:
                continue
            lignes_reception.append(
                {
                    "ligne_achat": ligne,
                    "quantite": quantite,
                    "numero_lot": f"LOT-ACH-{commande.pk:03d}-{index + 1}",
                    "date_peremption": timezone.localdate()
                    + timedelta(days=self.hasard.randint(300, 600)),
                    "prix_unitaire": ligne.prix_achat_unitaire,
                }
            )
        reception = receptionner_commande(
            commande,
            lignes_reception,
            utilisateur=self.utilisateurs["stock"],
            notes="Réception de démonstration — contrôle conforme.",
        )
        ReceptionAchat.objects.filter(pk=reception.pk).update(
            date_reception=date_reception
        )
        MouvementStock.objects.filter(reference=reception.numero).update(
            date=date_reception
        )
        for ligne_reception in LigneReception.objects.filter(reception=reception):
            LotStock.objects.filter(pk=ligne_reception.lot_id).update(
                date_reception=date_reception
            )
        return reception

    def _creer_commandes_achat(self):
        # 1. Commande en brouillon (3 lignes) — ne modifie pas le stock (RG04).
        commande_brouillon, _ = self._creer_commande(
            self.fournisseurs[0],
            [("azithromycine_250", 30), ("ciprofloxacine_500", 25), ("vitamine_b", 40)],
            notes="Commande de réassort en préparation.",
        )
        CommandeAchat.objects.filter(pk=commande_brouillon.pk).update(
            date_creation=self._date_ancienne(2, 4)
        )

        # 2. Commande validée, non encore réceptionnée.
        commande_validee, _ = self._creer_commande(
            self.fournisseurs[1],
            [("doliprane_500", 60), ("amoxicilline_500", 80), ("omeprazole_20", 50)],
            notes="Commande transmise au fournisseur.",
        )
        valider_commande(commande_validee, utilisateur=self.utilisateurs["pharmacien"])
        CommandeAchat.objects.filter(pk=commande_validee.pk).update(
            date_creation=self._date_ancienne(12, 16),
            date_commande=self._date_ancienne(10, 12),
        )

        # 3. Commande partiellement réceptionnée (50 % des quantités).
        commande_partielle, lignes_partielles = self._creer_commande(
            self.fournisseurs[2],
            [("ibuprofene_400", 40), ("smecta_3g", 60), ("betadine_10", 30)],
            notes="Réception partielle : reliquat attendu.",
        )
        valider_commande(commande_partielle, utilisateur=self.utilisateurs["stock"])
        date_partielle = self._date_ancienne(20, 24)
        CommandeAchat.objects.filter(pk=commande_partielle.pk).update(
            date_creation=self._date_ancienne(30, 35),
            date_commande=self._date_ancienne(26, 29),
        )
        self._receptionner(
            commande_partielle, lignes_partielles, [0.5, 0.5, 0.5], date_partielle
        )

        # 4. Commande entièrement réceptionnée via le service d'achat.
        commande_recue, lignes_recues = self._creer_commande(
            self.fournisseurs[0],
            [("efferalgan_1g", 50), ("augmentin_1g", 30), ("vitamine_c_500", 80)],
            notes="Commande soldée — réception complète.",
        )
        valider_commande(commande_recue, utilisateur=self.utilisateurs["stock"])
        date_recue = self._date_ancienne(36, 40)
        CommandeAchat.objects.filter(pk=commande_recue.pk).update(
            date_creation=self._date_ancienne(48, 55),
            date_commande=self._date_ancienne(44, 47),
        )
        self._receptionner(commande_recue, lignes_recues, [1.0, 1.0, 1.0], date_recue)

    # ------------------------------------------------------------------
    # Ventes, retours et inventaire
    # ------------------------------------------------------------------
    def _date_vente(self, jours_avant: int):
        if jours_avant == 0:
            return timezone.now() - timedelta(minutes=self.hasard.randint(5, 240))
        return _heure(
            timezone.localdate() - timedelta(days=jours_avant),
            heure=self.hasard.randint(8, 18),
            minute=self.hasard.randint(0, 59),
        )

    def _creer_ventes(self):
        medicaments = list(
            Medicament.objects.filter(statut=Medicament.Statut.ACTIF)
        )
        modes = [
            Paiement.Mode.ESPECES,
            Paiement.Mode.MOBILE_MONEY,
            Paiement.Mode.CARTE,
        ]
        prefixes = {
            Paiement.Mode.MOBILE_MONEY: "MV",
            Paiement.Mode.CARTE: "CB",
        }

        for index in range(NB_VENTES):
            jours_avant = 0 if index >= NB_VENTES - 3 else self.hasard.randint(3, 59)
            nombre_lignes = self.hasard.randint(1, 3)
            lignes = []

            for medicament in self.hasard.sample(medicaments, len(medicaments)):
                if len(lignes) >= nombre_lignes:
                    break
                lot = lots_fefo(medicament).first()
                if lot is None:
                    continue
                quantite = min(self.hasard.randint(1, 3), lot.quantite)
                if quantite <= 0:
                    continue
                lignes.append({"lot": lot, "quantite": quantite})

            if not lignes:
                continue

            mode = self.hasard.choices(modes, weights=[65, 25, 10], k=1)[0]
            reference = ""
            if mode != Paiement.Mode.ESPECES:
                reference = (
                    f"{prefixes[mode]}-DEMO-{index + 1:04d}-"
                    f"{self.hasard.randint(1000, 9999)}"
                )
            client = (
                self.hasard.choice(self.clients)
                if self.hasard.random() < 0.65
                else None
            )

            vente, _ = creer_vente(
                utilisateur=self.utilisateurs["caissier"],
                lignes=lignes,
                client=client,
                mode_paiement=mode,
                reference_paiement=reference,
                paiement_confirme=(mode != Paiement.Mode.ESPECES),
                notes="Vente de démonstration.",
            )
            date_vente = self._date_vente(jours_avant)
            Vente.objects.filter(pk=vente.pk).update(date_vente=date_vente)
            Paiement.objects.filter(vente=vente).update(date_paiement=date_vente)
            MouvementStock.objects.filter(reference=vente.numero).update(
                date=date_vente
            )
            vente.refresh_from_db()
            self.ventes.append(vente)

        # Garantit au moins trois ventes aujourd'hui pour le tableau de bord.
        aujourdhui = timezone.localdate()
        nombre_aujourdhui = Vente.objects.filter(
            date_vente__date=aujourdhui
        ).count()
        while nombre_aujourdhui < 3:
            vente = self._creer_vente_du_jour()
            if vente is None:
                break
            nombre_aujourdhui += 1

    def _creer_vente_du_jour(self):
        medicaments = list(
            Medicament.objects.filter(statut=Medicament.Statut.ACTIF)
        )
        self.hasard.shuffle(medicaments)
        lignes = []
        for medicament in medicaments:
            lot = lots_fefo(medicament).first()
            if lot is None:
                continue
            quantite = min(self.hasard.randint(1, 2), lot.quantite)
            if quantite > 0:
                lignes.append({"lot": lot, "quantite": quantite})
            if len(lignes) >= 1:
                break
        if not lignes:
            return None
        vente, _ = creer_vente(
            utilisateur=self.utilisateurs["caissier"],
            lignes=lignes,
            client=self.hasard.choice(self.clients),
            mode_paiement=Paiement.Mode.ESPECES,
            notes="Vente de démonstration du jour.",
        )
        date_vente = timezone.now() - timedelta(minutes=self.hasard.randint(5, 120))
        Vente.objects.filter(pk=vente.pk).update(date_vente=date_vente)
        Paiement.objects.filter(vente=vente).update(date_paiement=date_vente)
        MouvementStock.objects.filter(reference=vente.numero).update(
            date=date_vente
        )
        vente.refresh_from_db()
        self.ventes.append(vente)
        return vente

    def _creer_retour_et_annulation(self):
        candidates = [
            vente
            for vente in self.ventes
            if vente.statut == Vente.Statut.VALIDEE and vente.nombre_articles >= 2
        ]
        if not candidates:
            return

        self.ventes.sort(key=lambda vente: vente.date_vente)
        candidates.sort(key=lambda vente: vente.date_vente)

        # 1. Retour partiel avec remise en stock.
        vente_retour = candidates[0]
        ligne = next(
            (
                ligne
                for ligne in vente_retour.lignes.all()
                if ligne.quantite_retournable > 0
            ),
            None,
        )
        if ligne is not None:
            retour = creer_retour(
                vente=vente_retour,
                lignes=[
                    {
                        "ligne_vente": ligne,
                        "quantite": 1,
                        "remise_en_stock": True,
                    }
                ],
                utilisateur=self.utilisateurs["pharmacien"],
                motif="Retour client — traitement interrompu sur avis médical.",
                mode_remboursement=RetourVente.ModeRemboursement.ESPECES,
                notes="Produit non ouvert, remis en stock après contrôle.",
            )
            date_retour = min(
                vente_retour.date_vente + timedelta(days=1),
                timezone.now() - timedelta(hours=2),
            )
            RetourVente.objects.filter(pk=retour.pk).update(date_retour=date_retour)
            MouvementStock.objects.filter(reference=retour.numero).update(
                date=date_retour
            )

        # 2. Annulation d'une autre vente par opération compensatoire traçable.
        annulee = next(
            (
                vente
                for vente in candidates[1:]
                if vente.pk != vente_retour.pk
                and vente.statut == Vente.Statut.VALIDEE
                and vente.nombre_articles > 0
            ),
            None,
        )
        if annulee is not None:
            retour_annulation = annuler_vente(
                vente=annulee,
                utilisateur=self.utilisateurs["pharmacien"],
                motif="Annulation de démonstration — erreur de saisie au comptoir.",
                remise_en_stock=True,
            )
            date_annulation = min(
                annulee.date_vente + timedelta(days=1),
                timezone.now() - timedelta(hours=2),
            )
            RetourVente.objects.filter(pk=retour_annulation.pk).update(
                date_retour=date_annulation
            )
            MouvementStock.objects.filter(
                reference=retour_annulation.numero
            ).update(date=date_annulation)

    def _creer_inventaire(self):
        lots = list(
            LotStock.objects.filter(
                quantite__gt=0,
                date_peremption__gte=timezone.localdate(),
            )
            .order_by("pk")[:8]
        )
        if not lots:
            return
        inventaire = creer_inventaire(
            utilisateur=self.utilisateurs["stock"],
            notes="Inventaire tournant de démonstration — non validé.",
            lots=lots,
        )
        Inventaire.objects.filter(pk=inventaire.pk).update(
            date_creation=timezone.now() - timedelta(hours=6)
        )
        ligne = LigneInventaire.objects.filter(inventaire=inventaire).first()
        if ligne:
            ligne.quantite_comptee = max(ligne.quantite_theorique - 1, 0)
            ligne.save(update_fields=["quantite_comptee"])
        self.inventaire = inventaire

    # ------------------------------------------------------------------
    # Résumé
    # ------------------------------------------------------------------
    def _afficher_resume(self):
        aujourdhui = timezone.localdate()
        ventes_today = Vente.objects.filter(date_vente__date=aujourdhui)
        montant_today = sum(
            (vente.montant_total for vente in ventes_today), Decimal("0")
        )
        alertes = [
            medicament
            for medicament in Medicament.objects.filter(
                statut=Medicament.Statut.ACTIF
            )
            if medicament.est_en_alerte
        ]
        proches = LotStock.objects.filter(
            quantite__gt=0,
            date_peremption__gte=aujourdhui,
            date_peremption__lte=aujourdhui + timedelta(days=30),
        ).count()
        perimes = LotStock.objects.filter(
            quantite__gt=0, date_peremption__lt=aujourdhui
        ).count()

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 72))
        self.stdout.write(self.style.SUCCESS(" Données de démonstration PharmaGest créées"))
        self.stdout.write(self.style.SUCCESS("=" * 72))
        self.stdout.write(
            f"Pharmacie          : {ParametrePharmacie.get_solo().nom}\n"
            f"Catégories         : {Categorie.objects.count()}\n"
            f"Médicaments         : {Medicament.objects.count()} "
            f"({Medicament.objects.filter(statut=Medicament.Statut.ACTIF).count()} actifs, "
            f"{Medicament.objects.filter(statut=Medicament.Statut.ARCHIVE).count()} archivés)\n"
            f"Fournisseurs        : {Fournisseur.objects.count()}\n"
            f"Clients             : {Client.objects.count()}\n"
            f"Lots de stock       : {LotStock.objects.count()} "
            f"(dont {proches} proches de la péremption et {perimes} périmés)\n"
            f"Commandes d'achat   : {CommandeAchat.objects.count()}\n"
            f"Réceptions          : {ReceptionAchat.objects.count()}\n"
            f"Ventes              : {Vente.objects.count()} "
            f"({ventes_today.count()} aujourd'hui pour {montant_today:.2f} Ar)\n"
            f"Retours / annul.    : {RetourVente.objects.count()}\n"
            f"Paiements           : {Paiement.objects.count()}\n"
            f"Mouvements de stock : {MouvementStock.objects.count()}\n"
            f"Inventaires         : {Inventaire.objects.count()} "
            f"(statut : {getattr(getattr(self, 'inventaire', None), 'get_statut_display', lambda: '—')()})\n"
            f"Alertes de stock    : {len(alertes)} médicament(s) actif(s)"
        )

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(" Comptes de connexion"))
        self.stdout.write(
            f"  {'Identifiant':<12} {'Mot de passe':<18} Rôle\n"
            f"  {'-' * 12} {'-' * 18} {'-' * 30}"
        )
        for username, role in (
            ("admin", "Administrateur"),
            ("pharmacien", "Pharmacien responsable"),
            ("stock", "Gestionnaire de stock"),
            ("caissier", "Caissier"),
            ("gestion", "Responsable de gestion"),
        ):
            self.stdout.write(f"  {username:<12} {MOT_DE_PASSE:<18} {role}")

        self.stdout.write("")
        self.stdout.write(
            self.style.WARNING(
                "Données 100 % fictives réservées au développement et aux "
                "démonstrations. Ne pas utiliser telles quelles en production."
            )
        )
