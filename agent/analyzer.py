"""
Benchmark de transformation organisationnelle via Claude.
Deux appels enchaînés pour contourner la limite de tokens :
  - Appel A : synthèse + 3 lectures So What?, qualité sources, FCS, dimensionnement,
              gouvernance, performance, dimension Afrique/MENA, questions clients
  - Appel B : externalisation, RSE, signaux faibles, prospective, recommandations
              (avec angle_mission conseil), index sources
"""
import logging
import os
from datetime import datetime
from typing import List, Dict, Any

import anthropic

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────
#  TOOL PART A
# ─────────────────────────────────────────

TOOL_PART_A = {
    "name": "benchmark_part_a",
    "description": "Stocke la 1re partie du benchmark (synthèse + 3 lectures So What?, FCS, dimensionnement, gouvernance, performance, Afrique/MENA, questions clients).",
    "input_schema": {
        "type": "object",
        "properties": {
            "synthese_executive": {
                "type": "object",
                "properties": {
                    "texte": {"type": "string"},
                    "sources": {"type": "array", "items": {"type": "integer"}},
                    "lectures_so_what": {
                        "type": "object",
                        "description": "3 lectures So What? de la synthèse : implications pour le secteur, pour les clients de LMS, pour LMS ORH",
                        "properties": {
                            "secteur": {
                                "type": "string",
                                "description": "So What? pour le secteur : que signifient ces tendances pour les acteurs du marché ?"
                            },
                            "clients": {
                                "type": "string",
                                "description": "So What? pour les clients de LMS : quels enjeux RH/orga cela crée-t-il pour nos clients ?"
                            },
                            "cabinet": {
                                "type": "string",
                                "description": "So What? pour LMS ORH : quelles opportunités de mission, d'offre ou de positionnement ?"
                            }
                        },
                        "required": ["secteur", "clients", "cabinet"]
                    }
                },
                "required": ["texte", "lectures_so_what"]
            },
            "qualite_sources": {
                "type": "object",
                "properties": {
                    "nb_sources_recentes": {"type": "integer"},
                    "nb_sources_secteur_specifiques": {"type": "integer"},
                    "fiabilite_globale": {"type": "string", "enum": ["Élevée", "Moyenne", "Limitée"]},
                    "note_methodologique": {"type": "string"}
                },
                "required": ["fiabilite_globale", "note_methodologique"]
            },
            "facteurs_cles_succes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "niveau": {"type": "string", "enum": ["Stratégique", "Organisationnel", "Opérationnel", "Technologique", "Humain & RH"]},
                        "facteur": {"type": "string"},
                        "description": {"type": "string"},
                        "importance": {"type": "string", "enum": ["Critique", "Élevée", "Modérée"]},
                        "sources": {"type": "array", "items": {"type": "integer"}}
                    },
                    "required": ["niveau", "facteur", "description", "importance"]
                }
            },
            "tendances_dimensionnement": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "tendance": {"type": "string"},
                        "description": {"type": "string"},
                        "impact_effectifs": {"type": "string", "enum": ["Réduction", "Croissance", "Réallocation", "Stable", "Incertain"]},
                        "fonctions_concernees": {"type": "array", "items": {"type": "string"}},
                        "sources": {"type": "array", "items": {"type": "integer"}}
                    },
                    "required": ["tendance", "description", "impact_effectifs"]
                }
            },
            "pratiques_gouvernance": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "pratique": {"type": "string"},
                        "description": {"type": "string"},
                        "maturite": {"type": "string", "enum": ["Émergente", "En développement", "Mature/Répandue"]},
                        "sources": {"type": "array", "items": {"type": "integer"}}
                    },
                    "required": ["pratique", "description", "maturite"]
                }
            },
            "gestion_performance": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "pratique": {"type": "string"},
                        "description": {"type": "string"},
                        "niveau_adoption": {"type": "string", "enum": ["Pionnier (<20%)", "En diffusion (20-60%)", "Majoritaire (>60%)"]},
                        "sources": {"type": "array", "items": {"type": "integer"}}
                    },
                    "required": ["pratique", "description", "niveau_adoption"]
                }
            }
        },
            "dimension_afrique_mena": {
                "type": "object",
                "description": "Analyse spécifique Afrique/MENA : particularités, écarts et opportunités vs benchmark international",
                "properties": {
                    "contexte_regional": {
                        "type": "string",
                        "description": "Spécificités du marché Afrique/MENA pour ce secteur (réglementation, maturité, dynamiques locales)"
                    },
                    "ecarts_vs_international": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "axe": {"type": "string"},
                                "situation_internationale": {"type": "string"},
                                "situation_afrique_mena": {"type": "string"},
                                "gap_a_combler": {"type": "string"}
                            },
                            "required": ["axe", "situation_afrique_mena", "gap_a_combler"]
                        }
                    },
                    "opportunites_maroc": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Opportunités spécifiques de transformation orga pour les entreprises marocaines du secteur"
                    },
                    "sources": {"type": "array", "items": {"type": "integer"}}
                },
                "required": ["contexte_regional", "opportunites_maroc"]
            },
            "questions_clients": {
                "type": "object",
                "description": "Les 4 grandes questions orga que posent les clients du secteur à LMS ORH",
                "properties": {
                    "dimensionnement": {
                        "type": "object",
                        "properties": {
                            "questions_typiques": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Questions des clients sur taille des équipes, structures, ratios d'encadrement"
                            },
                            "tendances_observees": {"type": "string"},
                            "sources": {"type": "array", "items": {"type": "integer"}}
                        },
                        "required": ["questions_typiques", "tendances_observees"]
                    },
                    "gouvernance": {
                        "type": "object",
                        "properties": {
                            "questions_typiques": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Questions des clients sur modes de décision, reporting, conformité, contrôle"
                            },
                            "tendances_observees": {"type": "string"},
                            "sources": {"type": "array", "items": {"type": "integer"}}
                        },
                        "required": ["questions_typiques", "tendances_observees"]
                    },
                    "externalisation": {
                        "type": "object",
                        "properties": {
                            "questions_typiques": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Questions des clients sur make-or-buy, sous-traitance, modèles hybrides"
                            },
                            "tendances_observees": {"type": "string"},
                            "sources": {"type": "array", "items": {"type": "integer"}}
                        },
                        "required": ["questions_typiques", "tendances_observees"]
                    },
                    "systemes_information": {
                        "type": "object",
                        "properties": {
                            "questions_typiques": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Questions des clients sur digitalisation, SIRH, ERP, IA dans les processus orga"
                            },
                            "tendances_observees": {"type": "string"},
                            "sources": {"type": "array", "items": {"type": "integer"}}
                        },
                        "required": ["questions_typiques", "tendances_observees"]
                    }
                },
                "required": ["dimensionnement", "gouvernance", "externalisation", "systemes_information"]
            }
        },
        "required": ["synthese_executive", "qualite_sources", "facteurs_cles_succes",
                     "tendances_dimensionnement", "pratiques_gouvernance", "gestion_performance",
                     "dimension_afrique_mena", "questions_clients"]
    }
}

