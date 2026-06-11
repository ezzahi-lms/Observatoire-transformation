"""
pdf_collector.py — Extraction de texte depuis le dossier Magazines (PDFs presse).

Supporte le français, l'anglais, l'italien, l'arabe et l'espagnol.
Utilise pymupdf (fitz) en priorité, pdfplumber en fallback.

Intégration : appelé depuis collector.collect() si magazines_dir est configuré.
"""
import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Mois FR/IT/ES/AR pour parsing de dates dans les noms de fichiers
_MOIS_MAP = {
    # Français
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "août": 8, "aout": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12,
    # Anglais
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    # Italien
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4,
    "maggio": 5, "giugno": 6, "luglio": 7, "agosto": 8,
    "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
    # Espagnol
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}

# Mots-clés RH/Orga toujours pertinents pour le filtre de pertinence
_BASE_KEYWORDS = {
    "rh", "hr", "ressources humaines", "human resources", "organisation", "organization",
    "transformation", "management", "leadership", "talent", "compétence", "competence",
    "digital", "numérique", "innovation", "formation", "recrutement", "emploi",
    "travail", "work", "entreprise", "company", "dirigeant", "stratégie", "strategy",
    "performance", "gouvernance", "governance", "culture", "diversité", "diversity",
    "ia", "ai", "intelligence artificielle", "artificial intelligence",
    "risorse umane", "lavoro", "azienda",   # IT
    "recursos humanos", "empresa", "trabajo", # ES
}


# ─────────────────────────────────────────────────────────────────────────────
#  EXTRACTION DE TEXTE
# ─────────────────────────────────────────────────────────────────────────────

def _extract_text_fitz(pdf_path: Path, max_chars: int) -> str:
    """Extraction via pymupdf — meilleure gestion arabe/RTL et langues latines."""
    import fitz  # type: ignore
    text_parts = []
    total = 0
    with fitz.open(str(pdf_path)) as doc:
        for page_num, page in enumerate(doc):
            if total >= max_chars:
                break
            # Extraire avec préservation de l'ordre de lecture
            text = page.get_text("text", flags=fitz.TEXT_PRESERVE_WHITESPACE)
            if text:
                chunk = text[:max_chars - total]
                text_parts.append(chunk)
                total += len(chunk)
            if page_num >= 4:  # max 5 pages
                break
    return "\n".join(text_parts).strip()


def _extract_text_pdfplumber(pdf_path: Path, max_chars: int) -> str:
    """Fallback via pdfplumber."""
    import pdfplumber  # type: ignore
    text_parts = []
    total = 0
    with pdfplumber.open(str(pdf_path)) as pdf:
        for i, page in enumerate(pdf.pages):
            if total >= max_chars or i >= 5:
                break
            text = page.extract_text() or ""
            chunk = text[:max_chars - total]
            text_parts.append(chunk)
            total += len(chunk)
    return "\n".join(text_parts).strip()


def _extract_text(pdf_path: Path, max_chars: int = 3000) -> str:
    """Essaie fitz, puis pdfplumber, puis retourne chaîne vide."""
    try:
        return _extract_text_fitz(pdf_path, max_chars)
    except ImportError:
        logger.debug("pymupdf non disponible, tentative pdfplumber")
    except Exception as e:
        logger.debug(f"fitz erreur sur {pdf_path.name}: {e}")

    try:
        return _extract_text_pdfplumber(pdf_path, max_chars)
    except ImportError:
        logger.warning("Ni pymupdf ni pdfplumber installé — pip install pymupdf")
    except Exception as e:
        logger.warning(f"pdfplumber erreur sur {pdf_path.name}: {e}")

    return ""


# ─────────────────────────────────────────────────────────────────────────────
#  PARSING DATE DEPUIS LE NOM DE FICHIER
# ─────────────────────────────────────────────────────────────────────────────

