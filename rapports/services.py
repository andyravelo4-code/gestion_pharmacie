"""Calculs et agrégations utilisés par les rapports PharmaGest.

Toutes les valeurs sont calculées côté serveur à partir des données réelles :
aucun indicateur n'est saisi ni calculé uniquement dans le navigateur.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from achats.models import CommandeAchat, ReceptionAchat
from medicaments.models import Medicament
from stock.models import LotStock
from ventes.models import LigneVente, Paiement, RetourVente, Vente

ZERO = Decimal("0")

MOIS_FR = (
    "janv.",
    "févr.",
    "mars",
    "avr.",
    "mai",
    "juin",
    "juil.",
    "août",
    "sept.",
    "oct.",
    "nov.",
    "déc.",
)


# ---------------------------------------------------------------------------
# Dates et périodes
# ---------------------------------------------------------------------------
def lire_date(valeur):
    """Convertit une chaîne ISO ou française en date, sinon ``None``."""
    if not valeur:
        return None
    if isinstance(valeur, datetime):
        return valeur.date()
    if isinstance(valeur, date):
        return valeur
    valeur = str(valeur).strip()
    for format_date in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(valeur, format_date).date()
        except ValueError:
            continue
    return None


def normaliser_periode(debut=None, fin=None, jours_defaut=30):
    """Retourne une période cohérente (deux dates, début <= fin)."""
    fin = fin or timezone.localdate()
    debut = debut or (fin - timedelta(days=max(jours_defaut - 1, 0)))
    if debut > fin:
        debut, fin = fin, debut
    return debut, fin


def resoudre_periode(debut=None, fin=None, jours_defaut=30):
    """Résout les filtres GET ``debut`` et ``fin`` avec des valeurs par défaut."""
    return normaliser_periode(lire_date(debut), lire_date(fin), jours_defaut)


def resoudre_jours(valeur, defaut=30, minimum=1, maximum=3650):
    try:
        jours = int(valeur)
    except (TypeError, ValueError):
        jours = int(defaut or 30)
    return max(minimum, min(maximum, jours))


def libelle_periode(debut, fin):
    return f"Du {debut:%d/%m/%Y} au {fin:%d/%m/%Y}"


def _decimal(valeur):
    return valeur if valeur is not None else ZERO


# ---------------------------------------------------------------------------
# Ventes
# ---------------------------------------------------------------------------
def ventes_periode(debut, fin, statut=Vente.Statut.VALIDEE):
    return Vente.objects.filter(
        statut=statut,
        date_vente__date__range=(debut, fin),
    )


def totaux_ventes(debut, fin):
    """Totaux d'une période : brut, retours, net, panier et encaissements."""
    ventes = ventes_periode(debut, fin)
    agregat = ventes.aggregate(
        brut=Sum("montant_total"),
        articles=Sum("lignes__quantite"),
    )
    brut = _decimal(agregat["brut"])
    nombre = ventes.count()
    articles = agregat["articles"] or 0

    retours = _decimal(
        RetourVente.objects.filter(
            date_retour__date__range=(debut, fin)
        ).aggregate(total=Sum("montant_rembourse"))["total"]
    )
    encaissements = _decimal(
        Paiement.objects.filter(
            statut=Paiement.Statut.CONFIRME,
            vente__statut=Vente.Statut.VALIDEE,
            vente__date_vente__date__range=(debut, fin),
        ).aggregate(total=Sum("montant"))["total"]
    )
    net = brut - retours
    panier_moyen = (brut / nombre) if nombre else ZERO
    return {
        "brut": brut,
        "retours": retours,
        "net": net,
        "nombre": nombre,
        "articles": articles,
        "panier_moyen": panier_moyen,
        "encaissements": encaissements,
    }


