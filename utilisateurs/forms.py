"""Formulaires des comptes utilisateurs et de l'authentification."""
from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
)
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from core.forms import FormulaireModeleStyle, FormulaireStyleMixin
from utilisateurs.models import Role, Utilisateur


class FormulaireConnexion(FormulaireStyleMixin, AuthenticationForm):
    username = forms.CharField(
        label="Identifiant",
        widget=forms.TextInput(attrs={"placeholder": "Votre identifiant", "autofocus": True}),
    )
    password = forms.CharField(
        label="Mot de passe",
        strip=False,
        widget=forms.PasswordInput(attrs={"placeholder": "Votre mot de passe"}),
    )

    error_messages = {
        "invalid_login": "Identifiant ou mot de passe incorrect. Vérifiez également que votre compte est actif.",
        "inactive": "Ce compte est désactivé. Contactez l'administrateur.",
    }


class FormulaireUtilisateur(FormulaireModeleStyle):
    roles = forms.ModelMultipleChoiceField(
        label="Rôles et fonctions",
        queryset=Role.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        help_text="Un utilisateur peut cumuler plusieurs fonctions.",
    )
    password1 = forms.CharField(
        label="Mot de passe",
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="8 caractères minimum, non entièrement numérique, pas trop courant.",
    )
    password2 = forms.CharField(
        label="Confirmation du mot de passe",
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    class Meta:
        model = Utilisateur
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "telephone",
            "adresse",
            "is_active",
            "roles",
        ]
        labels = {
            "first_name": "Prénom",
            "last_name": "Nom",
            "is_active": "Compte activé",
            "username": "Identifiant de connexion",
        }
        widgets = {
            "username": forms.TextInput(attrs={"autocomplete": "off"}),
            "adresse": forms.TextInput(),
        }
        help_texts = {
            "username": "Lettres, chiffres et caractères @/./+/-/_ uniquement.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        creation = not self.instance or not self.instance.pk
        if creation:
            self.fields["password1"].required = True
            self.fields["password2"].required = True
        else:
            self.fields["password1"].label = "Nouveau mot de passe (facultatif)"
            self.fields["password2"].label = "Confirmer le nouveau mot de passe"
            self.instance.roles.all()  # préchargement
            self.initial["roles"] = self.instance.roles.all()

    def clean(self):
        donnees = super().clean()
        mot_de_passe1 = donnees.get("password1")
        mot_de_passe2 = donnees.get("password2")
        if mot_de_passe1 or mot_de_passe2:
            if mot_de_passe1 != mot_de_passe2:
                self.add_error("password2", "Les deux mots de passe ne correspondent pas.")
            elif mot_de_passe1:
                try:
                    validate_password(mot_de_passe1, self.instance)
                except ValidationError as erreur:
                    self.add_error("password1", erreur)
        return donnees

    def clean_roles(self):
        roles = self.cleaned_data.get("roles")
        if not roles:
            raise ValidationError("Au moins un rôle doit être attribué à l'utilisateur.")
        return roles

    def save(self, commit=True):
        utilisateur = super().save(commit=False)
        mot_de_passe = self.cleaned_data.get("password1")
        if mot_de_passe:
            utilisateur.set_password(mot_de_passe)
        if commit:
            utilisateur.save()
            self.save_m2m()
        return utilisateur


class FormulaireProfil(FormulaireModeleStyle):
    class Meta:
        model = Utilisateur
        fields = ["first_name", "last_name", "email", "telephone", "adresse"]
        labels = {
            "first_name": "Prénom",
            "last_name": "Nom",
            "telephone": "Téléphone",
            "adresse": "Adresse",
        }
        widgets = {"adresse": forms.TextInput()}


class FormulaireMotDePasse(FormulaireStyleMixin, PasswordChangeForm):
    pass


class FormulaireReinitialisation(FormulaireStyleMixin, PasswordResetForm):
    email = forms.EmailField(
        label="Adresse e-mail du compte",
        max_length=254,
        widget=forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "vous@exemple.mg"}),
    )


class FormulaireNouveauMotDePasse(FormulaireStyleMixin, SetPasswordForm):
    pass
