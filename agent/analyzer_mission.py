"""
Benchmark stratégique personnalisé pour une mission consultant RH.
Deux modes :
  - Rapide  : 1 appel Claude (max_tokens=4096) — outil mission_benchmark
  - Approfondi : 3 appels Claude (max_tokens=8192) — outils mission_part_a/b/c
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

logger = logging.getLogger(__name__)

# Anthropic et Google Generative AI sont importés en lazy dans leurs fonctions d'appel

# ─────────────────────────────────────────────────────────────────────────────
#  SYSTEM PROMPT (dynamique — formaté à l'appel)
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT_MISSION = """Tu es un expert senior en transformation RH et organisationnelle, associé chez LMS ORH — cabinet de conseil au Maroc & Afrique.

Ta mission : produire un benchmark stratégique personnalisé pour la mission : {nom_mission}
Entreprise cible : {entreprise_cible} — Secteur : {secteur}
Question centrale : {angle_strategique_rh}

Pour chaque axe analysé, applique systématiquement le filtre de lecture RH :
1. BUSINESS MODEL → compétences émergentes/obsolètes, nouveaux profils, impacts pyramide des âges
2. ORGANISATION → évolution effectifs, nouveaux modèles org (agile, matriciel, plateforme), rôles créés/supprimés/transformés
3. GOUVERNANCE → instances RH (CODIR, comités sociaux), politiques sociales, conformité droit du travail
4. INNOVATION MANAGÉRIALE → pratiques différenciantes, outils RH innovants (IA RH, SIRH, analytics), expérience employé