def top_produits(debut, fin, limite=5):
    """Top des produits vendus sur la période (quantité et montant)."""
    lignes = (
        LigneVente.objects.filter(
            vente__statut=Vente.Statut.VALIDEE,
            vente__date_vente__date__range=(debut, fin),
        )
        .values(
            "medicament_id",
            "medicament__nom",
            "medicament__dosage",
            "medicament__categorie__nom",
        )
        .annotate(quantite=Sum("quantite"), montant=Sum("sous_total"))
        .order_by("-montant", "-quantite")[:limite]
    )
    return [
        {
            "medicament_id": ligne["medicament_id"],
            "nom": ligne["medicament__nom"],
            "dosage": ligne["medicament__dosage"],
            "categorie": ligne["medicament__categorie__nom"],
            "quantite": ligne["quantite"] or 0,
            "montant": _decimal(ligne["montant"]),
        }
        for ligne in lignes
    ]


def repartition_paiements(debut, fin):
    """Montants encaissés (paiements confirmés) par mode de paiement."""
    lignes = (
        Paiement.objects.filter(
            statut=Paiement.Statut.CONFIRME,
            vente__statut=Vente.Statut.VALIDEE,
            vente__date_vente__date__range=(debut, fin),
        )
        .values("mode")
        .annotate(total=Sum("montant"), nombre=Count("pk"))
        .order_by("-total")
    )
    libelles = dict(Paiement.Mode.choices)
    resultat = [
        {
            "mode": ligne["mode"],
            "libelle": libelles.get(ligne["mode"], ligne["mode"]),
            "total": _decimal(ligne["total"]),
            "nombre": ligne["nombre"],
        }
        for ligne in lignes
    ]
    total = sum((ligne["total"] for ligne in resultat), ZERO)
    return {"lignes": resultat, "total": total}


def evolution_mensuelle(mois=6):
    """Évolution du chiffre d'affaires validé sur les derniers mois."""
    aujourd_hui = timezone.localdate()
    premier_mois = aujourd_hui.replace(day=1)
    for _ in range(max(mois - 1, 0)):
        premier_mois = (premier_mois - timedelta(days=1)).replace(day=1)

    debut = premier_mois
    donnees = (
        Vente.objects.filter(
            statut=Vente.Statut.VALIDEE,
            date_vente__date__gte=debut,
            date_vente__date__lte=aujourd_hui,
        )
        .annotate(mois_vente=TruncMonth("date_vente"))
        .values("mois_vente")
        .annotate(total=Sum("montant_total"))
        .order_by("mois_vente")
    )
    par_mois = {}
    for ligne in donnees:
        valeur = ligne["mois_vente"]
        if isinstance(valeur, datetime):
            cle = (valeur.year, valeur.month)
        elif isinstance(valeur, date):
            cle = (valeur.year, valeur.month)
        else:
            continue
        par_mois[cle] = _decimal(ligne["total"])

    labels, valeurs = [], []
    curseur = premier_mois
    for _ in range(max(mois, 1)):
        cle = (curseur.year, curseur.month)
        labels.append(f"{MOIS_FR[curseur.month - 1]} {curseur.year}")
        valeurs.append(float(par_mois.get(cle, ZERO)))
        curseur = (curseur.replace(day=28) + timedelta(days=4)).replace(day=1)

    return {"labels": labels, "valeurs": valeurs}


def repartition_categories(debut, fin):
    """Répartition du chiffre d'affaires par catégorie de médicament."""
    lignes = (
        LigneVente.objects.filter(
            vente__statut=Vente.Statut.VALIDEE,
            vente__date_vente__date__range=(debut, fin),
        )
        .values("medicament__categorie__nom")
        .annotate(montant=Sum("sous_total"), quantite=Sum("quantite"))
        .order_by("-montant")
    )
    details = [
        {
            "categorie": ligne["medicament__categorie__nom"] or "Non classé",
            "montant": _decimal(ligne["montant"]),
            "quantite": ligne["quantite"] or 0,
        }
        for ligne in lignes
    ]
    return {
        "labels": [ligne["categorie"] for ligne in details],
        "valeurs": [float(ligne["montant"]) for ligne in details],
        "details": details,
    }


