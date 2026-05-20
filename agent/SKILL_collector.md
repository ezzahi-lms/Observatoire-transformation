# SKILL — collector.py
**Module de collecte des sources de veille**

---

## Rôle

`collector.py` est la première étape du pipeline. Il agrège les articles bruts à partir
de deux canaux complémentaires — flux RSS et recherche web — puis déduplique et tronque
le résultat avant de le passer à l'analyseur.

```
sectors.yaml + settings.yaml
         ↓
    collector.collect()
         ↓
   [article₁, article₂, …, article₆₀]
         ↓
    analyzer.analyze()
```

---

## Interface publique

### `collect(sector_config, settings) → List[Dict]`

Point d'entrée principal. Appelle `collect_rss` puis `collect_web`, fusionne, déduplique
par URL, tronque à `max_articles_total`.

**Paramètres :**

| Paramètre | Type | Source |
|-----------|------|--------|
| `sector_config` | dict | `sectors.yaml` — un bloc secteur |
| `settings` | dict | `settings.yaml` |

**Retour — liste de dicts article :**

```python
{
    "title":   "Titre de l'article",
    "summary": "Résumé (800 chars max)",
    "url":     "https://...",
    "source":  "Nom de la source",
    "date":    "2026-05-01",   # ou "N/A" pour les résultats web
    "type":    "rss" | "web"
}
```

### `collect_rss(sector_config, days_back=35) → List[Dict]`

Parcourt chaque entrée de `rss_feeds` dans le secteur. Filtre les articles plus vieux
que `days_back` jours. Ignore les entrées sans titre.

### `collect_web(sector_config, max_per_query=8) → List[Dict]`

Lance chaque requête de `search_queries` via DuckDuckGo (DDGS). Déduplique les URLs
à l'intérieur de la collecte web (entre requêtes). Les résultats n'ont pas de date.

---

## Configuration (settings.yaml)

```yaml
collection:
  days_back: 35             # Fenêtre temporelle pour les RSS (jours)
  max_search_results: 15    # Résultats max par requête DuckDuckGo
  max_articles_total: 60    # Plafond global envoyé à l'analyseur
```

**Impact du plafond :** Le plafond sert à contrôler la taille du prompt envoyé à Claude.
Chaque article occupe environ 100-150 tokens (titre + résumé 400 chars). 60 articles ≈
7 000-9 000 tokens de contexte source.

---

## Format des flux RSS dans sectors.yaml

```yaml
rss_feeds:
  - url: "https://www.pharmaceutical-technology.com/feed/"
    name: "Pharmaceutical Technology"
  - url: "https://medias24.com/rss"
    name: "Medias24 Maroc"
```

Les entrées sont des **dicts** `{url, name}`. Le champ `name` est utilisé comme
`source` dans les articles collectés (affiché dans les rapports).

---

## Logique de déduplication

1. Déduplication interne web (entre requêtes) : par URL
2. Déduplication globale RSS+web : par URL, ou par titre si URL vide
3. Ordre de priorité : RSS d'abord (articles datés, sources expertes), puis web

---

## Dépendances

| Package | Usage |
|---------|-------|
| `feedparser` | Parsing des flux RSS |
| `duckduckgo-search` (ou `ddgs`) | Recherche web |

---

## Calibration

### Volume d'articles

| Situation | Action |
|-----------|--------|
| Trop peu d'articles (< 20) | Augmenter `days_back`, ajouter des flux RSS, ajouter des requêtes |
| Trop d'articles génériques | Affiner les requêtes (plus spécifiques, ajouter "Maroc", "2025") |
| Articles trop anciens | Réduire `days_back` (ex: 21 jours pour un secteur très actif) |
| Flux RSS morts | Remplacer dans `sectors.yaml`, tester avec `check_sources.py` |

### Qualité des sources

- **RSS > Web** : les articles RSS sont datés et proviennent de sources identifiées —
  Claude les préfère pour sourcer ses affirmations.
- Viser un ratio **60-70% RSS / 30-40% web** pour un benchmark de qualité.
- Les articles web sans date (`"N/A"`) sont marqués `"Contextuelle"` dans l'index sources.

### Requêtes efficaces

Construire des requêtes qui couvrent les 4 axes clients (Dimensionnement, Gouvernance,
Externalisation, SI) et la dimension Afrique/MENA :

```yaml
search_queries:
  # Transformation générale
  - "transformation organisationnelle [secteur] Maroc 2025"
  # Dimension Afrique
  - "[secteur] Africa organizational transformation MENA 2025"
  # Axe Dimensionnement
  - "dimensionnement effectifs [secteur] Maroc externalisation"
  # Axe Gouvernance
  - "gouvernance [secteur] Maroc Afrique conformité"
  # Axe SI
  - "digitalisation SIRH [secteur] Maroc transformation numérique"
  # Acteurs locaux nommés
  - "[Acteur1] [Acteur2] Maroc transformation organisation"
```

---

## Diagnostic

```bash
# Tester les flux RSS d'un secteur en live
python check_sources.py --sector pharma_maroc

# Voir le nombre d'articles collectés
python main.py run --sector pharma_maroc   # Affiche "→ N articles collectés"
```

Lire les logs :
```
reports/agent.log → lignes "RSS [source] : N articles" et "Total articles collectés"
```

---

## Gestion des erreurs

| Erreur | Cause | Comportement |
|--------|-------|-------------|
| `feedparser` timeout | Serveur RSS lent/mort | `logger.warning` + continue |
| DDGS `RatelimitException` | DuckDuckGo rate limit | `logger.warning` + continue |
| URL RSS vide | Config sectors.yaml mal formée | Ignoré silencieusement |
| 0 articles collectés | Tous les flux morts + réseau | `logger.warning`, pipeline s'arrête |
