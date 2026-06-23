"""
feedback_log.py — Journal de feedback à friction zéro (inspiré de la V2 de Zidane).

L'équipe tague chaque livrable en une seconde : OK / mitigé / à jeter, sans
champ libre obligatoire. Les tags alimentent une rétrospective hebdomadaire.

100 % code (aucun appel LLM, aucun coût token). Stockage : un fichier JSONL
append-only sous reports/feedback/feedback_log.jsonl.
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

TAGS = ("ok", "mitige", "jeter")
_LABELS = {"ok": "👍 OK", "mitige": "😐 Mitigé", "jeter": "🗑️ À jeter"}


def _log_path(reports_dir) -> Path:
    d = Path(reports_dir) / "feedback"
    d.mkdir(parents=True, exist_ok=True)
    return d / "feedback_log.jsonl"


def log_feedback(reports_dir, item_id: str, tag: str,
                 sector: str = "", livrable: str = "", note: str = "") -> Dict:
    """Enregistre un tag de feedback. tag ∈ {ok, mitige, jeter}. note optionnelle."""
    tag = (tag or "").lower().strip()
    if tag not in TAGS:
        raise ValueError(f"tag invalide '{tag}' — attendu {TAGS}")
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "item_id": item_id,
        "tag": tag,
        "sector": sector,
        "livrable": livrable,
        "note": note,
    }
    path = _log_path(reports_dir)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    logger.info(f"Feedback enregistré : {item_id} → {tag}")
    return entry


def _read_all(reports_dir) -> List[Dict]:
    path = _log_path(reports_dir)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def weekly_summary(reports_dir, since_days: int = 7,
                   now_iso: Optional[str] = None) -> Dict:
    """Agrège les tags des `since_days` derniers jours (matériau de la rétro hebdo).

    now_iso : horodatage de référence ISO (passé explicitement pour rester
    déterministe / testable). Si None, utilise l'instant courant.
    """
    rows = _read_all(reports_dir)
    ref = datetime.fromisoformat(now_iso) if now_iso else datetime.now()
    cutoff = ref - timedelta(days=since_days)

    recent = []
    for r in rows:
        try:
            if datetime.fromisoformat(r["ts"]) >= cutoff:
                recent.append(r)
        except Exception:
            continue

    counts = {t: sum(1 for r in recent if r.get("tag") == t) for t in TAGS}
    total = len(recent)
    by_sector: Dict[str, Dict[str, int]] = {}
    for r in recent:
        s = r.get("sector") or "—"
        by_sector.setdefault(s, {t: 0 for t in TAGS})
        if r.get("tag") in TAGS:
            by_sector[s][r["tag"]] += 1

    pct_utile = round((counts["ok"] / total) * 100) if total else 0
    return {
        "since_days": since_days,
        "total": total,
        "counts": counts,
        "pct_utile": pct_utile,          # part de tags "OK" (proxy de l'utilité perçue)
        "by_sector": by_sector,
        "a_jeter": [r for r in recent if r.get("tag") == "jeter"],  # à inspecter en priorité en rétro
    }


def render_summary_md(summary: Dict) -> str:
    """Rend l'agrégat hebdo en Markdown pour la rétrospective."""
    c = summary["counts"]
    out = [
        f"# Rétro feedback — {summary['since_days']} derniers jours",
        "",
        f"**{summary['total']} retours** · {_LABELS['ok']} {c['ok']} · "
        f"{_LABELS['mitige']} {c['mitige']} · {_LABELS['jeter']} {c['jeter']} "
        f"· **{summary['pct_utile']}% jugés utiles**",
        "",
    ]
    if summary["by_sector"]:
        out.append("## Par secteur")
        for s, cc in summary["by_sector"].items():
            out.append(f"- **{s}** : 👍 {cc['ok']} · 😐 {cc['mitige']} · 🗑️ {cc['jeter']}")
    return "\n".join(out)
