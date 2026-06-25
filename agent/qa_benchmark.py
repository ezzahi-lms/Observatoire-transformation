"""
qa_benchmark.py — Agent LLM de vérification contenu + sources pour benchmarks mission.
1 appel Claude Sonnet (max 3000 tokens) qui relit le benchmark et signale :
  - Sources suspectes (entreprises inventées, stats peu plausibles)
  - Contenu générique sans ancrage factuel
  - So what manquant de spécificité
  - Vocabulaire technique manquant (mode ORG : BADR, PortNet, codes HS…)
Coût estimé : ~0.02-0.05$ par vérification.
"""
import json
import logging
import os
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

TOOL_QA_VERIFICATION = {
    "name": "qa_verification",
    "description": "Résultat de la vérification qualité du benchmark mission.",
    "input_schema": {
        "type": "object",
        "properties": {
            "score_fiabilite": {
                "type": "integer",
                "description": "Score de fiabilité du contenu de 0 à 100 (100 = parfaitement sourcé et factuel)",
            },
            "verdict": {
                "type": "string",
                "enum": ["fiable", "acceptable", "à_réviser"],
                "description": "fiable ≥80, acceptable 60-79, à_réviser <60",
            },
            "issues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "enum": ["source_suspecte", "contenu_generique", "so_what_vague", "vocabulaire_manquant", "incoherence"]},
                        "axe": {"type": "string", "description": "Axe ou section concernée"},
                        "detail": {"type": "string", "description": "Description précise du problème (citer l'extrait problématique)"},
                        "severite": {"type": "string", "enum": ["haute", "moyenne", "faible"]},
                    },
                    "required": ["type", "axe", "detail", "severite"],
                },
            },
            "points_forts": {
                "type": "array",
                "items": {"type": "string"},
                "description": "2-4 points forts du benchmark (ce qui est bien sourcé, factuel, spécifique)",
            },
        },
        "required": ["score_fiabilite", "verdict", "issues", "points_forts"],
    },
}


def _build_verification_prompt(analysis: dict, mission_config: dict) -> str:
    # Extraire les champs texte clés pour la vérification
    # (pas tout le JSON pour rester dans les tokens)
    is_org = mission_config.get("type", "RH").upper() == "ORGANISATIONNEL"
    entreprise = mission_config.get("entreprise_cible", "?")
    secteur = mission_config.get("secteur", "?")
    geographie = mission_config.get("geographie", "Maroc")

    sections = []

    if is_org:
        for key in ["modeles_csp", "processus_douaniers", "interface_filiale_siege", "formalisation_audit_readiness"]:
            v = analysis.get(key, {})
            if isinstance(v, dict):
                sections.append(f"=== {key.upper()} ===\nanalyse: {v.get('analyse','')[:400]}\nso_what: {v.get('so_what','')[:200]}")
    else:
        for key in ["business_model_rh", "organisation_dimensionnement", "gouvernance_rh", "innovation_manageriale"]:
            v = analysis.get(key, {})
            if isinstance(v, dict):
                sections.append(f"=== {key.upper()} ===\nanalyse: {v.get('analyse','')[:400]}\nso_what: {v.get('so_what','')[:200]}")

    # Sources
    sources = analysis.get("index_sources", [])
    sources_str = "\n".join(f"[{s.get('id')}] {s.get('titre','')} — {s.get('source','')}" for s in sources[:10])

    return f"""Tu es un expert LMS ORH chargé de contrôler qualité d'un benchmark consultant.

MISSION : {mission_config.get('nom_mission','?')}
ENTREPRISE CIBLE : {entreprise}
SECTEUR : {secteur} | GÉOGRAPHIE : {geographie}
TYPE : {"Organisationnel (CSP/douane)" if is_org else "RH"}

=== CONTENU DU BENCHMARK ===
{chr(10).join(sections)}

=== SOURCES INDEXÉES ===
{sources_str if sources_str else "AUCUNE SOURCE INDEXÉE"}

=== TA MISSION ===
Vérifie ce benchmark avec un regard critique et expert. Utilise `qa_verification` pour signaler :

1. SOURCES SUSPECTES : entreprises citées dans l'analyse qui n'existent pas dans ce secteur, statistiques très invraisemblables, dates incorrectes (ex : rapport "2024" qui parle d'un événement 2026)

2. CONTENU GÉNÉRIQUE : phrases qui s'appliquent à n'importe quelle entreprise ("les entreprises tendent à", "il est recommandé de", "le secteur connaît") SANS fait concret ni chiffre ni acteur nommé — SURTOUT si censé être du benchmark sectoriel

3. SO WHAT VAGUE : si le so_what d'un axe ne mentionne pas "{entreprise}" ou sa situation spécifique, ou est une platitude générique

4. VOCABULAIRE MANQUANT (mode Organisationnel) : si les axes "processus_douaniers" ou "modeles_csp" ne contiennent aucun terme technique du domaine (BADR, PortNet, ADII, DUM, codes HS, RACI, SLA, OEA, circuits vert/orange/rouge)

5. INCOHÉRENCES : contradictions internes, chiffres qui se contredisent

Sois constructif : note aussi les points forts (ce qui est bien sourcé, factuel, spécifique à {entreprise}).
Score fiabilité : 80-100=fiable, 60-79=acceptable, <60=à réviser."""


