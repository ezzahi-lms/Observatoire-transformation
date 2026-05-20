"""
Agent de Veille Stratégique — Observatoire de la Transformation Organisationnelle

Usage :
  python main.py run [--sector pharma]   # Lancer une analyse immédiatement
  python main.py schedule                # Démarrer le scheduler mensuel
  python main.py list                    # Lister les rapports générés
  python main.py sectors                 # Afficher les secteurs disponibles
"""
import argparse
import logging
import os
import sys

# Forcer UTF-8 sur la console Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv, dotenv_values

# ── Chargement de l'environnement ──────────────────────────────────────────────
ROOT = Path(__file__).parent

# Charger le .env et injecter manuellement dans os.environ (contourne les
# problèmes d'encodage de load_dotenv sur certains systèmes Windows)
_env_path = ROOT / ".env"
if _env_path.exists():
    for _k, _v in dotenv_values(_env_path, encoding="utf-8").items():
        if _v is not None and _k not in os.environ:
            os.environ[_k] = _v
load_dotenv(_env_path, encoding="utf-8", override=False)

# ── Configuration du logging ───────────────────────────────────────────────────
def _setup_logging(settings: dict):
    log_file = ROOT / settings.get("logging", {}).get("file", "reports/agent.log")
    log_file.parent.mkdir(parents=True, exist_ok=True)
    level = getattr(logging, settings.get("logging", {}).get("level", "INFO"))
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )

logger = logging.getLogger(__name__)


