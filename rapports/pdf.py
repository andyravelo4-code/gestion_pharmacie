"""Génération des documents PDF ReportLab de PharmaGest.

Aucune ressource distante n'est utilisée : les polices standard Helvetica et,
le cas échéant, le logo local de la pharmacie suffisent.
"""
import io
import os
from datetime import date, datetime
from decimal import Decimal
from functools import partial

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from core.models import ParametrePharmacie
from core.utils import format_montant

LARGEUR, HAUTEUR = A4
MARGE = 1.4 * cm
LARGEUR_CONTENU = LARGEUR - 2 * MARGE

VERT = colors.HexColor("#0f7a5a")
VERT_FONCE = colors.HexColor("#0a5a42")
VERT_CLAIR = colors.HexColor("#e7f5ef")
GRIS = colors.HexColor("#6c7a77")
GRIS_CLAIR = colors.HexColor("#f8fbfa")
BORDURE = colors.HexColor("#dfe7e4")
ROUGE = colors.HexColor("#b42318")
ORANGE = colors.HexColor("#b54708")

STYLE_NORMAL = ParagraphStyle(
    "normal", fontName="Helvetica", fontSize=8.5, leading=11, textColor=colors.HexColor("#1c2b27")
)
STYLE_PETIT = ParagraphStyle(
    "petit", fontName="Helvetica", fontSize=7.4, leading=9.4, textColor=colors.HexColor("#44534f")
)
STYLE_CELLULE = ParagraphStyle("cellule", fontName="Helvetica", fontSize=7.4, leading=9.2)
STYLE_CELLULE_DROITE = ParagraphStyle(
    "cellule_droite", parent=STYLE_CELLULE, alignment=TA_RIGHT
)
STYLE_CELLULE_CENTRE = ParagraphStyle(
    "cellule_centre", parent=STYLE_CELLULE, alignment=1
)
STYLE_ENTETE = ParagraphStyle(
    "entete",
    fontName="Helvetica-Bold",
    fontSize=7.2,
    leading=8.8,
    textColor=colors.white,
)
STYLE_ENTETE_DROITE = ParagraphStyle("entete_droite", parent=STYLE_ENTETE, alignment=TA_RIGHT)
STYLE_SECTION = ParagraphStyle(
    "section",
    fontName="Helvetica-Bold",
    fontSize=9.5,
    leading=12,
    textColor=VERT_FONCE,
    spaceBefore=9,
    spaceAfter=4,
)
STYLE_LABEL = ParagraphStyle(
    "label",
    fontName="Helvetica-Bold",
    fontSize=7.3,
    leading=9,
    textColor=GRIS,
)
STYLE_VALEUR = ParagraphStyle(
    "valeur", fontName="Helvetica", fontSize=8.2, leading=10.2
)
STYLE_TOTAL_LABEL = ParagraphStyle(
    "total_label", fontName="Helvetica-Bold", fontSize=8.8, leading=11, alignment=TA_RIGHT
)
STYLE_TOTAL_VALEUR = ParagraphStyle(
    "total_valeur",
    fontName="Helvetica-Bold",
    fontSize=9.2,
    leading=11,
    alignment=TA_RIGHT,
    textColor=VERT_FONCE,
)


# ---------------------------------------------------------------------------
# Texte et formats
# ---------------------------------------------------------------------------
_REMPLACEMENTS = {
    "\u202f": " ",
    "\u00a0": " ",
    "\u2009": " ",
    "’": "'",
    "‘": "'",
    "“": '"',
    "”": '"',
    "–": "-",
    "—": "-",
    "…": "...",
    "€": "EUR",
    "œ": "oe",
    "Œ": "OE",
    "™": "(TM)",
}


def _texte(valeur):
    """Nettoie un texte pour les polices standard (WinAnsi/cp1252)."""
    if valeur is None:
        return ""
    texte = str(valeur)
    for source, cible in _REMPLACEMENTS.items():
        texte = texte.replace(source, cible)
    return texte.encode("cp1252", "replace").decode("cp1252")