Règles de format :
- Commence chaque section par un chiffre ou un fait vérifiable
- Nomme au moins 1 entreprise ou initiative réelle par axe
- Termine chaque axe par : "Ce que cela signifie pour {entreprise_cible} : [2-3 lignes]"
- Niveau de certitude : confirmé / probable / à vérifier
- Langue : français, registre consultant senior"""


# ─────────────────────────────────────────────────────────────────────────────
#  OUTIL MODE RAPIDE
# ─────────────────────────────────────────────────────────────────────────────

TOOL_MISSION_RAPIDE = {
    "name": "mission_benchmark",
    "description": "Stocke le benchmark RH stratégique complet pour la mission.",
    "input_schema": {
        "type": "object",
        "properties": {
            "contexte_mission": {
                "type": "object",
                "properties": {
                    "texte": {"type": "string"},
                    "angle_rh": {"type": "string"},
                },
                "required": ["texte", "angle_rh"],
            },
            "business_model_rh": {
                "type": "object",
                "properties": {
                    "analyse": {"type": "string"},
                    "competences_emergentes": {"type": "array", "items": {"type": "string"}},
                    "competences_obsoletes": {"type": "array", "items": {"type": "string"}},
                    "so_what": {"type": "string"},
                },
                "required": ["analyse", "competences_emergentes", "competences_obsoletes", "so_what"],
            },
            "organisation_dimensionnement": {
                "type": "object",
                "properties": {
                    "analyse": {"type": "string"},
                    "tendances_effectifs": {"type": "string"},
                    "nouveaux_roles": {"type": "array", "items": {"type": "string"}},
                    "externalisation": {"type": "string"},
                    "so_what": {"type": "string"},
                },
                "required": ["analyse", "tendances_effectifs", "nouveaux_roles", "externalisation", "so_what"],
            },
            "gouvernance_rh": {
                "type": "object",
                "properties": {
                    "analyse": {"type": "string"},
                    "instances_rh": {"type": "string"},
                    "politiques_sociales": {"type": "string"},
                    "conformite": {"type": "string"},
                    "so_what": {"type": "string"},
                },
                "required": ["analyse", "instances_rh", "politiques_sociales", "conformite", "so_what"],
            },
            "innovation_manageriale": {
                "type": "object",
                "properties": {
                    "analyse": {"type": "string"},
                    "pratiques_differenciantes": {"type": "array", "items": {"type": "string"}},
                    "outils_rh": {"type": "array", "items": {"type": "string"}},
                    "experience_employe": {"type": "string"},
                    "so_what": {"type": "string"},
                },
                "required": ["analyse", "pratiques_differenciantes", "outils_rh", "experience_employe", "so_what"],
            },
            "signaux_faibles": {
                "type": "array",
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "properties": {
                        "signal": {"type": "string"},
                        "implication_rh": {"type": "string"},
                        "horizon": {"type": "string"},
                        "pertinence_mission": {"type": "string"},
                    },
                    "required": ["signal", "implication_rh", "horizon", "pertinence_mission"],
                },
            },
            "recommandations_mission": {
                "type": "array",
                "minItems": 3,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string"},
                        "justification": {"type": "string"},
                        "priorite": {"type": "string", "enum": ["Haute", "Moyenne", "Faible"]},
                        "kpi": {"type": "string"},
                        "horizon": {"type": "string"},
                    },
                    "required": ["action", "justification", "priorite", "kpi", "horizon"],
                },
            },
        },
        "required": [
            "contexte_mission",
            "business_model_rh",
            "organisation_dimensionnement",
            "gouvernance_rh",
            "innovation_manageriale",
            "signaux_faibles",
            "recommandations_mission",
        ],
    },
}


# ─────────────────────────────────────────────────────────────────────────────
#  OUTILS MODE APPROFONDI
# ─────────────────────────────────────────────────────────────────────────────

TOOL_MISSION_PART_A = {
    "name": "mission_part_a",
    "description": "Partie A : contexte_mission, business_model_rh, organisation_dimensionnement.",
    "input_schema": {
        "type": "object",
        "properties": {
            "contexte_mission": {
                "type": "object",
                "properties": {
                    "texte": {"type": "string"},
                    "angle_rh": {"type": "string"},
                },
                "required": ["texte", "angle_rh"],
            },
            "business_model_rh": {
                "type": "object",
                "properties": {
                    "analyse": {"type": "string"},
                    "competences_emergentes": {"type": "array", "items": {"type": "string"}},
                    "competences_obsoletes": {"type": "array", "items": {"type": "string"}},
                    "so_what": {"type": "string"},
                },
                "required": ["analyse", "competences_emergentes", "competences_obsoletes", "so_what"],
            },
            "organisation_dimensionnement": {
                "type": "object",
                "properties": {
                    "analyse": {"type": "string"},
                    "tendances_effectifs": {"type": "string"},
                    "nouveaux_roles": {"type": "array", "items": {"type": "string"}},
                    "externalisation": {"type": "string"},
                    "so_what": {"type": "string"},
                },
                "required": ["analyse", "tendances_effectifs", "nouveaux_roles", "externalisation", "so_what"],
            },
        },
        "required": ["contexte_mission", "business_model_rh", "organisation_dimensionnement"],
    },
}

TOOL_MISSION_PART_B = {
    "name": "mission_part_b",
    "description": "Partie B : gouvernance_rh, innovation_manageriale, signaux_faibles.",
    "input_schema": {
        "type": "object",
        "properties": {
            "gouvernance_rh": {
                "type": "object",
                "properties": {
                    "analyse": {"type": "string"},
                    "instances_rh": {"type": "string"},
                    "politiques_sociales": {"type": "string"},
                    "conformite": {"type": "string"},
                    "so_what": {"type": "string"},
                },
                "required": ["analyse", "instances_rh", "politiques_sociales", "conformite", "so_what"],
            },
            "innovation_manageriale": {
                "type": "object",
                "properties": {
                    "analyse": {"type": "string"},
                    "pratiques_differenciantes": {"type": "array", "items": {"type": "string"}},
                    "outils_rh": {"type": "array", "items": {"type": "string"}},
                    "experience_employe": {"type": "string"},
                    "so_what": {"type": "string"},
                },
                "required": ["analyse", "pratiques_differenciantes", "outils_rh", "experience_employe", "so_what"],
            },
            "signaux_faibles": {
                "type": "array",
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "properties": {
                        "signal": {"type": "string"},
                        "implication_rh": {"type": "string"},
                        "horizon": {"type": "string"},
                        "pertinence_mission": {"type": "string"},
                    },
                    "required": ["signal", "implication_rh", "horizon", "pertinence_mission"],
                },
            },
        },
        "required": ["gouvernance_rh", "innovation_manageriale", "signaux_faibles"],
    },
}


def _build_tool_part_c(slides_optionnelles: List[str]) -> Dict:
    """Construit l'outil mission_part_c dynamiquement selon les slides cochées."""
    slides_schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "cle": {"type": "string", "description": "Identifiant de la slide optionnelle"},
                "titre": {"type": "string"},
                "observation": {"type": "string"},
                "benchmark_sectoriel": {"type": "string"},
                "implication_rh": {"type": "string"},
                "so_what": {"type": "string"},
            },
            "required": ["cle", "titre", "observation", "benchmark_sectoriel", "implication_rh", "so_what"],
        },
    }

    return {
        "name": "mission_part_c",
        "description": "Partie C : recommandations_mission, slides_optionnelles, index_sources.",
        "input_schema": {
            "type": "object",
            "properties": {
                "recommandations_mission": {
                    "type": "array",
                    "minItems": 3,
                    "maxItems": 3,
                    "items": {
                        "type": "object",
                        "properties": {
                            "action": {"type": "string"},
                            "justification": {"type": "string"},
                            "priorite": {"type": "string", "enum": ["Haute", "Moyenne", "Faible"]},
                            "kpi": {"type": "string"},
                            "horizon": {"type": "string"},
                        },
                        "required": ["action", "justification", "priorite", "kpi", "horizon"],
                    },
                },
                "slides_optionnelles": slides_schema,
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
                            "pertinence": {"type": "string", "enum": ["Directe", "Contextuelle"]},
                        },
                        "required": ["id", "titre", "source", "pertinence"],
                    },
                },
            },
            "required": ["recommandations_mission", "slides_optionnelles", "index_sources"],
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS (calqués sur analyzer.py)
# ─────────────────────────────────────────────────────────────────────────────

