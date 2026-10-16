from django.apps import AppConfig


class UtilisateursConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "utilisateurs"
    verbose_name = "Utilisateurs et rôles"

    def ready(self):
        import utilisateurs.signals  # noqa: F401
