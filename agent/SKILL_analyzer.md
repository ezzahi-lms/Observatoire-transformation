# SKILL — analyzer.py
**Module d'analyse Claude — Benchmark de transformation organisationnelle**

---

## Rôle

`analyzer.py` est le cœur du pipeline. Il transforme la liste d'articles bruts en un
benchmark structuré exploitable par les consultants LMS ORH, via trois appels successifs
à l'API Claude (model `claude-sonnet-4-6`).

```
[articles] + sector_config + settings
         ↓
    analyzer.analyze()
    ├── Claude Part A  (synthèse, FCS, dimensionnement, gouvernance, performance)
    ├── Claude Part B  (externalisation, RSE, signaux, prospective, recommandations)
    └── Claude Part C  (Afrique/MENA, questions clients, index sources)
         ↓
    {benchmark complet fusionné}
         ↓
    reporter.generate_reports()
```

---

## Interface publique

### `analyze(sector_config, articles, settings, progress_callback=None) → Dict`

Lance les trois appels Claude et retourne le benchmark fusionné.

**Paramètres :**

| Paramètre | Type | Description |
|-----------|------|-------------|
| `sector_config` | dict | Config secteur depuis `sectors.yaml` (avec `"key"` injecté) |
| `articles` | list | Sortie de `collector.collect()` |
| `settings` | dict | Depuis `settings.yaml` |
| `progress_callback` | callable | `fn(step, total, msg)` — pour la progress bar UI |

**Retour :** dict avec toutes les clés des 3 parties + `_meta`.

---

## Architecture 3 appels

### Pourquoi 3 appels ?

La limite de sortie Claude est **8 192 tokens par appel**. Le benchmark complet dépasse
24 000 tokens en sortie. La solution : découper en 3 parties thématiques, chacune avec
son propre schéma JSON (`tool_use`).

### Répartition des parties

| Appel | Outil | Sections | Tokens sortie typiques |
|-------|-------|----------|----------------------|
| **Part A** | `benchmark_part_a` | Synthèse + So What? · Qualité sources · FCS · Dimensionnement · Gouvernance · Performance | ~5 500 |
| **Part B** | `benchmark_part_b` | Externalisation · RSE · Signaux faibles · Prospective · Recommandations (angle_mission) | ~5 500 |
| **Part C** | `benchmark_part_c` | Afrique/MENA · Questions clients (4 axes) · Index sources | ~4 000 |

### Fusion

```python
result = {**part_a, **part_b, **part_c}
```

### Reprise automatique (tmp)

Après chaque appel réussi, le résultat est sérialisé en JSON :

```
reports/.tmp_<sector>_part_a.json
reports/.tmp_<sector>_part_b.json
reports/.tmp_<sector>_part_c.json
```

Au prochain lancement du même secteur, si un tmp existe, il est rechargé sans rappeler
Claude. Les tmp sont supprimés en fin d'analyse réussie.

**Forcer une nouvelle analyse complète :**
```bash
del reports\.tmp_<sector>_*.json
```

---

## Schéma de sortie (clés du dict résultat)

### Part A

```
synthese_executive
  ├── texte                  : str — synthèse 2-4 paragraphes
  ├── sources                : [int] — IDs des sources citées
  └── lectures_so_what
        ├── secteur          : str — So What? pour les acteurs du marché
        ├── clients          : str — So What? pour les clients de LMS ORH
        └── cabinet          : str — So What? pour LMS ORH (opportunités mission)

qualite_sources
  ├── nb_sources_recentes        : int
  ├── nb_sources_secteur_specifiques : int
  ├── fiabilite_globale          : "Élevée" | "Moyenne" | "Limitée"
  └── note_methodologique        : str

facteurs_cles_succes           : [{niveau, facteur, description, importance, sources}]
tendances_dimensionnement      : [{tendance, description, impact_effectifs, fonctions_concernees, sources}]
pratiques_gouvernance          : [{pratique, description, maturite, sources}]
gestion_performance            : [{pratique, description, niveau_adoption, sources}]
```

### Part B

```
externalisation_partenariats   : [{domaine, tendance, direction, sources}]
rse_ethique                    : [{axe, description, niveau_engagement, sources}]
signaux_faibles                : [{signal, implication_organisationnelle, horizon_emergence, sources}]
prospective
  ├── horizon_court_terme      : {periode, evolutions_probables, risques_principaux}
  ├── horizon_moyen_terme      : {periode, evolutions_probables, risques_principaux}
  └── scenarios                : [{nom, description, conditions_realisation, implications_organisationnelles}]
recommandations                : [{action, justification, priorite, horizon, type, angle_mission, sources}]
```

### Part C

```
dimension_afrique_mena
  ├── contexte_regional        : str
  ├── ecarts_vs_international  : [{axe, situation_internationale, situation_afrique_mena, gap_a_combler}]
  └── opportunites_maroc       : [str]

questions_clients
  ├── dimensionnement          : {questions_typiques, tendances_observees, sources}
  ├── gouvernance              : {questions_typiques, tendances_observees, sources}
  ├── externalisation          : {questions_typiques, tendances_observees, sources}
  └── systemes_information     : {questions_typiques, tendances_observees, sources}

index_sources                  : [{id, titre, source, url, date, pertinence}]
```

