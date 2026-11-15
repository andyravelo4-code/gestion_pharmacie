# Base de données de démonstration

Ce dossier contient un export SQL de la base SQLite de démonstration utilisée
pendant le développement de PharmaGest.

## Contenu

| Fichier | Description |
| --- | --- |
| `pharmagest_demo.sql.gz` | Export SQL complet (schéma + données fictives), compressé avec gzip |
| `README.md` | Ce mode d’emploi |

L’export contient :

- les 32 tables du projet et les migrations appliquées ;
- 5 comptes fictifs (`admin`, `pharmacien`, `stock`, `caissier`, `gestion`) ;
- 6 catégories, 20 médicaments, 3 fournisseurs, 4 clients ;
- 42 lots de stock, 4 commandes d’achat, 2 réceptions ;
- 30 ventes, 30 paiements, 2 retours/annulations ;
- 109 mouvements de stock, 1 inventaire et le journal d’audit de démonstration.

Douze médicaments référencent une photo libre de droits
(`medicaments/demo/medicament_XX.jpg`). Les fichiers correspondants sont
versionnés dans `static/img/medicaments/demo/` ; après restauration, les
copier dans `media/` :

```bash
mkdir -p media/medicaments/demo
cp static/img/medicaments/demo/*.jpg media/medicaments/demo/
```

Les autres médicaments affichent le visuel de remplacement de l’interface.
Les crédits et licences sont détaillés dans
[`docs/CREDITS_IMAGES.md`](../docs/CREDITS_IMAGES.md).

> Toutes les données sont **fictives** et destinées à la démonstration ou aux
> tests. Ne jamais les utiliser en production.

## Restauration dans une base SQLite neuve

Depuis la racine du projet :

```bash
rm -f db.sqlite3
gzip -dc base_de_donnees/pharmagest_demo.sql.gz | sqlite3 db.sqlite3
```

Vérifier ensuite :

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py shell -c "from medicaments.models import Medicament; print(Medicament.objects.count())"
```

La commande doit afficher `20`.

## Alternative recommandée : migrations + jeu de données

L’export est fourni pour faciliter l’évaluation du projet. La méthode
reproductible reste :

```bash
.venv/bin/python manage.py migrate
.venv/bin/python manage.py donnees_demo
```

## Empreinte SHA-256

```text
34287c655818ea41a378661a151bbcfe2a6c19ba1edc730a85433a540e97be36  pharmagest_demo.sql.gz
```

## Compatibilité

L’export a été généré avec SQLite 3 et Django 5.2. Le format SQL est lisible par
`sqlite3` sur Linux, macOS et Windows. Pour PostgreSQL, utiliser les migrations
Django (`manage.py migrate`) plutôt que cet export SQLite.
