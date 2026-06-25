"""
Collecte d'articles depuis RSS feeds et DuckDuckGo.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
import feedparser
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)


def _parse_rss_date(entry) -> datetime | None:
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            return datetime(*entry.published_parsed[:6])
        except Exception:
            pass
    return None


def collect_rss(sector_config: Dict, days_back: int = 35) -> List[Dict[str, Any]]:
    """Collecte les articles depuis les flux RSS du secteur."""
    articles = []
    cutoff = datetime.now() - timedelta(days=days_back)
    feeds = sector_config.get("rss_feeds", [])

    for feed_info in feeds:
        url = feed_info.get("url", "")
        source_name = feed_info.get("name", url)
        try:
            feed = feedparser.parse(url)
            count = 0
            for entry in feed.entries:
                pub_date = _parse_rss_date(entry)
                if pub_date and pub_date < cutoff:
                    continue
                title = entry.get("title", "").strip()
                summary = entry.get("summary", entry.get("description", "")).strip()
                if not title:
                    continue
                articles.append({
                    "title": title,
                    "summary": summary[:800] if summary else "",
                    "url": entry.get("link", ""),
                    "source": source_name,
                    "date": pub_date.strftime("%Y-%m-%d") if pub_date else "N/A",
                    "type": "rss",
                })
                count += 1
            logger.info(f"RSS [{source_name}] : {count} articles collectés")
        except Exception as e:
            logger.warning(f"Impossible de lire le flux RSS {url} : {e}")

    return articles


def collect_web(sector_config: Dict, max_per_query: int = 8) -> List[Dict[str, Any]]:
    """Collecte des résultats web via DuckDuckGo."""
    articles = []
    queries = sector_config.get("search_queries", [])
    seen_urls = set()

    for query in queries:
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_per_query, region="fr-fr"))
            for r in results:
                url = r.get("href", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                articles.append({
                    "title": r.get("title", "").strip(),
                    "summary": r.get("body", "").strip()[:800],
                    "url": url,
                    "source": "Web Search",
                    "date": "N/A",
                    "type": "web",
                })
            logger.info(f"Web [{query[:50]}...] : {len(results)} résultats")
        except Exception as e:
            logger.warning(f"Erreur recherche web '{query[:40]}' : {e}")

    return articles


def collect(sector_config: Dict, settings: Dict) -> List[Dict[str, Any]]:
    """Point d'entrée principal : collecte RSS + web + rapports PDF web + PDFs magazines."""
    days_back = settings.get("collection", {}).get("days_back", 35)
    max_search = settings.get("collection", {}).get("max_search_results", 8)
    max_total = settings.get("collection", {}).get("max_articles_total", 60)

    logger.info("Collecte RSS...")
    rss_articles = collect_rss(sector_config, days_back=days_back)

    logger.info("Collecte web (articles)...")
    web_articles = collect_web(sector_config, max_per_query=max_search)

    # Collecte de rapports PDF depuis le web (études, whitepapers, benchmarks)
    web_report_articles: List[Dict[str, Any]] = []
    try:
        from agent.web_pdf_collector import collect_web_reports
        logger.info("Collecte rapports PDF web...")
        web_report_articles = collect_web_reports(sector_config, settings, max_reports=6)
    except Exception as e:
        logger.warning(f"Collecte rapports PDF web ignorée : {e}")

    # Collecte PDFs magazines si dossier configuré (usage local)
    pdf_articles: List[Dict[str, Any]] = []
    if settings.get("collection", {}).get("magazines_dir") or __import__("os").environ.get("MAGAZINES_DIR"):
        logger.info("Collecte PDFs magazines...")
        try:
            from agent.pdf_collector import collect_pdfs
            pdf_articles = collect_pdfs(sector_config, settings)
        except Exception as e:
            logger.warning(f"Collecte PDFs magazines ignorée : {e}")

    all_articles = rss_articles + web_articles + web_report_articles + pdf_articles

    # Dédupliquer par URL/chemin
    seen = set()
    unique = []
    for a in all_articles:
        key = a["url"] or a["title"]
        if key not in seen:
            seen.add(key)
            unique.append(a)

    # Tronquer au maximum configuré
    if len(unique) > max_total:
        unique = unique[:max_total]
        logger.info(f"Articles tronqués à {max_total}")

    logger.info(
        f"Total collectés : {len(unique)} "
        f"(RSS: {len(rss_articles)}, Web: {len(web_articles)}, "
        f"Rapports PDF: {len(web_report_articles)}, Magazines: {len(pdf_articles)})"
    )
    return unique