def _p(valeur, style=STYLE_CELLULE):
    """Paragraphe sécurisé (échappe les caractères XML)."""
    texte = (
        _texte(valeur)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return Paragraph(texte, style)


def _montant(valeur, devise):
    return _texte(format_montant(valeur, devise))


def _date(valeur):
    if not valeur:
        return "—"
    if isinstance(valeur, datetime):
        return timezone.localtime(valeur).strftime("%d/%m/%Y %H:%M")
    if isinstance(valeur, date):
        return valeur.strftime("%d/%m/%Y")
    return _texte(valeur)


def _quantite(valeur):
    return f"{int(valeur or 0):,}".replace(",", " ")


# ---------------------------------------------------------------------------
# Métadonnées et en-tête/pied de page
# ---------------------------------------------------------------------------
def meta_document(pharmacie=None, titre="Document", numero="", date_texte=None):
    """Construit les métadonnées communes à tous les PDF."""
    pharmacie = pharmacie or ParametrePharmacie.get_solo()
    logo = None
    try:
        if pharmacie.logo and getattr(pharmacie.logo, "path", None):
            if os.path.exists(pharmacie.logo.path):
                logo = pharmacie.logo.path
    except (ValueError, OSError):
        logo = None
    return {
        "titre": _texte(titre),
        "numero": _texte(numero),
        "date": _texte(
            date_texte
            if date_texte is not None
            else timezone.localtime().strftime("%d/%m/%Y à %H:%M")
        ),
        "nom": _texte(pharmacie.nom),
        "adresse": _texte(pharmacie.adresse),
        "telephone": _texte(pharmacie.telephone),
        "email": _texte(pharmacie.email),
        "nif": _texte(pharmacie.numero_fiscal),
        "devise": _texte(pharmacie.devise or "Ar"),
        "mentions_legales": _texte(
            pharmacie.mentions_legales
            or "Document généré par PharmaGest. Mentions légales à adapter."
        ),
        "logo": logo,
    }


def _dessiner_entete(canv, doc, meta):
    canv.saveState()
    haut = HAUTEUR - 28
    x_gauche = MARGE
    logo = meta.get("logo")
    if logo:
        try:
            image = ImageReader(logo)
            largeur_image, hauteur_image = image.getSize()
            if largeur_image and hauteur_image:
                ratio = min((2.7 * cm) / largeur_image, (1.45 * cm) / hauteur_image)
                largeur = largeur_image * ratio
                hauteur = hauteur_image * ratio
                canv.drawImage(
                    logo,
                    MARGE,
                    haut - hauteur + 2,
                    width=largeur,
                    height=hauteur,
                    mask="auto",
                )
                x_gauche = MARGE + 2.7 * cm + 0.3 * cm
        except Exception:  # pragma: no cover - logo illisible
            x_gauche = MARGE

    canv.setFillColor(colors.HexColor("#132a26"))
    canv.setFont("Helvetica-Bold", 13)
    canv.drawString(x_gauche, haut, meta.get("nom", ""))

    canv.setFont("Helvetica", 7.4)
    canv.setFillColor(GRIS)
    y = haut - 12
    for ligne in (
        meta.get("adresse"),
        " · ".join(
            valeur
            for valeur in (meta.get("telephone"), meta.get("email"))
            if valeur
        ),
        f"NIF : {meta['nif']}" if meta.get("nif") else "",
    ):
        if ligne:
            canv.drawString(x_gauche, y, ligne)
            y -= 9.2

    canv.setFillColor(VERT_FONCE)
    canv.setFont("Helvetica-Bold", 12)
    canv.drawRightString(LARGEUR - MARGE, haut, meta.get("titre", ""))

    canv.setFont("Helvetica", 8)
    canv.setFillColor(colors.HexColor("#1c2b27"))
    y = haut - 14
    if meta.get("numero"):
        canv.drawRightString(LARGEUR - MARGE, y, f"N° {meta['numero']}")
        y -= 10
    if meta.get("date"):
        canv.drawRightString(LARGEUR - MARGE, y, meta["date"])

    canv.setStrokeColor(VERT)
    canv.setLineWidth(1.2)
    canv.line(MARGE, HAUTEUR - 76, LARGEUR - MARGE, HAUTEUR - 76)
    canv.setStrokeColor(BORDURE)
    canv.setLineWidth(0.4)
    canv.line(MARGE, HAUTEUR - 78, LARGEUR - MARGE, HAUTEUR - 78)
    canv.restoreState()


def _dessiner_pied(canv, doc, meta):
    canv.saveState()
    canv.setStrokeColor(BORDURE)
    canv.setLineWidth(0.5)
    canv.line(MARGE, 42, LARGEUR - MARGE, 42)
    canv.setFont("Helvetica", 6.8)
    canv.setFillColor(GRIS)

    style_pied = ParagraphStyle(
        "pied",
        fontName="Helvetica",
        fontSize=6.6,
        leading=7.9,
        textColor=GRIS,
    )
    paragraphe = _p(meta.get("mentions_legales", ""), style_pied)
    largeur, hauteur = paragraphe.wrap(LARGEUR_CONTENU - 150, 24)
    paragraphe.drawOn(canv, MARGE, max(14, 38 - max(hauteur, 8)))
    canv.drawRightString(
        LARGEUR - MARGE,
        34,
        f"Devise : {meta.get('devise', 'Ar')}",
    )
    canv.restoreState()


class CanevasNumerote(canvas.Canvas):
    """Canevas qui affiche « Page X sur Y » après construction du document."""

    def __init__(self, *args, meta=None, **kwargs):
        self._meta = meta or {}
        super().__init__(*args, **kwargs)
        self._etats_pages = []

    def showPage(self):
        self._etats_pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._etats_pages)
        for etat in self._etats_pages:
            self.__dict__.update(etat)
            self.saveState()
            self.setFont("Helvetica", 6.8)
            self.setFillColor(GRIS)
            self.drawRightString(
                LARGEUR - MARGE,
                22,
                f"Page {self._pageNumber} sur {total}",
            )
            self.restoreState()
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)


