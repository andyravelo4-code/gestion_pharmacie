from django.contrib import admin

from ventes.models import LigneVente, Paiement, RetourVente, Vente


class LigneVenteInline(admin.TabularInline):
    model = LigneVente
    extra = 0
    can_delete = False
    readonly_fields = ["medicament", "lot", "quantite", "prix_unitaire", "sous_total"]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Vente)
class VenteAdmin(admin.ModelAdmin):
    list_display = ["numero", "date_vente", "client", "utilisateur", "montant_total", "statut"]
    list_filter = ["statut", "date_vente"]
    search_fields = ["numero", "client__nom", "utilisateur__username"]
    inlines = [LigneVenteInline]
    readonly_fields = [
        "numero",
        "date_vente",
        "utilisateur",
        "montant_total",
        "cle_idempotence",
    ]
    date_hierarchy = "date_vente"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Paiement)
class PaiementAdmin(admin.ModelAdmin):
    list_display = ["vente", "montant", "mode", "statut", "reference", "date_paiement"]
    list_filter = ["mode", "statut"]
    search_fields = ["vente__numero", "reference"]
    readonly_fields = ["date_paiement"]

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(RetourVente)
class RetourVenteAdmin(admin.ModelAdmin):
    list_display = ["numero", "vente", "type_retour", "date_retour", "montant_rembourse"]
    list_filter = ["type_retour", "date_retour"]
    search_fields = ["numero", "vente__numero", "motif"]
    readonly_fields = ["numero", "date_retour"]

    def has_delete_permission(self, request, obj=None):
        return False
