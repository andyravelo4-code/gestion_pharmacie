"""Context processors globaux : paramètres pharmacie et permissions d'affichage."""
from core.models import ParametrePharmacie
from utilisateurs.permissions import (
    ADMIN,
    GESTION_ACHATS,
    GESTION_MEDICAMENTS,
    GESTION_STOCK,
    RESPONSABLE_GESTION,
    VENTES,
)


def pharmacie(request):
    parametres = ParametrePharmacie.get_solo()
    return {
        "pharmacie": parametres,
        "devise": parametres.devise,
    }
