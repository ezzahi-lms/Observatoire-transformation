# CALIBRATION — Observatoire de la Transformation Organisationnelle
**Guide de réglage fin de l'agent de veille LMS ORH**

---

## 1. Principes de calibration

L'agent a trois leviers principaux :

```
┌─────────────────────────────────────────────────────────────────┐
│  COLLECTE          ANALYSE              RAPPORT                  │
│                                                                  │
│  Volume ?     →   Pertinence ?     →   Lisibilité ?             │
│  Fraîcheur ?  →   Profondeur ?     →   Exploitabilité ?         │
│  Couverture ? →   Token budget ?   →   Format adapté ?          │
└─────────────────────────────────────────────────────────────────┘
```

Chaque réglage dans cette section indique quel levier il actionne et quel fichier
éditer.

---

## 2. Calibration de la collecte

**Fichier :** `config/settings.yaml` (paramètres globaux) et `config/sectors.yaml`
(paramètres par secteur)

### Volume d'articles

```yaml
collection:
  days_back: 35              # Fenêtre RSS (jours)
  max_search_results: 15     # Résultats par requête DuckDuckGo
  max_articles_total: 60     # Plafond global envoyé à Claude
```

| Symptôme | Ajustement |
|----------|-----------|
| Articles < 20 pour un secteur actif | Augmenter `days_back` → 60 jours |
| Articles très génériques (non sectoriels) | Affiner les `search_queries` |
| Trop d'articles anglophones sur un secteur marocain | Ajouter requêtes FR avec "Maroc 2025" |
| Dépassement token input (>12 000) | Réduire `max_articles_total` → 45 |

### Seuil de fraîcheur

Un article est "récent" si daté de moins de 12 mois. Le taux de fraîcheur est affiché
dans le rapport et dans les logs. Valeur cible : **≥ 50 % d'articles récents**.

Si le taux est faible :
1. Réduire `days_back` sur un secteur à forte production (ex: 21 jours)
2. Remplacer les flux RSS peu actifs (tester avec `check_sources.py`)
3. Ajouter des flux qui publient fréquemment (journaux marocains : Medias24, Challenge)

### Qualité des flux RSS

```bash
# Diagnostic complet en live
python check_sources.py

# Par secteur
python check_sources.py --sector banque_finance
```

Indicateurs :
- `[OK] N articles [frais]` → garder
- `[OK] N articles [acceptable]` (3-12 mois) → surveiller
- `[??] ancien : >12 mois` → remplacer si possible
- `[XX]` → remplacer immédiatement

**Remplacer un flux mort :**
1. Trouver l'alternative sur le site source (souvent `/feed`, `/rss`, `/feed/news/`)
2. Tester manuellement : `python -c "import feedparser; f=feedparser.parse('URL'); print(len(f.entries))"`
3. Mettre à jour `sectors.yaml`
4. Relancer `check_sources.py` pour confirmer

### Équilibre RSS / Web

Le ratio optimal est **60-70 % RSS / 30-40 % web** :
- Les articles RSS sont datés → Claude peut évaluer la fraîcheur
- Les articles RSS ont une source identifiée → meilleure attribution [N]
- Les résultats web complètent avec des requêtes ciblées Maroc/Afrique

Si trop peu de flux RSS disponibles pour un secteur, augmenter `max_search_results`
pour compenser avec plus de résultats web.

---

## 3. Calibration de l'analyse Claude

**Fichier :** `agent/analyzer.py`

### Budget tokens par appel

Limite : **8 192 tokens en sortie** par appel. Surveiller dans les logs :

```
benchmark_part_a — 10314 in / 5491 out  ← OK (marge de 2700)
benchmark_part_b — 10571 in / 7920 out  ← ATTENTION (marge de 272)
benchmark_part_c — 10200 in / 4100 out  ← OK (marge de 4092)
```

Si `out` dépasse régulièrement **7 500** pour une partie, anticiper le redécoupage
avant le prochain overflow (qui provoque un blocage silencieux).

**Redécouper une partie surchargée :**

Exemple : Part B approche 8 192 tokens → déplacer `rse_ethique` vers Part C.

```python
# 1. Retirer de TOOL_PART_B.properties + required
# 2. Ajouter dans TOOL_PART_C.properties + required
# 3. Retirer de prompt_b, ajouter dans prompt_c
# 4. Vérifier : py -c "import agent.analyzer; print('OK')"
```

### Température et reproductibilité

```yaml
analysis:
  temperature: 0.3    # Factuel et stable (recommandé)
```