# ─────────────────────────────────────────
#  TOOL PART B
# ─────────────────────────────────────────

TOOL_PART_B = {
    "name": "benchmark_part_b",
    "description": "Stocke la 2e partie du benchmark (externalisation, RSE, signaux, prospective, recommandations, sources).",
    "input_schema": {
        "type": "object",
        "properties": {
            "externalisation_partenariats": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "domaine": {"type": "string"},
                        "tendance": {"type": "string"},
                        "direction": {"type": "string", "enum": ["Vers plus d'externalisation", "Vers plus d'internalisation", "Nouveaux modèles hybrides", "Stable"]},
                        "sources": {"type": "array", "items": {"type": "integer"}}
                    },
                    "required": ["domaine", "tendance", "direction"]
                }
            },
            "rse_ethique": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "axe": {"type": "string"},
                        "description": {"type": "string"},
                        "niveau_engagement": {"type": "string", "enum": ["Fort", "Modéré", "Émergent"]},
                        "sources": {"type": "array", "items": {"type": "integer"}}
                    },
                    "required": ["axe", "description", "niveau_engagement"]
                }
            },
            "signaux_faibles": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "signal": {"type": "string"},
                        "implication_organisationnelle": {"type": "string"},
                        "horizon_emergence": {"type": "string"},
                        "sources": {"type": "array", "items": {"type": "integer"}}
                    },
                    "required": ["signal", "implication_organisationnelle", "horizon_emergence"]
                }
            },
            "prospective": {
                "type": "object",
                "properties": {
                    "horizon_court_terme": {
                        "type": "object",
                        "properties": {
                            "periode": {"type": "string"},
                            "evolutions_probables": {"type": "array", "items": {"type": "string"}},
                            "risques_principaux": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["periode", "evolutions_probables", "risques_principaux"]
                    },
                    "horizon_moyen_terme": {
                        "type": "object",
                        "properties": {
                            "periode": {"type": "string"},
                            "evolutions_probables": {"type": "array", "items": {"type": "string"}},
                            "risques_principaux": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["periode", "evolutions_probables", "risques_principaux"]
                    },
                    "scenarios": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "nom": {"type": "string", "enum": ["Optimiste", "Central", "Pessimiste"]},
                                "description": {"type": "string"},
                                "conditions_realisation": {"type": "string"},
                                "implications_organisationnelles": {"type": "string"}
                            },
                            "required": ["nom", "description", "implications_organisationnelles"]
                        }
                    }
                },
                "required": ["horizon_court_terme", "horizon_moyen_terme", "scenarios"]
            },
            "recommandations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string"},
                        "justification": {"type": "string"},
                        "priorite": {"type": "string", "enum": ["Haute", "Moyenne", "Faible"]},
                        "horizon": {"type": "string"},
                        "type": {"type": "string", "enum": ["Stratégique", "Organisationnel", "RH & Compétences", "Digital", "Gouvernance", "RSE"]},
                        "angle_mission": {
                            "type": "string",
                            "description": "Angle d'intervention conseil LMS ORH : quelle mission concrète ce besoin peut-il générer ? (ex. diagnostic organisationnel, étude de dimensionnement, design de gouvernance, accompagnement SI-RH...)"
                        },
                        "sources": {"type": "array", "items": {"type": "integer"}}
                    },
                    "required": ["action", "justification", "priorite", "horizon", "type", "angle_mission"]
                }
            },
            "index_sources": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "titre": {"type": "string"},
                        "source": {"type": "string"},
                        "url": {"type": "string"},
                        "date": {"type": "string"},
                        "pertinence": {"type": "string", "enum": ["Directe", "Contextuelle"]}
                    },
                    "required": ["id", "titre", "source", "pertinence"]
                }
            }
        },
        "required": ["externalisation_partenariats", "rse_ethique", "signaux_faibles",
                     "prospective", "recommandations", "index_sources"]
    }
}