def _construire(story, meta):
    tampon = io.BytesIO()
    document = BaseDocTemplate(
        tampon,
        pagesize=A4,
        leftMargin=MARGE,
        rightMargin=MARGE,
        topMargin=3.5 * cm,
        bottomMargin=2.1 * cm,
        title=meta.get("titre", "Document PharmaGest"),
        author=meta.get("nom", "PharmaGest"),
        subject=meta.get("titre", ""),
        creator="PharmaGest",
        pageCompression=0,
    )
    cadre = Frame(
        document.leftMargin,
        document.bottomMargin,
        document.width,
        document.height,
        id="contenu",
        showBoundary=0,
    )
    document.addPageTemplates(
        [
            PageTemplate(
                id="principal",
                frames=[cadre],
                onPage=lambda canv, doc: (
                    _dessiner_entete(canv, doc, meta),
                    _dessiner_pied(canv, doc, meta),
                ),
            )
        ]
    )
    document.build(
        story,
        canvasmaker=partial(CanevasNumerote, meta=meta),
    )
    return tampon.getvalue()


# ---------------------------------------------------------------------------
# Blocs réutilisables
# ---------------------------------------------------------------------------
def _section(titre):
    return Paragraph(_texte(titre), STYLE_SECTION)


def _note(texte):
    return Paragraph(_texte(texte), STYLE_PETIT)


def _largeurs(largeurs):
    total = sum(largeurs) or 1
    return [largeur * LARGEUR_CONTENU / total for largeur in largeurs]


def _tableau(entetes, lignes, largeurs, alignements=None):
    """Tableau ReportLab avec en-tête répété et mise en forme lisible."""
    alignements = alignements or ["LEFT"] * len(entetes)
    styles_entete = [
        STYLE_ENTETE_DROITE if alignement == "RIGHT" else STYLE_ENTETE
        for alignement in alignements
    ]
    donnees = [
        [_p(entete, style) for entete, style in zip(entetes, styles_entete)]
    ]
    vide = not lignes
    if vide:
        donnees.append(
            [_p("Aucune donnée pour cette sélection.", STYLE_CELLULE)]
            + [""] * (len(entetes) - 1)
        )
    else:
        for ligne in lignes:
            cellules = []
            for valeur, alignement in zip(ligne, alignements):
                if alignement == "RIGHT":
                    style = STYLE_CELLULE_DROITE
                elif alignement == "CENTER":
                    style = STYLE_CELLULE_CENTRE
                else:
                    style = STYLE_CELLULE
                cellules.append(_p(valeur, style))
            donnees.append(cellules)

    tableau = Table(
        donnees,
        colWidths=_largeurs(largeurs),
        repeatRows=1,
        hAlign="LEFT",
    )
    commandes = [
        ("BACKGROUND", (0, 0), (-1, 0), VERT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.3, BORDURE),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.2),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS_CLAIR]),
    ]
    if vide:
        commandes.append(("SPAN", (0, 1), (-1, 1)))
        commandes.append(("ALIGN", (0, 1), (-1, 1), "CENTER"))
        commandes.append(("TEXTCOLOR", (0, 1), (-1, 1), GRIS))
    tableau.setStyle(TableStyle(commandes))
    return tableau


