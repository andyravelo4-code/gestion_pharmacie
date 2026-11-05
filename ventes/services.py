"""Services de vente atomiques, FEFO, retours et annulations.

Les règles RG05 à RG08 et RG12 sont appliquées ici, côté serveur.
"""
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from core.exceptions import LotNonDelivrable, OperationRefusee, StockInsuffisant
from stock.models import LotStock, MouvementStock
from stock.services import appliquer_mouvement
from ventes.models import LigneRetour, LigneVente, Paiement, RetourVente, Vente


def lots_fefo(medicament):
    """Lots délivrables triés par date de péremption (FEFO)."""
    return (
        LotStock.objects.filter(
            medicament=medicament,
            bloque=False,
            quantite__gt=0,
            date_peremption__gte=timezone.localdate(),
        )
        .select_related("medicament", "fournisseur")
        .order_by("date_peremption", "pk")
    )


def creer_vente(
    *,
    utilisateur,
    lignes,
    client=None,
    mode_paiement=Paiement.Mode.ESPECES,
    reference_paiement="",
    montant_recu=None,
    paiement_confirme=False,
    notes="",
    cle_idempotence=None,
):
    """Valide une vente : contrôle du stock, sortie, paiement et total figé.

    :param lignes: liste de dicts ``{"lot": LotStock, "quantite": int}``.
    :return: (vente, creee)
    """
    if cle_idempotence:
        existante = Vente.objects.filter(cle_idempotence=cle_idempotence).first()
        if existante:
            return existante, False

    if mode_paiement not in Paiement.Mode.values:
        raise OperationRefusee("Mode de paiement invalide.")
    if mode_paiement != Paiement.Mode.ESPECES:
        if not (reference_paiement or "").strip():
            raise OperationRefusee(
                "Une référence de transaction est obligatoire pour un paiement non espèces."
            )
        if not paiement_confirme:
            raise OperationRefusee(
                "Le paiement électronique doit être vérifié et confirmé avant la validation "
                "de la vente."
            )

    try:
        vente = _creer_vente(
            utilisateur=utilisateur,
            lignes=lignes,
            client=client,
            mode_paiement=mode_paiement,
            reference_paiement=reference_paiement,
            montant_recu=montant_recu,
            notes=notes,
            cle_idempotence=cle_idempotence,
        )
        return vente, True
    except IntegrityError:
        if cle_idempotence:
            existante = Vente.objects.filter(cle_idempotence=cle_idempotence).first()
            if existante:
                return existante, False
        raise


@transaction.atomic
def _creer_vente(
    *,
    utilisateur,
    lignes,
    client,
    mode_paiement,
    reference_paiement,
    montant_recu,
    notes,
    cle_idempotence,
):
    # Regroupe les lignes par lot et refuse les quantités invalides.
    quantites = {}
    for ligne in lignes:
        lot = ligne.get("lot")
        quantite = int(ligne.get("quantite") or 0)
        if lot is None:
            raise OperationRefusee("Aucun lot n'a été sélectionné pour une ligne de vente.")
        if quantite <= 0:
            raise OperationRefusee("La quantité vendue doit être strictement positive.")
        quantites[lot.pk] = quantites.get(lot.pk, 0) + quantite

    if not quantites:
        raise OperationRefusee("Le panier est vide.")

    lots = {
        lot.pk: lot
        for lot in LotStock.objects.select_for_update()
        .select_related("medicament")
        .filter(pk__in=quantites.keys())
        .order_by("pk")
    }
    if len(lots) != len(quantites):
        raise OperationRefusee("Un des lots sélectionnés n'existe plus.")

    total = Decimal("0")
    lignes_preparees = []
    for lot_pk, quantite in quantites.items():
        lot = lots[lot_pk]
        if not lot.medicament.est_actif:
            raise OperationRefusee(
                f"Le médicament {lot.medicament} est archivé et ne peut plus être vendu."
            )
        if lot.est_perime:
            raise LotNonDelivrable(
                f"Le lot {lot.numero_lot} de {lot.medicament} est périmé (RG08)."
            )
        if lot.bloque:
            raise LotNonDelivrable(
                f"Le lot {lot.numero_lot} de {lot.medicament} est bloqué (RG08)."
            )
        if quantite > lot.quantite:
            raise StockInsuffisant(
                f"Stock insuffisant pour {lot.medicament} (lot {lot.numero_lot}) : "
                f"{lot.quantite} disponible(s), {quantite} demandé(s)."
            )
        prix = lot.medicament.prix_vente
        lignes_preparees.append((lot, quantite, prix))
        total += prix * quantite

    vente = Vente.objects.create(
        client=client,
        utilisateur=utilisateur,
        montant_total=total,
        cle_idempotence=cle_idempotence,
        notes=notes,
    )

    for lot, quantite, prix in lignes_preparees:
        LigneVente.objects.create(
            vente=vente,
            medicament=lot.medicament,
            lot=lot,
            quantite=quantite,
            prix_unitaire=prix,
        )
        appliquer_mouvement(
            lot=lot,
            type_mouvement=MouvementStock.Type.SORTIE,
            quantite=quantite,
            utilisateur=utilisateur,
            reference=vente.numero,
            motif="Vente au comptoir",
            prix_unitaire=prix,
            verifier_delivrabilite=True,
        )

    montant_recu = Decimal(montant_recu) if montant_recu not in (None, "") else total
    if mode_paiement == Paiement.Mode.ESPECES and montant_recu < total:
        raise OperationRefusee(
            "Le montant reçu en espèces est inférieur au total à payer."
        )

    Paiement.objects.create(
        vente=vente,
        montant=total,
        mode=mode_paiement,
        statut=Paiement.Statut.CONFIRME,
        reference=(reference_paiement or "").strip(),
        montant_recu=montant_recu,
        confirme_par=utilisateur,
        date_confirmation=timezone.now(),
    )
    return vente


