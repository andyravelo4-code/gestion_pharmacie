"""Restauration d'une sauvegarde SQLite PharmaGest.

La commande refuse de remplacer la base active sans l'option ``--force`` et
crée systématiquement une sauvegarde de sécurité avant remplacement. Elle
ferme aussi les connexions Django ouvertes : arrêtez tout de même le serveur
web avant de restaurer une base de production.

La restauration PostgreSQL n'est pas automatisée ici : utilisez ``psql`` ou
l'outil fourni par l'hébergeur.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections


def _horodatage() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ouvrir_en_lecture(chemin: Path) -> sqlite3.Connection:
    """Ouvre une base SQLite en lecture seule (URI file:)."""
    return sqlite3.connect(f"file:{quote(str(chemin))}?mode=ro", uri=True)


def _tables(connexion: sqlite3.Connection) -> set[str]:
    lignes = connexion.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    return {ligne[0] for ligne in lignes}


def _verifier_base_pharmagest(chemin: Path) -> None:
    """Vérifie que le fichier est une base SQLite PharmaGest exploitable."""
    try:
        connexion = _ouvrir_en_lecture(chemin)
    except sqlite3.Error as erreur:
        raise CommandError(f"Impossible d'ouvrir le fichier SQLite : {erreur}") from erreur

    try:
        # Un fichier vide ou un simple fichier texte produit une erreur ici.
        try:
            noms = _tables(connexion)
        except sqlite3.DatabaseError as erreur:
            raise CommandError(
                f"Le fichier ne semble pas être une base SQLite valide : {erreur}"
            ) from erreur

        if "utilisateurs_utilisateur" not in noms and "django_migrations" not in noms:
            raise CommandError(
                "Ce fichier n'est pas reconnu comme une base PharmaGest : "
                "les tables « utilisateurs_utilisateur » ou « django_migrations » "
                "sont absentes. Restauration annulée."
            )

        try:
            resultat = connexion.execute("PRAGMA integrity_check").fetchone()
        except sqlite3.DatabaseError as erreur:
            raise CommandError(f"Contrôle d'intégrité impossible : {erreur}") from erreur
        if not resultat or resultat[0] != "ok":
            raise CommandError(
                "Le contrôle d'intégrité SQLite a échoué : "
                f"{resultat[0] if resultat else 'aucun résultat'}. Restauration annulée."
            )

        if "django_migrations" in noms:
            try:
                nombre = connexion.execute(
                    "SELECT COUNT(*) FROM django_migrations"
                ).fetchone()[0]
            except sqlite3.DatabaseError:
                nombre = 0
            if nombre == 0:
                raise CommandError(
                    "La sauvegarde ne contient aucune migration appliquée. "
                    "Restauration annulée : utilisez une sauvegarde complète."
                )
    finally:
        connexion.close()


def _sauvegarde_de_securite(base: Path, dossier: Path) -> Path:
    """Copie cohérente de la base active avant remplacement."""
    dossier.mkdir(parents=True, exist_ok=True)
    destination = dossier / f"avant_restauration_{_horodatage()}.sqlite3"
    source = destination
    compteur = 1
    while destination.exists():
        destination = source.with_name(
            f"avant_restauration_{_horodatage()}_{compteur}.sqlite3"
        )
        compteur += 1

    source_connexion = sqlite3.connect(str(base))
    cible_connexion = sqlite3.connect(str(destination))
    try:
        source_connexion.backup(cible_connexion)
    except sqlite3.Error as erreur:
        destination.unlink(missing_ok=True)
        raise CommandError(
            f"Impossible de créer la sauvegarde de sécurité : {erreur}"
        ) from erreur
    finally:
        cible_connexion.close()
        source_connexion.close()

    try:
        os.chmod(destination, 0o600)
    except OSError:
        pass
    return destination


class Command(BaseCommand):
    help = (
        "Restaure une sauvegarde SQLite PharmaGest. Exige --force si la base "
        "active existe déjà et crée une sauvegarde de sécurité avant remplacement."
    )
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument(
            "fichier",
            help="Chemin du fichier de sauvegarde SQLite (.sqlite3) à restaurer.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help=(
                "Remplace la base active existante. Sans cette option, la commande "
                "refuse d'écraser une base déjà présente."
            ),
        )

    def handle(self, *args, **options):
        db = settings.DATABASES["default"]
        moteur = db.get("ENGINE", "")
        if "sqlite3" not in moteur:
            raise CommandError(
                "La restauration automatique n'est prise en charge que pour SQLite. "
                "Pour PostgreSQL, utilisez psql (ex. : psql -d pharmagest -f sauvegarde.sql) "
                "après avoir sauvegardé la base active."
            )

        source = Path(options["fichier"]).expanduser()
        if not source.is_absolute():
            source = (Path.cwd() / source).resolve()
        destination = Path(db.get("NAME") or "").expanduser()
        try:
            destination = destination.resolve()
        except OSError:
            destination = Path(db.get("NAME"))

        if not source.exists():
            raise CommandError(f"Fichier de sauvegarde introuvable : {source}")
        if not source.is_file():
            raise CommandError(f"Le chemin indiqué n'est pas un fichier : {source}")
        if source == destination:
            raise CommandError(
                "Le fichier à restaurer est la base active elle-même. "
                "Choisissez un autre fichier de sauvegarde."
            )

        self.stdout.write(f"Vérification de la sauvegarde : {source}")
        _verifier_base_pharmagest(source)
        self.stdout.write(self.style.SUCCESS("Sauvegarde valide (intégrité SQLite OK)."))

        if destination.exists():
            if not options["force"]:
                raise CommandError(
                    f"La base active existe déjà : {destination}. "
                    "Pour la remplacer, relancez la commande avec --force. "
                    "Une sauvegarde de sécurité sera alors créée automatiquement."
                )
            securite = _sauvegarde_de_securite(destination, Path(settings.BACKUP_DIR))
            self.stdout.write(
                self.style.WARNING(
                    f"Sauvegarde de sécurité créée avant remplacement : {securite}"
                )
            )

        # Ferme les connexions Django vers l'ancienne base avant de remplacer
        # le fichier. Le serveur web doit de préférence être arrêté.
        connections.close_all()
        destination.parent.mkdir(parents=True, exist_ok=True)

        temporaire = destination.with_name(destination.name + ".restauration.tmp")
        try:
            shutil.copy2(source, temporaire)
            os.replace(temporaire, destination)
        except OSError as erreur:
            temporaire.unlink(missing_ok=True)
            raise CommandError(f"Échec du remplacement de la base : {erreur}") from erreur

        # Les anciens fichiers WAL/SHM/journal ne correspondent plus à la base
        # restaurée : on les supprime pour éviter toute incohérence.
        for suffixe in ("-wal", "-shm", "-journal"):
            annexe = Path(str(destination) + suffixe)
            if annexe.exists():
                try:
                    annexe.unlink()
                except OSError:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Impossible de supprimer l'ancien fichier {annexe}."
                        )
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"Restauration terminée : {destination}\n"
                "Redémarrez le serveur, puis vérifiez avec « manage.py check » et "
                "« manage.py migrate --check ». Si la sauvegarde provient d'une "
                "version antérieure, appliquez les migrations nécessaires."
            )
        )
