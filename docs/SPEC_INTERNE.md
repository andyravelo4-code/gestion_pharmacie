# Spécifications internes de développement — PharmaGest

Document destiné aux développeurs (et agents) qui complètent l'interface. Les modèles,
services métier et conventions ci-dessous sont **déjà en place** : ne pas les modifier
sans coordination.

## 1. Stack et conventions

- Django 5.2, Python 3.14, SQLite, Bootstrap 5.3 (fichiers locaux), Bootstrap Icons, Chart.js local.
- Interface **100 % en français**, responsive, accessible aux tablettes/téléphones.
- Environnement virtuel : `.venv/bin/python` ; commandes : `.venv/bin/python manage.py ...`.
- Application à la racine du dépôt : `/home/tiavina/pharma_gest`.
- Chaque application a : `forms.py`, `views.py`, `urls.py`, `admin.py`, `tests.py`
  (tests autorisés à être dans `tests.py` ou un dossier `tests/`).
- Les modèles sont **figés** ; `makemigrations` a déjà été exécuté. Ne jamais modifier
  un modèle ou un service sans nécessité absolue et sans le signaler.
- Toutes les vues métier doivent vérifier les permissions côté serveur.

## 2. Permissions et rôles

`utilisateurs/permissions.py` fournit :

- `RoleRequisMixin` : `LoginRequiredMixin` + contrôle de rôle. Définir
  `roles_autorises = (...)`.
- `AdminRequisMixin` : réservé au rôle `ADMIN` ou superutilisateur.
- Constantes : `ADMIN`, `PHARMACIEN`, `GESTION_STOCK`, `CAISSIER`,
  `RESPONSABLE_GESTION`, `ADMIN_SEUL`, `GESTION_MEDICAMENTS`,
  `GESTION_STOCK_ROLES`, `GESTION_ACHATS_ROLES`, `VENTES_ROLES`, `LECTURE_GESTION`.

Un superutilisateur et tout utilisateur ayant le rôle `ADMIN` passent toujours.
Attributs de contexte utiles dans les templates : `est_admin`, `peut_medicaments`,
`peut_stock`, `peut_achats`, `peut_ventes`, `peut_rapports`, `peut_utilisateurs`,
`peut_parametres`.

Matrice cible :

| Module | Rôles |
| --- | --- |
| Médicaments : lecture | tous les connectés |
| Médicaments : création/modification/suppression, catégories | `ADMIN`, `PHARMACIEN` |
| Fournisseurs | `ADMIN`, `PHARMACIEN`, `GESTION_STOCK` |
| Clients et ventes | `ADMIN`, `PHARMACIEN`, `CAISSIER` |
| Stock, lots, inventaires, achats | `ADMIN`, `PHARMACIEN`, `GESTION_STOCK` |
| Rapports détaillés / PDF | `ADMIN`, `PHARMACIEN`, `RESPONSABLE_GESTION` |
| Utilisateurs, paramètres, sauvegardes, audit | `ADMIN` |

## 3. Formulaires et templates

- Hériter de `core.forms.FormulaireModeleStyle` ou `FormulaireStyle` (classes Bootstrap auto).
- Rendu d'un champ : `{% include "includes/form_field.html" with field=form.nom %}`
- Case à cocher : `{% include "includes/form_check.html" with field=form.actif %}`
- Pagination : `{% include "includes/pagination.html" %}` (utilise `{% querystring %}`).
- Base : `templates/base.html` avec les blocs `titre`, `titre_page`, `sous_titre_page`,
  `contenu`, `scripts`, `styles`.
- Filtre `montant` : `{% load core_extras %}` puis `{{ valeur|montant }}` ; devise dans
  `{{ devise }}` (contexte global). Autres filtres : `signe_quantite`, `pourcentage`.
- Statuts/couleurs : classes `.badge-actif`, `.badge-archive`, `.badge-danger-doux`,
  `.badge-warning-doux`, `.badge-info-doux`, `.stat-card`, `.empty-state`.
- Messages : `messages.success/error/warning/info` ; CSRF obligatoire sur tous les POST.
- Les actions destructrices ou sensibles (validation, annulation, blocage, suppression,
  réception, vente) s'effectuent en **POST** avec confirmation visuelle.
- Une page de liste propose recherche, filtres, tri et pagination.
- Aucun prix, stock ou total ne doit être calculé uniquement côté navigateur.

## 4. Audit

`core.utils.journaliser(request, action, module, description, objet=None)` avec
`core.models.JournalAudit.Action.*` (CREATION, MODIFICATION, SUPPRESSION, VALIDATION,
ANNULATION, RECEPTION, VENTE, RETOUR, CORRECTION, ARCHIVAGE...). Journaliser les
créations, modifications, validations, annulations, blocages et suppressions.

## 5. Modèles et services existants — à utiliser sans les réécrire

- `medicaments.models.Categorie`, `Medicament` (photo, seuil, stock_total(),
  stock_disponible(), est_en_alerte, est_en_rupture, archiver(), historique_sensible()).
