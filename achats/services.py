"""Services d'achat : validation de commande et réception atomique."""
from datetime import date

from django.db import transaction
from django.utils import timezone

from achats.models import CommandeAchat, LigneAchat, LigneReception, ReceptionAchat
from core.exceptions import OperationRefusee
from stock.services import receptionner_lot


@transaction.atomic
def valider_commande(commande, utilisateur=None):
    """Passe une commande brouillon en « Commandée » (RG04)."""
    commande = CommandeAchat.objects.select_for_update().get(pk=commande.pk)
    if commande.statut != CommandeAchat.Statut.BROUILLON:
        raise OperationRefusee("Seule une commande en brouillon peut être validée.")
    if not commande.lignes.exists():
        raise OperationRefusee("Impossible de valider une commande sans ligne.")
    commande.statut = CommandeAchat.Statut.COMMANDEE
    commande.date_commande = timezone.now()
    commande.utilisateur = utilisateur or commande.utilisateur
    commande.save(update_fields=["statut", "date_commande", "utilisateur", "date_modification"])
    return commande


@transaction.atomic
def annuler_commande(commande, utilisateur=None):
    commande = CommandeAchat.objects.select_for_update().get(pk=commande.pk)
    if not commande.peut_etre_annulee:
        raise OperationRefusee(
            "Une commande déjà réceptionnée (même partiellement) ne peut pas être annulée."
        )
    commande.statut = CommandeAchat.Statut.ANNULEE
    commande.save(update_fields=["statut", "date_modification"])
    return commande


@transaction.atomic
def receptionner_commande(commande, lignes_reception, utilisateur=None, notes=""):
    """Enregistre une réception (totale ou partielle) et augmente le stock.

    ``lignes_reception`` : liste de dictionnaires avec les clés
    ``ligne_achat``, ``quantite``, ``numero_lot``, ``date_peremption`` et
    ``prix_unitaire``. Les quantités nulles sont ignorées.

    RG04 : la commande seule n'augmente pas le stock.
    RG05 : la réception validée augmente le stock une seule fois.
    """
    commande = CommandeAchat.objects.select_for_update().get(pk=commande.pk)
    if not commande.peut_etre_receptionnee:
        raise OperationRefusee(
            "Cette commande ne peut pas être réceptionnée dans son statut actuel."
        )

    lignes_valides = []
    for item in lignes_reception:
        quantite = int(item.get("quantite") or 0)
        if quantite <= 0:
            continue
        ligne_achat = item["ligne_achat"]
        if ligne_achat.commande_id != commande.pk:
            raise OperationRefusee("Une ligne de réception ne correspond pas à la commande.")
        ligne_achat = LigneAchat.objects.select_for_update().get(pk=ligne_achat.pk)
        if quantite > ligne_achat.quantite_restante:
            raise OperationRefusee(
                f"Pour {ligne_achat.medicament}, la quantité reçue ({quantite}) dépasse "
                f"le restant dû ({ligne_achat.quantite_restante})."
            )
        numero_lot = (item.get("numero_lot") or "").strip()
        if not numero_lot:
            raise OperationRefusee(f"Le numéro de lot est obligatoire pour {ligne_achat.medicament}.")
        date_peremption = item.get("date_peremption")
        if not date_peremption:
            raise OperationRefusee(f"La date de péremption est obligatoire pour {ligne_achat.medicament}.")
        if isinstance(date_peremption, str):
            try:
                date_peremption = date.fromisoformat(date_peremption)
            except ValueError:
                raise OperationRefusee("La date de péremption est invalide.")
        if date_peremption < timezone.localdate():
            raise OperationRefusee(
                f"Le lot {numero_lot} de {ligne_achat.medicament} est déjà périmé : "
                "réception refusée."
            )
        prix_unitaire = item.get("prix_unitaire")
        if prix_unitaire is None:
            prix_unitaire = ligne_achat.prix_achat_unitaire
        if prix_unitaire < 0:
            raise OperationRefusee("Le prix unitaire ne peut pas être négatif.")
        lignes_valides.append(
            {
                "ligne_achat": ligne_achat,
                "quantite": quantite,
                "numero_lot": numero_lot,
                "date_peremption": date_peremption,
                "prix_unitaire": prix_unitaire,
            }
        )

    if not lignes_valides:
        raise OperationRefusee("Veuillez saisir au moins une quantité reçue.")

    reception = ReceptionAchat.objects.create(
        commande=commande,
        utilisateur=utilisateur,
        notes=notes,
    )

    for item in lignes_valides:
        ligne_achat = item["ligne_achat"]
        lot = receptionner_lot(
            medicament=ligne_achat.medicament,
            numero_lot=item["numero_lot"],
            date_peremption=item["date_peremption"],
            quantite=item["quantite"],
            prix_achat=item["prix_unitaire"],
            fournisseur=commande.fournisseur,
            utilisateur=utilisateur,
            reference=reception.numero,
        )
        LigneReception.objects.create(
            reception=reception,
            ligne_achat=ligne_achat,
            lot=lot,
            quantite=item["quantite"],
            numero_lot=item["numero_lot"],
            date_peremption=item["date_peremption"],
            prix_unitaire=item["prix_unitaire"],
        )
        ligne_achat.quantite_recue += item["quantite"]
        ligne_achat.save(update_fields=["quantite_recue"])

    commande.recalculer_statut()
    return reception
