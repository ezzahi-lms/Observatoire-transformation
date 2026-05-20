# SKILL — reporter.py
**Module de génération des rapports DOCX, HTML et JSON**

---

## Rôle

`reporter.py` est la dernière étape du pipeline. Il prend le dict benchmark produit par
`analyzer.py` et génère trois fichiers dans `reports/` :

```
{benchmark complet}
         ↓
    reporter.generate_reports()
    ├── veille_<secteur>_<AAAA-MM>.json    — données brutes (archive + régénération)
    ├── veille_<secteur>_<AAAA-MM>.html    — rapport enrichi (So What?, Afrique/MENA, grilles)
    └── veille_<secteur>_<AAAA-MM>.docx    — rapport Word pour diffusion clients
```

---

## Interface publique

### `generate_reports(analysis, settings, project_root) → List[str]`

Point d'entrée principal. Crée le dossier `reports/` si absent, calcule le nom de fichier,
appelle les générateurs dans l'ordre : JSON → HTML → DOCX.

**Paramètres :**

| Paramètre | Type | Description |
|-----------|------|-------------|
| `analysis` | dict | Sortie de `analyzer.analyze()` |
| `settings` | dict | Depuis `settings.yaml` |
| `project_root` | str | Chemin racine du projet (pour trouver `templates/`) |

**Retour :** liste des chemins absolus des fichiers générés.

### `generate_docx(analysis, output_path) → str`

Génère le rapport Word structuré avec tableaux, couleurs sémantiques et footer.

### `generate_html(analysis, output_path, template_path) → str`

Rend le template Jinja2 `templates/report.html` avec toutes les données du benchmark.
Utilise `autoescape=True` pour protéger contre les injections XSS.

### `generate_pdf(html_path, output_path) → str | None`

Optionnel — nécessite `weasyprint`. Retourne `None` si non installé.

---

## Nommage des fichiers

Le nom est construit depuis :
- `filename_pattern` dans `settings.yaml` (défaut : `veille_{sector}_{date}`)
- `sector` = label du secteur slugifié (minuscules, espaces → `_`, `&`, `—` supprimés)
- `date` = `AAAA-MM` de la date de génération

Exemples :
```
veille_industrie_pharmaceutique__maroc___afrique_2026-05.docx
veille_banque___finance__maroc___afrique_2026-05.html
```

---

## Sections du rapport DOCX

| Section | Données sources | Format |
|---------|----------------|--------|
| Page de titre | `_meta`, `qualite_sources` | Paragraphes centrés |
| Synthèse exécutive | `synthese_executive.texte` + `qualite_sources.note_methodologique` | Texte libre |
| Facteurs Clés de Succès | `facteurs_cles_succes` | Tableaux par niveau, couleur importance |
| Dimensionnement | `tendances_dimensionnement` | Tableau 4 colonnes |
| Gouvernance | `pratiques_gouvernance` | Tableau, couleur maturité |
| Performance | `gestion_performance` | Tableau, couleur adoption |
| Externalisation | `externalisation_partenariats` | Tableau, couleur direction |
| RSE & Éthique | `rse_ethique` | Tableau, couleur engagement |
| Signaux faibles | `signaux_faibles` | Liste à puces + détails |
| Prospective | `prospective` | CT + MT en listes, scénarios en tableau |
| Recommandations | `recommandations` | Tableau 5 colonnes |
| Sources | `index_sources` | Tableau trié par ID |
| Footer | `_meta` | Texte centré 8pt |

**Note :** Les sections `lectures_so_what`, `dimension_afrique_mena` et `questions_clients`
sont présentes dans le HTML mais pas encore dans le DOCX (à ajouter si besoin).

---

## Palettes couleurs

### Importance des FCS

| Valeur | Couleur hex | Rendu |
|--------|------------|-------|
| Critique | `#C0392B` | Rouge |
| Élevée | `#E67E22` | Orange |
| Modérée | `#27AE60` | Vert |

### Maturité governance

| Valeur | Couleur |
|--------|---------|
| Mature/Répandue | Vert `#27AE60` |
| En développement | Orange `#E67E22` |
| Émergente | Bleu `#2E86C1` |

### Adoption (performance)

| Valeur | Couleur |
|--------|---------|
| Majoritaire (>60%) | Vert |
| En diffusion (20-60%) | Orange |
| Pionnier (<20%) | Bleu |

### Direction (externalisation)

| Valeur | Couleur |
|--------|---------|
| Vers plus d'externalisation | Orange `#E67E22` |
| Vers plus d'internalisation | Bleu `#2E86C1` |
| Nouveaux modèles hybrides | Violet `#8E44AD` |
| Stable | Gris `#7F8C8D` |

### Scénarios

