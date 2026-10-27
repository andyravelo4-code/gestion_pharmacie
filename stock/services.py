"""Services de stock : toute modification passe par un mouvement traçable.

Ces fonctions sont atomiques et verrouillent le lot pour éviter les doubles
sorties et les stocks négatifs en cas de validations simultanées (RG05-RG07).
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from core.exceptions import LotNonDelivrable, OperationRefusee, StockInsuffisant
from core.utils import generer_numero
from stock.models import Inventaire, LigneInventaire, LotStock, MouvementStock

SIGNE = {
    MouvementStock.Type.ENTREE: 1,
    MouvementStock.Type.RETOUR: 1,
    MouvementStock.Type.CORRECTION_POSITIVE: 1,
    MouvementStock.Type.SORTIE: -1,
    MouvementStock.Type.CORRECTION_NEGATIVE: -1,
    MouvementStock.Type.PERTE: -1,
}


@transaction.atomic
def appliquer_mouvement(
    *,
    lot,
    type_mouvement,
    quantite,
    utilisateur=None,
    reference="",
    motif="",
    prix_unitaire=None,
    verifier_delivrabilite=False,
    medicament=None,
):
    """Applique un mouvement signé sur un lot et l'historise.

    :param quantite: quantité positive ; le sens est déterminé par le type.
    :param verifier_delivrabilite: refuse un lot périmé/bloqué (vente).
    """
    quantite = int(quantite)
    if quantite <= 0:
        raise OperationRefusee("La quantité du mouvement doit être strictement positive.")
    if type_mouvement not in SIGNE:
        raise OperationRefusee("Type de mouvement inconnu.")

    lot = LotStock.objects.select_for_update().get(pk=lot.pk)
    if medicament is not None and lot.medicament_id != medicament.pk:
        raise OperationRefusee("Le lot ne correspond pas au médicament sélectionné.")

    if verifier_delivrabilite and not lot.est_delivrable:
        if lot.est_perime:
            raise LotNonDelivrable(f"Le lot {lot.numero_lot} est périmé et ne peut pas être vendu.")
        if lot.bloque:
            raise LotNonDelivrable(f"Le lot {lot.numero_lot} est bloqué et ne peut pas être vendu.")
        raise LotNonDelivrable(f"Le lot {lot.numero_lot} n'a plus de stock disponible.")

    delta = SIGNE[type_mouvement] * quantite
    nouvelle_quantite = lot.quantite + delta
    if nouvelle_quantite < 0:
        raise StockInsuffisant(
            f"Stock insuffisant pour {lot.medicament} (lot {lot.numero_lot}) : "
            f"{lot.quantite} disponible(s), {quantite} demandé(s)."
        )

    lot.quantite = nouvelle_quantite
    lot.save(update_fields=["quantite", "date_modification"])

    mouvement = MouvementStock.objects.create(
        medicament=lot.medicament,
        lot=lot,
        type_mouvement=type_mouvement,
        quantite=delta,
        prix_unitaire=prix_unitaire if prix_unitaire is not None else lot.prix_achat,
        reference=reference,
        motif=motif,
        utilisateur=utilisateur,
    )
    return mouvement


@transaction.atomic
def receptionner_lot(
    *,
    medicament,
    numero_lot,
    date_peremption,
    quantite,
    prix_achat,
    fournisseur=None,
    utilisateur=None,
    reference="",
):
    """Crée ou complète un lot à la réception, puis enregistre l'entrée."""
    quantite = int(quantite)
    if quantite <= 0:
        raise OperationRefusee("La quantité reçue doit être supérieure à zéro.")

    lot, cree = LotStock.objects.select_for_update().get_or_create(
        medicament=medicament,
        numero_lot=numero_lot,
        date_peremption=date_peremption,
        defaults={
            "quantite": 0,
            "quantite_initiale": 0,
            "prix_achat": prix_achat,
            "fournisseur": fournisseur,
        },
    )
    if not cree:
        lot.prix_achat = prix_achat
        lot.fournisseur = fournisseur or lot.fournisseur
    lot.quantite_initiale += quantite
    lot.save(update_fields=["quantite_initiale", "prix_achat", "fournisseur", "date_modification"])

    appliquer_mouvement(
        lot=lot,
        type_mouvement=MouvementStock.Type.ENTREE,
        quantite=quantite,
        utilisateur=utilisateur,
        reference=reference,
        motif=f"Réception de {quantite} unité(s)",
        prix_unitaire=prix_achat,
    )
    lot.refresh_from_db()
    return lot


@transaction.atomic
def valider_inventaire(inventaire, utilisateur=None):
    """Applique les corrections d'un inventaire, une seule fois (RG09)."""
    inventaire = Inventaire.objects.select_for_update().get(pk=inventaire.pk)
    if inventaire.statut != Inventaire.Statut.EN_COURS:
        raise OperationRefusee("Cet inventaire a déjà été traité.")

    lignes = list(
        LigneInventaire.objects.select_related("lot__medicament")
        .filter(inventaire=inventaire)
        .order_by("pk")
    )
    if not lignes:
        raise OperationRefusee("Impossible de valider un inventaire sans ligne.")

    # Vérifie que le stock n'a pas bougé depuis le comptage.
    for ligne in lignes:
        lot_actuel = LotStock.objects.select_for_update().get(pk=ligne.lot_id)
        if lot_actuel.quantite != ligne.quantite_theorique:
            raise OperationRefusee(
                f"Le stock du lot {lot_actuel.numero_lot} a changé depuis le comptage. "
                "Veuillez recommencer l'inventaire."
            )

    for ligne in lignes:
        delta = ligne.ecart
        if delta == 0:
            continue
        lot = LotStock.objects.select_for_update().get(pk=ligne.lot_id)
        if delta > 0:
            type_mouvement = MouvementStock.Type.CORRECTION_POSITIVE
        else:
            type_mouvement = MouvementStock.Type.CORRECTION_NEGATIVE
        appliquer_mouvement(
            lot=lot,
            type_mouvement=type_mouvement,
            quantite=abs(delta),
            utilisateur=utilisateur,
            reference=inventaire.numero,
            motif=f"Inventaire physique — écart {delta:+d}",
            verifier_delivrabilite=False,
        )

    inventaire.statut = Inventaire.Statut.VALIDE
    inventaire.date_validation = timezone.now()
    inventaire.utilisateur = utilisateur or inventaire.utilisateur
    inventaire.save(update_fields=["statut", "date_validation", "utilisateur"])
    return inventaire


def creer_inventaire(*, utilisateur=None, notes="", lots=None):
    """Crée un inventaire en snapshotant les quantités théoriques."""
    inventaire = Inventaire.objects.create(
        numero=generer_numero("INV", Inventaire, longueur=4),
        utilisateur=utilisateur,
        notes=notes,
    )
    lots = lots if lots is not None else LotStock.objects.select_related("medicament").all()
    for lot in lots:
        LigneInventaire.objects.create(
            inventaire=inventaire,
            lot=lot,
            quantite_theorique=lot.quantite,
            quantite_comptee=lot.quantite,
        )
    return inventaire