# ─────────────────────────────────────────
#  SYSTEM PROMPT (mis en cache)
# ─────────────────────────────────────────

SYSTEM_PROMPT = """Tu es un expert senior en veille stratégique, associé chez LMS ORH — cabinet \
de conseil en transformation organisationnelle au Maroc & Afrique. Ta mission : produire des \
BENCHMARKS SECTORIELS exploitables par des dirigeants et consultants senior.

## Cadre de référence — Méthode 4P de LMS ORH

Chaque analyse doit être structurée autour des 4 dimensions clés :
- **Persona** : qui sont les acteurs (DRH, DAF, DG, régulateurs, syndicats…) et leurs préoccupations
- **Process** : quels processus organisationnels sont en transformation (RH, finance, opérations, SI…)
- **Périmètre** : quelle géographie, quelle taille d'entreprise, quel sous-secteur
- **Produit** : quelles solutions ou offres émergent pour adresser ces transformations

## 3 lectures "So What ?" obligatoires

Pour chaque constat majeur, produire 3 niveaux d'implication :
1. **So What? Secteur** : que signifie cette tendance pour les acteurs du secteur ?
2. **So What? Clients** : quels enjeux RH/orga cela crée-t-il pour les clients de LMS ORH ?
3. **So What? Cabinet** : quelle opportunité de mission ou d'offre pour LMS ORH ?

## Dimension Afrique/MENA — OBLIGATOIRE

Tout benchmark doit inclure :
- Contextualisation Maroc/Afrique subsaharienne/MENA
- Écarts identifiés entre pratiques internationales et réalités africaines
- Opportunités spécifiques pour les entreprises marocaines et africaines
- Particularités réglementaires, culturelles et de maturité organisationnelle

## 4 questions clients que LMS ORH adresse dans le secteur

Structurer les insights selon les 4 types de questions récurrentes des clients :
1. **Dimensionnement** : taille des équipes, ratios d'encadrement, structures
2. **Gouvernance** : modes de décision, reporting, conformité, contrôle
3. **Externalisation** : make-or-buy, modèles hybrides, sous-traitance
4. **Systèmes d'Information (SI)** : digitalisation, SIRH, ERP, IA dans les processus orga

## Axes du benchmark à couvrir

1. Facteurs Clés de Succès (stratégique → opérationnel → RH)
2. Tendances de dimensionnement des effectifs et structures
3. Pratiques de gouvernance (décision, conformité, reporting)
4. Gestion de la performance (KPIs, évaluation, incentives)
5. Externalisation & partenariats (make-or-buy, alliances)
6. RSE & Éthique (ESG, accès, diversité, environnement)
7. Signaux faibles (disruptions émergentes)
8. Analyse prospective avec scénarios (1-3 ans / 3-5 ans)
9. Recommandations avec angle de mission conseil LMS ORH

## Règle de citation des sources

Chaque affirmation DOIT être appuyée par [N] (numéro de la source). \
Si non sourcée depuis les articles, formuler comme "Tendance structurelle : …".

## Périmètre

UNIQUEMENT la transformation organisationnelle : structures, modèles opérationnels, RH, culture, \
gouvernance, digitalisation des organisations.
PAS les pipelines R&D, résultats cliniques, actualités boursières pures.

## Concision

Chaque champ texte : 1-3 phrases maximum. Factuel, direct, exploitable par des décideurs.

Langue : français, registre professionnel consultant senior."""


