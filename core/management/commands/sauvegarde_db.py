"""Commande de sauvegarde cohérente de la base de données.

Pour SQLite, utilise l'API de sauvegarde en ligne de ``sqlite3`` : le fichier
produit est cohérent même si l'application est en cours d'utilisation.
Pour PostgreSQL, délègue à ``pg_dump`` s'il est installé.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


def _horodatage() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _taille_lisible(octets: int) -> str:
    if octets < 1024:
        return f"{octets} octets"
    if octets < 1024 * 1024:
        return f"{octets / 1024:.1f} Ko"
    return f"{octets / (1024 * 1024):.2f} Mo"


class Command(BaseCommand):
    help = (
        "Crée une sauvegarde cohérente de la base de données dans BACKUP_DIR "
        "(ou à l'emplacement indiqué par --sortie)."
    )
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument(
            "--sortie",
            dest="sortie",
            metavar="CHEMIN",
            help=(
                "Fichier de destination explicite. Par défaut : "
                "backups/pharmagest_AAAAMMJJ_HHMMSS.sqlite3 (SQLite) ou .sql (PostgreSQL)."
            ),
        )

    def handle(self, *args, **options):
        db = settings.DATABASES["default"]
        moteur = db.get("ENGINE", "")
        dossier = Path(settings.BACKUP_DIR)
        dossier.mkdir(parents=True, exist_ok=True)

        if "sqlite3" in moteur:
            destination = self._sauvegarder_sqlite(db, options.get("sortie"), dossier)
        elif "postgresql" in moteur:
            destination = self._sauvegarder_postgresql(db, options.get("sortie"), dossier)
        else:
            raise CommandError(
                "Moteur de base de données non pris en charge pour la sauvegarde : "
                f"« {moteur} ». Utilisez l'outil natif du moteur (mysqldump, etc.)."
            )

        taille = destination.stat().st_size
        self.stdout.write(
            self.style.SUCCESS(
                f"Sauvegarde créée : {destination} ({_taille_lisible(taille)})"
            )
        )
        self.stdout.write(
            "Conservez ce fichier hors du serveur (disque externe, stockage chiffré) "
            "et testez régulièrement sa restauration."
        )
        return str(destination)

    # ------------------------------------------------------------------
    # SQLite
    # ------------------------------------------------------------------
    def _sauvegarder_sqlite(self, db, sortie, dossier) -> Path:
        source = Path(db.get("NAME") or "").expanduser()
        try:
            source = source.resolve()
        except OSError:
            source = Path(db.get("NAME"))

        if not source.is_file():
            raise CommandError(
                f"Base SQLite introuvable : {source}. Vérifiez DATABASES dans "
                "config/settings.py et exécutez les migrations."
            )

        if sortie:
            destination = Path(sortie).expanduser()
            if not destination.is_absolute():
                destination = (Path.cwd() / destination).resolve()
        else:
            destination = dossier / f"pharmagest_{_horodatage()}.sqlite3"

        if destination == source:
            raise CommandError(
                "Le fichier de destination ne peut pas être la base de données "
                "elle-même. Choisissez un autre chemin."
            )
        if destination.exists():
            raise CommandError(
                f"Le fichier de destination existe déjà : {destination}. "
                "Choisissez un autre nom ou supprimez-le manuellement."
            )

        destination.parent.mkdir(parents=True, exist_ok=True)

        connexion_source = None
        connexion_cible = None
        try:
            connexion_source = sqlite3.connect(str(source))
            connexion_cible = sqlite3.connect(str(destination))
            connexion_source.backup(connexion_cible)
            resultat = connexion_cible.execute("PRAGMA integrity_check").fetchone()
            if not resultat or resultat[0] != "ok":
                raise CommandError(
                    "La sauvegarde a été créée mais le contrôle d'intégrité SQLite "
                    f"a échoué : {resultat[0] if resultat else 'aucun résultat'}."
                )
        except sqlite3.Error as erreur:
            if destination.exists():
                destination.unlink(missing_ok=True)
            raise CommandError(f"Échec de la sauvegarde SQLite : {erreur}") from erreur
        finally:
            if connexion_cible is not None:
                connexion_cible.close()
            if connexion_source is not None:
                connexion_source.close()

        # Restreint l'accès au fichier de sauvegarde (données de santé).
        try:
            os.chmod(destination, 0o600)
        except OSError:
            pass
        return destination

    # ------------------------------------------------------------------
    # PostgreSQL
    # ------------------------------------------------------------------
    def _sauvegarder_postgresql(self, db, sortie, dossier) -> Path:
        pg_dump = shutil.which("pg_dump")
        if not pg_dump:
            raise CommandError(
                "pg_dump est introuvable dans le PATH. Installez le client PostgreSQL "
                "ou utilisez une sauvegarde managée par l'hébergeur."
            )

        if sortie:
            destination = Path(sortie).expanduser()
            if not destination.is_absolute():
                destination = (Path.cwd() / destination).resolve()
        else:
            destination = dossier / f"pharmagest_{_horodatage()}.sql"

        if destination.exists():
            raise CommandError(
                f"Le fichier de destination existe déjà : {destination}. "
                "Choisissez un autre nom ou supprimez-le manuellement."
            )
        destination.parent.mkdir(parents=True, exist_ok=True)

        commande = [
            pg_dump,
            "--no-password",
            "--format=plain",
            "--clean",
            "--if-exists",
            "--host", str(db.get("HOST") or "localhost"),
            "--port", str(db.get("PORT") or "5432"),
            "--username", str(db.get("USER") or ""),
            "--dbname", str(db.get("NAME") or ""),
            "--file", str(destination),
        ]
        environnement = os.environ.copy()
        if db.get("PASSWORD"):
            environnement["PGPASSWORD"] = str(db["PASSWORD"])

        try:
            subprocess.run(commande, check=True, env=environnement)
        except FileNotFoundError as erreur:
            raise CommandError("pg_dump est introuvable : " + str(erreur)) from erreur
        except subprocess.CalledProcessError as erreur:
            destination.unlink(missing_ok=True)
            raise CommandError(
                "La sauvegarde PostgreSQL a échoué (code "
                f"{erreur.returncode}). Vérifiez les identifiants et les droits "
                "de l'utilisateur de la base."
            ) from erreur

        try:
            os.chmod(destination, 0o600)
        except OSError:
            pass
        return destination