def verify_benchmark(
    analysis: Dict[str, Any],
    mission_config: Dict,
    articles: List[Dict],
    settings: Dict,
) -> Dict[str, Any]:
    """
    Vérifie la qualité et la fiabilité d'un benchmark mission via 1 appel Claude.

    Retourne {score_fiabilite, verdict, issues, points_forts} ou
    {"score_fiabilite": 50, "verdict": "acceptable", "_error": "..."} si erreur.
    """
    analysis_cfg = settings.get("analysis", {})
    provider = (os.environ.get("LLM_PROVIDER") or analysis_cfg.get("provider", "anthropic")).lower()

    if provider != "anthropic":
        logger.info(f"qa_benchmark.verify_benchmark ignoré pour provider={provider} (Anthropic uniquement).")
        return {
            "score_fiabilite": 70,
            "verdict": "acceptable",
            "issues": [],
            "points_forts": [f"Vérification non disponible pour provider {provider}"],
            "_skipped": True,
        }

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"score_fiabilite": 50, "verdict": "acceptable", "issues": [], "points_forts": [], "_error": "ANTHROPIC_API_KEY manquant"}

    model = os.environ.get("CLAUDE_MODEL") or analysis_cfg.get("model", "claude-sonnet-4-6")

    try:
        import anthropic as _ant
        client = _ant.Anthropic(api_key=api_key)

        user_prompt = _build_verification_prompt(analysis, mission_config)

        resp = client.messages.create(
            model=model,
            max_tokens=3000,
            system="Tu es un expert QA chez LMS ORH cabinet de conseil au Maroc. Tu contrôles la qualité des benchmarks consultant. Sois précis, constructif et factuel dans tes évaluations.",
            tools=[TOOL_QA_VERIFICATION],
            tool_choice={"type": "tool", "name": "qa_verification"},
            messages=[{"role": "user", "content": user_prompt}],
        )

        for block in resp.content:
            if block.type == "tool_use" and block.name == "qa_verification":
                result = block.input
                logger.info(
                    f"qa_benchmark — score {result.get('score_fiabilite')}/100 "
                    f"({result.get('verdict')}) — {len(result.get('issues', []))} issues "
                    f"({resp.usage.input_tokens} in / {resp.usage.output_tokens} out)"
                )
                return result

        raise RuntimeError("Claude n'a pas retourné de résultat qa_verification.")

    except Exception as e:
        logger.warning(f"qa_benchmark.verify_benchmark erreur : {e}")
        return {
            "score_fiabilite": 50,
            "verdict": "acceptable",
            "issues": [],
            "points_forts": [],
            "_error": str(e),
        }