def _bloc_resume(infos):
    """Petit tableau libellé/valeur sur deux colonnes de paires."""
    donnees = []
    for index in range(0, len(infos), 2):
        paire = infos[index : index + 2]
        ligne = []
        for libelle, valeur in paire:
            ligne.extend([_p(libelle, STYLE_LABEL), _p(valeur, STYLE_VALEUR)])
        while len(ligne) < 4:
            ligne.extend(["", ""])
        donnees.append(ligne)
    tableau = Table(donnees, colWidths=[0.16 * LARGEUR_CONTENU, 0.34 * LARGEUR_CONTENU] * 2)
    tableau.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (-1, -1), GRIS_CLAIR),
                ("BOX", (0, 0), (-1, -1), 0.4, BORDURE),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, BORDURE),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return tableau


def _bloc_totaux(lignes):
    donnees = [
        [_p(libelle, STYLE_TOTAL_LABEL), _p(valeur, STYLE_TOTAL_VALEUR)]
        for libelle, valeur in lignes
    ]
    tableau = Table(donnees, colWidths=[LARGEUR_CONTENU - 170, 170], hAlign="RIGHT")
    tableau.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), VERT_CLAIR),
                ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#c5e3d8")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d8ece5")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return tableau


def _statut_couleur(statut):
    if statut in {"ANNULEE", "RUPTURE"}:
        return ROUGE
    if statut in {"PARTIELLEMENT_RECEPTIONNEE", "FAIBLE"}:
        return ORANGE
    return VERT_FONCE


# ---------------------------------------------------------------------------
# Reçus et factures
# ---------------------------------------------------------------------------
def document_vente_pdf(vente, pharmacie=None, facture=False):
    """Reçu ou facture d'une vente."""
    pharmacie = pharmacie or ParametrePharmacie.get_solo()
    devise = pharmacie.devise or "Ar"
    titre = "FACTURE" if facture else "REÇU DE VENTE"
    meta = meta_document(
        pharmacie,
        titre,
        numero=vente.numero,
        date_texte=timezone.localtime(vente.date_vente).strftime("%d/%m/%Y à %H:%M"),
    )

    client = vente.client
    nom_client = client.nom_affichage if client else "Client de passage"
    caissier = vente.utilisateur.nom_complet if vente.utilisateur else "—"
    paiements = list(vente.paiements.all())
    modes = []
    for paiement in paiements:
        libelle = paiement.get_mode_display()
        if libelle not in modes:
            modes.append(libelle)
    mode_texte = ", ".join(modes) if modes else "—"

    story = []
    infos = [
        ("Client", nom_client),
        ("Caissier", caissier),
        ("Mode de paiement", mode_texte),
        ("Statut", vente.get_statut_display()),
    ]
    story.append(_bloc_resume(infos))

    if facture:
        story.append(Spacer(1, 7))
        story.append(_section("Coordonnées du client"))
        if client:
            story.append(
                _bloc_resume(
                    [
                        ("Nom", client.nom_affichage),
                        ("Téléphone", client.telephone or "—"),
                        ("E-mail", client.email or "—"),
                        ("Adresse", client.adresse or "—"),
                    ]
                )
            )
        else:
            story.append(_note("Vente au comptoir à un client de passage."))

    story.append(Spacer(1, 7))
    story.append(_section("Détail des articles"))
    lignes = []
    for ligne in vente.lignes.select_related("medicament", "lot").all():
        medicament = f"{ligne.medicament.nom} {ligne.medicament.dosage}".strip()
        lignes.append(
            [
                medicament,
                ligne.lot.numero_lot if ligne.lot_id else "—",
                _quantite(ligne.quantite),
                _montant(ligne.prix_unitaire, devise),
                _montant(ligne.sous_total, devise),
            ]
        )
    story.append(
        _tableau(
            ["Médicament", "Lot", "Qté", "Prix unitaire", "Sous-total"],
            lignes,
            [210, 95, 40, 80, 95],
            ["LEFT", "LEFT", "RIGHT", "RIGHT", "RIGHT"],
        )
    )

    totaux = [("Total", _montant(vente.montant_total, devise))]
    if vente.montant_retourne:
        totaux.append(("Retours enregistrés", _montant(vente.montant_retourne, devise)))
        totaux.append(("Net après retours", _montant(vente.montant_net, devise)))

    montant_recu = Decimal("0")
    for paiement in paiements:
        if paiement.mode == "ESPECES" and paiement.montant_recu is not None:
            montant_recu += paiement.montant_recu
    if montant_recu:
        totaux.append(("Montant reçu en espèces", _montant(montant_recu, devise)))
        rendu = montant_recu - vente.montant_total
        if rendu > 0:
            totaux.append(("Monnaie rendue", _montant(rendu, devise)))

    story.append(Spacer(1, 7))
    story.append(_bloc_totaux(totaux))
    story.append(Spacer(1, 8))
    if facture:
        story.append(
            _note(
                "Facture établie selon les prix appliqués au moment de la vente. "
                "Les médicaments vendus ne sont ni repris ni échangés sans justification "
                "et sans document de retour."
            )
        )
    else:
        story.append(
            _note(
                "Reçu à conserver comme justificatif d'achat. Les prix sont figés au moment "
                "de la vente. Toute réclamation doit être accompagnée de ce reçu."
            )
        )
    return _construire(story, meta)


