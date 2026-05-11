"""
Benchmark de transformation organisationnelle via Claude.
Deux appels enchaînés pour contourner la limite de tokens :
  - Appel A : synthèse, qualité sources, FCS, dimensionnement, gouvernance, performance
  - Appel B : externalisation, RSE, signaux faibles, prospective, recommandations, index sources
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
    "description": "Stocke la 1re partie du benchmark (synthèse, FCS, dimensionnement, gouvernance, performance).",
    "input_schema": {
        "type": "object",
        "properties": {
            "synthese_executive": {
                "type": "object",
                "properties": {
                    "texte": {"type": "string"},
                    "sources": {"type": "array", "items": {"type": "integer"}}
                },
                "required": ["texte"]
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
        "required": ["synthese_executive", "qualite_sources", "facteurs_cles_succes",
                     "tendances_dimensionnement", "pratiques_gouvernance", "gestion_performance"]
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
                        "sources": {"type": "array", "items": {"type": "integer"}}
                    },
                    "required": ["action", "justification", "priorite", "horizon", "type"]
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

SYSTEM_PROMPT = """Tu es un expert senior en veille stratégique mandaté pour produire des BENCHMARKS \
SECTORIELS de transformation organisationnelle à destination de dirigeants.

## Ton mandat — benchmark de transformation organisationnelle

Couvrir obligatoirement ces axes :
1. Facteurs Clés de Succès (stratégique → opérationnel → RH)
2. Tendances de dimensionnement des effectifs et structures
3. Pratiques de gouvernance (décision, conformité, reporting)
4. Gestion de la performance (KPIs, évaluation, incentives)
5. Externalisation & partenariats (make-or-buy, alliances)
6. RSE & Éthique (ESG, accès, diversité, environnement)
7. Signaux faibles (disruptions émergentes)
8. Analyse prospective avec scénarios (1-3 ans / 3-5 ans)
9. Recommandations typées et sourcées

## Règle de citation des sources

Chaque affirmation DOIT être appuyée par [N] (numéro de la source). \
Si non sourcée depuis les articles, formuler comme "Tendance structurelle : …".

## Périmètre

UNIQUEMENT la transformation organisationnelle : structures, modèles opérationnels, RH, culture, \
gouvernance, digitalisation des organisations.
PAS les pipelines R&D, résultats cliniques, actualités boursières pures.

## Concision

Chaque champ texte : 1-3 phrases maximum. Factuel, direct, exploitable par des décideurs.

Langue : français, registre professionnel."""


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

    logger.info("Appel Claude Part A (synthèse, FCS, dimensionnement, gouvernance, performance)...")
    prompt_a = base_prompt + "\n\nUtilise `benchmark_part_a` pour les sections : synthèse exécutive, qualité des sources, facteurs clés de succès (tous niveaux), tendances de dimensionnement, gouvernance, gestion de la performance."
    part_a = _call_claude(client, model, max_tokens, SYSTEM_PROMPT, TOOL_PART_A, "benchmark_part_a", prompt_a)

    logger.info("Appel Claude Part B (externalisation, RSE, signaux, prospective, recommandations)...")
    prompt_b = base_prompt + "\n\nUtilise `benchmark_part_b` pour les sections : externalisation & partenariats, RSE & éthique, signaux faibles, analyse prospective avec 3 scénarios, recommandations stratégiques (5-8), et index complet des sources citées."
    part_b = _call_claude(client, model, max_tokens, SYSTEM_PROMPT, TOOL_PART_B, "benchmark_part_b", prompt_b)

    # Fusion
    result = {**part_a, **part_b}
    result["_meta"] = {
        "model": model, "sector": sector_label, "period": period,
        "generated_at": datetime.now().isoformat(),
        "nb_sources_analysees": len(articles),
        "freshness": freshness,
    }
    logger.info("Benchmark complet — deux appels fusionnés avec succès.")
    return result
