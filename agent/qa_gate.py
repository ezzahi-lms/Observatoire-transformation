"""
qa_gate.py — Contrôle qualité automatique des benchmarks de veille.

Inspiré de l'agent QA de la « Plateforme Veille V2 » (Zidane) : avant qu'un
benchmark soit diffusé, on le passe au crible de contrôles pondérés, on calcule
un score /100, et on décide automatiquement :
  - score >= seuil  → "publiable"
  - score <  seuil  → "quarantaine" (le pilote relit avant diffusion)

100 % code Python — AUCUN appel LLM, donc AUCUN coût en tokens.

Le QA porte sur le dict structuré retourné par analyzer.analyze() (et compatible
avec analyzer_mission). Contrôles :
  1. Index des sources présent
  2. Sources citées [N] valides (dans la plage des articles)
  3. Sections obligatoires complètes
  4. Recommandations assorties d'un angle de mission conseil
  5. 3 lectures "So What ?" complètes (secteur / clients / cabinet)
  6. Fraîcheur des sources suffisante
  7. Volet réglementaire / gouvernance couvert
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_MIN_SCORE = 80


def _collect_cited_ids(data) -> set:
    """Parcourt récursivement le résultat et collecte les IDs de sources cités (champs `sources`)."""
    ids = set()
    if isinstance(data, dict):
        for k, v in data.items():
            if k == "sources" and isinstance(v, list):
                ids |= {s for s in v if isinstance(s, int)}
            else:
                ids |= _collect_cited_ids(v)
    elif isinstance(data, list):
        for it in data:
            ids |= _collect_cited_ids(it)
    return ids


def _filled(x, n: int = 20) -> bool:
    """True si x est une chaîne d'au moins n caractères significatifs."""
    return isinstance(x, str) and len(x.strip()) >= n


def run_qa(result: dict, articles: list, settings: dict) -> dict:
    """Évalue la qualité d'un benchmark. Retourne {score, status, checks, issues, ...}."""
    checks = []

    def add(name, passed, weight, detail=""):
        checks.append({"name": name, "passed": bool(passed), "weight": weight, "detail": detail})

    n_art = len(articles or [])

    # 1. Index des sources présent (25)
    index = result.get("index_sources") or []
    add("Index des sources présent", len(index) > 0, 25,
        f"{len(index)} sources indexées" if index else "index_sources VIDE")

    # 2. IDs cités valides (15)
    cited = _collect_cited_ids(result)
    invalid = sorted(i for i in cited if not (1 <= i <= n_art)) if n_art else sorted(cited)
    add("Sources citées valides", not invalid, 15,
        f"{len(cited)} citations valides" if not invalid else f"IDs hors plage : {invalid[:10]}")

    # 3. Sections obligatoires complètes (25)
    se = result.get("synthese_executive") or {}
    missing = []
    if not _filled(se.get("texte"), 40):              missing.append("synthèse exécutive")
    if not result.get("facteurs_cles_succes"):        missing.append("FCS")
    if not result.get("recommandations"):             missing.append("recommandations")
    if not result.get("dimension_afrique_mena"):      missing.append("dimension Afrique/MENA")
    if not result.get("questions_clients"):           missing.append("questions clients")
    add("Sections obligatoires complètes", not missing, 25,
        "toutes présentes" if not missing else "manquantes : " + ", ".join(missing))

    # 4. Recommandations avec angle de mission (10)
    recos = result.get("recommandations") or []
    n_no_angle = sum(1 for r in recos if not _filled((r or {}).get("angle_mission"), 10))
    reco_ok = bool(recos) and n_no_angle == 0
    add("Recommandations avec angle mission", reco_ok, 10,
        "toutes avec angle conseil" if reco_ok else f"{n_no_angle}/{len(recos)} sans angle_mission")

    # 5. 3 lectures So What complètes (10)
    sw = se.get("lectures_so_what") or {}
    sw_ok = all(_filled(sw.get(k), 15) for k in ("secteur", "clients", "cabinet"))
    add("3 lectures So What complètes", sw_ok, 10,
        "secteur/clients/cabinet OK" if sw_ok else "lectures So What incomplètes")

    # 6. Fraîcheur des sources (10)
    fresh = (result.get("_meta") or {}).get("freshness") or {}
    pct = fresh.get("pct_recent", 0)
    fresh_ok = pct >= 40 or n_art >= 15
    add("Fraîcheur des sources", fresh_ok, 10, f"{pct}% de sources <12 mois ({n_art} sources)")

    # 7. Volet réglementaire / gouvernance couvert (5)
    reg_ok = bool(result.get("signaux_faibles")) or bool(result.get("pratiques_gouvernance"))
    add("Volet réglementaire/gouvernance couvert", reg_ok, 5,
        "présent" if reg_ok else "aucun signal faible / pratique de gouvernance")

    total = sum(c["weight"] for c in checks)
    got = sum(c["weight"] for c in checks if c["passed"])
    score = round(got / total * 100) if total else 0

    min_score = (settings.get("qa") or {}).get("min_score", DEFAULT_MIN_SCORE)
    status = "publiable" if score >= min_score else "quarantaine"
    issues = [f"{c['name']} — {c['detail']}" for c in checks if not c["passed"]]

    logger.info(
        f"QA gate — score {score}/100 → {status.upper()} "
        f"({sum(1 for c in checks if c['passed'])}/{len(checks)} contrôles OK)"
    )
    return {
        "score": score,
        "min_score": min_score,
        "status": status,
        "checks": checks,
        "issues": issues,
        "evaluated_at": datetime.now().isoformat(),
    }


def save_quarantine(result: dict, sector_label: str, reports_dir) -> Optional[Path]:
    """Si le benchmark est en quarantaine, l'archive dans reports/quarantaine/ pour relecture."""
    qa = result.get("_qa") or {}
    if qa.get("status") != "quarantaine":
        return None
    qdir = Path(reports_dir) / "quarantaine"
    qdir.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() else "_" for c in (sector_label or "secteur"))[:40]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = qdir / f"{safe}_{ts}.json"
    try:
        path.write_text(
            json.dumps({"sector": sector_label, "qa": qa, "result": result},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.warning(f"Benchmark en QUARANTAINE → {path.name} (score {qa.get('score')}/100)")
        return path
    except Exception as e:
        logger.warning(f"Impossible d'écrire la quarantaine : {e}")
        return None
