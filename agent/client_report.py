"""
Solution 3 — Rapport Innovation RH Client.

Génère chaque mois :
  - Un rapport interne consultant (HTML) avec angles commerciaux
  - Une infographie client HTML (1 page, format email/LinkedIn)

Les deux versions sont sauvegardées dans reports/innovation/ avec un statut
JSON (en_attente → validé → envoyé) géré par le manager LMS via Streamlit.

Fonctions publiques :
  generate_innovation_report(secteur_cfg, mois, settings)
  generate_infographie_html(report_data, config_client)
  generate_rapport_interne(report_data, config_client)
  list_pending_reports()
  validate_report(report_id)
  reject_report(report_id)
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
#  CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

ROOT        = Path(__file__).parent.parent
INNOV_DIR   = ROOT / "reports" / "innovation"
LOG_FILE    = INNOV_DIR / "log.json"

# Palette LMS
BORDEAUX    = "#8B1A1A"
BORDEAUX_LT = "#F5EDED"
DARK        = "#2D2D2D"
GRAY        = "#595959"
GRAY_LT     = "#F4F4F4"
WHITE       = "#FFFFFF"

# ─────────────────────────────────────────────────────────────────────────────
#  PROMPT SYSTÈME
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT_INNOVATION = """\
Tu es un expert en veille RH et en développement commercial pour un cabinet
de conseil en Organisation & RH (LMS ORH) spécialisé Maroc & Afrique.

MISSION DU MOIS :
Secteur analysé : {secteur}
Période couverte : {mois}
Géographie : {geographie}

ÉTAPE 1 — SÉLECTION DE L'INNOVATION PHARE
Parmi les sources fournies, sélectionne l'innovation RH du mois qui répond
à OUI sur au moins 3 de ces critères :
  ✓ LMS peut proposer une mission concrète en lien direct
  ✓ Au moins 1 chiffre récent vérifiable (≥ 2024)
  ✓ Au moins 1 entreprise réelle nommée avec un fait précis
  ✓ Compréhensible par un dirigeant non-RH en 30 secondes
  ✓ Signal confirmé ou renforcé dans les 30 derniers jours

ÉTAPE 2 — SÉLECTION DE 2 SIGNAUX FAIBLES
  Signal 1 : tendance émergente, horizon 6-18 mois
  Signal 2 : tendance émergente, horizon 12-36 mois
  Les deux signaux doivent être DISTINCTS de l'innovation phare.

ÉTAPE 3 — RÉDACTION DOUBLE VERSION

VERSION INTERNE CONSULTANT (détaillée, avec angles commerciaux) :
  - Observation factuelle avec chiffre réel et source [N]
  - Entreprise(s) pionnière(s) nommée(s) avec fait précis
  - Pourquoi c'est important pour le secteur
  - Angles d'approche commerciale : 2-3 formulations naturelles pour aborder
    le sujet avec le client sans paraître commercial

VERSION CLIENT (infographie, langage dirigeant) :
  - Titre ultra-court (5 mots max)
  - 1 chiffre clé percutant
  - Description : 2 phrases maximum, niveau dirigeant, sans jargon
  - "Ce que ça change pour vous :" — 1 phrase active et directe

RÈGLES ABSOLUES :
  - Chaque innovation phare cite au moins 1 chiffre réel avec source [N]
  - Chaque innovation phare nomme au moins 1 entreprise réelle avec fait précis
  - Les angles commerciaux sont en langage naturel, jamais en ton "vendeur"
  - Les champs titre_client ont max 5-6 mots
  - Ne jamais laisser de champ vide ou avec des crochets non remplacés
"""

# ─────────────────────────────────────────────────────────────────────────────
#  FORMAT DE SORTIE GROQ / GEMINI
# ─────────────────────────────────────────────────────────────────────────────

GROQ_OUTPUT_FORMAT = """\
Retourne un objet JSON avec exactement cette structure.
Remplace TOUS les textes entre [crochets] par du vrai contenu.

