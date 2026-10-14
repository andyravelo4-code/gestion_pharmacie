"""Exceptions métier compréhensibles par l'utilisateur."""


class OperationRefusee(ValueError):
    """Une règle de gestion empêche l'opération."""


class StockInsuffisant(OperationRefusee):
    """La quantité demandée dépasse le stock disponible (RG07)."""


class LotNonDelivrable(OperationRefusee):
    """Le lot est périmé, bloqué ou vide (RG08)."""


class DoubleValidation(OperationRefusee):
    """L'opération a déjà été validée (protection contre les doublons)."""