| Valeur | Couleur |
|--------|---------|
| Optimiste | Vert `#27AE60` |
| Central | Bleu `#2E86C1` |
| Pessimiste | Rouge `#C0392B` |

### Types de recommandation

| Type | Couleur |
|------|---------|
| Stratégique | Bleu foncé `#1A5F8A` |
| Organisationnel | Bleu `#2E86C1` |
| RH & Compétences | Violet `#8E44AD` |
| Digital | Teal `#16A085` |
| Gouvernance | Orange foncé `#D35400` |
| RSE | Vert `#27AE60` |

---

## Helpers internes

### `_safe_list(val) → list`

Protège contre les champs qui devraient être une liste de dicts mais que Claude retourne
parfois comme une string JSON (ex: `"[{...}]"`). Tente de parser la string, retourne
`[]` en cas d'échec. Appliqué systématiquement sur tous les champs itérés.

```python
# Usage interne
for item in _safe_list(analysis.get("recommandations", [])):
    row[0].text = item.get("action", "")   # item est garanti dict
```

### `_sources_str(ids) → str`

Formate une liste d'IDs en suffix de citation : `" [1, 3, 7]"` ou `""` si vide.

### `_shd_cell(cell, hex_color, text, bold, font_size)`

Colorie le fond d'une cellule Word et y écrit un texte en blanc.

---

## Template HTML — `templates/report.html`

Template Jinja2 avec CSS intégré. Variables injectées :

```python
template.render(
    analysis=analysis,          # Dict complet benchmark
    sector="...",
    period="mai 2026",
    generated_at="20/05/2026 à 10:30",
    nb_sources=60,
    freshness={"recent_count": 45, "pct_recent": 75},
    niveaux_fcs=["Stratégique", "Organisationnel", ...],
    importance_colors={"Critique": "C0392B", ...},
    # ... toutes les palettes
)
```

**Classes CSS clés :**

| Classe | Section |
|--------|---------|
| `.so-what-grid` | Grille 3 cartes So What? |
| `.so-what-secteur/clients/cabinet` | Couleur par lecture |
| `.afrique-box` | Encadré contexte Afrique/MENA |
| `.questions-grid` | Grille 2×2 questions clients |
| `.rec-mission` | Boîte violette angle_mission |

---

## Régénérer les rapports sans rappeler Claude

Le JSON est toujours sauvegardé en premier. Il permet de régénérer DOCX/HTML après
modification du template ou du code sans payer de nouveaux tokens :

```python
import json, yaml
from agent import reporter

with open("reports/veille_pharma_maroc_2026-05.json", encoding="utf-8") as f:
    analysis = json.load(f)

with open("config/settings.yaml") as f:
    settings = yaml.safe_load(f)

reporter.generate_reports(analysis, settings, ".")
# → Écrase les fichiers DOCX/HTML existants
```

---

## Configuration (settings.yaml)

```yaml
reporting:
  formats: [docx, html]          # Ajouter "pdf" si weasyprint installé
  output_dir: reports
  filename_pattern: veille_{sector}_{date}
```

---

## Dépendances

| Package | Usage |
|---------|-------|
| `python-docx` | Génération DOCX |
| `jinja2` | Template HTML |
| `weasyprint` | PDF (optionnel) |

---

## Ajouter une section au rapport DOCX

1. Vérifier que la clé est dans le dict `analysis` (sortie analyzer)
2. Dans `generate_docx()`, après la section précédente :

```python
# Exemple : ajouter dimension_afrique_mena
_heading(doc, "Dimension Afrique & MENA", 1)
afrique = analysis.get("dimension_afrique_mena", {})
if afrique.get("contexte_regional"):
    doc.add_paragraph(afrique["contexte_regional"])

ecarts = afrique.get("ecarts_vs_international", [])
if ecarts:
    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    _table_header(table, ["Axe", "International", "Afrique/MENA", "Gap"])
    for item in ecarts:
        row = table.add_row().cells
        row[0].text = item.get("axe", "")
        row[1].text = item.get("situation_internationale", "")
        row[2].text = item.get("situation_afrique_mena", "")
        row[3].text = item.get("gap_a_combler", "")
```

---

## Gestion des erreurs

| Erreur | Cause | Action |
|--------|-------|--------|
| `AttributeError: 'str' object has no attribute 'get'` | `_safe_list()` non appliqué sur un champ | Encapsuler l'itération avec `_safe_list()` |
| Template HTML non trouvé | `templates/report.html` absent ou chemin incorrect | Vérifier que `templates/` n'est pas dans `.gitignore` |
| DOCX corrompu à l'ouverture | Cellule Word sans paragraphe | Vérifier que chaque cellule a au moins un `Paragraph` |
| PDF vide | `weasyprint` crash sur CSS custom | Tester `weasyprint` séparément, simplifier le CSS |