# ── Chargement des configs ─────────────────────────────────────────────────────
def load_settings() -> dict:
    with open(ROOT / "config" / "settings.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_sectors() -> dict:
    with open(ROOT / "config" / "sectors.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f).get("sectors", {})


# ── Pipeline principal ─────────────────────────────────────────────────────────
def run_pipeline(sector_key: str, settings: dict, sectors: dict) -> list[str]:
    """Exécute le pipeline complet : collecte → analyse → rapport."""
    from agent import collector, analyzer, reporter

    if sector_key not in sectors:
        available = ", ".join(sectors.keys())
        raise ValueError(f"Secteur '{sector_key}' introuvable. Disponibles : {available}")

    sector_config = {**sectors[sector_key], "key": sector_key}
    sector_label = sector_config.get("label", sector_key)

    print(f"\n{'='*60}")
    print(f"  VEILLE STRATÉGIQUE — {sector_label.upper()}")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"{'='*60}\n")

    # ── Étape 1 : Collecte ──
    print("[ 1/3 ] Collecte des sources...")
    articles = collector.collect(sector_config, settings)
    print(f"        → {len(articles)} articles collectés\n")

    if not articles:
        logger.warning("Aucun article collecté. Vérifiez votre connexion et les sources configurées.")
        return []

    # ── Étape 2 : Analyse ──
    print("[ 2/3 ] Analyse avec Claude...")
    analysis = analyzer.analyze(sector_config, articles, settings)
    nb_fcs   = len(analysis.get("facteurs_cles_succes", []))
    nb_signaux = len(analysis.get("signaux_faibles", []))
    nb_recs  = len(analysis.get("recommandations", []))
    nb_src   = len(analysis.get("index_sources", []))
    print(f"        → {nb_fcs} FCS · {nb_signaux} signaux · {nb_recs} recommandations · {nb_src} sources citées\n")

    # ── Étape 3 : Rapport ──
    print("[ 3/3 ] Génération des rapports...")
    files = reporter.generate_reports(analysis, settings, str(ROOT))
    for f in files:
        print(f"        → {f}")

    print(f"\n  Analyse terminée avec succès.")
    print(f"{'='*60}\n")
    return files


# ── Commande : run ─────────────────────────────────────────────────────────────
def cmd_run(args, settings, sectors):
    sector_key = args.sector or settings.get("agent", {}).get("default_sector", "pharmaceutique")
    try:
        run_pipeline(sector_key, settings, sectors)
    except ValueError as e:
        print(f"\nERREUR : {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Erreur pipeline : {e}")
        sys.exit(1)


# ── Commande : schedule ────────────────────────────────────────────────────────
def cmd_schedule(args, settings, sectors):
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

    sched_cfg = settings.get("scheduling", {})
    if not sched_cfg.get("enabled", True):
        print("Scheduler désactivé dans settings.yaml.")
        return

    sector_key = args.sector or settings.get("agent", {}).get("default_sector", "pharmaceutique")
    day = sched_cfg.get("day_of_month", 1)
    hour = sched_cfg.get("hour", 8)
    minute = sched_cfg.get("minute", 0)

    scheduler = BlockingScheduler(timezone="Europe/Paris")

    def job():
        logger.info(f"Démarrage automatique — secteur : {sector_key}")
        try:
            run_pipeline(sector_key, settings, sectors)
        except Exception as e:
            logger.exception(f"Erreur lors de l'exécution planifiée : {e}")

    scheduler.add_job(
        job,
        CronTrigger(day=day, hour=hour, minute=minute),
        id="veille_mensuelle",
        name=f"Veille {sector_key}",
        replace_existing=True,
    )

    next_run = scheduler.get_job("veille_mensuelle").next_run_time
    print(f"\nScheduler démarré (Ctrl+C pour arrêter)")
    print(f"  Secteur    : {sector_key}")
    print(f"  Fréquence  : le {day} de chaque mois à {hour:02d}h{minute:02d}")
    if next_run:
        print(f"  Prochaine  : {next_run.strftime('%d/%m/%Y %H:%M')}")
    print()

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("\nScheduler arrêté.")


# ── Commande : list ────────────────────────────────────────────────────────────
def cmd_list(args, settings, sectors):
    output_dir = ROOT / settings.get("reporting", {}).get("output_dir", "reports")
    if not output_dir.exists():
        print("Aucun rapport généré.")
        return

    files = sorted(
        [f for f in output_dir.iterdir() if f.suffix in (".docx", ".html", ".pdf")],
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )

    if not files:
        print("Aucun rapport trouvé dans", output_dir)
        return

    print(f"\nRapports générés ({len(files)}) :")
    for f in files:
        mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%d/%m/%Y %H:%M")
        size_kb = f.stat().st_size // 1024
        print(f"  [{mtime}]  {f.name}  ({size_kb} KB)")
    print()


# ── Commande : sectors ─────────────────────────────────────────────────────────
def cmd_sectors(args, settings, sectors):
    default = settings.get("agent", {}).get("default_sector", "")
    print("\nSecteurs disponibles :")
    for key, cfg in sectors.items():
        marker = " (défaut)" if key == default else ""
        feeds = len(cfg.get("rss_feeds", []))
        queries = len(cfg.get("search_queries", []))
        print(f"  {key:<20}  {cfg.get('label', '')}{marker}")
        print(f"                       {feeds} flux RSS · {queries} requêtes web")
    print()


# ── CLI ────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        prog="veille",
        description="Agent de veille stratégique — Transformation Organisationnelle",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Exemples :
  python main.py run                        # Secteur par défaut (pharmaceutique)
  python main.py run --sector banque_finance
  python main.py schedule                   # Scheduler mensuel
  python main.py list                       # Lister les rapports
  python main.py sectors                    # Secteurs disponibles""",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # run
    p_run = sub.add_parser("run", help="Lancer une analyse immédiatement")
    p_run.add_argument("--sector", "-s", help="Clé du secteur (ex: pharmaceutique)")

    # schedule
    p_sched = sub.add_parser("schedule", help="Démarrer le scheduler mensuel")
    p_sched.add_argument("--sector", "-s", help="Clé du secteur à surveiller")

    # list
    sub.add_parser("list", help="Lister les rapports générés")

    # sectors
    sub.add_parser("sectors", help="Afficher les secteurs disponibles")

    args = parser.parse_args()

    settings = load_settings()
    _setup_logging(settings)
    sectors = load_sectors()

    dispatch = {
        "run": cmd_run,
        "schedule": cmd_schedule,
        "list": cmd_list,
        "sectors": cmd_sectors,
    }
    dispatch[args.command](args, settings, sectors)


if __name__ == "__main__":
    main()