def _format_articles(articles: List[Dict]) -> str:
    lines = [f"## {len(articles)} sources numérotées — citer via [N]\n"]
    for i, a in enumerate(articles, 1):
        date = a.get("date", "N/A")
        age = ""
        if date != "N/A":
            try:
                months = (datetime.now() - datetime.fromisoformat(date)).days // 30
                age = f" ({months}m)"
            except Exception:
                pass
        lines.append(f"[{i}] {a['source']} {date}{age} | {a['title']}")
        if a.get("summary"):
            lines.append(f"     {a['summary'][:400]}")
        lines.append("")
    return "\n".join(lines)


def _call_anthropic(client, model: str, max_tokens: int, system_text: str,
                    tool: dict, tool_name: str, user_prompt: str) -> dict:
    """Appel Anthropic avec tool_use pour sortie JSON structurée."""
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=[{"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}}],
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

    schema = tool.get("input_schema", {})
    schema_json = json.dumps(schema, ensure_ascii=False, indent=2)

    combined_prompt = (
        f"{system_text}\n\n"
        f"═══ SCHÉMA JSON DE SORTIE ATTENDU ═══\n"
        f"Réponds UNIQUEMENT avec un objet JSON valide respectant EXACTEMENT "
        f"cette structure (tous les champs `required` sont obligatoires) :\n"
        f"{schema_json}\n"
        f"═══════════════════════════════════════\n\n"
        f"{user_prompt}"
    )

    response = client.models.generate_content(
        model=model_name,
        contents=combined_prompt,
        config=genai_types.GenerateContentConfig(
            response_mime_type="application/json",
            max_output_tokens=max_tokens,
            temperature=0.3,
        ),
    )

    raw = response.text.strip()

    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0].strip()

    result = json.loads(raw)
    logger.info(f"{tool_name} (Gemini/{model_name}) — réponse JSON reçue")
    return result


def _call_llm(provider: str, model: str, max_tokens: int, system_text: str,
              tool: dict, tool_name: str, user_prompt: str,
              client=None) -> dict:
    """Dispatcher : appelle Anthropic ou Gemini selon le provider."""
    if provider == "gemini":
        return _call_gemini(model, max_tokens, system_text, tool, tool_name, user_prompt)
    else:
        if client is None:
            raise ValueError("client Anthropic requis pour provider='anthropic'.")
        return _call_anthropic(client, model, max_tokens, system_text, tool, tool_name, user_prompt)


def _tmp_path(reports_dir: Path, entreprise: str, part: str) -> Path:
    safe = "".join(c if c.isalnum() else "_" for c in entreprise)
    return reports_dir / f".tmp_mission_{safe}_{part}.json"


def _save_tmp(path: Path, data: dict) -> None:
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"Sauvegarde tmp → {path.name}")
    except Exception as e:
        logger.warning(f"Impossible de sauvegarder tmp {path.name} : {e}")


