"""Administration Django des médicaments et catégories."""
from django.contrib import admin

from medicaments.models import Categorie, Medicament


@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    list_display = ("nom", "nombre_medicaments", "date_creation", "date_modification")
    search_fields = ("nom", "description")
    readonly_fields = ("date_creation", "date_modification")
    ordering = ("nom",)

    @admin.display(description="Médicaments")
    def nombre_medicaments(self, obj):
        return obj.medicaments.count()


@admin.register(Medicament)
class MedicamentAdmin(admin.ModelAdmin):
    list_display = (
        "nom",
        "dosage",
        "categorie",
        "forme",
        "prix_vente",
        "seuil_alerte",
        "statut",
        "date_modification",
    )
    search_fields = ("nom", "denomination_generique", "code_barres", "laboratoire")
    list_filter = ("statut", "categorie", "forme", "date_creation")
    list_select_related = ("categorie",)
    readonly_fields = ("date_creation", "date_modification")
    ordering = ("nom",)
    fieldsets = (
        (
            "Identification",
            {
                "fields": (
                    "nom",
                    "denomination_generique",
                    "categorie",
                    "forme",
                    "dosage",
                    "laboratoire",
                    "code_barres",
                    "photo",
                )
            },
        ),
        (
            "Prix et stock",
            {"fields": ("prix_achat", "prix_vente", "seuil_alerte")},
        ),
        (
            "Suivi",
            {"fields": ("statut", "date_creation", "date_modification")},
        ),
    )
