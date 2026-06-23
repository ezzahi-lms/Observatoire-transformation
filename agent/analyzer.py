"""
Benchmark de transformation organisationnelle via Claude.
Trois appels enchaînés pour contourner la limite de 8 192 tokens :
  - Appel A : synthèse + 3 lectures So What?, qualité sources, FCS, dimensionnement,
              gouvernance, performance
  - Appel B : externalisation, RSE, signaux faibles, prospective, recommandations
              (avec angle_mission conseil)
  - Appel C : dimension Afrique/MENA, questions clients, index des sources
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# Anthropic importé en lazy dans _call_anthropic() pour éviter crash si non installé
# Google Generative AI importé en lazy dans _call_gemini()


# ─────────────────────────────────────────
#  TOOL PART A
# ─────────────────────────────────────────

TOOL_PART_A = {
    "name": "benchmark_part_a",
    "description": "Stocke la 1re partie du benchmark (synthèse + 3 lectures So What?, qualité sources, FCS, dimensionnement, gouvernance, performance).",
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
                        "angle_mission": {
                            "type": "string",
                            "description": "Angle d'intervention conseil LMS ORH : quelle mission concrète ce besoin peut-il générer ? (ex. diagnostic organisationnel, étude de dimensionnement, design de gouvernance, accompagnement SI-RH...)"
                        },
                        "sources": {"type": "array", "items": {"type": "integer"}}
                    },
                    "required": ["action", "justification", "priorite", "horizon", "type", "angle_mission"]
                }
            },
        },
        "required": ["externalisation_partenariats", "rse_ethique", "signaux_faibles",
                     "prospective", "recommandations"]
    }
}

# ─────────────────────────────────────────
#  TOOL PART C
# ─────────────────────────────────────────

TOOL_PART_C = {
    "name": "benchmark_part_c",
    "description": "Stocke la 3e partie du benchmark (dimension Afrique/MENA, questions clients, index des sources).",
    "input_schema": {
        "type": "object",
        "properties": {
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
        "required": ["dimension_afrique_mena", "questions_clients", "index_sources"]
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

## Sources multilingues

Les sources peuvent être en français, anglais, italien, arabe ou espagnol. \
Analyser le contenu dans sa langue d'origine et produire TOUJOURS l'analyse en français, \
registre professionnel consultant senior."""


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


def _format_articles(articles: List[Dict], summary_len: int = 400) -> str:
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
            lines.append(f"     {a['summary'][:summary_len]}")
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
            _type = a.get("type", "")
            _pertinence = (
                "Directe"      if _type == "rss" else
                "PDF · Presse" if _type == "pdf" else
                "Contextuelle"
            )
            # Pour les PDFs, l'URL est un chemin local — ne pas l'exposer dans le rapport
            _url = a.get("url", "")
            if _type == "pdf":
                _url = ""
            index.append({
                "id": idx,
                "titre": a.get("title", "Sans titre")[:120],
                "source": a.get("source", ""),
                "url": _url,
                "date": date_val or "N/A",
                "pertinence": _pertinence,
                "type": _type,
            })
    return index


def _call_anthropic(client, model: str, max_tokens: int, system_cached: str,
                    tool: dict, tool_name: str, user_prompt: str) -> dict:
    """Appel Anthropic avec tool_use pour sortie JSON structurée."""
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
                f"{tool_name} (Anthropic) — {resp.usage.input_tokens} in / "
                f"{resp.usage.output_tokens} out "
                f"(cache: {getattr(resp.usage, 'cache_read_input_tokens', 0)})"
            )
            return block.input
    raise RuntimeError(f"Anthropic n'a pas retourné de résultat pour {tool_name}.")


def _call_gemini(model_name: str, max_tokens: int, system_text: str,
                 tool: dict, tool_name: str, user_prompt: str) -> dict:
    """Appel Google Gemini avec JSON mode (google-genai SDK v2+)."""
    try:
        from google import genai
        from google.genai import types as genai_types
    except ImportError:
        raise ImportError(
            "google-genai non installé. "
            "Exécuter : pip install google-genai>=1.0.0"
        )

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY manquant. Ajoutez GEMINI_API_KEY dans le fichier .env "
            "(obtenir sur https://aistudio.google.com/app/apikey)."
        )

    client = genai.Client(
        api_key=api_key,
        http_options={"api_version": "v1beta"},
    )

    # Schéma passé nativement à l'API Gemini (pas dans le prompt) — économise les tokens d'entrée
    schema = tool.get("input_schema", {})

    combined_prompt = (
        f"{system_text}\n\n"
        f"⚠️ CONCISION : chaque champ texte = 1-2 phrases max. Listes : 3-5 items max.\n\n"
        f"{user_prompt}"
    )

    response = client.models.generate_content(
        model=model_name,
        contents=combined_prompt,
        config=genai_types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            max_output_tokens=max_tokens,
            temperature=0.3,
        ),
    )

    raw = response.text.strip()

    # Nettoyer les éventuels blocs markdown ```json ... ```
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0].strip()

    result = json.loads(raw)
    logger.info(f"{tool_name} (Gemini/{model_name}) — réponse JSON reçue")
    return result