- `0.0` → très reproductible, moins de variation entre deux analyses du même secteur
- `0.3` → bon équilibre factuel/nuancé (valeur actuelle)
- `0.7+` → plus créatif mais moins stable, déconseillé pour les benchmarks factuels

### Ajuster les prompts

Les prompts sont dans `analyze()` sous `prompt_a`, `prompt_b`, `prompt_c`. Chaque
prompt = `base_prompt` + instructions spécifiques à la partie.

**Renforcer la rigueur :**
```
"⚠️ OBLIGATOIRE — chaque item doit citer au moins une source [N]."
```

**Orienter les recommandations vers les missions LMS ORH :**
```
"Chaque angle_mission doit nommer un livrable concret LMS ORH :
ex. 'Diagnostic organisationnel', 'Étude de dimensionnement',
'Design de gouvernance', 'Accompagnement SIRH', 'Plan de transformation'."
```

**Forcer plus d'écarts dans la section Afrique/MENA :**
```
"ecarts_vs_international : inclure au moins 4 axes d'écart avec
des chiffres quand disponibles (ex. taux d'encadrement, niveau digital)."
```

### Modifier le SYSTEM_PROMPT

Le SYSTEM_PROMPT est mis en **cache côté Anthropic** (cache_control ephemeral, TTL 5 min).
Le modifier déclenche un recalcul du cache au prochain appel (surcoût tokens).

Éviter de le modifier à chaque run. Le modifier uniquement pour :
- Changer de méthode d'analyse (ajout d'un nouveau cadre)
- Corriger un biais systématique constaté sur plusieurs secteurs
- Ajouter une contrainte de périmètre nouvelle

---

## 4. Calibration par secteur

**Fichier :** `config/sectors.yaml`

### context_note — le levier le plus puissant

La `context_note` est injectée directement dans le `base_prompt` de chaque appel.
C'est la principale façon de spécialiser Claude pour un secteur :

```yaml
context_note: >
  [Contexte factuel : acteurs, chiffres, régulateur]
  Questions-clés des clients LMS ORH : comment...? quel...?
  FOCUS : transformations organisationnelles UNIQUEMENT.
  [Optionnel : périmètre négatif] PAS les résultats financiers purs.
```

**Bonne context_note :**
- Nomme les acteurs locaux majeurs (Claude peut les citer dans le benchmark)
- Donne des chiffres de référence (marchés, emplois, taux)
- Formule les questions clients comme les vrais clients le feraient
- Rappelle explicitement le périmètre ("UNIQUEMENT")

**À éviter :**
- Trop courte (< 3 lignes) → Claude généralise trop
- Trop longue (> 30 lignes) → dilue le signal dans le prompt

### benchmark_axes — les axes prioritaires

Les `benchmark_axes` structurent les instructions données à Claude. Ils apparaissent
sous forme de bullets dans le `base_prompt`.

Format recommandé :
```yaml
benchmark_axes:
  # Un axe = "Catégorie : détail spécifique au secteur"
  - "FCS Stratégique : [enjeux stratégiques propres au secteur]"
  - "Dimensionnement : [tendances d'effectifs spécifiques]"
  - "Gouvernance : [structure de gouvernance locale]"
  - "Externalisation & Partenariats : [logique make-or-buy du secteur]"
  - "Systèmes d'Information : [SI spécifiques du secteur]"
  - "Dimension Afrique & MENA : [best practices régionaux nommés]"
  - "RSE & Durabilité : [enjeux RSE spécifiques]"
```

Viser **8-12 axes**. Trop peu → benchmark générique. Trop nombreux → Claude superficiel.

### search_queries — couvrir les 4 axes clients

Construire des requêtes qui couvrent systématiquement :

| Axe client | Exemple de requête |
|-----------|-------------------|
| Dimensionnement | `"dimensionnement effectifs [secteur] Maroc ratio encadrement"` |
| Gouvernance | `"gouvernance [secteur] Maroc Afrique conformité réglementation"` |
| Externalisation | `"externalisation outsourcing [secteur] Maroc make-or-buy"` |
| SI | `"digitalisation SIRH ERP [secteur] Maroc transformation numérique"` |
| Afrique/MENA | `"[secteur] Africa MENA transformation organisationnelle hub Maroc"` |
| Acteurs locaux | `"[Acteur1] [Acteur2] transformation organisation Maroc"` |

---

## 5. Diagnostic qualité d'un secteur

```bash
python check_agents.py --sector mon_secteur
```

