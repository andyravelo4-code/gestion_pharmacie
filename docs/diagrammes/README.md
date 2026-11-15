# Diagrammes exportés en image

Ce dossier contient les huit diagrammes du dossier de conception, exportés en
PNG à partir des blocs Mermaid de [`../CONCEPTION.md`](../CONCEPTION.md).

| Fichier | Diagramme |
| --- | --- |
| `01-architecture.png` | Architecture logicielle (applications Django, services) |
| `02-cas-utilisation.png` | Acteurs et cas d'utilisation UML |
| `03-mcd-relations.png` | MCD — relations entre entités |
| `04-mcd-entites-attributs.png` | MCD — entités et attributs |
| `05-sequence-vente-fefo.png` | Séquence — vente FEFO et idempotence |
| `06-sequence-reception.png` | Séquence — réception d'une commande |
| `07-cycle-de-vie.png` | Cycle de vie des objets métier |
| `08-sequence-retour-annulation.png` | Séquence — retour et annulation |

## Procédé d'export

1. Les blocs `mermaid` sont extraits de `docs/CONCEPTION.md`.
2. Une page HTML les place dans un conteneur avec la bibliothèque Mermaid ;
   le rendu est effectué dans le navigateur (Firefox headless).
3. Le SVG obtenu est intégré à une seconde page HTML, elle-même capturée en
   PNG par Firefox. Cette étape est nécessaire car Mermaid utilise des
   `<foreignObject>` pour une partie des libellés : un convertisseur SVG
   classique comme `rsvg-convert` ne les afficherait pas.
4. Les PNG sont référencés dans `docs/CONCEPTION.md` (liens après chaque
   diagramme et galerie en fin de document).

Les sources restent les blocs Mermaid : modifier le Markdown puis régénérer
les images si un diagramme évolue.
