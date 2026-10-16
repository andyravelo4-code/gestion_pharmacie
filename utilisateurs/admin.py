from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm
from django.utils.html import format_html

from utilisateurs.models import Role, Utilisateur


class AjoutUtilisateurAdmin(UserCreationForm):
    roles = forms.ModelMultipleChoiceField(
        label="Rôles",
        queryset=Role.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
    )

    class Meta(UserCreationForm.Meta):
        model = Utilisateur
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "telephone",
            "roles",
        )


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ["nom", "code", "ordre", "nombre_utilisateurs"]
    search_fields = ["nom", "code"]
    ordering = ["ordre"]

    @admin.display(description="Utilisateurs")
    def nombre_utilisateurs(self, obj):
        return obj.utilisateurs.count()


@admin.register(Utilisateur)
class UtilisateurAdmin(BaseUserAdmin):
    add_form = AjoutUtilisateurAdmin
    list_display = ["username", "nom_complet", "email", "roles_affiches", "is_active", "last_login"]
    list_filter = ["is_active", "is_staff", "roles"]
    search_fields = ["username", "first_name", "last_name", "email", "telephone"]
    ordering = ["last_name", "first_name"]
    filter_horizontal = ["roles", "groups", "user_permissions"]
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Profil pharmaceutique", {"fields": ("telephone", "adresse", "roles")}),
    )
    add_fieldsets = (
        (
            "Compte",
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "password1",
                    "password2",
                    "first_name",
                    "last_name",
                    "email",
                    "telephone",
                    "roles",
                ),
            },
        ),
    )

    @admin.display(description="Rôles")
    def roles_affiches(self, obj):
        noms = [role.nom for role in obj.roles.all()]
        return format_html(", ".join(noms)) if noms else "—"