# ---------------------------------------------------------------------------
# Stock
# ---------------------------------------------------------------------------
def etat_stock(recherche="", etat=""):
    """État complet du stock actif, ligne par ligne, avec totaux."""
    aujourd_hui = timezone.localdate()
    medicaments = (
        Medicament.objects.filter(statut=Medicament.Statut.ACTIF)
        .select_related("categorie")
        .prefetch_related("lots")
        .order_by("nom", "dosage")
    )
    recherche = (recherche or "").strip().lower()
    etat = (etat or "").strip().lower()

    lignes = []
    totaux = {
        "quantite_physique": 0,
        "quantite_delivrable": 0,
        "valeur_achat": ZERO,
        "valeur_vente": ZERO,
    }
    for medicament in medicaments:
        lots = list(medicament.lots.all())
        stock_physique = sum(lot.quantite for lot in lots)
        stock_disponible = sum(
            lot.quantite
            for lot in lots
            if not lot.bloque and lot.date_peremption >= aujourd_hui
        )
        valeur_achat = sum((lot.quantite * lot.prix_achat for lot in lots), ZERO)
        valeur_vente = stock_physique * medicament.prix_vente

        if stock_disponible <= 0:
            etat_ligne = "rupture"
        elif stock_disponible <= medicament.seuil_alerte:
            etat_ligne = "faible"
        else:
            etat_ligne = "normal"

        ligne = {
            "medicament": medicament,
            "nom": medicament.nom,
            "dosage": medicament.dosage,
            "categorie": medicament.categorie.nom,
            "stock_physique": stock_physique,
            "stock_disponible": stock_disponible,
            "seuil": medicament.seuil_alerte,
            "valeur_achat": valeur_achat,
            "valeur_vente": valeur_vente,
            "etat": etat_ligne,
        }
        texte_recherche = " ".join(
            [
                medicament.nom,
                medicament.denomination_generique,
                medicament.dosage,
                medicament.categorie.nom,
            ]
        ).lower()
        if recherche and recherche not in texte_recherche:
            continue
        if etat and etat_ligne != etat:
            continue

        lignes.append(ligne)
        totaux["quantite_physique"] += stock_physique
        totaux["quantite_delivrable"] += stock_disponible
        totaux["valeur_achat"] += valeur_achat
        totaux["valeur_vente"] += valeur_vente

    totaux["nombre_references"] = len(lignes)
    return {"lignes": lignes, "totaux": totaux}


def alertes_stock(limite=12):
    """Médicaments en rupture ou sous leur seuil, les plus critiques d'abord."""
    resultat = etat_stock()
    lignes = [ligne for ligne in resultat["lignes"] if ligne["etat"] in {"rupture", "faible"}]
    lignes.sort(
        key=lambda ligne: (
            0 if ligne["etat"] == "rupture" else 1,
            ligne["stock_disponible"],
            ligne["nom"],
        )
    )
    return lignes[:limite]


# ---------------------------------------------------------------------------
# Péremptions
# ---------------------------------------------------------------------------
def lots_peremption(jours=30):
    """Lots encore en stock périmés ou proches de la péremption."""
    aujourd_hui = timezone.localdate()
    jours = resoudre_jours(jours, 30)
    date_limite = aujourd_hui + timedelta(days=jours)

    lots = (
        LotStock.objects.filter(quantite__gt=0, date_peremption__lte=date_limite)
        .select_related("medicament", "medicament__categorie", "fournisseur")
        .order_by("date_peremption", "medicament__nom")
    )
    perimes, proches = [], []
    totaux = {
        "quantite_perimes": 0,
        "quantite_proches": 0,
        "valeur_achat_perimes": ZERO,
        "valeur_achat_proches": ZERO,
        "valeur_vente_perimes": ZERO,
        "valeur_vente_proches": ZERO,
    }
    for lot in lots:
        est_perime = lot.est_perime
        ligne = {
            "lot": lot,
            "medicament": lot.medicament,
            "categorie": lot.medicament.categorie.nom,
            "fournisseur": lot.fournisseur,
            "quantite": lot.quantite,
            "date_peremption": lot.date_peremption,
            "jours": lot.jours_avant_peremption,
            "valeur_achat": lot.quantite * lot.prix_achat,
            "valeur_vente": lot.quantite * lot.medicament.prix_vente,
            "est_perime": est_perime,
        }
        if est_perime:
            perimes.append(ligne)
            totaux["quantite_perimes"] += lot.quantite
            totaux["valeur_achat_perimes"] += ligne["valeur_achat"]
            totaux["valeur_vente_perimes"] += ligne["valeur_vente"]
        else:
            proches.append(ligne)
            totaux["quantite_proches"] += lot.quantite
            totaux["valeur_achat_proches"] += ligne["valeur_achat"]
            totaux["valeur_vente_proches"] += ligne["valeur_vente"]

    totaux["valeur_achat_totale"] = (
        totaux["valeur_achat_perimes"] + totaux["valeur_achat_proches"]
    )
    totaux["valeur_vente_totale"] = (
        totaux["valeur_vente_perimes"] + totaux["valeur_vente_proches"]
    )
    return {
        "perimes": perimes,
        "proches": proches,
        "totaux": totaux,
        "jours": jours,
        "date_limite": date_limite,
    }