def _call_groq(model_name: str, max_tokens: int, system_text: str,
               tool: dict, tool_name: str, user_prompt: str) -> dict:
    """Appel Groq (llama-3.3-70b etc.) avec JSON mode via OpenAI-compatible API."""
    try:
        from groq import Groq
    except ImportError:
        raise ImportError("groq non installé. Exécuter : pip install groq>=0.9.0")

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY manquant. Ajoutez GROQ_API_KEY dans le fichier .env "
            "(obtenir sur https://console.groq.com)."
        )

    client = Groq(api_key=api_key)

    schema = tool.get("input_schema", {})
    schema_json = json.dumps(schema, ensure_ascii=False, indent=2)

    system_with_schema = (
        f"{system_text}\n\n"
        f"SCHÉMA JSON DE SORTIE ATTENDU (respecter EXACTEMENT, "
        f"tous les champs `required` sont obligatoires) :\n"
        f"```json\n{schema_json}\n```\n"
        f"RÈGLES IMPÉRATIVES POUR LA RÉPONSE :\n"
        f"1. Réponds UNIQUEMENT avec le JSON valide, sans texte autour.\n"
        f"2. INTERDIT de laisser un champ de texte vide (chaîne vide \"\"). "
        f"Chaque champ de type string doit contenir au minimum 2-3 phrases substantielles.\n"
        f"3. Utilise ta connaissance du secteur ET les sources fournies. "
        f"Si une source ne couvre pas exactement le sujet, complète avec tes connaissances "
        f"du secteur en citant des faits vérifiables.\n"
        f"4. Les listes doivent contenir au minimum 3 éléments concrets et nommés."
    )

    last_error = None
    for attempt in range(2):
        try:
            temperature = 0.3 if attempt == 0 else 0.5
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_with_schema},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                max_tokens=max_tokens,
                temperature=temperature,
            )
            raw = response.choices[0].message.content.strip()
            result = json.loads(raw)
            logger.info(
                f"{tool_name} (Groq/{model_name}) tentative {attempt+1} — "
                f"{response.usage.prompt_tokens} in / {response.usage.completion_tokens} out"
            )
            # Détection réponse vide : si la plupart des champs string sont courts
            str_vals = [v for v in result.values() if isinstance(v, str)]
            if str_vals and sum(1 for v in str_vals if len(v.strip()) < 20) / len(str_vals) > 0.5:
                logger.warning(f"Réponse Groq principalement vide (tentative {attempt+1})")
                if attempt == 0:
                    continue
            return result
        except Exception as e:
            last_error = e
            logger.warning(f"Groq tentative {attempt+1} échouée : {e}")
            if attempt == 0:
                continue

    raise RuntimeError(
        f"Groq n'a pas produit de résultat utilisable après 2 tentatives. "
        f"Dernière erreur : {last_error}"
    )


def _call_llm(provider: str, model: str, max_tokens: int, system_text: str,
              tool: dict, tool_name: str, user_prompt: str,
              client=None) -> dict:
    """Dispatcher : appelle Anthropic, Gemini ou Groq selon le provider."""
    if provider == "gemini":
        return _call_gemini(model, max_tokens, system_text, tool, tool_name, user_prompt)
    elif provider == "groq":
        return _call_groq(model, max_tokens, system_text, tool, tool_name, user_prompt)
    else:
        if client is None:
            raise ValueError("client Anthropic requis pour provider='anthropic'.")
        return _call_anthropic(client, model, max_tokens, system_text, tool, tool_name, user_prompt)


def _tmp_path(reports_dir: Path, sector_key: str, part: str) -> Path:
    """Chemin du fichier temporaire pour une partie de l'analyse."""
    safe = "".join(c if c.isalnum() else "_" for c in sector_key)
    return reports_dir / f".tmp_{safe}_{part}.json"


def _save_tmp(path: Path, data: dict) -> None:
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"Sauvegarde tmp → {path.name}")
    except Exception as e:
        logger.warning(f"Impossible de sauvegarder tmp {path.name} : {e}")


def _load_tmp(path: Path) -> dict | None:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            logger.info(f"Reprise depuis tmp existant → {path.name}")
            return data
    except Exception as e:
        logger.warning(f"tmp {path.name} illisible, on recalcule : {e}")
    return None


def _clear_tmp(paths: list) -> None:
    for p in paths:
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass


