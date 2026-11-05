"""Gestion du panier de caisse stocké en session (prix recalculés côté serveur)."""
from decimal import Decimal

from django.utils import timezone

from core.exceptions import OperationRefusee
from stock.models import LotStock
from ventes.models import Paiement

CLE_SESSION = "pharmagest_panier"


def lire_panier(request):
    panier_brut = request.session.get(CLE_SESSION, {})
    panier = {}
    if isinstance(panier_brut, dict):
        for lot_id, quantite in panier_brut.items():
            try:
                quantite = int(quantite)
            except (TypeError, ValueError):
                continue
            if quantite > 0:
                panier[str(lot_id)] = quantite
    return panier


def enregistrer_panier(request, panier):
    request.session[CLE_SESSION] = {str(k): int(v) for k, v in panier.items() if int(v) > 0}
    request.session.modified = True


def vider_panier(request):
    request.session.pop(CLE_SESSION, None)
    request.session.modified = True


def ajouter_lot(request, lot, quantite):
    quantite = int(quantite)
    if quantite <= 0:
        raise OperationRefusee("La quantité doit être supérieure à zéro.")
    if not lot.est_delivrable:
        raise OperationRefusee(
            f"Le lot {lot.numero_lot} n'est pas délivrable (périmé, bloqué ou vide)."
        )
    panier = lire_panier(request)
    deja = panier.get(str(lot.pk), 0)
    nouvelle = deja + quantite
    if nouvelle > lot.quantite:
        raise OperationRefusee(
            f"Stock insuffisant pour le lot {lot.numero_lot} : "
            f"{lot.quantite} disponible(s), {nouvelle} demandé(s)."
        )
    panier[str(lot.pk)] = nouvelle
    enregistrer_panier(request, panier)
    return nouvelle


def ajouter_medicament_fefo(request, medicament, quantite):
    """Répartit la quantité demandée sur les lots FEFO disponibles."""
    quantite = int(quantite)
    if quantite <= 0:
        raise OperationRefusee("La quantité doit être supérieure à zéro.")
    lots = list(
        LotStock.objects.filter(
            medicament=medicament,
            bloque=False,
            quantite__gt=0,
            date_peremption__gte=timezone.localdate(),
        ).order_by("date_peremption", "pk")
    )
    if not lots:
        raise OperationRefusee(f"Aucun lot valide n'est disponible pour {medicament}.")
    panier = lire_panier(request)
    restant = quantite
    ajoute = 0
    for lot in lots:
        if restant <= 0:
            break
        deja = panier.get(str(lot.pk), 0)
        disponible = max(lot.quantite - deja, 0)
        if disponible <= 0:
            continue
        prise = min(disponible, restant)
        panier[str(lot.pk)] = deja + prise
        restant -= prise
        ajoute += prise
    enregistrer_panier(request, panier)
    if ajoute == 0:
        raise OperationRefusee(f"Le stock disponible de {medicament} est épuisé.")
    return ajoute, quantite - restant


def modifier_lot(request, lot_id, quantite):
    quantite = int(quantite)
    panier = lire_panier(request)
    if quantite <= 0:
        panier.pop(str(lot_id), None)
        enregistrer_panier(request, panier)
        return 0
    lot = LotStock.objects.filter(pk=lot_id).first()
    if not lot:
        raise OperationRefusee("Ce lot n'existe plus.")
    if not lot.est_delivrable:
        raise OperationRefusee(f"Le lot {lot.numero_lot} n'est plus délivrable.")
    if quantite > lot.quantite:
        raise OperationRefusee(
            f"Stock insuffisant pour le lot {lot.numero_lot} : {lot.quantite} disponible(s)."
        )
    panier[str(lot_id)] = quantite
    enregistrer_panier(request, panier)
    return quantite


def retirer_lot(request, lot_id):
    panier = lire_panier(request)
    panier.pop(str(lot_id), None)
    enregistrer_panier(request, panier)


def detail_panier(request):
    """Construit les lignes à partir de la base ; le prix appliqué est le prix actuel."""
    panier = lire_panier(request)
    lignes = []
    total = Decimal("0")
    erreurs = []
    nombre_articles = 0
    try:
        identifiants = {int(lot_id) for lot_id in panier}
    except (TypeError, ValueError):
        identifiants = set()
    lots = LotStock.objects.select_related("medicament", "fournisseur").in_bulk(identifiants)
    for lot_id, quantite in panier.items():
        try:
            lot = lots.get(int(lot_id))
        except (TypeError, ValueError):
            lot = None
        if not lot:
            erreurs.append("Un lot du panier n'existe plus et a été ignoré.")
            continue
        disponible = lot.quantite
        sous_total = lot.medicament.prix_vente * quantite
        erreur = None
        if lot.est_perime:
            erreur = "Lot périmé : retirez-le du panier."
        elif lot.bloque:
            erreur = "Lot bloqué : retirez-le du panier."
        elif quantite > disponible:
            erreur = f"Stock insuffisant : {disponible} disponible(s)."
        if erreur:
            erreurs.append(f"{lot.medicament} (lot {lot.numero_lot}) — {erreur}")
        total += sous_total
        nombre_articles += quantite
        lignes.append(
            {
                "lot": lot,
                "medicament": lot.medicament,
                "quantite": quantite,
                "prix_unitaire": lot.medicament.prix_vente,
                "sous_total": sous_total,
                "disponible": disponible,
                "erreur": erreur,
            }
        )
    return {
        "lignes": lignes,
        "total": total,
        "erreurs": erreurs,
        "nombre_articles": nombre_articles,
    }


def lignes_pour_service(detail):
    return [
        {"lot": ligne["lot"], "quantite": ligne["quantite"]}
        for ligne in detail["lignes"]
        if not ligne["erreur"]
    ]


MODES_A_CONFIRMER = set(Paiement.Mode.values) - {Paiement.Mode.ESPECES}