# ---------------------------------------------------------------------------
# Bons de commande et de réception
# ---------------------------------------------------------------------------
def bon_commande_pdf(commande, pharmacie=None):
    pharmacie = pharmacie or ParametrePharmacie.get_solo()
    devise = pharmacie.devise or "Ar"
    meta = meta_document(
        pharmacie,
        "BON DE COMMANDE",
        numero=commande.numero,
        date_texte=f"Édité le {timezone.localtime():%d/%m/%Y}",
    )
    fournisseur = commande.fournisseur
    story = [
        _bloc_resume(
            [
                ("Fournisseur", fournisseur.nom),
                ("Statut", commande.get_statut_display()),
                ("Date de création", _date(commande.date_creation)),
                (
                    "Date de validation",
                    _date(commande.date_commande) if commande.date_commande else "—",
                ),
                ("Téléphone", fournisseur.telephone or "—"),
                ("E-mail", fournisseur.email or "—"),
                ("Adresse", fournisseur.adresse or "—"),
                ("N° fiscal fournisseur", fournisseur.numero_fiscal or "—"),
            ]
        )
    ]
    if commande.notes:
        story.append(Spacer(1, 5))
        story.append(_note(f"Notes : {commande.notes}"))

    story.append(Spacer(1, 7))
    story.append(_section("Articles commandés"))
    lignes = []
    for ligne in commande.lignes.select_related("medicament").all():
        medicament = f"{ligne.medicament.nom} {ligne.medicament.dosage}".strip()
        lignes.append(
            [
                medicament,
                _quantite(ligne.quantite_commandee),
                _quantite(ligne.quantite_recue),
                _montant(ligne.prix_achat_unitaire, devise),
                _montant(ligne.sous_total, devise),
            ]
        )
    story.append(
        _tableau(
            ["Médicament", "Qté commandée", "Qté reçue", "Prix unitaire", "Sous-total"],
            lignes,
            [220, 65, 55, 85, 95],
            ["LEFT", "RIGHT", "RIGHT", "RIGHT", "RIGHT"],
        )
    )
    story.append(Spacer(1, 7))
    story.append(
        _bloc_totaux(
            [
                ("Quantité totale commandée", _quantite(commande.quantite_totale_commandee)),
                ("Quantité totale reçue", _quantite(commande.quantite_totale_recue)),
                ("Total de la commande", _montant(commande.montant_total, devise)),
            ]
        )
    )
    story.append(Spacer(1, 8))
    story.append(
        _note(
            "Bon de commande à retourner signé au fournisseur. La commande ne modifie pas "
            "le stock : seule la réception effective l'augmente."
        )
    )
    return _construire(story, meta)


