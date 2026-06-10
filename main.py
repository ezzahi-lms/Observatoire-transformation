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


def load_innov_blocs() -> list:
    """Charge les blocs rapports_innovation depuis sectors.yaml."""
    with open(ROOT / "config" / "sectors.yaml", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("rapports_innovation", [])


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


# ── Job Innovation mensuel ────────────────────────────────────────────────────
def run_innovation_pipeline(settings: dict):
    """
    Génère les rapports innovation pour tous les secteurs actifs.
    Appelé le 1er du mois à 07h00 par le scheduler.
    """
    from agent.client_report import generate_all

    mois = datetime.now().strftime("%B %Y").capitalize()
    innov_blocs = load_innov_blocs()
    all_sectors = load_sectors()

    active = [b for b in innov_blocs if b.get("actif", False)]
    if not active:
        logger.info("Innovation : aucun secteur actif configuré.")
        return

    generated_secteurs = []
    for bloc in active:
        sk = bloc.get("secteur_key", "")
        if sk not in all_sectors:
            logger.warning(f"Innovation : secteur_key '{sk}' introuvable dans sectors.yaml")
            continue

        secteur_cfg = dict(all_sectors[sk])
        secteur_cfg["geographie"] = bloc.get("geographie", "Maroc")
        clients = bloc.get("clients", [])

        logger.info(f"Innovation : génération {sk} — {mois} ({len(clients)} clients)")
        try:
            result = generate_all(
                secteur_cfg=secteur_cfg,
                mois=mois,
                settings=settings,
                clients=clients,
            )
            logger.info(f"Innovation {sk} → {result['report_id']} (en attente de validation)")
            generated_secteurs.append(secteur_cfg.get("label", sk))
        except Exception as e:
            logger.exception(f"Innovation {sk} : erreur génération : {e}")

    # Notification manager si au moins un rapport généré
    if generated_secteurs:
        _notify_manager_after_generation(settings, generated_secteurs)


# ── Notification manager post-génération ─────────────────────────────────────
def _notify_manager_after_generation(settings: dict, secteurs: list):
    """Envoie la notification manager après génération — ignore silencieusement si SMTP non configuré."""
    from mailer import send_manager_notification, check_smtp_config

    ok, _ = check_smtp_config()
    if not ok:
        logger.info("Innovation : SMTP non configuré — notification manager ignorée.")
        return

    innov_blocs = load_innov_blocs()
    # Recherche de l'email manager dans sectors.yaml (bloc manager_validation)
    manager_email = None
    manager_nom   = "Manager"
    for bloc in innov_blocs:
        mv = bloc.get("manager_validation", {})
        if mv.get("email"):
            manager_email = mv["email"]
            break

    if not manager_email:
        manager_email = os.environ.get("MANAGER_EMAIL", "")
    if not manager_email:
        logger.warning("Innovation : aucun email manager configuré (manager_validation.email ou MANAGER_EMAIL).")
        return

    try:
        send_manager_notification(
            manager_email=manager_email,
            nb_rapports=len(secteurs),
            secteurs=secteurs,
            manager_nom=manager_nom,
        )
        logger.info(f"Innovation : notification manager envoyée → {manager_email}")
    except Exception as e:
        logger.error(f"Innovation : erreur notification manager : {e}")


# ── Jobs relance J+1 / J+2 ───────────────────────────────────────────────────
def _run_relance(day: int, settings: dict):
    """Envoie les relances pour tous les rapports encore en attente."""
    from agent.client_report import list_pending_reports
    from mailer import send_validation_reminder, check_smtp_config

    ok, _ = check_smtp_config()
    if not ok:
        logger.info(f"Relance J+{day} : SMTP non configuré — ignorée.")
        return

    pending = list_pending_reports()
    if not pending:
        logger.info(f"Relance J+{day} : aucun rapport en attente.")
        return

    innov_blocs = load_innov_blocs()
    manager_email = None
    manager_nom   = "Manager"
    for bloc in innov_blocs:
        mv = bloc.get("manager_validation", {})
        if mv.get("email"):
            manager_email = mv["email"]
            break
    if not manager_email:
        manager_email = os.environ.get("MANAGER_EMAIL", "")
    if not manager_email:
        logger.warning(f"Relance J+{day} : aucun email manager configuré.")
        return

    for rpt in pending:
        rid     = rpt.get("report_id", "")
        secteur = rpt.get("secteur", "")
        try:
            send_validation_reminder(
                report_id=rid,
                manager_email=manager_email,
                day=day,
                secteur=secteur,
                manager_nom=manager_nom,
            )
            logger.info(f"Relance J+{day} envoyée — {rid}")
        except Exception as e:
            logger.error(f"Relance J+{day} erreur {rid} : {e}")


# ── Commande : schedule ────────────────────────────────────────────────────────
def cmd_schedule(args, settings, sectors):
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

    sched_cfg = settings.get("scheduling", {})
    if not sched_cfg.get("enabled", True):
        print("Scheduler désactivé dans settings.yaml.")
        return

    sector_key = args.sector or settings.get("agent", {}).get("default_sector", "pharmaceutique")
    day    = sched_cfg.get("day_of_month", 1)
    hour   = sched_cfg.get("hour", 8)
    minute = sched_cfg.get("minute", 0)

    # Innovation : 1er du mois à 07h00 (configurable)
    innov_cfg  = sched_cfg.get("innovation", {})
    innov_day  = innov_cfg.get("day_of_month", 1)
    innov_hour = innov_cfg.get("hour", 7)
    innov_min  = innov_cfg.get("minute", 0)

    scheduler = BlockingScheduler(timezone="Africa/Casablanca")

    # Job veille sectorielle
    def job_veille():
        logger.info(f"Démarrage automatique — secteur : {sector_key}")
        try:
            run_pipeline(sector_key, settings, sectors)
        except Exception as e:
            logger.exception(f"Erreur lors de l'exécution planifiée : {e}")

    scheduler.add_job(
        job_veille,
        CronTrigger(day=day, hour=hour, minute=minute),
        id="veille_mensuelle",
        name=f"Veille {sector_key}",
        replace_existing=True,
    )

    # Job innovation mensuel
    def job_innovation():
        logger.info("Démarrage automatique — Rapports Innovation")
        run_innovation_pipeline(settings)

    scheduler.add_job(
        job_innovation,
        CronTrigger(day=innov_day, hour=innov_hour, minute=innov_min),
        id="innovation_mensuelle",
        name="Rapports Innovation RH",
        replace_existing=True,
    )

    # Relance J+1 : 2e du mois à 09h00
    scheduler.add_job(
        lambda: _run_relance(1, settings),
        CronTrigger(day=2, hour=9, minute=0),
        id="innovation_relance_j1",
        name="Relance Innovation J+1",
        replace_existing=True,
    )

    # Relance J+2 : 3e du mois à 09h00
    scheduler.add_job(
        lambda: _run_relance(2, settings),
        CronTrigger(day=3, hour=9, minute=0),
        id="innovation_relance_j2",
        name="Relance Innovation J+2",
        replace_existing=True,
    )

    next_veille  = scheduler.get_job("veille_mensuelle").next_run_time
    next_innov   = scheduler.get_job("innovation_mensuelle").next_run_time
    print(f"\nScheduler démarré (Ctrl+C pour arrêter)")
    print(f"  Veille sectorielle  : {sector_key} — le {day} à {hour:02d}h{minute:02d}")
    if next_veille:
        print(f"    Prochaine : {next_veille.strftime('%d/%m/%Y %H:%M')}")
    print(f"  Rapports Innovation : le {innov_day} à {innov_hour:02d}h{innov_min:02d}")
    if next_innov:
        print(f"    Prochaine : {next_innov.strftime('%d/%m/%Y %H:%M')}")
    print(f"  Relances validation : J+1 le 2 à 09h00, J+2 le 3 à 09h00")
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
