"""Filtres de gabarit PharmaGest."""
from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def montant(valeur):
    """Formate 12500.5 → « 12 500,50 » (sans devise)."""
    try:
        valeur = Decimal(valeur or 0)
    except (InvalidOperation, TypeError, ValueError):
        return valeur
    entier, _, decimales = f"{valeur:.2f}".partition(".")
    try:
        entier = f"{int(entier):,}".replace(",", "\u202f")
    except ValueError:
        return valeur
    return f"{entier},{decimales}"


@register.filter
def signe_quantite(valeur):
    try:
        valeur = int(valeur)
    except (TypeError, ValueError):
        return valeur
    return f"+{valeur}" if valeur > 0 else str(valeur)


@register.filter
def pourcentage(valeur, total):
    try:
        valeur = Decimal(valeur or 0)
        total = Decimal(total or 0)
        if total == 0:
            return 0
        return round(float(valeur * 100 / total), 1)
    except (InvalidOperation, TypeError, ValueError, ZeroDivisionError):
        return 0


@register.filter
def classe_stock(medicament):
    if getattr(medicament, "est_en_rupture", False):
        return "danger"
    if getattr(medicament, "est_en_alerte", False):
        return "warning"
    return "success"


@register.simple_tag(takes_context=True)
def parametres_url(context, **kwargs):
    """Construit une query string en conservant les filtres existants."""
    request = context.get("request")
    params = request.GET.copy() if request else {}
    for cle, valeur in kwargs.items():
        if valeur in (None, ""):
            params.pop(cle, None)
        else:
            params[cle] = valeur
    return params.urlencode()