def bon_reception_pdf(reception, pharmacie=None):
    pharmacie = pharmacie or ParametrePharmacie.get_solo()
    devise = pharmacie.devise or "Ar"
    commande = reception.commande
    meta = meta_document(
        pharmacie,
        "BON DE RÉCEPTION",
        numero=reception.numero,
        date_texte=_date(reception.date_reception),
    )
    story = [
        _bloc_resume(
            [
                ("Commande", commande.numero),
                ("Fournisseur", commande.fournisseur.nom),
                ("Date de réception", _date(reception.date_reception)),
                (
                    "Réceptionné par",
                    reception.utilisateur.nom_complet
                    if reception.utilisateur
                    else "—",
                ),
                ("Statut de la commande", commande.get_statut_display()),
                ("Quantité totale reçue", _quantite(reception.quantite_totale)),
            ]
        )
    ]
    if reception.notes:
        story.append(Spacer(1, 5))
        story.append(_note(f"Notes : {reception.notes}"))

    story.append(Spacer(1, 7))
    story.append(_section("Articles reçus"))
    lignes = []
    for ligne in reception.lignes.select_related(
        "ligne_achat__medicament", "lot"
    ).all():
        medicament = (
            f"{ligne.ligne_achat.medicament.nom} "
            f"{ligne.ligne_achat.medicament.dosage}"
        ).strip()
        lignes.append(
            [
                medicament,
                ligne.numero_lot,
                _date(ligne.date_peremption),
                _quantite(ligne.quantite),
                _montant(ligne.prix_unitaire, devise),
                _montant(ligne.sous_total, devise),
            ]
        )
    story.append(
        _tableau(
            ["Médicament", "Lot", "Péremption", "Qté", "Prix unitaire", "Sous-total"],
            lignes,
            [185, 70, 65, 40, 80, 85],
            ["LEFT", "LEFT", "LEFT", "RIGHT", "RIGHT", "RIGHT"],
        )
    )
    story.append(Spacer(1, 7))
    story.append(
        _bloc_totaux(
            [
                ("Quantité totale reçue", _quantite(reception.quantite_totale)),
                ("Total réceptionné", _montant(reception.montant_total, devise)),
            ]
        )
    )
    story.append(Spacer(1, 8))
    story.append(
        _note(
            "La réception a été enregistrée atomiquement : le stock et les lots ont été "
            "mis à jour une seule fois. Ce bon vaut preuve de livraison."
        )
    )
    return _construire(story, meta)


# ---------------------------------------------------------------------------
# Rapports
# ---------------------------------------------------------------------------
def rapport_stock_pdf(lignes, totaux, pharmacie=None, recherche="", etat=""):
    pharmacie = pharmacie or ParametrePharmacie.get_solo()
    devise = pharmacie.devise or "Ar"
    meta = meta_document(
        pharmacie,
        "RAPPORT DE STOCK",
        date_texte=f"Édité le {timezone.localtime():%d/%m/%Y à %H:%M}",
    )
    story = []
    filtres = [f"Références actives : {totaux.get('nombre_references', len(lignes))}"]
    if recherche:
        filtres.append(f"Recherche : {recherche}")
    if etat:
        filtres.append(f"État : {etat}")
    story.append(_note(" · ".join(filtres)))
    story.append(Spacer(1, 6))

    donnees = []
    for ligne in lignes:
        medicament = f"{ligne['nom']} {ligne['dosage']}".strip()
        donnees.append(
            [
                medicament,
                ligne["categorie"],
                _quantite(ligne["stock_physique"]),
                _quantite(ligne["stock_disponible"]),
                _quantite(ligne["seuil"]),
                _montant(ligne["valeur_achat"], devise),
                _montant(ligne["valeur_vente"], devise),
            ]
        )
    story.append(
        _tableau(
            [
                "Médicament",
                "Catégorie",
                "Stock physique",
                "Délivrable",
                "Seuil",
                "Valeur au prix d'achat",
                "Valeur au prix de vente",
            ],
            donnees,
            [130, 72, 48, 45, 34, 85, 85],
            ["LEFT", "LEFT", "RIGHT", "RIGHT", "RIGHT", "RIGHT", "RIGHT"],
        )
    )
    story.append(Spacer(1, 7))
    story.append(
        _bloc_totaux(
            [
                ("Quantité physique totale", _quantite(totaux["quantite_physique"])),
                ("Quantité délivrable totale", _quantite(totaux["quantite_delivrable"])),
                ("Valeur totale au prix d'achat", _montant(totaux["valeur_achat"], devise)),
                (
                    "Valeur potentielle au prix de vente",
                    _montant(totaux["valeur_vente"], devise),
                ),
            ]
        )
    )
    story.append(Spacer(1, 7))
    story.append(
        _note(
            "Le stock délivrable exclut les lots périmés ou bloqués. La valeur potentielle "
            "au prix de vente est une estimation, pas une marge ni un bénéfice réalisé."
        )
    )
    return _construire(story, meta)


