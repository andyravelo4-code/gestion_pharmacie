from django.contrib import admin

from core.models import JournalAudit, ParametrePharmacie


@admin.register(ParametrePharmacie)
class ParametreAdmin(admin.ModelAdmin):
    list_display = ["nom", "telephone", "email", "devise", "seuil_peremption_jours"]

    def has_add_permission(self, request):
        return not ParametrePharmacie.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(JournalAudit)
class JournalAuditAdmin(admin.ModelAdmin):
    list_display = ["date", "utilisateur", "action", "module", "description"]
    list_filter = ["action", "module", "date"]
    search_fields = ["description", "details", "utilisateur__username"]
    readonly_fields = [
        "utilisateur",
        "action",
        "module",
        "objet_id",
        "description",
        "details",
        "adresse_ip",
        "date",
    ]
    date_hierarchy = "date"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