{
  "secteur": "[nom du secteur analysé]",
  "mois": "[mois et année ex: Juin 2026]",
  "innovation_phare": {
    "titre_interne": "[titre accrocheur 8 mots max — version consultant]",
    "titre_client": "[titre ultra-court 5 mots max — version dirigeant]",
    "chiffre_cle": "[chiffre percutant avec unité ex: 68% ou 3 entreprises sur 5]",
    "observation_interne": "[2-3 phrases factuelles avec chiffre, source [N] et entreprise nommée]",
    "entreprises_nommees": ["[entreprise réelle 1]", "[entreprise réelle 2]"],
    "source": "[source ou médias de l'information]",
    "horizon": "[immédiat / 6-12 mois / 12-24 mois]",
    "description_client": "[2 phrases maximum en langage dirigeant sans jargon RH]",
    "so_what_client": "[1 phrase active : ce que ça change concrètement pour le client]",
    "angles_commerciaux": [
      "[formulation naturelle 1 pour aborder le sujet — ex: Saviez-vous que...]",
      "[formulation naturelle 2 — question ouverte orientée client]",
      "[formulation naturelle 3 — lien avec une problématique client connue]"
    ]
  },
  "signal_faible_1": {
    "titre_interne": "[titre signal 1 — 6 mots max]",
    "titre_client": "[titre client signal 1 — 5 mots max]",
    "observation_interne": "[2 phrases sur le signal avec source [N] si disponible]",
    "description_client": "[1 phrase en langage dirigeant]",
    "horizon_badge": "Dans 6-12 mois"
  },
  "signal_faible_2": {
    "titre_interne": "[titre signal 2 — 6 mots max]",
    "titre_client": "[titre client signal 2 — 5 mots max]",
    "observation_interne": "[2 phrases sur le signal avec source [N] si disponible]",
    "description_client": "[1 phrase en langage dirigeant]",
    "horizon_badge": "Dans 1-2 ans"
  }
}
"""


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS LLM
# ─────────────────────────────────────────────────────────────────────────────

def _format_articles(articles: List[Dict], max_art: int = 15, summary_len: int = 300) -> str:
    lines = [f"## {min(len(articles), max_art)} sources — citer via [N]\n"]
    for i, a in enumerate(articles[:max_art], 1):
        lines.append(f"[{i}] {a.get('source', '')} {a.get('date', '')} | {a.get('title', '')}")
        if a.get("summary"):
            lines.append(f"     {a['summary'][:summary_len]}")
        lines.append("")
    return "\n".join(lines)


def _call_anthropic_innovation(client, model: str, system_text: str, user_prompt: str) -> dict:
    """Appel Anthropic avec web_search + sortie JSON."""
    # Étape 1 : recherche web préliminaire
    research_context = ""
    try:
        r = client.messages.create(
            model=model,
            max_tokens=1500,
            system=system_text,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            tool_choice={"type": "auto"},
            messages=[{"role": "user", "content": (
                "Effectue des recherches web sur les innovations RH du mois dans ce secteur. "
                "Trouve au moins 1 chiffre récent et 1 entreprise réelle. "
                "Synthétise en bullet points.\n\n" + user_prompt[:600]
            )}],
        )
        for block in r.content:
            if hasattr(block, "text") and block.text:
                research_context = block.text
                logger.info(f"Web search innovation — {len(research_context)} chars")
                break
    except Exception as e:
        logger.info(f"Web search ignoré : {e}")

    enriched = user_prompt
    if research_context:
        enriched += f"\n\n**Recherches web (intégrer obligatoirement) :**\n{research_context}"

    # Étape 2 : sortie JSON
    resp = client.messages.create(
        model=model,
        max_tokens=3000,
        system=system_text,
        messages=[{"role": "user", "content": enriched}],
    )
    raw = ""
    for block in resp.content:
        if hasattr(block, "text"):
            raw = block.text.strip()
            break
    # Extraire le JSON de la réponse
    if "```json" in raw:
        raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in raw:
        raw = raw.split("```", 1)[1].split("```", 1)[0].strip()
    start = raw.find("{")
    if start >= 0:
        raw = raw[start:]
    return json.loads(raw)


def _call_groq_innovation(model_name: str, system_text: str, user_prompt: str,
                          max_tokens: int = 3000) -> dict:
    """Appel Groq JSON mode pour innovation."""
    try:
        from groq import Groq
    except ImportError:
        raise ImportError("groq non installé : pip install groq>=0.9.0")

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY manquant.")

    client = Groq(api_key=api_key)
    system_final = f"{system_text}\n\nFORMAT DE RÉPONSE :\n{GROQ_OUTPUT_FORMAT}"

    for attempt in range(2):
        try:
            resp = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_final},
                    {"role": "user",   "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                max_tokens=max_tokens,
                temperature=0.4 + attempt * 0.1,
            )
            raw = resp.choices[0].message.content.strip()
            result = json.loads(raw)
            logger.info(
                f"Innovation (Groq/{model_name}) — "
                f"{resp.usage.prompt_tokens} in / {resp.usage.completion_tokens} out"
            )
            # Vérification contenu non vide
            ip = result.get("innovation_phare", {})
            if not ip.get("titre_client") or not ip.get("chiffre_cle"):
                logger.warning(f"Innovation Groq vide (tentative {attempt+1})")
                if attempt == 0:
                    continue
            return result
        except Exception as e:
            logger.warning(f"Groq innovation tentative {attempt+1} : {e}")
            if attempt == 0:
                continue
    raise RuntimeError("Groq innovation : échec après 2 tentatives")


def _call_gemini_innovation(model_name: str, system_text: str, user_prompt: str,
                             max_tokens: int = 3000) -> dict:
    """Appel Gemini JSON mode pour innovation."""
    try:
        from google import genai
        from google.genai import types as genai_types
    except ImportError:
        raise ImportError("google-genai non installé : pip install google-genai>=1.0.0")

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY manquant.")

    client = genai.Client(api_key=api_key, http_options={"api_version": "v1beta"})
    combined = f"{system_text}\n\nFORMAT DE RÉPONSE :\n{GROQ_OUTPUT_FORMAT}\n\n{user_prompt}"
    resp = client.models.generate_content(
        model=model_name,
        contents=combined,
        config=genai_types.GenerateContentConfig(
            response_mime_type="application/json",
            max_output_tokens=max_tokens,
            temperature=0.4,
        ),
    )
    raw = resp.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0].strip()
    return json.loads(raw)


# ─────────────────────────────────────────────────────────────────────────────
#  GÉNÉRATION DU RAPPORT
# ─────────────────────────────────────────────────────────────────────────────

def generate_innovation_report(
    secteur_cfg: Dict,
    mois: str,
    settings: Dict,
    articles: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """
    Génère le rapport Innovation du mois pour un secteur.

    Args:
        secteur_cfg : dict depuis sectors.yaml (clé secteur avec label, geographie, clients…)
        mois        : "Juin 2026"
        settings    : dict depuis settings.yaml
        articles    : liste d'articles collectés (si None, collecte auto)

    Returns:
        dict avec innovation_phare, signal_faible_1, signal_faible_2 + métadonnées
    """
    INNOV_DIR.mkdir(parents=True, exist_ok=True)

    label = secteur_cfg.get("label", secteur_cfg.get("nom", "Secteur"))
    geographie = secteur_cfg.get("geographie", "Maroc")

    analysis_cfg = settings.get("analysis", {})
    provider = (os.environ.get("LLM_PROVIDER") or analysis_cfg.get("provider", "groq")).lower()

    # Collecte articles si pas fournis
    if not articles:
        try:
            from agent import collector as col
            articles = col.collect(secteur_cfg, settings)
            logger.info(f"Innovation : {len(articles)} articles collectés pour {label}")
        except Exception as e:
            logger.warning(f"Collecte innovation échouée : {e} — on continue sans articles")
            articles = []

    # Limite selon provider
    max_art = 10 if provider in ("groq", "gemini") else 20
    summary_len = 200 if provider in ("groq", "gemini") else 400
    articles_text = _format_articles(articles, max_art=max_art, summary_len=summary_len)

    system_text = SYSTEM_PROMPT_INNOVATION.format(
        secteur=label,
        mois=mois,
        geographie=geographie,
    )

    user_prompt = (
        f"Analyse les innovations RH du mois pour le secteur **{label}** ({geographie}).\n"
        f"Période : {mois}\n\n"
        f"**Sources collectées (citer via [N]) :**\n{articles_text}\n\n"
        f"Sélectionne l'innovation phare et les 2 signaux faibles selon les critères "
        f"définis. Produis les deux versions (interne + client)."
    )

    # Appel LLM
    if provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY manquant.")
        try:
            import anthropic as _ant
        except ImportError:
            raise ImportError("anthropic non installé : pip install anthropic>=0.40.0")
        client_ant = _ant.Anthropic(api_key=api_key)
        model = (os.environ.get("CLAUDE_MODEL")
                 or analysis_cfg.get("model", "claude-sonnet-4-6"))
        result = _call_anthropic_innovation(client_ant, model, system_text, user_prompt)

    elif provider == "gemini":
        model = (os.environ.get("GEMINI_MODEL")
                 or analysis_cfg.get("gemini_model", "gemini-2.5-flash"))
        result = _call_gemini_innovation(model, system_text, user_prompt,
                                         max_tokens=analysis_cfg.get("gemini_max_tokens", 3000))
    else:  # groq (défaut)
        model = (os.environ.get("GROQ_MODEL")
                 or analysis_cfg.get("groq_model", "llama-3.3-70b-versatile"))
        result = _call_groq_innovation(model, system_text, user_prompt,
                                       max_tokens=analysis_cfg.get("groq_max_tokens", 3000))

    # Enrichir avec métadonnées
    safe_label = "".join(c if c.isalnum() else "_" for c in label)
    safe_mois  = "".join(c if c.isalnum() else "_" for c in mois)
    report_id  = f"{safe_label}_{safe_mois}"

    result["_meta"] = {
        "report_id":   report_id,
        "secteur":     label,
        "mois":        mois,
        "geographie":  geographie,
        "provider":    provider,
        "model":       model if provider != "anthropic" else analysis_cfg.get("model", ""),
        "generated_at": datetime.now().isoformat(),
        "statut":      "en_attente",
        "nb_sources":  len(articles),
    }

    # Sauvegarde JSON brut
    raw_path = INNOV_DIR / f"{report_id}_raw.json"
    raw_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"Rapport innovation sauvegardé → {raw_path.name}")

    # Mise à jour du log
    _update_log(report_id, result["_meta"])

    return result


# ─────────────────────────────────────────────────────────────────────────────
#  GÉNÉRATION HTML
# ─────────────────────────────────────────────────────────────────────────────

def generate_infographie_html(
    report_data: Dict,
    config_client: Optional[Dict] = None,
) -> str:
    """
    Génère l'infographie HTML 1 page.

    Structure McKinsey (données hero, règles fines, UPPERCASE, barre CSS,
    2 colonnes signaux, CTA texte, zéro arrondi) appliquée à la charte LMS ORH :
      · Bordeaux  #8B1A1A  — accent principal, chiffre hero, barre, labels
      · Bordeaux pâle #F5EDED — fond callout
      · Bordeaux clair #C8AAAA — accent secondaire signal 2
      · Gris foncé #2D2D2D — texte titres
      · Gris #595959 — texte secondaire
      · Gris règle #E5E5E5
      · Fond signaux #F5F5F5
    """
    import re as _re

    ip   = report_data.get("innovation_phare", {})
    sf1  = report_data.get("signal_faible_1", {})
    sf2  = report_data.get("signal_faible_2", {})
    meta = report_data.get("_meta", {})

    secteur    = meta.get("secteur",  report_data.get("secteur", ""))
    mois       = meta.get("mois",     report_data.get("mois", ""))
    nom_client = (config_client or {}).get("nom", "")
    email_cons = (config_client or {}).get("email_consultant", "contact@lms-orh.com")
    nom_cons   = (config_client or {}).get("nom_consultant", "LMS ORH")

    # ── Palette LMS ORH ───────────────────────────────────────────────────────
    BORD   = "#8B1A1A"   # bordeaux principal LMS
    BORD_L = "#F5EDED"   # bordeaux très pâle — fond callout
    BORD_M = "#C8AAAA"   # bordeaux clair — accent secondaire (signal 2)
    BORD_T = "#F0E4E4"   # bordeaux track barre (fond de la jauge)
    DARK   = "#2D2D2D"   # gris foncé LMS — titres, textes forts
    GRAY2  = "#595959"   # gris secondaire LMS
    GRAY3  = "#9A9A9A"   # gris tertiaire — source, metadata
    RULE   = "#E5E5E5"   # gris séparateur LMS
    BG     = "#FFFFFF"   # fond blanc
    BGS    = "#F5F5F5"   # fond section signaux (gris clair LMS)
    BGPAGE = "#EDEEF0"   # fond page (légèrement gris)

    # ── Logo LMS (base64 ou wordmark texte LMS) ───────────────────────────────
    assets_dir = Path(__file__).parent.parent / "assets"
    logo_b64   = ""
    for _n in ("logo_lms.png", "Logo LMS.png", "logo_lms_dark.png", "logo_lms.jpg"):
        _p = assets_dir / _n
        if _p.exists():
            import base64 as _b64
            logo_b64 = _b64.b64encode(_p.read_bytes()).decode()
            break

    if logo_b64:
        logo_html = (
            f'<img src="data:image/png;base64,{logo_b64}" height="28" alt="LMS ORH" '
            f'style="display:block;"/>'
        )
    else:
        # Wordmark LMS ORH en bordeaux si pas de logo
        logo_html = (
            f'<span style="font-family:\'Helvetica Neue\',Arial,sans-serif;'
            f'font-size:16px;font-weight:700;letter-spacing:.5px;color:{BORD};">'
            f'LMS ORH</span>'
        )

    # ── Barre CSS (si le chiffre clé contient un %) ───────────────────────────
    chiffre_raw = ip.get("chiffre_cle", "")
    pct_m = _re.search(r"(\d+)\s*%", chiffre_raw)
    bar_html = ""
    if pct_m:
        pct = min(int(pct_m.group(1)), 100)
        bar_html = f"""
        <div style="margin:20px 0 4px;">
          <div style="display:flex;align-items:center;gap:10px;">
            <div style="flex:1;height:6px;background:{BORD_T};">
              <div style="width:{pct}%;height:6px;background:{BORD};"></div>
            </div>
            <span style="font-size:11px;font-weight:700;color:{BORD};
                         min-width:32px;text-align:right;">{pct}%</span>
          </div>
        </div>"""

    # ── Horizon label (texte UPPERCASE épuré) ─────────────────────────────────
    def _horizon(text: str, color: str = BORD) -> str:
        return (
            f'<span style="font-size:9px;font-weight:700;letter-spacing:1.2px;'
            f'text-transform:uppercase;color:{color};">{text}</span>'
        )

    # ── CTA ───────────────────────────────────────────────────────────────────
    cta_q = (
        f"Cette évolution concerne-t-elle {nom_client}&nbsp;?"
        if nom_client else
        "Ces évolutions concernent-elles votre organisation&nbsp;?"
    )

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Veille Innovation RH — {secteur} — {mois}</title>
</head>
<body style="margin:0;padding:24px 16px;background:{BGPAGE};
             font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">

<div style="max-width:600px;margin:0 auto;background:{BG};">

  <!-- ══ BANDE TOP BORDEAUX LMS ══ -->
  <div style="height:4px;background:{BORD};"></div>

  <!-- ══ EN-TÊTE ══ -->
  <div style="padding:20px 32px 16px;border-bottom:1px solid {RULE};
              display:flex;justify-content:space-between;align-items:center;">
    <div>{logo_html}</div>
    <div style="text-align:right;">
      <div style="font-size:9px;font-weight:700;letter-spacing:1.4px;
                  text-transform:uppercase;color:{GRAY2};">
        VEILLE INNOVATION RH
      </div>
      <div style="font-size:10px;color:{GRAY3};margin-top:2px;">
        {secteur} &nbsp;·&nbsp; {mois}
      </div>
    </div>
  </div>

  <!-- ══ INNOVATION PHARE ══ -->
  <div style="padding:28px 32px 24px;">

    <!-- Label catégorie bordeaux -->
    <div style="font-size:9px;font-weight:700;letter-spacing:1.6px;
                text-transform:uppercase;color:{BORD};margin-bottom:18px;">
      Innovation du mois
    </div>

    <!-- Chiffre hero bordeaux -->
    <div style="font-size:52px;font-weight:700;color:{BORD};line-height:1;
                letter-spacing:-1px;margin-bottom:6px;">
      {chiffre_raw}
    </div>

    <!-- Titre gris foncé -->
    <div style="font-size:16px;font-weight:600;color:{DARK};line-height:1.35;
                margin-bottom:4px;">
      {ip.get("titre_client", "")}
    </div>

    <!-- Barre CSS bordeaux -->
    {bar_html}

    <!-- Règle fine -->
    <div style="height:1px;background:{RULE};margin:18px 0;"></div>

    <!-- Description -->
    <div style="font-size:13px;color:{GRAY2};line-height:1.7;margin-bottom:18px;">
      {ip.get("description_client", "")}
    </div>

    <!-- Callout "Ce que ça change" — bordure bordeaux + fond bordeaux pâle -->
    <div style="border-left:3px solid {BORD};background:{BORD_L};
                padding:12px 16px;">
      <div style="font-size:9px;font-weight:700;letter-spacing:1.2px;
                  text-transform:uppercase;color:{BORD};margin-bottom:6px;">
        Ce que ça change pour vous
      </div>
      <div style="font-size:13px;color:{DARK};line-height:1.6;">
        {ip.get("so_what_client", "")}
      </div>
    </div>

  </div>

  <!-- ══ RÈGLE SÉPARATRICE ══ -->
  <div style="height:1px;background:{RULE};margin:0 32px;"></div>

  <!-- ══ SIGNAUX À SURVEILLER ══ -->
  <div style="background:{BGS};padding:22px 32px 24px;">

    <div style="font-size:9px;font-weight:700;letter-spacing:1.6px;
                text-transform:uppercase;color:{GRAY2};margin-bottom:18px;">
      Signaux à surveiller
    </div>

    <!-- 2 colonnes -->
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr valign="top">

        <!-- Signal 1 — accent bordeaux -->
        <td width="48%" style="padding-right:16px;">
          <div style="height:2px;background:{BORD};width:24px;margin-bottom:12px;"></div>
          {_horizon(sf1.get("horizon_badge", "Dans 6–12 mois"), BORD)}
          <div style="font-size:13px;font-weight:600;color:{DARK};
                      line-height:1.35;margin:7px 0 6px;">
            {sf1.get("titre_client", "")}
          </div>
          <div style="font-size:12px;color:{GRAY2};line-height:1.6;">
            {sf1.get("description_client", "")}
          </div>
        </td>

        <!-- Séparateur vertical -->
        <td width="4%" style="text-align:center;">
          <div style="width:1px;background:{RULE};height:100%;
                      margin:0 auto;min-height:80px;"></div>
        </td>

        <!-- Signal 2 — accent bordeaux clair -->
        <td width="48%" style="padding-left:16px;">
          <div style="height:2px;background:{BORD_M};width:24px;margin-bottom:12px;"></div>
          {_horizon(sf2.get("horizon_badge", "Dans 1–2 ans"), GRAY2)}
          <div style="font-size:13px;font-weight:600;color:{DARK};
                      line-height:1.35;margin:7px 0 6px;">
            {sf2.get("titre_client", "")}
          </div>
          <div style="font-size:12px;color:{GRAY2};line-height:1.6;">
            {sf2.get("description_client", "")}
          </div>
        </td>

      </tr>
    </table>

  </div>

  <!-- ══ RÈGLE SÉPARATRICE ══ -->
  <div style="height:1px;background:{RULE};"></div>

  <!-- ══ FOOTER ══ -->
  <div style="padding:20px 32px 24px;">

    <!-- CTA texte — question bordeaux, lien bordeaux souligné (sans bouton) -->
    <div style="font-size:13px;color:{DARK};font-weight:600;margin-bottom:10px;">
      {cta_q}
    </div>
    <div style="font-size:12px;color:{GRAY2};margin-bottom:16px;">
      Répondez directement à cet email ou écrivez à
      <a href="mailto:{email_cons}"
         style="color:{BORD};text-decoration:underline;">{email_cons}</a>
    </div>

    <!-- Règle fine footer -->
    <div style="height:1px;background:{RULE};margin-bottom:14px;"></div>

    <!-- Mention source -->
    <div style="font-size:10px;color:{GRAY3};line-height:1.6;">
      Source : LMS ORH — Veille Innovation RH &nbsp;·&nbsp;
      {nom_cons} &nbsp;·&nbsp; {mois} &nbsp;·&nbsp;
      Usage exclusif client — ne pas diffuser
    </div>

  </div>

  <!-- ══ BANDE BAS BORDEAUX LMS ══ -->
  <div style="height:3px;background:{BORD};"></div>

</div>

</body>
</html>"""
    return html