# ---------------------------------------------------------------------------
# Achats
# ---------------------------------------------------------------------------
def statistiques_achats(debut, fin):
    commandes = list(
        CommandeAchat.objects.filter(date_creation__date__range=(debut, fin))
        .select_related("fournisseur", "utilisateur")
        .prefetch_related("lignes__medicament")
        .order_by("-date_creation")
    )
    receptions = list(
        ReceptionAchat.objects.filter(date_reception__date__range=(debut, fin))
        .select_related("commande__fournisseur", "utilisateur")
        .prefetch_related("lignes__ligne_achat__medicament")
        .order_by("-date_reception")
    )

    statuts_engages = {
        CommandeAchat.Statut.COMMANDEE,
        CommandeAchat.Statut.PARTIELLEMENT_RECEPTIONNEE,
        CommandeAchat.Statut.RECEPTIONNEE,
    }
    total_commande = sum(
        (
            commande.montant_total
            for commande in commandes
            if commande.statut in statuts_engages
        ),
        ZERO,
    )
    total_receptionne = sum(
        (reception.montant_total for reception in receptions), ZERO
    )
    return {
        "commandes": commandes,
        "receptions": receptions,
        "total_commande": total_commande,
        "total_receptionne": total_receptionne,
        "nombre_commandes": len(commandes),
        "nombre_receptions": len(receptions),
    }


# ---------------------------------------------------------------------------
# Tableau de bord
# ---------------------------------------------------------------------------
def indicateurs_tableau_bord(debut, fin):
    """Indicateurs synthétiques du tableau de bord (données réelles)."""
    aujourd_hui = timezone.localdate()
    nombre_actifs = Medicament.objects.filter(statut=Medicament.Statut.ACTIF).count()

    totaux_jour = totaux_ventes(aujourd_hui, aujourd_hui)
    totaux_periode = totaux_ventes(debut, fin)

    etat = etat_stock()
    stocks_faibles = sum(1 for ligne in etat["lignes"] if ligne["etat"] == "faible")
    ruptures = sum(1 for ligne in etat["lignes"] if ligne["etat"] == "rupture")

    from core.models import ParametrePharmacie

    seuil = ParametrePharmacie.get_solo().seuil_jours
    peremptions = lots_peremption(seuil)

    return {
        "medicaments_actifs": nombre_actifs,
        "ventes_jour_brut": totaux_jour["brut"],
        "ventes_jour_net": totaux_jour["net"],
        "ventes_jour_nombre": totaux_jour["nombre"],
        "stocks_faibles": stocks_faibles,
        "ruptures": ruptures,
        "peremptions_proches": len(peremptions["proches"]),
        "peremptions_jours": seuil,
        "ca_periode": totaux_periode["brut"],
        "ca_periode_net": totaux_periode["net"],
        "retours_periode": totaux_periode["retours"],
        "encaissements_periode": totaux_periode["encaissements"],
        "nombre_ventes_periode": totaux_periode["nombre"],
        "panier_moyen_periode": totaux_periode["panier_moyen"],
        "etat_stock": etat,
        "peremptions": peremptions,
    }