def _compute_freshness(articles: List[Dict]) -> Dict:
    now = datetime.now()
    recent, total = 0, 0
    for a in articles:
        d = a.get("date", "")
        if d and d != "N/A":
            try:
                if (now - datetime.fromisoformat(d)).days <= 365:
                    recent += 1
                total += 1
            except Exception:
                pass
    return {"recent_count": recent, "total_dated": total,
            "pct_recent": round(recent / total * 100) if total else 0}


def _format_articles(articles: List[Dict]) -> str:
    lines = [f"## {len(articles)} sources numérotées — citer via [N]\n"]
    for i, a in enumerate(articles, 1):
        date = a.get("date", "N/A")
        age = ""
        if date != "N/A":
            try:
                months = (datetime.now() - datetime.fromisoformat(date)).days // 30
                age = f" ⚠️{months}m" if months > 18 else f" ({months}m)"
            except Exception:
                pass
        lines.append(f"[{i}] {a['source']} {date}{age} | {a['title']}")
        if a.get("summary"):
            lines.append(f"     {a['summary'][:400]}")
        lines.append("")
    return "\n".join(lines)


def _collect_cited_ids(data) -> set:
    """Parcourt récursivement le résultat et collecte tous les IDs de sources cités."""
    ids = set()
    if isinstance(data, dict):
        for k, v in data.items():
            if k == "sources" and isinstance(v, list):
                for s in v:
                    if isinstance(s, int):
                        ids.add(s)
            else:
                ids |= _collect_cited_ids(v)
    elif isinstance(data, list):
        for item in data:
            ids |= _collect_cited_ids(item)
    return ids


def _build_fallback_index(articles: List[Dict], result: Dict) -> List[Dict]:
    """
    Reconstruit l'index_sources depuis les articles collectés en se basant
    sur les IDs cités dans le résultat (champs `sources: [N, ...]`).
    Si aucun ID n'est trouvé, inclut tous les articles.
    """
    cited_ids = _collect_cited_ids(result)

    # Si Claude n'a cité aucun ID via les champs sources, inclure tous les articles
    if not cited_ids:
        cited_ids = set(range(1, len(articles) + 1))

    index = []
    for idx in sorted(cited_ids):
        if 1 <= idx <= len(articles):
            a = articles[idx - 1]
            date_val = a.get("date", "")
            # Normaliser la date
            if date_val and date_val != "N/A":
                try:
                    date_val = datetime.fromisoformat(date_val).strftime("%Y-%m-%d")
                except Exception:
                    pass
            index.append({
                "id": idx,
                "titre": a.get("title", "Sans titre")[:120],
                "source": a.get("source", ""),
                "url": a.get("url", ""),
                "date": date_val or "N/A",
                "pertinence": "Directe" if a.get("type") == "rss" else "Contextuelle",
            })
    return index


def _call_claude(client, model, max_tokens, system_cached, tool, tool_name, user_prompt):
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=[{"type": "text", "text": system_cached, "cache_control": {"type": "ephemeral"}}],
        tools=[tool],
        tool_choice={"type": "tool", "name": tool_name},
        messages=[{"role": "user", "content": user_prompt}],
    )
    for block in resp.content:
        if block.type == "tool_use" and block.name == tool_name:
            logger.info(
                f"{tool_name} — {resp.usage.input_tokens} in / {resp.usage.output_tokens} out "
                f"(cache: {getattr(resp.usage, 'cache_read_input_tokens', 0)})"
            )
            return block.input
    raise RuntimeError(f"Claude n'a pas retourné de résultat pour {tool_name}.")


