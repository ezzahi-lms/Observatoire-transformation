"""
Diagnostic des agents sectoriels — vérifie la complétude de chaque secteur.
Usage : python check_agents.py
"""
import yaml
from pathlib import Path

ROOT = Path(__file__).parent
AXES_CLIENTS = ["Dimensionnement", "Gouvernance", "Externalisation", "SI"]
AFRIQUE_MOTS = ["afrique", "maroc", "mena", "maghreb", "africain", "marocain"]

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Couleurs terminal
OK   = "\033[92m[OK]\033[0m "
WARN = "\033[93m[??]\033[0m "
ERR  = "\033[91m[XX]\033[0m "

def check(condition, label_ok, label_fail, level="err"):
    icon = OK if condition else (WARN if level == "warn" else ERR)
    msg  = label_ok if condition else label_fail
    return condition, f"  {icon}  {msg}"

def audit_sector(key, cfg):
    lines  = []
    score  = 0
    total  = 0

    checks = [
        check(bool(cfg.get("label")),
              f"label : {cfg.get('label', '?')}",
              "label manquant"),

        check(len(cfg.get("search_queries", [])) >= 8,
              f"{len(cfg.get('search_queries', []))} requêtes de recherche",
              f"requêtes insuffisantes ({len(cfg.get('search_queries', []))} < 8)"),

        check(len(cfg.get("rss_feeds", [])) >= 3,
              f"{len(cfg.get('rss_feeds', []))} flux RSS",
              f"flux RSS insuffisants ({len(cfg.get('rss_feeds', []))} < 3)"),

        check(len(cfg.get("benchmark_axes", [])) >= 6,
              f"{len(cfg.get('benchmark_axes', []))} axes benchmark",
              f"axes benchmark insuffisants ({len(cfg.get('benchmark_axes', []))} < 6)"),

        check(bool(cfg.get("context_note")),
              "context_note défini",
              "context_note manquant"),

        check(any(m in cfg.get("context_note", "").lower() for m in AFRIQUE_MOTS),
              "dimension Afrique/MENA dans le contexte",
              "dimension Afrique/MENA absente du contexte",
              level="warn"),
    ]

    # Vérification 4 axes clients dans benchmark_axes
    axes_text = " ".join(cfg.get("benchmark_axes", [])).lower()
    for axe in AXES_CLIENTS:
        ok = axe.lower() in axes_text
        checks.append(check(ok,
              f"axe client '{axe}' couvert",
              f"axe client '{axe}' non couvert",
              level="warn"))

    for ok, line in checks:
        lines.append(line)
        total += 1
        if ok:
            score += 1

    return score, total, lines


def main():
    cfg_path = ROOT / "config" / "sectors.yaml"
    with open(cfg_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    sectors = data.get("sectors", {})
    print()
    print("=" * 62)
    print("  DIAGNOSTIC DES AGENTS SECTORIELS — Observatoire LMS ORH")
    print("=" * 62)

    global_score = 0
    global_total = 0

    for key, cfg in sectors.items():
        score, total, lines = audit_sector(key, cfg)
        pct = round(score / total * 100) if total else 0
        status = OK if pct == 100 else (WARN if pct >= 70 else ERR)
        print(f"\n{status}  [{key}]  {cfg.get('label', key)}  —  {score}/{total} critères ({pct}%)")
        for line in lines:
            print(line)
        global_score += score
        global_total += total

    pct_global = round(global_score / global_total * 100) if global_total else 0
    print()
    print("=" * 62)
    print(f"  SCORE GLOBAL : {global_score}/{global_total} ({pct_global}%)")
    if pct_global == 100:
        print("  [OK] Tous les agents sont complets.")
    elif pct_global >= 75:
        print("  [??] Quelques axes a completer (voir [??] ci-dessus).")
    else:
        print("  [XX] Plusieurs agents incomplets - corriger avant analyse.")
    print("=" * 62)
    print()


if __name__ == "__main__":
    main()
