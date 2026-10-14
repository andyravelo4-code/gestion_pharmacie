"""Fonctions utilitaires partagées par les applications PharmaGest."""
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone


def generer_numero(prefixe, modele, champ="numero", longueur=4):
    """Génère un numéro séquentiel lisible du type ``VTE-20261117-0001``.

    Le champ ciblé doit être unique. En cas de collision concurrente,
    l'insertion échoue grâce à la contrainte d'unicité (aucun doublon silencieux).
    """
    aujourdhui = timezone.localdate().strftime("%Y%m%d")
    base = f"{prefixe}-{aujourdhui}-"
    valeurs = (
        modele.objects.filter(**{f"{champ}__startswith": base})
        .values_list(champ, flat=True)
    )
    sequence = 0
    for valeur in valeurs:
        try:
            sequence = max(sequence, int(str(valeur).rsplit("-", 1)[1]))
        except (ValueError, IndexError):
            continue
    return f"{base}{sequence + 1:0{longueur}d}"


def aujourdhui():
    return timezone.localdate()


def dans_jours(nombre):
    return timezone.localdate() + timedelta(days=nombre)


def quantite_apres(quantite, delta):
    """Retourne la nouvelle quantité ou lève une erreur si elle devient négative."""
    nouvelle = quantite + delta
    if nouvelle < 0:
        raise ValueError("La quantité en stock ne peut pas devenir négative (RG07).")
    return nouvelle


def format_montant(valeur, devise="Ar"):
    """Formate un montant à la française : 12 500,00 Ar."""
    if valeur is None:
        valeur = Decimal("0")
    valeur = Decimal(valeur)
    entier, _, decimales = f"{valeur:.2f}".partition(".")
    entier = f"{int(entier):,}".replace(",", " ")
    return f"{entier},{decimales} {devise}".strip()


def arrondir_montant(valeur):
    return Decimal(valeur).quantize(Decimal("0.01"))


def journaliser(request, action, module, description, objet=None, objet_id="", details=""):
    """Enregistre une entrée d'audit sans faire échouer l'opération métier."""
    from core.models import JournalAudit

    utilisateur = None
    if request is not None and getattr(request, "user", None) and request.user.is_authenticated:
        utilisateur = request.user
    adresse_ip = None
    if request is not None:
        adresse_ip = request.META.get("REMOTE_ADDR")
    try:
        return JournalAudit.objects.create(
            utilisateur=utilisateur,
            action=action,
            module=module,
            objet_id=str(objet_id or (getattr(objet, "pk", "") or "")),
            description=description[:255],
            details=details,
            adresse_ip=adresse_ip,
        )
    except Exception:  # pragma: no cover - l'audit ne doit pas bloquer le métier
        return None


def executer_atomique(fonction):
    """Petit raccourci lisible pour les services métier."""

    @transaction.atomic
    def enveloppe(*args, **kwargs):
        return fonction(*args, **kwargs)

    return enveloppe
