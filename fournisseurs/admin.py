"""Administration Django des fournisseurs."""
from django.contrib import admin

from fournisseurs.models import Fournisseur


@admin.register(Fournisseur)
class FournisseurAdmin(admin.ModelAdmin):
    list_display = (
        "nom",
        "contact_principal",
        "telephone",
        "email",
        "numero_fiscal",
        "actif",
        "date_creation",
    )
    search_fields = ("nom", "telephone", "email", "numero_fiscal", "contact_principal")
    list_filter = ("actif", "date_creation")
    readonly_fields = ("date_creation", "date_modification")
    ordering = ("nom",)
