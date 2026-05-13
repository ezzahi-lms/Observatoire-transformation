"""
Diagnostic des sources de collecte — teste chaque flux RSS en live.
Usage : python check_sources.py [--sector pharma_maroc]
"""
import sys, io, yaml, time, argparse
from pathlib import Path
from datetime import datetime, timezone

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

try:
    import feedparser
except ImportError:
    print("feedparser manquant — pip install feedparser")
    sys.exit(1)

try:
    import requests
except ImportError:
    requests = None

ROOT    = Path(__file__).parent
TIMEOUT = 10  # secondes par flux

# ── Palette texte ──────────────────────────────────────────────────────────────
def grn(t): return f"\033[92m{t}\033[0m"
def yel(t): return f"\033[93m{t}\033[0m"
def red(t): return f"\033[91m{t}\033[0m"
def blu(t): return f"\033[94m{t}\033[0m"
def bld(t): return f"\033[1m{t}\033[0m"


def age_label(entry):
    """Retourne l'âge du dernier article en mois, ou '?' si inconnu."""
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                dt = datetime(*t[:6], tzinfo=timezone.utc)
                months = (datetime.now(timezone.utc) - dt).days // 30
                return months
            except Exception:
                pass
    return None


def extract_url(feed_entry):
    """Accepte une string URL ou un dict {url, name}."""
    if isinstance(feed_entry, dict):
        return feed_entry.get("url", ""), feed_entry.get("name", "")
    return str(feed_entry), ""


def test_feed(feed_entry):
    """
    Retourne un dict :
      ok      : bool
      url     : str
      name    : str
      entries : int   (nb articles)
      latest  : int|None  (âge en mois du dernier article)
      error   : str   (message si échec)
    """
    url, name = extract_url(feed_entry)
    if not url:
        return {"ok": False, "url": "", "name": name, "entries": 0,
                "latest": None, "error": "URL manquante"}
    try:
        feed = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0"})
        if feed.bozo and not feed.entries:
            return {"ok": False, "url": url, "name": name, "entries": 0,
                    "latest": None, "error": str(feed.bozo_exception)[:80]}
        n = len(feed.entries)
        latest = age_label(feed.entries[0]) if feed.entries else None
        return {"ok": True, "url": url, "name": name, "entries": n,
                "latest": latest, "error": ""}
    except Exception as e:
        return {"ok": False, "url": url, "name": name, "entries": 0,
                "latest": None, "error": str(e)[:80]}


def render_feed_line(res):
    name_str = f" ({res['name']})" if res.get("name") else ""
    if res["ok"]:
        n = res["entries"]
        m = res["latest"]
        age_str = f", dernier : {m} mois" if m is not None else ""
        freshness = ""
        if m is not None:
            if m <= 3:    freshness = grn(" [frais]")
            elif m <= 12: freshness = yel(" [acceptable]")
            else:         freshness = red(f" [ancien : {m} mois]")
        status = grn(f"[OK] {n} articles{age_str}")
        return f"  {status}{freshness}  {name_str}\n       {res['url']}"
    else:
        return f"  {red('[XX]')} {res['error']}  {name_str}\n       {res['url']}"


def audit_sector_sources(key, cfg):
    feeds   = cfg.get("rss_feeds", [])
    queries = cfg.get("search_queries", [])

    print(f"\n{bld(blu('['+ key +']'))}  {cfg.get('label', key)}")
    print(f"  {len(feeds)} flux RSS  |  {len(queries)} requêtes DuckDuckGo\n")

    # ── Flux RSS ──────────────────────────────────────────────────────────────
    ok_count = 0
    stale_count = 0
    fail_count = 0

    for feed_entry in feeds:
        res = test_feed(feed_entry)
        print(render_feed_line(res))
        if res["ok"]:
            if res["latest"] is not None and res["latest"] > 12:
                stale_count += 1
            else:
                ok_count += 1
        else:
            fail_count += 1
        time.sleep(0.3)   # politesse serveurs

    # ── Requêtes DuckDuckGo (affichage seul, pas d'exécution) ────────────────
    print(f"\n  {bld('Requêtes de recherche configurées :')}")
    for i, q in enumerate(queries, 1):
        print(f"    {i:2}. {q}")

    # ── Résumé secteur ────────────────────────────────────────────────────────
    total = len(feeds)
    print()
    if fail_count == 0 and stale_count == 0:
        print(f"  {grn('[OK]')} Toutes les sources actives et fraîches.")
    else:
        if fail_count:
            print(f"  {red('[XX]')} {fail_count}/{total} flux inaccessibles — à remplacer.")
        if stale_count:
            print(f"  {yel('[??]')} {stale_count}/{total} flux anciens (>12 mois) — à vérifier.")
    print("  " + "─" * 56)

    return ok_count, stale_count, fail_count, total


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sector", help="Tester un seul secteur (ex: pharma_maroc)")
    args = parser.parse_args()

    cfg_path = ROOT / "config" / "sectors.yaml"
    with open(cfg_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    sectors = data.get("sectors", {})

    if args.sector:
        if args.sector not in sectors:
            print(red(f"Secteur inconnu : {args.sector}"))
            print(f"Secteurs disponibles : {', '.join(sectors.keys())}")
            sys.exit(1)
        sectors = {args.sector: sectors[args.sector]}

    print()
    print("=" * 62)
    print("  DIAGNOSTIC DES SOURCES — Observatoire LMS ORH")
    print(f"  {len(sectors)} secteur(s) — test RSS en live")
    print("=" * 62)

    g_ok = g_stale = g_fail = g_total = 0
    for key, cfg in sectors.items():
        ok, stale, fail, total = audit_sector_sources(key, cfg)
        g_ok += ok; g_stale += stale; g_fail += fail; g_total += total

    print()
    print("=" * 62)
    print(f"  BILAN GLOBAL : {g_total} flux testés")
    print(f"    {grn(f'{g_ok} OK')}  |  {yel(f'{g_stale} anciens')}  |  {red(f'{g_fail} inaccessibles')}")
    if g_fail == 0:
        print(grn("  Toutes les sources répondent."))
    else:
        print(red(f"  {g_fail} flux à remplacer dans config/sectors.yaml."))
    print("=" * 62)
    print()


if __name__ == "__main__":
    main()
