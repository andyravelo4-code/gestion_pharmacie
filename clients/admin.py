"""Administration Django des clients."""
from django.contrib import admin

from clients.models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = (
        "nom_affichage",
        "telephone",
        "email",
        "adresse",
        "actif",
        "date_creation",
    )
    search_fields = ("nom", "telephone", "email", "adresse")
    list_filter = ("actif", "date_creation")
    readonly_fields = ("date_creation", "date_modification")
    ordering = ("nom", "telephone")

    @admin.display(description="Client")
    def nom_affichage(self, obj):
        return obj.nom_affichage