### Métadonnées

```
_meta
  ├── model                    : str
  ├── sector                   : str
  ├── period                   : str — ex: "mai 2026"
  ├── generated_at             : ISO datetime
  ├── nb_sources_analysees     : int
  └── freshness                : {recent_count, total_dated, pct_recent}
```

---

## SYSTEM_PROMPT — Méthode LMS ORH

Le system prompt (mis en cache côté Anthropic) encode le cadre analytique :

| Composante | Rôle |
|-----------|------|
| **Méthode 4P** | Persona · Process · Périmètre · Produit — structure l'analyse |
| **3 lectures So What?** | Secteur → Clients → Cabinet — oblige Claude à expliciter les implications |
| **Dimension Afrique/MENA** | Contextualisation systématique — différenciateur de l'observatoire |
| **4 questions clients** | Dimensionnement · Gouvernance · Externalisation · SI — cadre les recommandations |
| **Périmètre strict** | "UNIQUEMENT la transformation organisationnelle" — évite les dérives |
| **Concision** | "1-3 phrases max par champ" — contrôle les tokens de sortie |

---

## Valeurs énumérées (contraintes Claude)

Ces enums sont définis dans les schémas `TOOL_PART_*` et forcent Claude à choisir
parmi des valeurs fixes — ce qui garantit la cohérence des couleurs dans les rapports.

| Champ | Valeurs acceptées |
|-------|------------------|
| `importance` (FCS) | Critique · Élevée · Modérée |
| `impact_effectifs` | Réduction · Croissance · Réallocation · Stable · Incertain |
| `maturite` | Émergente · En développement · Mature/Répandue |
| `niveau_adoption` | Pionnier (<20%) · En diffusion (20-60%) · Majoritaire (>60%) |
| `direction` (externalisation) | Vers plus d'externalisation · Vers plus d'internalisation · Nouveaux modèles hybrides · Stable |
| `niveau_engagement` (RSE) | Fort · Modéré · Émergent |
| `nom` (scénarios) | Optimiste · Central · Pessimiste |
| `priorite` (recommandations) | Haute · Moyenne · Faible |
| `type` (recommandations) | Stratégique · Organisationnel · RH & Compétences · Digital · Gouvernance · RSE |
| `pertinence` (index sources) | Directe · Contextuelle |
| `fiabilite_globale` | Élevée · Moyenne · Limitée |
| `niveau` (FCS) | Stratégique · Organisationnel · Opérationnel · Technologique · Humain & RH |

---

## Fallback index_sources

Si Claude retourne un `index_sources` vide dans Part C, `_build_fallback_index()` le
reconstruit automatiquement depuis les articles collectés, en se basant sur les IDs
citées dans les champs `sources: [N, ...]` de toutes les sections. Si aucun ID cité,
tous les articles sont inclus.

---

## Configuration (settings.yaml)

```yaml
analysis:
  model: claude-sonnet-4-6
  max_tokens: 8192      # Limite par appel — ne pas dépasser (3 appels)
  temperature: 0.3      # Bas = factuel et reproductible
```

**Variable d'environnement :** `CLAUDE_MODEL` surcharge `settings.yaml` si définie.

---

## Calibration

### Ajuster les prompts

Les prompts sont construits dans `analyze()`. Chaque partie a un prompt spécifique
qui liste les sections à remplir. Pour modifier les instructions :

```python
# Exemple : rendre les lectures So What? plus orientées missions commerciales
prompt_a = base_prompt + "\n\n... "
"⚠️ So What? Cabinet : prioriser les angles de VENTE DE MISSION ..."
```

### Réduire le volume de Part A ou B si token overflow

Si `benchmark_part_a` dépasse 8 192 tokens en sortie, déplacer une section vers Part C
(ex: `gestion_performance`). Mettre à jour :
1. `TOOL_PART_A` — retirer la propriété + du `required`
2. `TOOL_PART_C` — ajouter la propriété + au `required`
3. `prompt_a` — retirer la mention
4. `prompt_c` — ajouter la mention

### Surveiller les tokens

Les logs affichent après chaque appel :
```
benchmark_part_a — 10314 in / 5491 out (cache: 0)
benchmark_part_b — 10571 in / 7920 out (cache: 0)
benchmark_part_c — 10200 in / 4100 out (cache: 0)
```

Si `out` approche 8 192, anticiper un refactoring de découpe.

---

## Dépendances

| Package | Usage |
|---------|-------|
| `anthropic` | Client API Claude |
| `python-dotenv` | Lecture `.env` |

---

## Gestion des erreurs

| Erreur | Cause | Action |
|--------|-------|--------|
| `ValueError: ANTHROPIC_API_KEY manquant` | `.env` absent ou vide | Vérifier `.env` |
| `RuntimeError: Claude n'a pas retourné de résultat` | `tool_use` non déclenché | Vérifier le schéma TOOL_PART_* |
| Blocage à l'étape 2/3 | Timeout réseau (ngrok) | Les tmp sauvegardent la progression — relancer |
| `index_sources` vide | Claude a oublié Part C | Fallback automatique depuis les articles |
