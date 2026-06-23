"""
brief.py — Brève quotidienne de veille (format inspiré de la « Plateforme Veille V2 » de Zidane).

Produit une note courte (lecture 5 min) pour un secteur :
  - météo du jour (1 phrase)
  - top 3
  - 6 à 8 items hiérarchisés ACTION / VEILLE / INFO (fait + so what + sources)
  - signal faible

⚠️ ADDITIF et OPT-IN : ce module n'est PAS planifié automatiquement. Chaque brève
= 1 appel LLM (donc coût / quota). À déclencher à la demande (bouton UI ou CLI),
pour garder la maîtrise des coûts. Réutilise le dispatcher LLM de analyzer.py.
"""
import logging
import os
from datetime import datetime
from typing import Dict, List

from agent.analyzer import _call_llm, _format_articles

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
#  TOOL — sortie structurée de la brève
# ─────────────────────────────────────────
BRIEF_TOOL = {
    "name": "breve_quotidienne",
    "description": "Stocke la brève quotidienne : météo, top 3, items catégorisés (ACTION/VEILLE/INFO), signal faible.",
    "input_schema": {
        "type": "object",
        "properties": {
            "meteo_du_jour": {
                "type": "string",
                "description": "1 phrase qui résume l'ambiance / la tendance du secteur aujourd'hui",
            },
            "top_3": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Les 3 informations les plus importantes du jour, une ligne chacune",
            },
            "items": {
                "type": "array",
                "description": "6 à 8 items maximum, hiérarchisés",
                "items": {
                    "type": "object",
                    "properties": {
                        "categorie": {"type": "string", "enum": ["ACTION", "VEILLE", "INFO"]},
                        "titre": {"type": "string"},
                        "fait": {"type": "string", "description": "Le fait, factuel et sourcé"},
                        "so_what": {"type": "string", "description": "Implication concrète pour LMS ORH / ses clients"},
                        "sources": {"type": "array", "items": {"type": "integer"}},
                    },
                    "required": ["categorie", "titre", "fait", "so_what"],
                },
            },
            "signal_faible": {
                "type": "string",
                "description": "Un signal émergent à surveiller, pour discussion d'équipe",
            },
        },
        "required": ["meteo_du_jour", "top_3", "items", "signal_faible"],
    },
}

BRIEF_SYSTEM = """Tu es l'agent curateur de la veille stratégique de LMS ORH, cabinet de conseil en \
transformation organisationnelle (Maroc & Afrique). Tu produis une BRÈVE QUOTIDIENNE lisible en 5 minutes.

Règles :
- Maximum 8 items. Hiérarchise : ACTION (démarche commerciale ou interne à mener cette semaine) > \
VEILLE (à surveiller) > INFO (culture sectorielle).
- Chaque item = un fait factuel + un « so what » (implication concrète pour le cabinet ou ses clients).
- Chaque affirmation chiffrée doit être appuyée par [N] (numéro de source).
- Périmètre : UNIQUEMENT la transformation organisationnelle (structures, modèles opérationnels, RH, \
gouvernance, digitalisation). Pas de revue de presse généraliste.
- Ton : factuel, direct, registre consultant senior. Français."""

# ─────────────────────────────────────────
#  RÉSOLUTION DU PROVIDER (compact, miroir de analyzer.analyze)
# ─────────────────────────────────────────
def _resolve(settings: Dict):
    cfg = settings.get("analysis", {})
    provider = (os.environ.get("LLM_PROVIDER") or cfg.get("provider", "anthropic")).lower()
    client = None
    if provider == "gemini":
        model = os.environ.get("GEMINI_MODEL") or cfg.get("gemini_model", "gemini-2.5-pro")
        max_tokens = cfg.get("gemini_max_tokens", 4096)
    elif provider == "groq":
        model = os.environ.get("GROQ_MODEL") or cfg.get("groq_model", "llama-3.3-70b-versatile")
        max_tokens = cfg.get("groq_max_tokens", 7000)
    else:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY manquant pour provider=anthropic.")
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        model = os.environ.get("CLAUDE_MODEL") or cfg.get("model", "claude-opus-4-8")
        max_tokens = cfg.get("max_tokens", 8192)
    return provider, model, max_tokens, client


def generate_brief(sector_config: Dict, articles: List[Dict], settings: Dict) -> Dict:
    """Génère la brève quotidienne d'un secteur (1 appel LLM)."""
    provider, model, max_tokens, client = _resolve(settings)
    n = settings.get("analysis", {}).get("brief_max_articles", 20)
    arts = articles[:n]
    label = sector_config.get("label", "secteur")
    period = datetime.now().strftime("%d/%m/%Y")
    articles_text = _format_articles(arts, summary_len=300)

    prompt = (
        f"Produis la brève quotidienne de veille — **{label}** — {period}.\n\n"
        f"**Sources (citer via [N]) :**\n{articles_text}\n\n"
        "Utilise `breve_quotidienne`. Maximum 8 items, hiérarchisés ACTION > VEILLE > INFO. "
        "Chaque item : fait factuel + so what (implication cabinet/clients). Top 3 = les 3 plus importants."
    )
    brief = _call_llm(provider, model, max_tokens, BRIEF_SYSTEM,
                      BRIEF_TOOL, "breve_quotidienne", prompt, client)
    brief["_meta"] = {
        "sector": label, "period": period, "provider": provider, "model": model,
        "generated_at": datetime.now().isoformat(), "nb_sources": len(arts),
    }
    logger.info(f"Brève {label} — {len(brief.get('items', []))} items générés.")
    return brief


def render_brief_md(brief: Dict, sector_label: str = "") -> str:
    """Rend la brève en Markdown (lecture 5 min)."""
    label = sector_label or brief.get("_meta", {}).get("sector", "Secteur")
    period = brief.get("_meta", {}).get("period", "")
    out = [f"# Brève quotidienne — {label}", f"*{period}*", ""]
    out.append(f"**🌤️ Météo du jour :** {brief.get('meteo_du_jour', '')}")
    out.append("")
    top = brief.get("top_3", [])
    if top:
        out.append("## ⭐ Top 3")
        for i, t in enumerate(top, 1):
            out.append(f"{i}. {t}")
        out.append("")
    labels = {"ACTION": "🔴 ACTION", "VEILLE": "🟠 VEILLE", "INFO": "🔵 INFO"}
    for cat in ("ACTION", "VEILLE", "INFO"):
        items = [it for it in brief.get("items", []) if it.get("categorie") == cat]
        if not items:
            continue
        out.append(f"## {labels[cat]}")
        for it in items:
            src = "".join(f" [{n}]" for n in it.get("sources", []))
            out.append(f"- **{it.get('titre', '')}** — {it.get('fait', '')}{src}")
            out.append(f"  - *So what :* {it.get('so_what', '')}")
        out.append("")
    sf = brief.get("signal_faible")
    if sf:
        out.append("## 📡 Signal faible")
        out.append(sf)
    return "\n".join(out)