def _load_tmp(path: Path) -> Optional[dict]:
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


# ─────────────────────────────────────────────────────────────────────────────
#  FONCTION PRINCIPALE
# ─────────────────────────────────────────────────────────────────────────────

def analyze_mission(
    mission_config: Dict,
    articles: List[Dict],
    settings: Dict,
    progress_callback: Optional[Callable] = None,
) -> Dict[str, Any]:
    """
    Génère un benchmark stratégique RH personnalisé pour une mission consultant.

    mission_config keys:
      nom_mission, entreprise_cible, secteur, angle_strategique_rh,
      periode, mode ("Rapide" | "Approfondi"), sources, slides_optionnelles

    progress_callback(step, total, msg) — appelé après chaque étape Claude.
    """
    analysis_cfg = settings.get("analysis", {})
    provider = (
        os.environ.get("LLM_PROVIDER")
        or analysis_cfg.get("provider", "anthropic")
    ).lower()

    client = None
    if provider == "gemini":
        model = (
            os.environ.get("GEMINI_MODEL")
            or analysis_cfg.get("gemini_model", "gemini-1.5-flash")
        )
        logger.info(f"Provider : Gemini — modèle : {model}")
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

    nom_mission = mission_config.get("nom_mission", "Mission RH")
    entreprise_cible = mission_config.get("entreprise_cible", "Entreprise")
    secteur = mission_config.get("secteur", "")
    angle = mission_config.get("angle_strategique_rh", "")
    periode = mission_config.get("periode", "6 derniers mois")
    mode = mission_config.get("mode", "Rapide")
    slides_optionnelles = mission_config.get("slides_optionnelles", [])

    system_text = SYSTEM_PROMPT_MISSION.format(
        nom_mission=nom_mission,
        entreprise_cible=entreprise_cible,
        secteur=secteur,
        angle_strategique_rh=angle,
    )

    articles_text = _format_articles(articles)
    reports_dir = Path(settings.get("reporting", {}).get("output_dir", "reports"))
    reports_dir.mkdir(exist_ok=True)

    base_prompt = f"""Benchmark RH Mission — **{nom_mission}**
Entreprise cible : **{entreprise_cible}** — Secteur : **{secteur}**
Angle stratégique : {angle}
Période couverte : {periode}

**Sources collectées (citer via [N]) :**
{articles_text}"""

    # ─────────────────────────────────────────────────────────────────────────
    #  MODE RAPIDE : 1 appel
    # ─────────────────────────────────────────────────────────────────────────
    if mode == "Rapide":
        max_tokens = 4096
        tmp = _tmp_path(reports_dir, entreprise_cible, "rapide")
        result = _load_tmp(tmp)
        if result is None:
            if progress_callback:
                progress_callback(0, 1, f"Appel {provider.title()} unique — Mode Rapide…")
            prompt = (
                base_prompt
                + "\n\nUtilise `mission_benchmark` pour produire le benchmark complet en un seul appel : "
                "contexte_mission, business_model_rh, organisation_dimensionnement, gouvernance_rh, "
                "innovation_manageriale, signaux_faibles (max 3), recommandations_mission (exactement 3)."
            )
            result = _call_llm(
                provider, model, max_tokens, system_text,
                TOOL_MISSION_RAPIDE, "mission_benchmark", prompt, client,
            )
            _save_tmp(tmp, result)

        if progress_callback:
            progress_callback(1, 1, "Benchmark Rapide généré.")

        result["_meta"] = {
            "provider": provider, "model": model,
            "mode": "Rapide",
            "mission": nom_mission,
            "entreprise": entreprise_cible,
            "generated_at": datetime.now().isoformat(),
            "nb_sources_analysees": len(articles),
        }
        _clear_tmp([tmp])
        return result

    # ─────────────────────────────────────────────────────────────────────────
    #  MODE APPROFONDI : 3 appels
    # ─────────────────────────────────────────────────────────────────────────
    max_tokens = 8192
    tmp_a = _tmp_path(reports_dir, entreprise_cible, "part_a")
    tmp_b = _tmp_path(reports_dir, entreprise_cible, "part_b")
    tmp_c = _tmp_path(reports_dir, entreprise_cible, "part_c")

    # -- Part A --
    part_a = _load_tmp(tmp_a)
    if part_a is None:
        if progress_callback:
            progress_callback(0, 3, "Appel 1/3 — Contexte, Business Model RH, Organisation…")
        prompt_a = (
            base_prompt
            + "\n\nUtilise `mission_part_a` pour les sections :\n"
            "1. contexte_mission (résumé de la mission et de l'angle RH)\n"
            "2. business_model_rh (analyse, compétences émergentes/obsolètes, so_what pour "
            + entreprise_cible + ")\n"
            "3. organisation_dimensionnement (analyse, tendances effectifs, nouveaux rôles, "
            "externalisation, so_what pour " + entreprise_cible + ")"
        )
        part_a = _call_llm(
            provider, model, max_tokens, system_text,
            TOOL_MISSION_PART_A, "mission_part_a", prompt_a, client,
        )
        _save_tmp(tmp_a, part_a)
    else:
        if progress_callback:
            progress_callback(1, 3, "Part A rechargée depuis cache — Appel 2/3 en cours…")

    # -- Part B --
    part_b = _load_tmp(tmp_b)
    if part_b is None:
        if progress_callback:
            progress_callback(1, 3, "Appel 2/3 — Gouvernance RH, Innovation managériale, Signaux faibles…")
        prompt_b = (
            base_prompt
            + "\n\nUtilise `mission_part_b` pour les sections :\n"
            "1. gouvernance_rh (analyse, instances RH, politiques sociales, conformité, so_what pour "
            + entreprise_cible + ")\n"
            "2. innovation_manageriale (analyse, pratiques différenciantes, outils RH, expérience employé, "
            "so_what pour " + entreprise_cible + ")\n"
            "3. signaux_faibles (max 3 : signal, implication_rh, horizon, pertinence_mission)"
        )
        part_b = _call_llm(
            provider, model, max_tokens, system_text,
            TOOL_MISSION_PART_B, "mission_part_b", prompt_b, client,
        )
        _save_tmp(tmp_b, part_b)
    else:
        if progress_callback:
            progress_callback(2, 3, "Part B rechargée depuis cache — Appel 3/3 en cours…")

    # -- Part C --
    tool_part_c = _build_tool_part_c(slides_optionnelles)
    part_c = _load_tmp(tmp_c)
    if part_c is None:
        if progress_callback:
            progress_callback(2, 3, "Appel 3/3 — Recommandations, Slides optionnelles, Index sources…")

        slides_instruction = ""
        if slides_optionnelles:
            slides_labels = ", ".join(slides_optionnelles)
            slides_instruction = (
                f"\nPour les slides_optionnelles, produis une entrée par thème demandé "
                f"({slides_labels}) avec les champs : cle (identifiant), titre, observation, "
                f"benchmark_sectoriel, implication_rh, so_what."
            )

        prompt_c = (
            base_prompt
            + "\n\nUtilise `mission_part_c` pour les sections :\n"
            "1. recommandations_mission (exactement 3 : action, justification, priorite, kpi, horizon)\n"
            + slides_instruction
            + "\n2. index_sources : toutes les sources citées [N] dans ce benchmark "
            "(id, titre, source, url, date, pertinence : Directe/Contextuelle)"
        )
        part_c = _call_llm(
            provider, model, max_tokens, system_text,
            tool_part_c, "mission_part_c", prompt_c, client,
        )
        _save_tmp(tmp_c, part_c)

    if progress_callback:
        progress_callback(3, 3, "Fusion et finalisation du benchmark…")

    # -- Fusion --
    result = {**part_a, **part_b, **part_c}
    result["_meta"] = {
        "provider": provider, "model": model,
        "mode": "Approfondi",
        "mission": nom_mission,
        "entreprise": entreprise_cible,
        "generated_at": datetime.now().isoformat(),
        "nb_sources_analysees": len(articles),
    }

    _clear_tmp([tmp_a, tmp_b, tmp_c])
    logger.info("Benchmark mission complet — trois appels fusionnés.")
    return result