@transaction.atomic
def creer_retour(
    *,
    vente,
    lignes,
    utilisateur,
    motif,
    mode_remboursement=RetourVente.ModeRemboursement.ESPECES,
    type_retour=RetourVente.Type.RETOUR,
    notes="",
):
    """Enregistre un retour traçable et une éventuelle remise en stock.

    :param lignes: liste de dicts
        ``{"ligne_vente": LigneVente, "quantite": int, "remise_en_stock": bool}``.
    """
    vente = Vente.objects.select_for_update().get(pk=vente.pk)
    motif = (motif or "").strip()
    if not motif:
        raise OperationRefusee("Le motif du retour est obligatoire.")

    lignes_valides = []
    montant = Decimal("0")
    for item in lignes:
        quantite = int(item.get("quantite") or 0)
        if quantite <= 0:
            continue
        ligne = item["ligne_vente"]
        if ligne.vente_id != vente.pk:
            raise OperationRefusee("Une ligne de retour ne correspond pas à la vente.")
        ligne = LigneVente.objects.select_related("lot__medicament").get(pk=ligne.pk)
        if quantite > ligne.quantite_retournable:
            raise OperationRefusee(
                f"Pour {ligne.medicament}, la quantité retournée ({quantite}) dépasse "
                f"la quantité encore retournable ({ligne.quantite_retournable})."
            )
        remise = bool(item.get("remise_en_stock"))
        if remise:
            if ligne.lot.est_perime:
                raise OperationRefusee(
                    f"Le lot {ligne.lot.numero_lot} est périmé : il ne peut pas être remis en stock."
                )
            if ligne.lot.bloque:
                raise OperationRefusee(
                    f"Le lot {ligne.lot.numero_lot} est bloqué : débloquez-le avant remise en stock."
                )
        lignes_valides.append((ligne, quantite, remise))
        montant += ligne.prix_unitaire * quantite

    if not lignes_valides:
        raise OperationRefusee("Aucune quantité à retourner n'a été saisie.")

    retour = RetourVente.objects.create(
        vente=vente,
        type_retour=type_retour,
        utilisateur=utilisateur,
        motif=motif,
        montant_rembourse=montant,
        mode_remboursement=mode_remboursement,
        notes=notes,
    )

    for ligne, quantite, remise in lignes_valides:
        LigneRetour.objects.create(
            retour=retour,
            ligne_vente=ligne,
            quantite=quantite,
            prix_unitaire=ligne.prix_unitaire,
            remise_en_stock=remise,
        )
        if remise:
            appliquer_mouvement(
                lot=ligne.lot,
                type_mouvement=MouvementStock.Type.RETOUR,
                quantite=quantite,
                utilisateur=utilisateur,
                reference=retour.numero,
                motif=f"Retour sur vente {vente.numero}",
                prix_unitaire=ligne.prix_unitaire,
            )

    if all(ligne.quantite_retournable == 0 for ligne in vente.lignes.all()) or (
        type_retour == RetourVente.Type.ANNULATION
    ):
        vente.statut = Vente.Statut.ANNULEE
        vente.save(update_fields=["statut"])

    return retour


def annuler_vente(*, vente, utilisateur, motif, remise_en_stock=True):
    """Annule une vente par opération compensatoire traçable (jamais de suppression)."""
    lignes = [
        {
            "ligne_vente": ligne,
            "quantite": ligne.quantite_retournable,
            "remise_en_stock": remise_en_stock,
        }
        for ligne in vente.lignes.all()
        if ligne.quantite_retournable > 0
    ]
    if not lignes:
        raise OperationRefusee("Cette vente a déjà été entièrement retournée.")
    return creer_retour(
        vente=vente,
        lignes=lignes,
        utilisateur=utilisateur,
        motif=motif or "Annulation de la vente",
        mode_remboursement=RetourVente.ModeRemboursement.ESPECES,
        type_retour=RetourVente.Type.ANNULATION,
        notes="Annulation enregistrée comme opération compensatoire.",
    )


@transaction.atomic
def confirmer_paiement(paiement, utilisateur=None):
    """Confirme un paiement électronique après vérification fiable."""
    if paiement.mode == Paiement.Mode.ESPECES:
        return paiement
    paiement = Paiement.objects.select_for_update().get(pk=paiement.pk)
    if paiement.statut == Paiement.Statut.CONFIRME:
        return paiement
    paiement.confirmer(utilisateur)
    return paiement
