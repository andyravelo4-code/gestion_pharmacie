"""Validateurs personnalisés (images, quantités)."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible


@deconstructible
class ValiderImage:
    """Vérifie la taille et le contenu réel d'une image téléversée.

    La vérification par Pillow empêche de renommer un fichier arbitraire en .jpg.
    """

    def __init__(self, max_octets=None):
        self.max_octets = max_octets or getattr(settings, "MAX_IMAGE_SIZE", 3 * 1024 * 1024)

    def __call__(self, fichier):
        if not fichier:
            return
        taille = getattr(fichier, "size", 0)
        if taille and taille > self.max_octets:
            limite = self.max_octets // (1024 * 1024)
            raise ValidationError(f"L'image ne doit pas dépasser {limite} Mo.")
        try:
            from PIL import Image

            fichier.seek(0)
            image = Image.open(fichier)
            image.verify()
            format_image = (image.format or "").upper()
            if format_image not in {"JPEG", "PNG", "WEBP", "GIF"}:
                raise ValidationError("Format d'image non pris en charge (JPEG, PNG, WEBP ou GIF).")
        except ValidationError:
            raise
        except Exception:
            raise ValidationError("Le fichier téléversé n'est pas une image valide.")
        finally:
            try:
                fichier.seek(0)
            except Exception:
                pass

    def __eq__(self, other):
        return isinstance(other, ValiderImage) and self.max_octets == other.max_octets


def valider_quantite_positive(valeur):
    if valeur is None or valeur <= 0:
        raise ValidationError("La quantité doit être supérieure à zéro.")