Score sur 10 critères :

| Critère | Poids | Vérification |
|---------|-------|-------------|
| Label défini | — | `label` présent |
| Requêtes suffisantes | ≥ 8 | `len(search_queries)` |
| Flux RSS suffisants | ≥ 3 | `len(rss_feeds)` |
| Axes suffisants | ≥ 6 | `len(benchmark_axes)` |
| context_note | Présent | Champ non vide |
| Mots-clés Afrique | ≥ 2 | Requêtes contenant "Afrique/Africa/MENA/Maroc" |
| Axe Dimensionnement | Présent | Dans requêtes OU axes |
| Axe Gouvernance | Présent | Dans requêtes OU axes |
| Axe Externalisation | Présent | Dans requêtes OU axes |
| Axe SI | Présent | Dans requêtes OU axes |

**Cible : 10/10 pour tous les secteurs avant mise en production.**

---

## 6. Calibration du rapport

**Fichier :** `templates/report.html` et `agent/reporter.py`

### Modifier les couleurs sémantiques

Les palettes sont définies en tête de `reporter.py` :

```python
IMPORTANCE_COLORS = {"Critique": "C0392B", "Élevée": "E67E22", "Modérée": "27AE60"}
```

Modifier ici pour changer les couleurs dans DOCX et HTML simultanément.

### Ajouter une section au DOCX

Voir `agent/SKILL_reporter.md` — section "Ajouter une section au rapport DOCX".

### Modifier le template HTML

1. Éditer `templates/report.html` directement
2. Régénérer depuis le JSON sans rappeler Claude :

```bash
python -c "
import json, yaml
from agent import reporter

with open('reports/veille_pharma_maroc_2026-05.json', encoding='utf-8') as f:
    analysis = json.load(f)
with open('config/settings.yaml') as f:
    settings = yaml.safe_load(f)

reporter.generate_reports(analysis, settings, '.')
print('Rapport régénéré.')
"
```

---

## 7. Procédure de test d'un nouveau secteur

```
1. Ajouter le secteur dans sectors.yaml
2. python check_agents.py --sector ma_cle       → 10/10 ?
3. python check_sources.py --sector ma_cle      → 0 flux XX ?
4. python main.py run --sector ma_cle           → pipeline complet
5. Ouvrir reports/*.html dans le navigateur     → sections complètes ?
6. Ouvrir reports/*.docx dans Word              → mise en forme correcte ?
7. Vérifier index_sources dans le JSON          → sources bien citées ?
8. Vérifier lectures_so_what                    → 3 angles distincts ?
9. Vérifier dimension_afrique_mena              → contexte régional présent ?
10. Vérifier questions_clients                  → 4 axes couverts ?
```

---

## 8. Réglages recommandés par type de secteur

| Type de secteur | `days_back` | `max_articles_total` | Nb requêtes | Nb flux RSS |
|----------------|------------|---------------------|------------|------------|
| Secteur marocain très actif (pharma, banque) | 35 | 60 | 12-16 | 6-8 |
| Secteur marocain peu médiatisé (distribution) | 60 | 60 | 10-12 | 4-6 |
| Secteur avec bonne couverture internationale | 35 | 60 | 10-14 | 5-7 |
| Secteur émergent / peu de RSS disponibles | 60 | 45 | 14-16 | 3-4 |

---

## 9. Suivi dans le temps

### Signaux d'alerte à surveiller

| Signal | Action |
|--------|--------|
| `fiabilite_globale: Limitée` dans le rapport | Revoir les flux RSS et requêtes |
| Moins de 30 % d'articles récents (< 12 mois) | Réduire `days_back` |
| Benchmark générique (non sectoriel) | Renforcer `context_note` et `benchmark_axes` |
| `index_sources` reconstruit automatiquement | Claude n'a pas cité les sources → revoir le prompt |
| Part B régulièrement proche de 8 192 tokens | Anticiper un redécoupage |
| Blocage après mise à jour sectors.yaml | Vérifier syntaxe YAML : `python check_agents.py` |

### Calendrier de maintenance recommandé

| Fréquence | Action |
|-----------|--------|
| Mensuel (après chaque analyse) | Vérifier les flux RSS (`check_sources.py`) |
| Trimestriel | Revoir les `search_queries` (nouvelles thématiques émergentes ?) |
| Semestriel | Revoir les `benchmark_axes` et `context_note` (évolution du secteur ?) |
| Annuel | Évaluer l'ajout de nouveaux secteurs, retirer les obsolètes |