def _parse_date_from_filename(name: str) -> Optional[str]:
    """
    Tente de déduire la date de publication depuis le nom de fichier.
    Formats reconnus :
      01-06-26-xxx   → 2026-06-01
      01-06-2026     → 2026-06-01
      05-2026        → 2026-05-01
      28 Mai 2026    → 2026-05-28
      Juin 2026      → 2026-06-01
    Retourne une chaîne ISO 'YYYY-MM-DD' ou None.
    """
    # Conserver les séparateurs originaux pour les patterns numériques
    raw = name.lower()
    # Version normalisée (underscores→espaces) pour les patterns texte
    clean = raw.replace("_", " ").replace("•", " ").replace("·", " ")

    # Format JJ-MM-AA ou JJ-MM-AAAA en début (séparateur - ou .)
    m = re.match(r"^(\d{2})[.\-](\d{2})[.\-](\d{2,4})", raw)
    if m:
        d, mo, y = m.group(1), m.group(2), m.group(3)
        y = "20" + y if len(y) == 2 else y
        try:
            return datetime(int(y), int(mo), int(d)).strftime("%Y-%m-%d")
        except ValueError:
            pass

    # Format JJ Mois AAAA (ex: "28 Mai 2026", "1 giugno 2026")
    # Lookbehind pour éviter "N417 Juin" → 17 Juin (faux positif)
    for mois_str, mois_num in _MOIS_MAP.items():
        m = re.search(rf"(?<![a-z0-9])(\d{{1,2}})\s+{mois_str}\s+(\d{{4}})", clean)
        if m:
            d, y = int(m.group(1)), int(m.group(2))
            try:
                return datetime(y, mois_num, d).strftime("%Y-%m-%d")
            except ValueError:
                pass

    # Format Mois AAAA seul (ex: "Juin 2026", "giugno 2026")
    for mois_str, mois_num in _MOIS_MAP.items():
        m = re.search(rf"{mois_str}\s+(\d{{4}})", clean)
        if m:
            y = int(m.group(1))
            try:
                return datetime(y, mois_num, 1).strftime("%Y-%m-%d")
            except ValueError:
                pass

    # Format MM-AAAA (ex: "05-2026")
    m = re.search(r"(\d{2})[.\-](\d{4})", raw)
    if m:
        mo, y = m.group(1), m.group(2)
        try:
            return datetime(int(y), int(mo), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass

    # Année seule
    m = re.search(r"(202\d)", raw)
    if m:
        return f"{m.group(1)}-01-01"

    return None


# ─────────────────────────────────────────────────────────────────────────────
#  SCORING PERTINENCE SECTORIELLE
# ─────────────────────────────────────────────────────────────────────────────

def _build_sector_keywords(sector_config: dict) -> set:
    """Construit un ensemble de mots-clés à partir de la config secteur."""
    kws = set(_BASE_KEYWORDS)

    # Depuis les requêtes de recherche
    for q in sector_config.get("search_queries", []):
        for word in re.split(r'\s+|"', q.lower()):
            if len(word) >= 4:
                kws.add(word)

    # Label du secteur
    label = sector_config.get("label", "")
    for word in label.lower().split():
        if len(word) >= 4:
            kws.add(word)

    # Champ optionnel dédié
    for kw in sector_config.get("keywords", []):
        kws.add(kw.lower().strip())

    return kws


def _score_relevance(text: str, keywords: set) -> int:
    """Compte les occurrences de mots-clés dans le texte (insensible à la casse)."""
    text_lower = text.lower()
    return sum(1 for kw in keywords if kw in text_lower)


# ─────────────────────────────────────────────────────────────────────────────
#  SOURCE NAME DEPUIS LE NOM DE FICHIER
# ─────────────────────────────────────────────────────────────────────────────

# Mojibake courants dans les noms de fichiers WhatsApp (encodage cassé sur Windows)
_MOJIBAKE = {
    "ÔÇó": "•", "ÔÇô": "–", "ÔÇö": "—", "ÔÇÖ": "'", "ÔÇÜ": "'",
    "ÔÇ£": '"', "ÔÇØ": '"', "ÔÿÅ": " ", "Ôÿå": " ", "Ôÿ©": " ",
    "ÔÇá": "!", "ÔÇ░": " ", "ÔÇ¡": " ", "ÔÇ½": " ", "ÔÇ┤": " ",
    "☆": " ", "®": "", "+®": "é", "+¨": "è", "+á": "à",
}


def _fix_mojibake(s: str) -> str:
    for bad, good in _MOJIBAKE.items():
        s = s.replace(bad, good)
    return s


def _source_name(filename: str) -> str:
    """
    Dérive un nom de source lisible depuis le nom de fichier.
    Ex: 'Capital N417 • Juin 2026.Pdf'                         → 'Capital N417'
    Ex: 'Biblio Observ Transfo_0012_Capital N417 • Juin 2026'  → 'Capital N417'
    """
    name = Path(filename).stem
    # Corriger le mojibake avant tout traitement
    name = _fix_mojibake(name)
    # Supprimer le préfixe WhatsApp "Biblio Observ Transfo_XXXX_"
    name = re.sub(r"^Biblio\s+Observ\s+Transfo_?\d+_?\s*", "", name, flags=re.IGNORECASE)
    # Remplacer underscores par espaces
    name = name.replace("_", " ")
    # Supprimer la date en début (JJ-MM-AA-...)
    name = re.sub(r"^\d{2}[.\- ]\d{2}[.\- ]\d{2,4}[.\- ]*", "", name)
    # Supprimer suffixe @handle
    name = re.sub(r"\s*@\S+$", "", name)
    # Supprimer suffixe "• Mois AAAA" ou "Mercredi JJ Mois AAAA" etc.
    name = re.sub(r"\s*[•·]\s*.{0,20}\d{4}.*$", "", name)
    # Supprimer suffixe date textuelle " JJ Mois AAAA" (ex: " 1 giugno 2026")
    name = re.sub(
        r"\s+\d{1,2}\s+(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre"
        r"|january|february|march|april|may|june|july|august|september|october|november|december"
        r"|gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre"
        r"|enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)"
        r"\s+\d{4}.*$",
        "", name, flags=re.IGNORECASE,
    )
    # Supprimer suffixe " Mois AAAA" seul (ex: " Juin 2026")
    name = re.sub(
        r"\s+(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre"
        r"|january|february|march|april|may|june|july|august|september|october|november|december"
        r"|gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre"
        r"|enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)"
        r"\s+\d{4}.*$",
        "", name, flags=re.IGNORECASE,
    )
    # Supprimer suffixe jour de semaine (avec "du/de la" optionnel) et tout ce qui suit
    _days = r"lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche"
    name = re.sub(rf"\s+(?:du\s+|de\s+la\s+)?(?:{_days})\b.*$", "", name, flags=re.IGNORECASE)
    # Supprimer "du" ou "de" orphelin en fin
    name = re.sub(r"\s+\b(du|de|au)\b\s*$", "", name, flags=re.IGNORECASE)
    # Supprimer suffixe numérique MM-AAAA (ex: "05-2026")
    name = re.sub(r"\s+\d{2}-\d{4}\s*$", "", name)
    # Supprimer plage de mois "Mai-Juin 2026" ou "Avril/Mai 2026"
    _months_re = (
        r"janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre"
        r"|january|february|march|april|may|june|july|august|september|october|november|december"
        r"|gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre"
        r"|enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre"
    )
    name = re.sub(rf"\s+(?:{_months_re})[-/](?:{_months_re})\s+\d{{4}}.*$", "", name, flags=re.IGNORECASE)
    # Supprimer mois isolé en fin (ex: "Avril" restant après "Avril Mai 2026")
    _months_re = (
        r"janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre"
        r"|january|february|march|april|may|june|july|august|september|october|november|december"
        r"|gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre"
        r"|enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre"
    )
    name = re.sub(rf"\s+(?:{_months_re})\s*$", "", name, flags=re.IGNORECASE)
    # Nettoyer espaces multiples
    name = re.sub(r"\s{2,}", " ", name)
    return name.strip() or Path(filename).stem


# ─────────────────────────────────────────────────────────────────────────────
#  COLLECTE PRINCIPALE
# ─────────────────────────────────────────────────────────────────────────────

def collect_pdfs(sector_config: dict, settings: dict) -> List[Dict]:
    """
    Scanne le dossier magazines_dir, extrait le texte des PDFs récents,
    filtre par pertinence sectorielle et retourne des articles au format
    standard (même structure que collect_rss / collect_web).

    Config settings.yaml attendue :
      collection:
        magazines_dir: "chemin/vers/Magazines"
        pdf_days_back: 40          # fenêtre de sélection (défaut = days_back)
        pdf_max_chars: 3000        # chars extraits par PDF (défaut 3000)
        pdf_min_score: 1           # score pertinence min (défaut 1)
        pdf_max_docs: 20           # nb max de PDFs injectés (défaut 20)
    """
    coll_cfg = settings.get("collection", {})
    magazines_dir = coll_cfg.get("magazines_dir", "") or os.environ.get("MAGAZINES_DIR", "")

    if not magazines_dir:
        logger.debug("pdf_collector : magazines_dir non configuré — ignoré.")
        return []

    mag_path = Path(magazines_dir)
    if not mag_path.exists():
        logger.warning(f"pdf_collector : dossier introuvable — {mag_path}")
        return []

    days_back   = coll_cfg.get("pdf_days_back", coll_cfg.get("days_back", 40))
    max_chars   = coll_cfg.get("pdf_max_chars", 3000)
    min_score   = coll_cfg.get("pdf_min_score", 1)
    max_docs    = coll_cfg.get("pdf_max_docs", 20)

    cutoff         = datetime.now() - timedelta(days=days_back)
    keywords       = _build_sector_keywords(sector_config)
    articles       = []
    skipped_old    = 0
    skipped_irr    = 0
    _seen_content: set = set()   # empreinte texte pour déduplication contenu identique

    # Collecter tous les PDFs (insensible à la casse) sans doublons
    _seen_paths: set = set()
    _all_pdfs: list = []
    for p in mag_path.iterdir():
        if p.suffix.lower() == ".pdf" and p.resolve() not in _seen_paths:
            _seen_paths.add(p.resolve())
            _all_pdfs.append(p)
    pdf_files = sorted(_all_pdfs, key=lambda p: p.stat().st_mtime, reverse=True)

    for pdf_path in pdf_files:
        if len(articles) >= max_docs:
            break

        # Filtre par date (modification du fichier si pas de date dans le nom)
        file_date_str = _parse_date_from_filename(pdf_path.name)
        if file_date_str:
            try:
                file_date = datetime.fromisoformat(file_date_str)
            except ValueError:
                file_date = datetime.fromtimestamp(pdf_path.stat().st_mtime)
        else:
            file_date = datetime.fromtimestamp(pdf_path.stat().st_mtime)

        if file_date < cutoff:
            skipped_old += 1
            continue

        # Extraction texte
        text = _extract_text(pdf_path, max_chars=max_chars)
        if not text or len(text) < 80:
            logger.debug(f"PDF vide ou illisible : {pdf_path.name}")
            continue

        # Déduplication contenu (même journal en deux fichiers différents)
        _fingerprint = text[:200].strip()
        if _fingerprint in _seen_content:
            logger.debug(f"PDF doublon contenu ignoré : {pdf_path.name}")
            continue
        _seen_content.add(_fingerprint)

        # Filtre pertinence
        score = _score_relevance(text, keywords)
        if score < min_score:
            skipped_irr += 1
            logger.debug(f"PDF non pertinent (score={score}) : {pdf_path.name}")
            continue

        source = _source_name(pdf_path.name)
        articles.append({
            "title":   source,
            "summary": text[:max_chars],
            "url":     str(pdf_path),         # chemin local comme référence
            "source":  f"PDF · {source}",
            "date":    file_date_str or file_date.strftime("%Y-%m-%d"),
            "type":    "pdf",
            "lang":    "multilingue",         # hint pour le LLM
            "score":   score,
        })

    logger.info(
        f"PDF [{sector_config.get('label', '')}] : {len(articles)} docs pertinents "
        f"({skipped_old} trop anciens, {skipped_irr} non pertinents)"
    )
    return articles