- `fournisseurs.models.Fournisseur` (`commandes`, `montant_total_achats`, `desactiver`).
- `clients.models.Client` (`ventes`, `actif`).
- `stock.models.LotStock` (`est_perime`, `est_delivrable`, `jours_avant_peremption`,
  `bloquer`, `debloquer`), `MouvementStock`, `Inventaire`, `LigneInventaire`.
- `stock.services` : `appliquer_mouvement`, `receptionner_lot`, `creer_inventaire`,
  `valider_inventaire`.
- `achats.models.CommandeAchat` (statuts BROUILLON, COMMANDEE,
  PARTIELLEMENT_RECEPTIONNEE, RECEPTIONNEE, ANNULEE ; `montant_total`,
  `peut_etre_receptionnee`), `LigneAchat`, `ReceptionAchat`, `LigneReception`.
- `achats.services` : `valider_commande`, `annuler_commande`,
  `receptionner_commande(commande, lignes_reception, utilisateur, notes)` où
  `lignes_reception` = liste de dicts `{ligne_achat, quantite, numero_lot,
  date_peremption, prix_unitaire}`.
- `ventes.models` : `Vente`, `LigneVente` (prix figé), `Paiement`, `RetourVente`,
  `LigneRetour`.
- `ventes.services` : `lots_fefo(medicament)`, `creer_vente(...)`, `creer_retour(...)`,
  `annuler_vente(...)`, `confirmer_paiement(...)`. Les exceptions métier sont dans
  `core.exceptions` (`OperationRefusee`, `StockInsuffisant`, `LotNonDelivrable`).
- `core.models.ParametrePharmacie.get_solo()` : nom, adresse, téléphone, email, NIF,
  devise, `seuil_peremption_jours`, `mentions_legales`, logo.
- `core.utils` : `generer_numero`, `format_montant`, `journaliser`.

## 6. Contrat d'URL (noms à respecter impérativement)

### medicaments (`namespace medicaments`)
`liste`, `detail`, `creer`, `modifier`, `supprimer`, `archiver`,
`categories`, `categorie_creer`, `categorie_modifier`, `categorie_supprimer`.

### fournisseurs
`liste`, `detail`, `creer`, `modifier`, `basculer` (activation/désactivation).

### clients
`liste`, `detail`, `creer`, `modifier`, `basculer`.

### stock
`tableau`, `lots`, `lot_detail`, `bloquer_lot`, `mouvements`, `alertes`,
`inventaires`, `inventaire_creer`, `inventaire_detail`, `inventaire_valider`.

### achats
`liste`, `creer`, `detail`, `modifier`, `ajouter_ligne`, `modifier_ligne`,
`supprimer_ligne`, `valider`, `annuler`, `receptionner`, `receptions`,
`reception_detail`.

### ventes
`caisse`, `liste`, `detail`, `retour`, `retours`, `annuler`, `panier_ajouter`,
`panier_modifier`, `panier_retirer`, `panier_vider`, `valider`, `paiements`,
`confirmer_paiement`.

### rapports
`tableau_bord` (racine `/`), `ventes`, `achats`, `stock`, `peremptions`, `journal`,
`pdf_ventes`, `pdf_achats`, `pdf_stock`, `pdf_peremptions`, `recu_vente`,
`facture_vente`, `bon_commande`, `bon_reception`.

### core
`parametres`, `sauvegardes`, `telecharger_sauvegarde`.

### utilisateurs
`connexion`, `deconnexion`, `profil`, `mot_de_passe`, `liste`, `creer`, `detail`,
`modifier`, `basculer`, réinitialisation via les vues Django standard.

## 7. Qualité et vérifications

Avant de rendre le travail :

1. `.venv/bin/python manage.py check` doit passer.
2. Créer des tests Django (`TestCase`) pour ses vues/modèles/services : permissions,
   calculs, filtres, cas d'erreur, PDF.
3. `.venv/bin/python manage.py test <app>` doit passer (ou signaler précisément un
   échec externe à son périmètre).
4. Pas de dépendance CDN : les fichiers statiques sont locaux.
5. Ne pas lancer `migrate`/`flush` sur une base contenant des données utilisateur sans
   autorisation. Les tests utilisent une base dédiée.

## 8. Règles métier rappelées

- RG02 : code-barres unique quand renseigné.
- RG04 : une commande ne modifie pas le stock ; seule la réception le fait (une fois).
- RG05/RG06 : réception/vente validées modifient le stock une seule fois, atomiquement.
- RG07 : stock jamais négatif.
- RG08 : lots périmés/bloqués exclus de la vente.
- RG09 : auteur, date et historique conservés.
- RG10 : aucune suppression silencieuse d'une vente/achat validé ; opération compensatoire.
- RG11 : contrôle des permissions sur chaque vue.
- RG12 : prix figé sur les lignes de vente et documents.
