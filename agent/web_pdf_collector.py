"""
Collecte de rapports et documents PDF disponibles sur le web.

Complément au collecteur d'articles (RSS + DuckDuckGo texte).
Stratégie :
  1. Recherches DuckDuckGo ciblées "rapport PDF / étude benchmark"
  2. Filtrage des URLs .pdf ou provenant de sources reconnues (ILO, OCDE, BCG…)
  3. Téléchargement + extraction texte (fitz → pdfplumber en fallback)
"""
import io
import logging
from typing import List, Dict, Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Sources reconnues pour des rapports de qualité (RH, organisation, business)
_REPORT_DOMAINS = {
    # Internationaux
    "ilo.org", "oecd.org", "worldbank.org", "ifc.org",
    "mckinsey.com", "bcg.com", "deloitte.com", "pwc.com",
    "kpmg.com", "ey.com", "accenture.com", "capgemini.com",
    "mercer.com", "hay.com", "hbr.org", "gartner.com",
    "shrm.org", "weforum.org",
    # France
    "andrh.fr", "anact.fr", "apec.fr",
    "dares.travail-emploi.gouv.fr", "travail-emploi.gouv.fr",
    "hcp.ma", "ammc.ma", "bank-al-maghrib.ma",
    "cgem.ma", "ompic.ma",
}

# Suffixes de requêtes pour trouver des rapports (appliqués aux queries secteur)
_REPORT_SUFFIXES = [
    "rapport étude PDF 2024 2025",
    "benchmark rapport annuel 2024",
]

_MAX_PDF_BYTES = 10 * 1024 * 1024   # 10 MB — taille max téléchargée
_MAX_TEXT_CHARS = 4000               # Caractères extraits par PDF
_MAX_PDF_PAGES = 6                   # Pages extraites max


def _is_pdf_url(url: str) -> bool:
    """Vrai si l'URL pointe explicitement vers un fichier .pdf."""
    path = urlparse(url).path.lower()
    return path.endswith(".pdf") or "/pdf/" in path or "%2fpdf%2f" in path.lower()


def _from_report_domain(url: str) -> bool:
    """Vrai si le domaine est une source reconnue de rapports."""
    domain = urlparse(url).netloc.lower().lstrip("www.")
    return any(domain == d or domain.endswith("." + d) for d in _REPORT_DOMAINS)


def _extract_pdf_bytes(content: bytes) -> str | None:
    """Extrait le texte d'un PDF depuis ses bytes. Fitz prioritaire, pdfplumber en fallback."""
    # ── fitz (PyMuPDF) ────────────────────────────────────────────────────────
    try:
        import fitz
        doc = fitz.open(stream=content, filetype="pdf")
        parts = []
        for i, page in enumerate(doc):
            if i >= _MAX_PDF_PAGES:
                break
            parts.append(page.get_text())
        doc.close()
        text = "\n".join(parts)
        if len(text.strip()) > 150:
            return text[:_MAX_TEXT_CHARS]
    except Exception:
        pass

    # ── pdfplumber ────────────────────────────────────────────────────────────
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            parts = []
            for i, page in enumerate(pdf.pages):
                if i >= _MAX_PDF_PAGES:
                    break
                t = page.extract_text() or ""
                parts.append(t)
            text = "\n".join(parts)
            if len(text.strip()) > 150:
                return text[:_MAX_TEXT_CHARS]
    except Exception:
        pass

    return None


def _fetch_pdf(url: str, timeout: int = 15) -> str | None:
    """Télécharge un PDF depuis une URL et retourne son texte extrait."""
    try:
        import requests
        resp = requests.get(
            url, timeout=timeout, stream=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; LMS-Veille/1.0)"},
            allow_redirects=True,
        )
        if resp.status_code != 200:
            return None

        content_type = resp.headers.get("Content-Type", "").lower()
        is_pdf_ct = "pdf" in content_type or "octet-stream" in content_type
        if not is_pdf_ct and not _is_pdf_url(url):
            return None

        # Lecture limitée
        chunks = []
        total = 0
        for chunk in resp.iter_content(chunk_size=65_536):
            total += len(chunk)
            if total > _MAX_PDF_BYTES:
                logger.debug(f"PDF trop volumineux ({url[:60]}), skip")
                return None
            chunks.append(chunk)

        content = b"".join(chunks)
        if len(content) < 1024:
            return None

        return _extract_pdf_bytes(content)

    except Exception as e:
        logger.debug(f"Fetch PDF échoué {url[:60]}: {e}")
        return None


def collect_web_reports(sector_config: Dict, settings: Dict,
                         max_reports: int = 6) -> List[Dict[str, Any]]:
    """
    Collecte des rapports et études PDF depuis le web.

    Fonctionne en 2 passes :
      - Requêtes DuckDuckGo "rapport PDF" sur les thèmes du secteur
      - Filtrage des résultats sur les URLs .pdf et domaines reconnus
      - Téléchargement + extraction texte pour les candidats retenus

    Args:
        sector_config : config du secteur (label, search_queries, …)
        settings      : settings.yaml
        max_reports   : nombre maximum de rapports à retourner

    Returns:
        Liste de dicts compatibles avec collector.collect()
        {title, summary, url, source, date, type="web_report"}
    """
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS

    sector_label = sector_config.get("label", "")
    base_queries = sector_config.get("search_queries", [])[:3]

    # Construire les requêtes ciblées "rapport PDF"
    report_queries: List[str] = []
    for bq in base_queries:
        topic = bq[:50].rstrip()
        for suffix in _REPORT_SUFFIXES:
            report_queries.append(f"{topic} {suffix}")

    # Requête générique secteur
    if sector_label:
        report_queries.append(
            f"benchmark {sector_label} organisation RH rapport PDF Maroc 2024 2025"
        )

    collected: List[Dict[str, Any]] = []
    seen_urls: set = set()

    for query in report_queries[:6]:
        if len(collected) >= max_reports:
            break
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=8, region="fr-fr"))

            for r in results:
                if len(collected) >= max_reports:
                    break
                url = r.get("href", "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)

                # Sélectionner si URL .pdf OU domaine rapport reconnu
                if not _is_pdf_url(url) and not _from_report_domain(url):
                    continue

                text = _fetch_pdf(url)
                if not text or len(text.strip()) < 200:
                    continue

                domain = urlparse(url).netloc.lstrip("www.")
                collected.append({
                    "title": r.get("title", "").strip(),
                    "summary": text,
                    "url": url,
                    "source": f"Rapport — {domain}",
                    "date": "N/A",
                    "type": "web_report",
                })
                logger.info(f"Rapport PDF collecté : {url[:80]}")

        except Exception as e:
            logger.warning(f"Erreur collecte rapports '{query[:45]}': {e}")

    logger.info(f"Rapports PDF web : {len(collected)} collectés")
    return collected