def generate_rapport_interne(
    report_data: Dict,
    config_client: Optional[Dict] = None,
) -> str:
    """
    Génère le rapport HTML complet version consultant (avec angles commerciaux).
    """
    ip   = report_data.get("innovation_phare", {})
    sf1  = report_data.get("signal_faible_1", {})
    sf2  = report_data.get("signal_faible_2", {})
    meta = report_data.get("_meta", {})

    secteur    = meta.get("secteur", report_data.get("secteur", ""))
    mois       = meta.get("mois",    report_data.get("mois", ""))
    nom_client = (config_client or {}).get("nom", "")
    gen_at     = meta.get("generated_at", "")[:10]

    angles = ip.get("angles_commerciaux", [])
    angles_html = "".join(
        f'<li style="margin-bottom:8px;">{a}</li>' for a in angles
    )

    entreprises = ip.get("entreprises_nommees", [])
    ent_html = ", ".join(f"<strong>{e}</strong>" for e in entreprises) if entreprises else "—"

    titre_section = (
        f"<p style='background:{BORDEAUX_LT};border-radius:4px;padding:10px 14px;"
        f"font-size:13px;color:{BORDEAUX};'>"
        f"<strong>Client concerné :</strong> {nom_client}</p>"
        if nom_client else ""
    )

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8"/>
<title>Rapport Interne — Veille Innovation RH — {secteur} — {mois}</title>
<style>
  body {{font-family:Arial,sans-serif;margin:0;padding:24px;color:{DARK};background:#FAFAFA;}}
  .container {{max-width:760px;margin:0 auto;background:white;border-radius:6px;
               padding:36px;box-shadow:0 2px 12px rgba(0,0,0,.08);}}
  h1 {{color:{BORDEAUX};font-size:22px;margin-bottom:4px;}}
  h2 {{color:{BORDEAUX};font-size:16px;border-bottom:2px solid {BORDEAUX};
       padding-bottom:6px;margin-top:28px;}}
  .badge {{background:{BORDEAUX};color:white;font-size:10px;padding:3px 10px;
           border-radius:3px;text-transform:uppercase;display:inline-block;
           margin-bottom:12px;}}
  .badge-gray {{background:{GRAY};color:white;font-size:10px;padding:2px 8px;
               border-radius:3px;text-transform:uppercase;display:inline-block;
               margin-bottom:8px;}}
  .chiffre {{font-size:38px;font-weight:bold;color:{BORDEAUX};margin:10px 0 4px;}}
  .so-what {{background:{BORDEAUX_LT};border-radius:4px;padding:12px 16px;
             font-size:13px;color:{BORDEAUX};margin-top:14px;}}
  .angles {{background:{GRAY_LT};border-radius:4px;padding:16px 20px;margin-top:14px;}}
  .angles h3 {{color:{DARK};font-size:14px;margin:0 0 10px;}}
  .angles ul {{margin:0;padding-left:18px;}}
  .signal {{background:{GRAY_LT};border-left:4px solid {GRAY};
            padding:14px 18px;margin-top:12px;border-radius:0 4px 4px 0;}}
  .meta {{font-size:11px;color:{GRAY};margin-top:32px;border-top:1px solid #EEE;
          padding-top:12px;}}
</style>
</head>
<body>
<div class="container">

  <h1>Rapport Veille Innovation RH — Usage Consultant</h1>
  <p style="color:{GRAY};font-size:13px;margin-top:4px;">
    {secteur} &nbsp;·&nbsp; {mois} &nbsp;·&nbsp; Confidentiel LMS ORH
  </p>
  {titre_section}

  <!-- INNOVATION PHARE -->
  <h2>★ Innovation phare du mois</h2>
  <span class="badge">Innovation du mois</span>
  <div class="chiffre">{ip.get("chiffre_cle", "")}</div>
  <p style="font-size:17px;font-weight:bold;margin:6px 0 14px;">{ip.get("titre_interne", "")}</p>

  <p style="font-size:13px;line-height:1.7;">{ip.get("observation_interne", "")}</p>

  <p style="font-size:13px;margin-top:10px;">
    <strong>Entreprises pionnières :</strong> {ent_html}<br/>
    <strong>Source :</strong> {ip.get("source", "—")}<br/>
    <strong>Horizon :</strong> {ip.get("horizon", "—")}
  </p>

  <div class="so-what">
    <strong>Ce que ça change pour vous (version client) :</strong><br/>
    {ip.get("so_what_client", "")}
  </div>

  <!-- ANGLES COMMERCIAUX -->
  <div class="angles">
    <h3>🎯 Angles d'approche commerciale</h3>
    <ul>{angles_html}</ul>
  </div>

  <!-- SIGNAUX FAIBLES -->
  <h2>◈ Signaux faibles</h2>

  <div class="signal">
    <span class="badge-gray">Signal 1 · {sf1.get("horizon_badge", "Dans 6-12 mois")}</span>
    <p style="font-size:15px;font-weight:bold;margin:8px 0 6px;">{sf1.get("titre_interne", "")}</p>
    <p style="font-size:13px;line-height:1.65;margin:0;">{sf1.get("observation_interne", "")}</p>
  </div>

  <div class="signal">
    <span class="badge-gray">Signal 2 · {sf2.get("horizon_badge", "Dans 1-2 ans")}</span>
    <p style="font-size:15px;font-weight:bold;margin:8px 0 6px;">{sf2.get("titre_interne", "")}</p>
    <p style="font-size:13px;line-height:1.65;margin:0;">{sf2.get("observation_interne", "")}</p>
  </div>

  <div class="meta">
    Généré le {gen_at} &nbsp;·&nbsp; Provider : {meta.get("provider", "")} &nbsp;·&nbsp;
    {meta.get("nb_sources", 0)} sources analysées &nbsp;·&nbsp; Usage exclusif consultant LMS ORH
  </div>

</div>
</body>
</html>"""
    return html


# ─────────────────────────────────────────────────────────────────────────────
#  GESTION DES RAPPORTS (statut, log)
# ─────────────────────────────────────────────────────────────────────────────

def _update_log(report_id: str, meta: dict) -> None:
    """Met à jour reports/innovation/log.json."""
    INNOV_DIR.mkdir(parents=True, exist_ok=True)
    try:
        log = json.loads(LOG_FILE.read_text(encoding="utf-8")) if LOG_FILE.exists() else {}
    except Exception:
        log = {}
    log[report_id] = meta
    LOG_FILE.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")


def list_pending_reports() -> List[Dict]:
    """Retourne la liste des rapports en attente de validation."""
    if not LOG_FILE.exists():
        return []
    try:
        log = json.loads(LOG_FILE.read_text(encoding="utf-8"))
        return [v for v in log.values() if v.get("statut") == "en_attente"]
    except Exception:
        return []


def list_all_reports() -> List[Dict]:
    """Retourne tous les rapports du log."""
    if not LOG_FILE.exists():
        return []
    try:
        log = json.loads(LOG_FILE.read_text(encoding="utf-8"))
        return sorted(log.values(), key=lambda x: x.get("generated_at", ""), reverse=True)
    except Exception:
        return []


def load_report(report_id: str) -> Optional[Dict]:
    """Charge un rapport depuis le JSON brut."""
    path = INNOV_DIR / f"{report_id}_raw.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def validate_report(report_id: str) -> bool:
    """Passe le statut du rapport à 'validé'."""
    return _set_statut(report_id, "validé")


def mark_sent(report_id: str) -> bool:
    """Passe le statut du rapport à 'envoyé'."""
    return _set_statut(report_id, "envoyé")


def reject_report(report_id: str) -> bool:
    """Passe le statut du rapport à 'rejeté'."""
    return _set_statut(report_id, "rejeté")


def _set_statut(report_id: str, statut: str) -> bool:
    """Mise à jour du statut dans le log ET dans le _raw.json."""
    try:
        # log.json
        log = json.loads(LOG_FILE.read_text(encoding="utf-8")) if LOG_FILE.exists() else {}
        if report_id in log:
            log[report_id]["statut"] = statut
            log[report_id]["updated_at"] = datetime.now().isoformat()
            LOG_FILE.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
        # _raw.json
        raw_path = INNOV_DIR / f"{report_id}_raw.json"
        if raw_path.exists():
            data = json.loads(raw_path.read_text(encoding="utf-8"))
            data.setdefault("_meta", {})["statut"] = statut
            raw_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"Rapport {report_id} → {statut}")
        return True
    except Exception as e:
        logger.error(f"Erreur statut {report_id} : {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
#  GÉNÉRATION COMPLÈTE (rapport + infographie + rapport interne)
# ─────────────────────────────────────────────────────────────────────────────

def generate_all(
    secteur_cfg: Dict,
    mois: str,
    settings: Dict,
    clients: Optional[List[Dict]] = None,
    articles: Optional[List[Dict]] = None,
    progress_callback=None,
) -> Dict[str, Any]:
    """
    Pipeline complet :
    1. Génère le rapport brut (LLM)
    2. Génère le rapport interne HTML
    3. Pour chaque client : génère l'infographie personnalisée HTML
    4. Sauvegarde tout dans reports/innovation/
    Retourne un dict avec les chemins des fichiers générés.
    """
    INNOV_DIR.mkdir(parents=True, exist_ok=True)

    if progress_callback:
        progress_callback("Génération du contenu LLM…")

    report_data = generate_innovation_report(secteur_cfg, mois, settings, articles)
    report_id   = report_data["_meta"]["report_id"]

    # Rapport interne
    html_interne = generate_rapport_interne(report_data)
    path_interne = INNOV_DIR / f"{report_id}_interne.html"
    path_interne.write_text(html_interne, encoding="utf-8")

    if progress_callback:
        progress_callback("Rapport interne généré.")

    # Infographies par client
    client_files = {}
    for cfg_client in (clients or []):
        nom_cl = cfg_client.get("nom", "client")
        html_cl = generate_infographie_html(report_data, cfg_client)
        safe_cl = "".join(c if c.isalnum() else "_" for c in nom_cl)
        path_cl = INNOV_DIR / f"{report_id}_{safe_cl}_infographie.html"
        path_cl.write_text(html_cl, encoding="utf-8")
        client_files[nom_cl] = str(path_cl)
        if progress_callback:
            progress_callback(f"Infographie {nom_cl} générée.")

    # Infographie générique (sans client)
    html_gen = generate_infographie_html(report_data, None)
    path_gen = INNOV_DIR / f"{report_id}_infographie.html"
    path_gen.write_text(html_gen, encoding="utf-8")

    return {
        "report_id":    report_id,
        "report_data":  report_data,
        "path_interne": str(path_interne),
        "path_infographie": str(path_gen),
        "client_files": client_files,
    }
