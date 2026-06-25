"""
Cadrage intelligent de la mission benchmark.

Deux fonctions :
  generate_cadrage_questions() → 5 questions ciblées pour cadrer la mission
  identify_comparables()       → 6-8 entreprises de référence + dimensions communes

Critères de sélection des comparables :
  - Taille similaire (CA, effectifs) — PAS uniquement même secteur
  - Positionnement stratégique comparable
  - Best practices fonctionnelles transférables
  - Mix : concurrent direct + best-in-class sectoriel + best practice fonctionnel
"""
import json
import os
import re
from typing import Dict, List, Any, Optional


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS LLM
# ─────────────────────────────────────────────────────────────────────────────

def _call_claude_simple(system_prompt: str, user_prompt: str, settings: dict,
                        max_tokens: int = 2000) -> str:
    """Appel Claude simple (messages, sans tool_use) pour le cadrage."""
    import anthropic
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY manquante")
    model = settings.get("analysis", {}).get("model", "claude-sonnet-4-6")
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return resp.content[0].text


def _extract_json(raw: str, fallback=None):
    """Extrait le premier JSON valide (array ou object) depuis une réponse LLM."""
    # Bloc code markdown
    m = re.search(r'```(?:json)?\s*([\[{].*?[}\]])\s*```', raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # JSON brut
    for pattern in (r'\[.*\]', r'\{.*\}'):
        m = re.search(pattern, raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                continue
    return fallback


# ─────────────────────────────────────────────────────────────────────────────
#  QUESTIONS DE CADRAGE
# ─────────────────────────────────────────────────────────────────────────────

def generate_cadrage_questions(mission_config: dict, settings: dict) -> List[dict]:
    """
    Génère 5 questions de cadrage ciblées pour affiner la mission benchmark.

    Args:
        mission_config : dict avec au minimum entreprise_cible, secteur, geographie,
                         type (RH/Organisationnel), angle_strategique_rh
        settings       : settings.yaml chargé

    Returns:
        Liste de 5 dicts {id, question, aide, placeholder, obligatoire}
    """
    entreprise = mission_config.get("entreprise_cible", "")
    secteur    = mission_config.get("secteur", "")
    geographie = mission_config.get("geographie", "")
    type_m     = mission_config.get("type", "RH")
    brief      = mission_config.get("angle_strategique_rh", "")

    system = (
        "Tu es un consultant senior LMS ORH expert en benchmark stratégique. "
        "Génère EXACTEMENT 5 questions de cadrage pour affiner une mission benchmark. "
        "Les questions doivent être SPÉCIFIQUES au contexte fourni, pas génériques.\n\n"
        "RÉPONDS UNIQUEMENT avec un JSON valide (tableau de 5 objets). Aucun texte avant/après.\n\n"
        "Format :\n"
        "[\n"
        '  {"id":"q1","question":"...","aide":"aide courte","placeholder":"exemple concret","obligatoire":true},\n'
        '  {"id":"q2",...,"obligatoire":true},\n'
        '  {"id":"q3",...,"obligatoire":true},\n'
        '  {"id":"q4",...,"obligatoire":false},\n'
        '  {"id":"q5",...,"obligatoire":false}\n'
        "]\n\n"
        "Couvre impérativement :\n"
        "q1 : Décision stratégique à éclairer (pourquoi ce benchmark ?)\n"
        "q2 : Périmètre exact (entités, fonctions, géographie)\n"
        "q3 : Dimensions/variables prioritaires pour la comparaison\n"
        "q4 : Contraintes spécifiques (réglementaires, budget, calendrier)\n"
        "q5 : Public cible et livrables attendus"
    )

    user = (
        f"Mission benchmark {type_m} :\n"
        f"- Entreprise cible : {entreprise}\n"
        f"- Secteur : {secteur}\n"
        f"- Géographie : {geographie}\n"
        f"- Brief initial : {brief or 'Non renseigné'}\n\n"
        "Génère 5 questions de cadrage spécifiques et actionnables pour cette mission."
    )

    try:
        raw    = _call_claude_simple(system, user, settings, max_tokens=1200)
        result = _extract_json(raw, fallback=[])
        if isinstance(result, list) and len(result) >= 3:
            return result[:5]
    except Exception:
        pass

    return _fallback_questions(type_m)


def _fallback_questions(type_m: str) -> List[dict]:
    """Questions de cadrage génériques si le LLM est indisponible."""
    if type_m.upper() == "ORGANISATIONNEL":
        return [
            {
                "id": "q1",
                "question": "Quelle décision stratégique ce benchmark doit-il éclairer ?",
                "aide": "Ex : créer un CSP, externaliser une fonction, restructurer un département",
                "placeholder": "Ex : Décision de création d'un CSP douanier mutualisé Maghreb",
                "obligatoire": True,
            },
            {
                "id": "q2",
                "question": "Quel est le périmètre exact (entités, fonctions, géographie) ?",
                "aide": "Ex : filiale marocaine uniquement, ou groupe ? Toutes fonctions ou périmètre délimité ?",
                "placeholder": "Ex : Filiale Maroc — douane, comptabilité fournisseurs, trésorerie",
                "obligatoire": True,
            },
            {
                "id": "q3",
                "question": "Quelles dimensions sont prioritaires pour la comparaison ?",
                "aide": "Ex : coûts, délais, taux d'automatisation, organisation, conformité",
                "placeholder": "Ex : Coût/déclaration, délai mainlevée, taux circuit vert, niveau OEA",
                "obligatoire": True,
            },
            {
                "id": "q4",
                "question": "Y a-t-il des contraintes spécifiques à intégrer ?",
                "aide": "Ex : réglementation locale, exigences groupe, budget, calendrier",
                "placeholder": "Ex : Exigences groupe, réglementation ADII, délai de décision 3 mois",
                "obligatoire": False,
            },
            {
                "id": "q5",
                "question": "À qui ce benchmark est-il destiné et quel est l'objectif final ?",
                "aide": "Ex : COMEX pour arbitrage investissement, DG pour validation projet",
                "placeholder": "Ex : DAF + DG Maroc → décision de création du CSP",
                "obligatoire": False,
            },
        ]
    else:
        return [
            {
                "id": "q1",
                "question": "Quelle décision RH ou organisationnelle ce benchmark doit-il éclairer ?",
                "aide": "Ex : restructurer la DRH, créer un HRSC régional, attirer des profils rares",
                "placeholder": "Ex : Décision de centralisation des fonctions RH dans un HRSC régional",
                "obligatoire": True,
            },
            {
                "id": "q2",
                "question": "Quel périmètre RH est analysé (fonctions, entités, niveau hiérarchique) ?",
                "aide": "Ex : DRH Maroc uniquement ou groupe ? HRBP uniquement ou toutes fonctions ?",
                "placeholder": "Ex : DRH Groupe + filiales MENA — recrutement, paie, formation",
                "obligatoire": True,
            },
            {
                "id": "q3",
                "question": "Quelles dimensions RH sont prioritaires pour la comparaison ?",
                "aide": "Ex : ratio HR/FTE, coût de la fonction RH, compétences, digitalisation",
                "placeholder": "Ex : Ratio HR/FTE, time-to-fill, coût recrutement, taux de rétention cadres",
                "obligatoire": True,
            },
            {
                "id": "q4",
                "question": "Quels sont les enjeux RH spécifiques à votre contexte ?",
                "aide": "Ex : tension sur certains profils, contexte syndical, contraintes légales locales",
                "placeholder": "Ex : Tension sur profils supply chain, préférence nationale, TNS élevé",
                "obligatoire": False,
            },
            {
                "id": "q5",
                "question": "Quel est le niveau de maturité RH actuel et la cible visée ?",
                "aide": "Ex : RH administrative → RH stratégique partenaire business",
                "placeholder": "Ex : Niveau actuel : RH admin. Cible : HRBP stratégique en 2 ans",
                "obligatoire": False,
            },
        ]


# ─────────────────────────────────────────────────────────────────────────────
#  IDENTIFICATION DES COMPARABLES — TOOL USE
# ─────────────────────────────────────────────────────────────────────────────

_TOOL_COMPARABLES = {
    "name": "benchmark_comparables",
    "description": (
        "Identifie les entreprises de référence et les dimensions communes pour un benchmark mission. "
        "Mix obligatoire : concurrents directs + best-in-class sectoriel + best practice fonctionnel "
        "d'autres secteurs + 1-2 aspirations world-class."
    ),
    "input_schema": {
        "type": "object",
        "required": ["comparables", "dimensions_communes", "note_methodologique"],
        "properties": {
            "comparables": {
                "type": "array",
                "description": "6 à 8 entreprises de référence avec justification",
                "items": {
                    "type": "object",
                    "required": ["nom", "secteur", "taille", "pays", "type_comparaison", "justification", "pertinence"],
                    "properties": {
                        "nom": {"type": "string", "description": "Nom de l'entreprise"},
                        "secteur": {"type": "string", "description": "Secteur d'activité"},
                        "taille": {"type": "string", "description": "CA indicatif et/ou effectifs — ex: CA ~500M€, ~3000 employés"},
                        "pays": {"type": "string", "description": "Pays principal d'opération"},
                        "type_comparaison": {
                            "type": "string",
                            "enum": ["Concurrent direct", "Best-in-class sectoriel", "Best practice fonctionnel", "Benchmark aspiration"],
                            "description": "Type de relation comparative",
                        },
                        "justification": {
                            "type": "string",
                            "description": "Pourquoi cette entreprise est pertinente — pratiques spécifiques ou similitudes clés",
                        },
                        "pertinence": {
                            "type": "string",
                            "enum": ["Haute", "Moyenne", "Indicative"],
                        },
                    },
                },
            },
            "dimensions_communes": {
                "type": "array",
                "description": "4 à 6 variables/dimensions mesurables pour structurer la comparaison",
                "items": {
                    "type": "object",
                    "required": ["dimension", "definition", "unite_mesure"],
                    "properties": {
                        "dimension": {"type": "string"},
                        "definition": {"type": "string", "description": "Définition opérationnelle de la dimension"},
                        "unite_mesure": {"type": "string", "description": "Ex: MAD/déclaration, %, jours, ratio"},
                    },
                },
            },
            "note_methodologique": {
                "type": "string",
                "description": "Note courte (2-3 phrases) sur la logique de sélection des comparables",
            },
        },
    },
}

_SYSTEM_COMPARABLES = """Tu es un consultant senior LMS ORH, expert en benchmark stratégique international.

MISSION : identifier les meilleures entreprises de référence pour un benchmark en adoptant \
une approche MULTI-CRITÈRES au-delà du seul secteur.

RÈGLES DE SÉLECTION IMPÉRATIVES :
1. Inclus OBLIGATOIREMENT ces 4 types (au moins 1 de chaque) :
   - Concurrent direct : même secteur + même géographie + taille similaire (± 30%)
   - Best-in-class sectoriel : même secteur mais plus mature/performant sur les dimensions clés
   - Best practice fonctionnel : secteur différent mais excellence reconnue sur la dimension analysée
   - Benchmark aspiration : référence world-class internationale sur la pratique cible

2. TAILLE : propose des entreprises de taille comparable. Si l'entreprise cible fait ~500M€ de CA, \
ne propose pas Amazon ou Nestlé global comme "concurrent direct" — propose une filiale ou une PME comparable.

3. GÉOGRAPHIE : favorise les références Maroc/MENA/Afrique francophone en priorité, complète avec \
France/Europe si pertinent.

4. DIMENSIONS COMMUNES : identifie des variables MESURABLES et COMPARABLES, pas des descriptions vagues.

Appelle l'outil benchmark_comparables avec ta réponse structurée."""


def identify_comparables(mission_config: dict, cadrage_answers: dict,
                          settings: dict) -> dict:
    """
    Identifie les meilleures entreprises de référence + dimensions communes.

    Critères : taille, positionnement, secteurs adjacents, pratiques world-class.
    PAS uniquement le même secteur.

    Args:
        mission_config  : config de la mission (enrichie avec les réponses cadrage)
        cadrage_answers : {q1: "...", q2: "...", ...}
        settings        : settings.yaml

    Returns:
        {comparables: [...], dimensions_communes: [...], note_methodologique: str}
    """
    entreprise    = mission_config.get("entreprise_cible", "")
    secteur       = mission_config.get("secteur", "")
    geographie    = mission_config.get("geographie", "")
    type_m        = mission_config.get("type", "RH")
    brief         = mission_config.get("angle_strategique_rh", "")
    existing_ref  = mission_config.get("concurrent_reference", "") or ""

    answers_text = "\n".join(
        f"  • {q_id} : {ans}"
        for q_id, ans in cadrage_answers.items()
        if ans and str(ans).strip()
    ) or "  (non renseignées)"

    user_prompt = (
        f"Mission benchmark {type_m} :\n"
        f"Entreprise cible : {entreprise}\n"
        f"Secteur : {secteur}\n"
        f"Géographie : {geographie}\n"
        f"Brief mission : {brief or 'Non renseigné'}\n"
        + (f"Référence mentionnée : {existing_ref}\n" if existing_ref else "")
        + f"\nRéponses au cadrage :\n{answers_text}\n\n"
        "Identifie 6 à 8 entreprises de référence avec un mix équilibré des 4 types. "
        "Identifie aussi 4 à 6 dimensions communes mesurables."
    )

    # Tentative 1 : tool_use (résultat structuré garanti)
    try:
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY manquante")
        model  = settings.get("analysis", {}).get("model", "claude-sonnet-4-6")
        client = anthropic.Anthropic(api_key=api_key)
        resp   = client.messages.create(
            model=model,
            max_tokens=2500,
            system=_SYSTEM_COMPARABLES,
            tools=[_TOOL_COMPARABLES],
            tool_choice={"type": "any"},
            messages=[{"role": "user", "content": user_prompt}],
        )
        for block in resp.content:
            if block.type == "tool_use" and block.name == "benchmark_comparables":
                return dict(block.input)
    except Exception:
        pass

    # Tentative 2 : JSON brut
    try:
        system_fallback = _SYSTEM_COMPARABLES.replace(
            "Appelle l'outil benchmark_comparables avec ta réponse structurée.",
            "Réponds UNIQUEMENT en JSON valide selon le schéma attendu.",
        )
        raw    = _call_claude_simple(system_fallback, user_prompt, settings, max_tokens=2500)
        result = _extract_json(raw, fallback={})
        if isinstance(result, dict) and "comparables" in result:
            return result
    except Exception:
        pass

    return {
        "comparables": [],
        "dimensions_communes": [],
        "note_methodologique": (
            "Identification automatique indisponible. "
            "Renseignez les comparables manuellement dans le champ ci-dessous."
        ),
    }
