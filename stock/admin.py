"""Administration des lots, mouvements et inventaires."""
from django.contrib import admin

from stock.models import Inventaire, LigneInventaire, LotStock, MouvementStock


class LigneInventaireInline(admin.TabularInline):
    model = LigneInventaire
    extra = 0
    autocomplete_fields = ["lot"]
    readonly_fields = ["ecart_affiche"]

    @admin.display(description="Écart")
    def ecart_affiche(self, obj):
        return obj.ecart


@admin.register(LotStock)
class LotStockAdmin(admin.ModelAdmin):
    list_display = (
        "medicament",
        "numero_lot",
        "date_peremption",
        "quantite",
        "prix_achat",
        "fournisseur",
        "bloque",
    )
    list_filter = ("bloque", "date_peremption", "fournisseur")
    search_fields = ("numero_lot", "medicament__nom", "medicament__code_barres")
    autocomplete_fields = ["medicament", "fournisseur"]
    date_hierarchy = "date_peremption"
    readonly_fields = ("date_creation", "date_modification", "date_reception")
    list_select_related = ("medicament", "fournisseur")


@admin.register(MouvementStock)
class MouvementStockAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "type_mouvement",
        "medicament",
        "lot",
        "quantite",
        "reference",
        "utilisateur",
    )
    list_filter = ("type_mouvement", "date")
    search_fields = (
        "medicament__nom",
        "reference",
        "lot__numero_lot",
        "motif",
    )
    autocomplete_fields = ["medicament", "lot", "utilisateur"]
    date_hierarchy = "date"
    readonly_fields = ("date",)
    list_select_related = ("medicament", "lot", "utilisateur")


@admin.register(Inventaire)
class InventaireAdmin(admin.ModelAdmin):
    list_display = ("numero", "date_creation", "utilisateur", "statut", "date_validation")
    list_filter = ("statut", "date_creation")
    search_fields = ("numero", "notes")
    autocomplete_fields = ["utilisateur"]
    readonly_fields = ("numero", "date_creation", "date_validation")
    inlines = [LigneInventaireInline]


@admin.register(LigneInventaire)
class LigneInventaireAdmin(admin.ModelAdmin):
    list_display = ("inventaire", "lot", "quantite_theorique", "quantite_comptee", "ecart")
    list_filter = ("inventaire__statut",)
    search_fields = ("inventaire__numero", "lot__numero_lot", "lot__medicament__nom")
    autocomplete_fields = ["inventaire", "lot"]
    list_select_related = ("inventaire", "lot__medicament")