def rapport_ventes_pdf(
    debut,
    fin,
    totaux,
    ventes,
    top,
    modes,
    pharmacie=None,
    limite_lignes=None,
):
    pharmacie = pharmacie or ParametrePharmacie.get_solo()
    devise = pharmacie.devise or "Ar"
    meta = meta_document(
        pharmacie,
        "RAPPORT DES VENTES",
        date_texte=f"Période du {debut:%d/%m/%Y} au {fin:%d/%m/%Y}",
    )
    story = [
        _note(
            "Chiffre d'affaires calculé sur les ventes validées. Les encaissements "
            "correspondent uniquement aux paiements confirmés : les deux notions peuvent différer."
        ),
        Spacer(1, 6),
    ]
    story.append(
        _bloc_resume(
            [
                ("Chiffre d'affaires brut", _montant(totaux["brut"], devise)),
                ("Retours enregistrés", _montant(totaux["retours"], devise)),
                ("Chiffre d'affaires net", _montant(totaux["net"], devise)),
                ("Encaissements confirmés", _montant(totaux["encaissements"], devise)),
                ("Nombre de ventes", _quantite(totaux["nombre"])),
                ("Articles vendus", _quantite(totaux["articles"])),
                ("Panier moyen", _montant(totaux["panier_moyen"], devise)),
                ("Période", f"{debut:%d/%m/%Y} – {fin:%d/%m/%Y}"),
            ]
        )
    )

    story.append(_section("Détail des ventes"))
    lignes = []
    ventes_affichees = ventes[:limite_lignes] if limite_lignes else ventes
    for vente in ventes_affichees:
        lignes.append(
            [
                vente.numero,
                _date(vente.date_vente),
                vente.client.nom_affichage if vente.client else "Client de passage",
                _quantite(vente.nombre_articles),
                _montant(vente.montant_total, devise),
                _montant(vente.montant_retourne, devise),
                _montant(vente.montant_net, devise),
                vente.get_statut_display(),
            ]
        )
    story.append(
        _tableau(
            [
                "Numéro",
                "Date",
                "Client",
                "Articles",
                "Brut",
                "Retours",
                "Net",
                "Statut",
            ],
            lignes,
            [72, 66, 88, 38, 62, 55, 62, 55],
            ["LEFT", "LEFT", "LEFT", "RIGHT", "RIGHT", "RIGHT", "RIGHT", "LEFT"],
        )
    )

    if top:
        story.append(_section("Top produits vendus"))
        lignes_top = [
            [
                f"{produit['nom']} {produit['dosage']}".strip(),
                produit["categorie"],
                _quantite(produit["quantite"]),
                _montant(produit["montant"], devise),
            ]
            for produit in top
        ]
        story.append(
            _tableau(
                ["Médicament", "Catégorie", "Quantité vendue", "Montant"],
                lignes_top,
                [220, 120, 80, 100],
                ["LEFT", "LEFT", "RIGHT", "RIGHT"],
            )
        )

    if modes and modes.get("lignes"):
        story.append(_section("Répartition par mode de paiement"))
        lignes_modes = [
            [ligne["libelle"], _quantite(ligne["nombre"]), _montant(ligne["total"], devise)]
            for ligne in modes["lignes"]
        ]
        story.append(
            _tableau(
                ["Mode de paiement", "Nombre de paiements", "Montant confirmé"],
                lignes_modes,
                [220, 120, 140],
                ["LEFT", "RIGHT", "RIGHT"],
            )
        )
    return _construire(story, meta)