def analyze(sector_config: Dict, articles: List[Dict], settings: Dict,
            progress_callback=None) -> Dict[str, Any]:
    """
    Lance l'analyse en 3 appels Claude.
    progress_callback(step: int, total: int, msg: str) — appelé après chaque appel Claude.
    Chaque partie est sauvegardée dans un fichier .tmp_<sector>_part_X.json après son
    calcul réussi. Si un tmp existe déjà (reprise après interruption réseau), il est
    rechargé sans rappeler Claude. Les tmp sont supprimés à la fin.
    """
    analysis_cfg = settings.get("analysis", {})
    provider = (
        os.environ.get("LLM_PROVIDER")
        or analysis_cfg.get("provider", "anthropic")
    ).lower()

    if provider == "gemini":
        max_tokens = analysis_cfg.get("gemini_max_tokens", 4096)
    elif provider == "groq":
        max_tokens = analysis_cfg.get("groq_max_tokens", 8192)
    else:
        max_tokens = analysis_cfg.get("max_tokens", 8192)
    client = None

    if provider == "gemini":
        model = (
            os.environ.get("GEMINI_MODEL")
            or analysis_cfg.get("gemini_model", "gemini-2.5-flash")
        )
        logger.info(f"Provider : Gemini — modèle : {model}")
    elif provider == "groq":
        model = (
            os.environ.get("GROQ_MODEL")
            or analysis_cfg.get("groq_model", "llama-3.3-70b-versatile")
        )
        logger.info(f"Provider : Groq — modèle : {model}")
    else:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY manquant. Ajoutez votre clé dans le fichier .env.")
        model = (
            os.environ.get("CLAUDE_MODEL")
            or analysis_cfg.get("model", "claude-sonnet-4-6")
        )
        try:
            import anthropic as _ant
        except ImportError:
            raise ImportError("anthropic non installé. Exécuter : pip install anthropic>=0.40.0")
        client = _ant.Anthropic(api_key=api_key)
        logger.info(f"Provider : Anthropic — modèle : {model}")

    sector_label = sector_config.get("label", "secteur")
    sector_key   = sector_config.get("key", sector_label)
    period = datetime.now().strftime("%B %Y")
    context_note = sector_config.get("context_note", "")
    benchmark_axes = sector_config.get("benchmark_axes", sector_config.get("focus_areas", []))
    freshness = _compute_freshness(articles)

    # Pour Gemini / Groq free tier : limiter le nombre d'articles et la longueur des résumés
    articles_for_llm = articles
    summary_len = 400
    if provider == "gemini":
        max_art = analysis_cfg.get("gemini_max_articles", 12)
        summary_len = analysis_cfg.get("gemini_summary_len", 150)
        articles_for_llm = articles[:max_art]
        logger.info(f"Gemini : {len(articles_for_llm)}/{len(articles)} articles, résumés ≤{summary_len} chars")
    elif provider == "groq":
        max_art = analysis_cfg.get("groq_max_articles", 10)
        summary_len = analysis_cfg.get("groq_summary_len", 200)
        articles_for_llm = articles[:max_art]
        logger.info(f"Groq : {len(articles_for_llm)}/{len(articles)} articles, résumés ≤{summary_len} chars")

    articles_text = _format_articles(articles_for_llm, summary_len=summary_len)

    # Dossier tmp = dossier reports (créé si absent)
    reports_dir = Path(settings.get("reporting", {}).get("output_dir", "reports"))
    reports_dir.mkdir(exist_ok=True)
    tmp_a = _tmp_path(reports_dir, sector_key, "part_a")
    tmp_b = _tmp_path(reports_dir, sector_key, "part_b")
    tmp_c = _tmp_path(reports_dir, sector_key, "part_c")

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

    # ── Part A ────────────────────────────────────────────────────────────────
    part_a = _load_tmp(tmp_a)
    if part_a is None:
        if progress_callback:
            progress_callback(0, 3, "Appel 1/3 en cours — Synthèse, FCS, Dimensionnement, Gouvernance, Performance…")
        logger.info("Appel Claude Part A...")
        prompt_a = (
            base_prompt
            + "\n\nUtilise `benchmark_part_a` pour les sections :\n"
            "1. synthèse exécutive (avec les 3 lectures So What? : secteur / clients LMS / cabinet LMS ORH)\n"
            "2. qualité des sources\n"
            "3. facteurs clés de succès (tous niveaux)\n"
            "4. tendances de dimensionnement\n"
            "5. pratiques de gouvernance\n"
            "6. gestion de la performance\n\n"
            "⚠️ Les lectures_so_what dans synthese_executive sont OBLIGATOIRES — 3 angles distincts : "
            "secteur, clients de LMS, cabinet LMS ORH."
        )
        part_a = _call_llm(provider, model, max_tokens, SYSTEM_PROMPT,
                           TOOL_PART_A, "benchmark_part_a", prompt_a, client)
        _save_tmp(tmp_a, part_a)
    else:
        if progress_callback:
            progress_callback(1, 3, "♻️ Part A rechargée depuis cache — Appel 2/3 en cours…")

    # ── Part B ────────────────────────────────────────────────────────────────
    part_b = _load_tmp(tmp_b)
    if part_b is None:
        if progress_callback:
            progress_callback(1, 3, "✅ Appel 1/3 terminé — Appel 2/3 en cours — Externalisation, RSE, Signaux, Recommandations…")
        logger.info("Appel Claude Part B...")
        prompt_b = (
            base_prompt
            + "\n\nUtilise `benchmark_part_b` pour les sections :\n"
            "1. externalisation & partenariats\n"
            "2. RSE & éthique\n"
            "3. signaux faibles\n"
            "4. analyse prospective avec 3 scénarios (Optimiste / Central / Pessimiste)\n"
            "5. recommandations stratégiques (5-8) — chacune DOIT avoir un `angle_mission` : "
            "quelle mission concrète LMS ORH peut-il proposer en réponse à ce besoin ?"
        )
        part_b = _call_llm(provider, model, max_tokens, SYSTEM_PROMPT,
                           TOOL_PART_B, "benchmark_part_b", prompt_b, client)
        _save_tmp(tmp_b, part_b)
    else:
        if progress_callback:
            progress_callback(2, 3, "♻️ Part B rechargée depuis cache — Appel 3/3 en cours…")

    # ── Part C ────────────────────────────────────────────────────────────────
    part_c = _load_tmp(tmp_c)
    if part_c is None:
        if progress_callback:
            progress_callback(2, 3, "✅ Appel 2/3 terminé — Appel 3/3 en cours — Afrique/MENA, Questions clients, Index sources…")
        logger.info("Appel Claude Part C...")
        prompt_c = (
            base_prompt
            + "\n\nUtilise `benchmark_part_c` pour les sections :\n"
            "1. dimension Afrique/MENA : contexte régional, écarts vs pratiques internationales "
            "(tableau axe / situation internationale / situation Afrique-MENA / gap à combler), "
            "opportunités spécifiques pour les entreprises marocaines du secteur\n"
            "2. questions clients — les 4 types de questions récurrentes que les clients posent à LMS ORH :\n"
            "   • dimensionnement (taille équipes, ratios, structures)\n"
            "   • gouvernance (décision, reporting, conformité)\n"
            "   • externalisation (make-or-buy, hybrides)\n"
            "   • systèmes d'information (SIRH, ERP, IA orga)\n"
            "3. index_sources : liste TOUTES les sources citées via [N] dans l'ENSEMBLE du benchmark. "
            "Pour chaque source citée, inclure id=N, titre, source, url, date, pertinence. "
            "Un index vide ou incomplet rend le rapport inexploitable pour les décideurs.\n\n"
            "⚠️ Dimension Afrique/MENA et questions_clients sont OBLIGATOIRES. "
            "index_sources doit couvrir toutes les sources de ce benchmark."
        )
        part_c = _call_llm(provider, model, max_tokens, SYSTEM_PROMPT,
                           TOOL_PART_C, "benchmark_part_c", prompt_c, client)
        _save_tmp(tmp_c, part_c)

    if progress_callback:
        progress_callback(3, 3, "✅ Appel 3/3 terminé — Fusion et génération du rapport…")

    # ── Fusion ────────────────────────────────────────────────────────────────
    result = {**part_a, **part_b, **part_c}

    # ── Reconstruction de l'index si Claude ne l'a pas rempli ─────────────────
    if not result.get("index_sources"):
        logger.warning("index_sources vide — reconstruction automatique depuis les articles collectés.")
        result["index_sources"] = _build_fallback_index(articles, result)
        logger.info(f"Index reconstruit : {len(result['index_sources'])} sources.")

    result["_meta"] = {
        "provider": provider, "model": model,
        "sector": sector_label, "period": period,
        "generated_at": datetime.now().isoformat(),
        "nb_sources_analysees": len(articles),
        "freshness": freshness,
    }

    # ── Contrôle qualité (QA gate) — 100 % code, aucun coût token ──────────────
    try:
        from agent.qa_gate import run_qa, save_quarantine
        result["_qa"] = run_qa(result, articles, settings)
        if result["_qa"]["status"] == "quarantaine":
            save_quarantine(result, sector_label, reports_dir)
            logger.warning(
                f"⚠️ Benchmark {sector_label} en quarantaine (score {result['_qa']['score']}/100) — "
                "relecture recommandée avant diffusion."
            )
    except Exception as e:
        logger.warning(f"QA gate non exécuté : {e}")

    # ── Nettoyage des tmp ─────────────────────────────────────────────────────
    _clear_tmp([tmp_a, tmp_b, tmp_c])

    logger.info("Benchmark complet — trois appels fusionnés avec succès.")
    return result
