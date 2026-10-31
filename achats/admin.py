"""Administration des commandes et réceptions d'achat."""
from django.contrib import admin

from achats.models import CommandeAchat, LigneAchat, LigneReception, ReceptionAchat


class LigneAchatInline(admin.TabularInline):
    model = LigneAchat
    extra = 0
    autocomplete_fields = ["medicament"]
    readonly_fields = ("quantite_recue", "sous_total_affiche")

    @admin.display(description="Sous-total")
    def sous_total_affiche(self, obj):
        return obj.sous_total


class LigneReceptionInline(admin.TabularInline):
    model = LigneReception
    extra = 0
    autocomplete_fields = ["ligne_achat", "lot"]
    readonly_fields = ("sous_total_affiche",)

    @admin.display(description="Sous-total")
    def sous_total_affiche(self, obj):
        return obj.sous_total


@admin.register(CommandeAchat)
class CommandeAchatAdmin(admin.ModelAdmin):
    list_display = (
        "numero",
        "fournisseur",
        "statut",
        "date_creation",
        "date_commande",
        "utilisateur",
    )
    list_filter = ("statut", "date_creation", "fournisseur")
    search_fields = ("numero", "fournisseur__nom", "notes")
    autocomplete_fields = ["fournisseur", "utilisateur"]
    readonly_fields = ("numero", "date_creation", "date_modification", "date_commande")
    date_hierarchy = "date_creation"
    inlines = [LigneAchatInline]
    list_select_related = ("fournisseur", "utilisateur")


@admin.register(LigneAchat)
class LigneAchatAdmin(admin.ModelAdmin):
    list_display = (
        "commande",
        "medicament",
        "quantite_commandee",
        "quantite_recue",
        "prix_achat_unitaire",
        "sous_total",
    )
    list_filter = ("commande__statut",)
    search_fields = ("commande__numero", "medicament__nom")
    autocomplete_fields = ["commande", "medicament"]
    list_select_related = ("commande", "medicament")


@admin.register(ReceptionAchat)
class ReceptionAchatAdmin(admin.ModelAdmin):
    list_display = ("numero", "commande", "date_reception", "utilisateur")
    list_filter = ("date_reception", "commande__fournisseur")
    search_fields = ("numero", "commande__numero", "commande__fournisseur__nom")
    autocomplete_fields = ["commande", "utilisateur"]
    readonly_fields = ("numero", "date_reception")
    date_hierarchy = "date_reception"
    inlines = [LigneReceptionInline]
    list_select_related = ("commande__fournisseur", "utilisateur")


@admin.register(LigneReception)
class LigneReceptionAdmin(admin.ModelAdmin):
    list_display = (
        "reception",
        "ligne_achat",
        "numero_lot",
        "date_peremption",
        "quantite",
        "prix_unitaire",
        "sous_total",
    )
    list_filter = ("date_peremption",)
    search_fields = (
        "reception__numero",
        "numero_lot",
        "ligne_achat__medicament__nom",
    )
    autocomplete_fields = ["reception", "ligne_achat", "lot"]
    list_select_related = ("reception", "ligne_achat__medicament", "lot")