def rapport_achats_pdf(debut, fin, statistiques, pharmacie=None):
    pharmacie = pharmacie or ParametrePharmacie.get_solo()
    devise = pharmacie.devise or "Ar"
    meta = meta_document(
        pharmacie,
        "RAPPORT DES ACHATS",
        date_texte=f"Période du {debut:%d/%m/%Y} au {fin:%d/%m/%Y}",
    )
    story = [
        _bloc_resume(
            [
                ("Total commandé", _montant(statistiques["total_commande"], devise)),
                (
                    "Total réceptionné",
                    _montant(statistiques["total_receptionne"], devise),
                ),
                ("Nombre de commandes", _quantite(statistiques["nombre_commandes"])),
                ("Nombre de réceptions", _quantite(statistiques["nombre_receptions"])),
                ("Période", f"{debut:%d/%m/%Y} – {fin:%d/%m/%Y}"),
            ]
        )
    ]

    story.append(_section("Commandes d'achat"))
    lignes = []
    for commande in statistiques["commandes"]:
        lignes.append(
            [
                commande.numero,
                commande.fournisseur.nom,
                _date(commande.date_creation),
                commande.get_statut_display(),
                _quantite(commande.quantite_totale_commandee),
                _montant(commande.montant_total, devise),
            ]
        )
    story.append(
        _tableau(
            ["Numéro", "Fournisseur", "Date", "Statut", "Quantité", "Montant"],
            lignes,
            [80, 150, 65, 100, 50, 85],
            ["LEFT", "LEFT", "LEFT", "LEFT", "RIGHT", "RIGHT"],
        )
    )
    story.append(
        _note(
            "Le total commandé exclut les brouillons et les commandes annulées. "
            "La commande seule ne modifie pas le stock."
        )
    )

    story.append(_section("Réceptions d'achat"))
    lignes = []
    for reception in statistiques["receptions"]:
        lignes.append(
            [
                reception.numero,
                reception.commande.numero,
                reception.commande.fournisseur.nom,
                _date(reception.date_reception),
                _quantite(reception.quantite_totale),
                _montant(reception.montant_total, devise),
            ]
        )
    story.append(
        _tableau(
            ["Numéro", "Commande", "Fournisseur", "Date", "Quantité", "Montant"],
            lignes,
            [80, 80, 145, 65, 50, 85],
            ["LEFT", "LEFT", "LEFT", "LEFT", "RIGHT", "RIGHT"],
        )
    )
    return _construire(story, meta)


def rapport_peremptions_pdf(donnees, pharmacie=None):
    pharmacie = pharmacie or ParametrePharmacie.get_solo()
    devise = pharmacie.devise or "Ar"
    totaux = donnees["totaux"]
    meta = meta_document(
        pharmacie,
        "RAPPORT DES PÉREMPTIONS",
        date_texte=f"Édité le {timezone.localtime():%d/%m/%Y à %H:%M}",
    )
    story = [
        _bloc_resume(
            [
                ("Horizon analysé", f"{donnees['jours']} jours"),
                ("Date limite", _date(donnees["date_limite"])),
                (
                    "Valeur d'achat des lots périmés",
                    _montant(totaux["valeur_achat_perimes"], devise),
                ),
                (
                    "Valeur d'achat des lots proches",
                    _montant(totaux["valeur_achat_proches"], devise),
                ),
                (
                    "Valeur d'achat totale à risque",
                    _montant(totaux["valeur_achat_totale"], devise),
                ),
                (
                    "Valeur de vente potentielle à risque",
                    _montant(totaux["valeur_vente_totale"], devise),
                ),
            ]
        )
    ]

    def _lignes_lots(lots):
        return [
            [
                f"{ligne['medicament'].nom} {ligne['medicament'].dosage}".strip(),
                ligne["lot"].numero_lot,
                _date(ligne["date_peremption"]),
                (
                    f"Périmé ({abs(ligne['jours'])} j)"
                    if ligne["est_perime"]
                    else f"{ligne['jours']} j"
                ),
                _quantite(ligne["quantite"]),
                _montant(ligne["valeur_achat"], devise),
                _montant(ligne["valeur_vente"], devise),
            ]
            for ligne in lots
        ]

    story.append(_section("Lots périmés encore en stock"))
    story.append(
        _tableau(
            [
                "Médicament",
                "Lot",
                "Péremption",
                "Échéance",
                "Quantité",
                "Valeur d'achat",
                "Valeur de vente",
            ],
            _lignes_lots(donnees["perimes"]),
            [145, 70, 65, 55, 40, 75, 75],
            ["LEFT", "LEFT", "LEFT", "LEFT", "RIGHT", "RIGHT", "RIGHT"],
        )
    )
    story.append(_section("Lots proches de la péremption"))
    story.append(
        _tableau(
            [
                "Médicament",
                "Lot",
                "Péremption",
                "Jours restants",
                "Quantité",
                "Valeur d'achat",
                "Valeur de vente",
            ],
            _lignes_lots(donnees["proches"]),
            [145, 70, 65, 55, 40, 75, 75],
            ["LEFT", "LEFT", "LEFT", "LEFT", "RIGHT", "RIGHT", "RIGHT"],
        )
    )
    story.append(Spacer(1, 7))
    story.append(
        _note(
            "Les lots périmés sont exclus de la vente (RG08). Les valeurs indiquées sont "
            "des valeurs de stock à risque, et non des pertes comptables définitivement constatées."
        )
    )
    return _construire(story, meta)