def analyze(sector_config: Dict, articles: List[Dict], settings: Dict) -> Dict[str, Any]:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY manquant. Ajoutez votre clé dans le fichier .env.")

    model = (os.environ.get("CLAUDE_MODEL")
             or settings.get("analysis", {}).get("model", "claude-sonnet-4-6"))
    max_tokens = settings.get("analysis", {}).get("max_tokens", 8192)
    client = anthropic.Anthropic(api_key=api_key)

    sector_label = sector_config.get("label", "secteur")
    period = datetime.now().strftime("%B %Y")
    context_note = sector_config.get("context_note", "")
    benchmark_axes = sector_config.get("benchmark_axes", sector_config.get("focus_areas", []))
    freshness = _compute_freshness(articles)
    articles_text = _format_articles(articles)

    axes_str = "\n".join(f"• {a}" for a in benchmark_axes)
    ctx = f"\n**Contexte :** {context_note}\n" if context_note else ""
    fresh_note = (
        f"\n**Fraîcheur :** {freshness['recent_count']}/{len(articles)} articles <12 mois "
        f"({freshness['pct_recent']}%). Signaler si insuffisant.\n"
    )

    base_prompt = f"""Benchmark de transformation organisationnelle — **{sector_label}** — **{period}**
{ctx}{fresh_note}
**Axes prioritaires :**
{axes_str}

**Sources (citer via [N]) :**
{articles_text}"""

    logger.info("Appel Claude Part A (synthèse + So What?, FCS, dimensionnement, gouvernance, performance, Afrique/MENA, questions clients)...")
    prompt_a = (
        base_prompt
        + "\n\nUtilise `benchmark_part_a` pour les sections :\n"
        "1. synthèse exécutive (avec les 3 lectures So What? : secteur / clients LMS / cabinet LMS ORH)\n"
        "2. qualité des sources\n"
        "3. facteurs clés de succès (tous niveaux)\n"
        "4. tendances de dimensionnement\n"
        "5. pratiques de gouvernance\n"
        "6. gestion de la performance\n"
        "7. dimension Afrique/MENA (contexte régional, écarts vs international, opportunités Maroc)\n"
        "8. questions clients (dimensionnement / gouvernance / externalisation / systèmes d'information)\n\n"
        "⚠️ Les lectures_so_what dans synthese_executive sont OBLIGATOIRES — 3 angles distincts : "
        "secteur, clients de LMS, cabinet LMS ORH. Dimension Afrique/MENA également OBLIGATOIRE."
    )
    part_a = _call_claude(client, model, max_tokens, SYSTEM_PROMPT, TOOL_PART_A, "benchmark_part_a", prompt_a)

    logger.info("Appel Claude Part B (externalisation, RSE, signaux, prospective, recommandations + angle_mission)...")
    prompt_b = (
        base_prompt
        + "\n\nUtilise `benchmark_part_b` pour les sections :\n"
        "1. externalisation & partenariats\n"
        "2. RSE & éthique\n"
        "3. signaux faibles\n"
        "4. analyse prospective avec 3 scénarios (Optimiste / Central / Pessimiste)\n"
        "5. recommandations stratégiques (5-8) — chacune DOIT avoir un `angle_mission` : "
        "quelle mission concrète LMS ORH peut-il proposer en réponse à ce besoin ?\n\n"
        "⚠️ OBLIGATOIRE — `index_sources` : liste TOUTES les sources citées via [N] dans "
        "l'ENSEMBLE du benchmark (Part A + Part B). Pour chaque source citée, inclure id=N, "
        "titre, source, url, date, pertinence. Un index vide ou incomplet rend le rapport "
        "inexploitable pour les décideurs."
    )
    part_b = _call_claude(client, model, max_tokens, SYSTEM_PROMPT, TOOL_PART_B, "benchmark_part_b", prompt_b)

    # Fusion
    result = {**part_a, **part_b}

    # ── Reconstruction de l'index si Claude ne l'a pas rempli ─────────────────
    if not result.get("index_sources"):
        logger.warning("index_sources vide — reconstruction automatique depuis les articles collectés.")
        result["index_sources"] = _build_fallback_index(articles, result)
        logger.info(f"Index reconstruit : {len(result['index_sources'])} sources.")

    result["_meta"] = {
        "model": model, "sector": sector_label, "period": period,
        "generated_at": datetime.now().isoformat(),
        "nb_sources_analysees": len(articles),
        "freshness": freshness,
    }
    logger.info("Benchmark complet — deux appels fusionnés avec succès.")
    return result
