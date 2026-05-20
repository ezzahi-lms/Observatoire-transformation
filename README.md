# Observatoire de la Transformation Organisationnelle
**Agent de veille stratégique — LMS ORH**

Génère automatiquement des benchmarks sectoriels sur la transformation organisationnelle
(structures, modèles opérationnels, RH, gouvernance, digitalisation) à destination des
consultants et dirigeants de LMS ORH.

---

## Sommaire

1. [Prérequis](#1-prérequis)
2. [Installation](#2-installation)
3. [Configuration](#3-configuration)
4. [Lancement](#4-lancement)
5. [Structure du projet](#5-structure-du-projet)
6. [Ajouter un secteur](#6-ajouter-un-secteur)
7. [Lire les rapports générés](#7-lire-les-rapports-générés)
8. [Diagnostic & maintenance](#8-diagnostic--maintenance)

---

## 1. Prérequis

| Outil | Version minimum | Usage |
|-------|----------------|-------|
| Python | 3.11+ | Runtime |
| pip | — | Dépendances |
| ngrok | compte gratuit | Accès distant à l'UI |
| Clé API Anthropic | claude-sonnet-4-6 | Analyse Claude |

---

## 2. Installation

```bash
# 1. Cloner le dépôt
git clone https://github.com/ezzahi-lms/Observatoire-transformation.git
cd Observatoire-transformation

# 2. Créer et activer un environnement virtuel
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Mac / Linux

# 3. Installer les dépendances
pip install -r requirements.txt
```

---

## 3. Configuration

### Fichier `.env` (à créer à la racine)

```env
ANTHROPIC_API_KEY=sk-ant-...
```

Copier `.env.example` comme base :

```bash
copy .env.example .env    # Windows
# cp .env.example .env    # Mac / Linux
```

### `config/settings.yaml`

Paramètres globaux de l'agent :

```yaml
agent:
  name: Observatoire Transformation
  version: 1.1.0
  default_sector: pharma_maroc       # Secteur lancé sans argument

collection:
  days_back: 35                      # Fenêtre temporelle RSS (jours)
  max_search_results: 15             # Résultats max par requête DuckDuckGo
  max_articles_total: 60             # Plafond total d'articles envoyés à Claude

analysis:
  model: claude-sonnet-4-6
  max_tokens: 8192                   # Limite par appel (3 appels enchaînés)
  temperature: 0.3

reporting:
  formats: [docx, html]             # Formats générés (docx, html, pdf)
  output_dir: reports
  filename_pattern: veille_{sector}_{date}

scheduling:
  enabled: true
  frequency: monthly
  day_of_month: 1
  hour: 8
  minute: 0
```

---

## 4. Lancement

### Interface web (recommandé)

```bash
# Démarrer l'application Streamlit
run_app.bat                    # Windows (double-clic ou terminal)

# Puis exposer via ngrok pour accès distant
run_ngrok.bat
```

L'UI est accessible à l'URL ngrok affichée dans la console.

### CLI (mode batch ou automatisation)

```bash
# Lancer une analyse (secteur par défaut)
python main.py run

# Lancer sur un secteur spécifique
python main.py run --sector banque_finance

# Lister les secteurs disponibles
python main.py sectors

# Lister les rapports générés
python main.py list

# Démarrer le scheduler mensuel (tourne en arrière-plan)
python main.py schedule
```

### Scheduler automatique

Configuré dans `settings.yaml` (`scheduling`), il lance le pipeline le 1er de chaque mois
à 8h00. Démarrer avec `python main.py schedule` depuis un terminal permanent ou une tâche
planifiée Windows.

---

## 5. Structure du projet

```
agent-veille/
│
├── agent/                        # Modules du pipeline
│   ├── collector.py              # Collecte RSS + DuckDuckGo
│   ├── analyzer.py               # Analyse Claude (3 appels)
│   └── reporter.py               # Génération DOCX + HTML
│
├── config/
│   ├── settings.yaml             # Paramètres globaux
│   ├── sectors.yaml              # Définition des secteurs (sources + axes)
│   └── users.yaml                # Utilisateurs UI (non versionné)
│
├── templates/
│   └── report.html               # Template Jinja2 du rapport HTML
│
├── reports/                      # Rapports générés (non versionnés)
│   ├── veille_pharma_maroc_2026-05.docx
│   ├── veille_pharma_maroc_2026-05.html
│   └── veille_pharma_maroc_2026-05.json
│
├── app.py                        # Interface Streamlit (UI web)
├── main.py                       # CLI (run / schedule / list / sectors)
├── check_agents.py               # Diagnostic : qualité des configs secteurs
├── check_sources.py              # Diagnostic : accessibilité des flux RSS
├── manage_users.py               # Gestion des utilisateurs UI
├── start_ngrok.py                # Lancement ngrok programmatique
│
├── .env                          # Clé API (non versionné)
├── .env.example                  # Modèle .env
├── requirements.txt
└── run_app.bat / run_ngrok.bat   # Raccourcis Windows
```

### Pipeline d'une analyse

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  collector   │ →   │  analyzer    │ →   │  reporter    │
│              │     │              │     │              │
│ RSS feeds    │     │ Claude Part A│     │ DOCX         │
│ DuckDuckGo   │     │ Claude Part B│     │ HTML         │
│              │     │ Claude Part C│     │ JSON         │
│ ~60 articles │     │ ~15 min      │     │              │
└──────────────┘     └──────────────┘     └──────────────┘
```

---

## 6. Ajouter un secteur

Éditer `config/sectors.yaml` en ajoutant un bloc sous la clé `sectors` :

```yaml
sectors:

  # Nouvelle clé — utilisée en CLI : python main.py run --sector ma_cle
  mon_secteur:
    label: "Mon Secteur — Maroc & Afrique"
    language: "fr"

    search_queries:
      - "transformation organisationnelle mon secteur Maroc 2025"
      - "mon secteur digital transformation Africa organizational"
      # ... 10-16 requêtes recommandées

    rss_feeds:
      - url: "https://exemple.com/feed"
        name: "Nom lisible de la source"
      # ... 3-6 flux minimum

    context_note: >
      Contexte sectoriel : acteurs clés, régulateur, enjeux spécifiques Maroc/Afrique.
      Questions-clés des clients LMS ORH dans ce secteur.
      FOCUS : transformations organisationnelles uniquement (pas de R&D, marchés boursiers...).

    benchmark_axes:
      - "FCS Stratégique : ..."
      - "FCS Organisationnel : ..."
      - "FCS Opérationnel : ..."
      - "FCS Technologique : ..."
      - "FCS Humain & RH : ..."
      - "Dimensionnement : ..."
      - "Gouvernance : ..."
      - "Externalisation & Partenariats : ..."
      - "Systèmes d'Information : ..."
      - "Dimension Afrique & MENA : ..."
      - "RSE & Durabilité : ..."
```

**Valider la configuration :**

```bash
# Vérifier la qualité de la config (10 critères)
python check_agents.py --sector mon_secteur

# Tester les flux RSS en live
python check_sources.py --sector mon_secteur

# Lancer une première analyse de test
python main.py run --sector mon_secteur
```

**Critères de qualité d'un secteur (check_agents.py) :**

| Critère | Minimum recommandé |
|---------|-------------------|
| Requêtes de recherche | ≥ 8 |
| Flux RSS | ≥ 3 |
| Axes benchmark | ≥ 6 |
| context_note | Présent |
| Mots-clés Afrique | ≥ 2 dans les requêtes |
| 4 axes clients couverts | Dimensionnement, Gouvernance, Externalisation, SI |

---

## 7. Lire les rapports générés

Trois formats produits à chaque analyse dans `reports/` :

### DOCX (Word)
Le rapport de référence, structuré en sections :

| Section | Contenu |
|---------|---------|
| Page de titre | Secteur, période, fiabilité des sources |
| Synthèse exécutive | Texte synthétique + note méthodologique |
| Facteurs Clés de Succès | Tableaux par niveau (Stratégique → Humain & RH) |
| Dimensionnement | Tendances effectifs et structures |
| Gouvernance | Pratiques et maturité |
| Gestion de la performance | KPIs et adoption |
| Externalisation | Directions make-or-buy |
| RSE & Éthique | Axes et engagement |
| Signaux faibles | Disruptions émergentes |
| Prospective | Horizons CT/MT + 3 scénarios |
| Recommandations | Tableau priorisé avec angle de mission LMS ORH |
| Sources | Index numéroté de toutes les sources citées |

### HTML (navigateur)
Rapport enrichi avec CSS, cartes colorées, sections interactives :
- **3 lectures So What?** : implications Secteur / Clients / Cabinet LMS ORH
- **Dimension Afrique/MENA** : tableau écarts international vs régional
- **Questions clients** : grille 2×2 des 4 axes (Dimensionnement, Gouvernance, Externalisation, SI)
- Toutes les sections du DOCX + couleurs sémantiques

Ouvrir directement dans un navigateur (`Ctrl+O` dans Chrome/Edge).

### JSON (données brutes)
Archive de toutes les données produites par Claude. Permet de **régénérer** DOCX et HTML
sans relancer l'analyse Claude (économise ~15 min et des tokens API) :

```python
# Régénération depuis JSON existant
import json
from agent import reporter
from pathlib import Path

with open("reports/veille_pharma_maroc_2026-05.json", encoding="utf-8") as f:
    analysis = json.load(f)

import yaml
with open("config/settings.yaml") as f:
    settings = yaml.safe_load(f)

reporter.generate_reports(analysis, settings, ".")
```

### Codes couleur

| Couleur | Signification |
|---------|--------------|
| Rouge `#C0392B` | Critique / Haute priorité / Pessimiste |
| Orange `#E67E22` | Élevée / Moyenne priorité |
| Vert `#27AE60` | Modérée / Faible / Optimiste / Mature |
| Bleu `#2E86C1` | Émergent / Pionnier / En développement |
| Violet `#8E44AD` | RH & Compétences / Modèle hybride |

---

## 8. Diagnostic & maintenance

### Tester les flux RSS

```bash
# Tous les secteurs
python check_sources.py

# Un secteur spécifique
python check_sources.py --sector pharma_maroc
```

Interprétation :
- `[OK] N articles, dernier : M mois [frais]` → source opérationnelle
- `[XX] Connection error` → flux mort, remplacer dans `sectors.yaml`
- `[??] ancien : 18 mois` → flux inactif, à évaluer

### Vérifier la configuration des secteurs

```bash
python check_agents.py
```

Affiche un score sur 10 pour chaque secteur et liste les critères manquants.

### Logs

```
reports/agent.log     # Journal complet (INFO + WARNING + ERROR)
```

### Fichiers temporaires (reprise automatique)

Si une analyse est interrompue (coupure réseau, ngrok déconnecté), des fichiers
`.tmp_<secteur>_part_X.json` sont créés dans `reports/`. Au prochain lancement du
même secteur, les parties déjà calculées sont rechargées automatiquement sans rappeler
Claude. Ils sont supprimés à la fin d'une analyse réussie.

Pour forcer une nouvelle analyse complète (supprimer les tmp) :

```bash
del reports\.tmp_pharma_maroc_*.json    # Windows
# rm reports/.tmp_pharma_maroc_*.json  # Mac / Linux
```

---

*Généré et maintenu par LMS ORH — Observatoire de la Transformation Organisationnelle*
