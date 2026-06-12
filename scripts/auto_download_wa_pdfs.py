"""
auto_download_wa_pdfs.py
------------------------
Telecharge automatiquement TOUS les PDFs du groupe WhatsApp "Biblio Observ Transfo"
en utilisant la section Documents de WhatsApp Web (Playwright).

- Premiere execution : scanner le QR code une seule fois
- Executions suivantes : session sauvegardee, aucun QR code requis
- Pas de limite de 25 fichiers (acces direct a WhatsApp Web, sans extension)
- Saute les fichiers deja presents dans le dossier Magazines

Usage :
    py -3 scripts/auto_download_wa_pdfs.py
"""

import os
import sys
import time
import shutil
from pathlib import Path

MAGAZINES_DIR = Path(r"C:\Users\LMS\OneDrive - LMS ORH\Bureau\LMS-Orga\Observatoire Transformation\Magazines")
AUTH_DIR      = Path.home() / ".wa_downloader_auth"   # session sauvegardee
GROUP_NAME    = "Biblio Observ Transfo"
TIMEOUT_MS    = 60_000   # 60s max par attente

# ---------------------------------------------------------------------------
# Dependances
# ---------------------------------------------------------------------------
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    print("Playwright non installe. Executez :")
    print("  py -3 -m pip install playwright")
    print("  py -3 -m playwright install chromium")
    sys.exit(1)


def log(msg):
    print(f"[WA] {msg}", flush=True)


def wait(seconds, label=""):
    if label:
        log(f"Attente {seconds}s ({label})...")
    time.sleep(seconds)


# ---------------------------------------------------------------------------
# Helpers WhatsApp Web
# ---------------------------------------------------------------------------
def wait_for_whatsapp(page):
    """Attend le chargement complet de WhatsApp Web (apres QR ou session)."""
    log("Chargement WhatsApp Web...")

    # Etape 1 : attendre que la page soit prete (QR code OU deja connecte)
    try:
        page.wait_for_selector(
            '[data-testid="qrcode"], [data-testid="chat-list"], canvas[aria-label="Scan me!"], #side',
            timeout=30_000,
        )
    except PWTimeout:
        log("La page WhatsApp Web ne repond pas. Verifiez votre connexion internet.")
        sys.exit(1)

    # Etape 2 : si QR code present, attendre que l'utilisateur scanne (5 minutes)
    qr = page.query_selector('[data-testid="qrcode"], canvas[aria-label="Scan me!"]')
    if qr:
        log(">> QR CODE AFFICHE <<")
        log("Scannez le QR code avec WhatsApp sur votre telephone :")
        log("  WhatsApp -> Menu -> Appareils connectes -> Connecter un appareil")
        log("Attente du scan (5 minutes max)...")
        try:
            page.wait_for_selector(
                '[data-testid="chat-list"], #side, [data-testid="default-user"]',
                timeout=300_000,
            )
        except PWTimeout:
            log("QR code non scanne en 5 minutes. Relancez le script.")
            sys.exit(1)

    log("WhatsApp Web connecte !")


def find_group(page):
    """Cherche et ouvre le groupe cible."""
    log(f"Recherche du groupe '{GROUP_NAME}'...")

    # Clic sur l'icone de recherche
    try:
        page.click('[data-testid="search"]', timeout=10_000)
    except PWTimeout:
        page.click('[aria-label="Rechercher ou démarrer une nouvelle discussion"]', timeout=10_000)

    wait(1)
    page.keyboard.type(GROUP_NAME)
    wait(2)

    # Chercher la conversation correspondante
    results = page.query_selector_all('[data-testid="cell-frame-container"]')
    for r in results:
        title = r.query_selector('[data-testid="cell-frame-title"]')
        if title and GROUP_NAME.lower() in title.inner_text().lower():
            r.click()
            log(f"Groupe '{GROUP_NAME}' ouvert.")
            wait(2)
            return True

    log(f"ERREUR : groupe '{GROUP_NAME}' introuvable.")
    log("Groupes disponibles :")
    for r in results[:10]:
        t = r.query_selector('[data-testid="cell-frame-title"]')
        if t:
            log(f"  - {t.inner_text()}")
    return False


def open_documents_tab(page):
    """Ouvre le panneau Infos du groupe > Documents."""
    log("Ouverture de la section Documents du groupe...")

    # Clic sur l'en-tete du groupe pour ouvrir les infos
    try:
        page.click('[data-testid="conversation-header"]', timeout=10_000)
    except PWTimeout:
        # Fallback : chercher le titre du chat en haut
        page.click('header [data-testid="conversation-info-header"]', timeout=10_000)

    wait(2)

    # Chercher l'onglet Docs / Documents
    selectors_docs = [
        'span:text("Docs")',
        'span:text("Documents")',
        '[data-testid="media-docs"]',
        'button:has-text("Docs")',
    ]
    for sel in selectors_docs:
        try:
            page.click(sel, timeout=5_000)
            log("Onglet Documents ouvert.")
            wait(2)
            return True
        except PWTimeout:
            continue

    log("ERREUR : onglet Documents introuvable.")
    return False


def download_visible_pdfs(page, already_downloaded):
    """Telecharge tous les PDFs visibles dans le panneau Documents."""
    new_count = 0

    # Chercher tous les elements de document
    doc_items = page.query_selector_all('[data-testid="media-item"]')
    if not doc_items:
        # Fallback selector
        doc_items = page.query_selector_all('div[role="button"]:has([data-testid="media-icon-document"])')

    log(f"  {len(doc_items)} document(s) visible(s).")

    for item in doc_items:
        # Extraire le nom du fichier
        filename_el = (
            item.query_selector('[data-testid="media-item-filename"]') or
            item.query_selector('span[title]') or
            item.query_selector('span.x1iyjqo2')  # classe WhatsApp Web
        )
        filename = filename_el.inner_text().strip() if filename_el else ""

        if not filename.lower().endswith(".pdf"):
            continue

        if filename in already_downloaded:
            continue

        dest = MAGAZINES_DIR / filename
        if dest.exists():
            already_downloaded.add(filename)
            continue

        # Clic sur le bouton de telechargement de cet element
        try:
            dl_btn = item.query_selector('[data-testid="media-download"]')
            if not dl_btn:
                dl_btn = item.query_selector('button[aria-label*="echarger"], button[aria-label*="ownload"]')

            if dl_btn:
                with page.expect_download(timeout=30_000) as dl_info:
                    dl_btn.click()
                download = dl_info.value
                save_path = MAGAZINES_DIR / (download.suggested_filename or filename)
                download.save_as(str(save_path))
                log(f"  [OK] {save_path.name}")
                already_downloaded.add(filename)
                new_count += 1
                wait(0.5)
            else:
                log(f"  [SKIP] Bouton download introuvable pour : {filename}")
        except Exception as e:
            log(f"  [ERREUR] {filename} : {e}")

    return new_count


def scroll_and_download_all(page, already_downloaded):
    """Fait defiler la liste et telecharge tous les PDFs."""
    total = 0
    scroll_attempts = 0
    max_no_new = 3   # Arrete apres 3 defilements sans nouveau PDF

    no_new_streak = 0

    while no_new_streak < max_no_new:
        new = download_visible_pdfs(page, already_downloaded)
        total += new

        if new == 0:
            no_new_streak += 1
            log(f"  Aucun nouveau PDF ({no_new_streak}/{max_no_new}) — defilement...")
        else:
            no_new_streak = 0
            log(f"  +{new} PDFs | Total : {total}")

        # Defiler vers le bas pour charger plus de documents
        panel = page.query_selector('[data-testid="media-docs-list"]') or \
                page.query_selector('[data-testid="media-list"]')

        if panel:
            panel.evaluate("el => el.scrollTop += el.clientHeight")
        else:
            page.keyboard.press("End")

        wait(2)
        scroll_attempts += 1

        if scroll_attempts > 100:  # securite anti-boucle infinie
            log("Limite de 100 defilements atteinte.")
            break

    return total


# ---------------------------------------------------------------------------
# Point d'entree
# ---------------------------------------------------------------------------
def main():
    MAGAZINES_DIR.mkdir(parents=True, exist_ok=True)
    AUTH_DIR.mkdir(parents=True, exist_ok=True)

    # Fichiers deja presents
    already_downloaded = {
        p.name for p in MAGAZINES_DIR.iterdir() if p.suffix.lower() == ".pdf"
    }
    log(f"{len(already_downloaded)} PDFs deja dans le dossier Magazines.")

    with sync_playwright() as p:
        log("Lancement du navigateur (Chrome)...")
        # Utilise Chrome installe sur le PC (evite les problemes de permissions avec Chromium Playwright)
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(AUTH_DIR),
                channel="chrome",
                headless=False,
                viewport={"width": 1280, "height": 900},
                accept_downloads=True,
            )
        except Exception as e1:
            log(f"Chrome echoue ({e1}), tentative avec Chromium...")
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(AUTH_DIR),
                headless=False,
                viewport={"width": 1280, "height": 900},
                accept_downloads=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )

        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://web.whatsapp.com", wait_until="domcontentloaded")

        wait_for_whatsapp(page)

        if not find_group(page):
            context.close()
            sys.exit(1)

        if not open_documents_tab(page):
            log("Tentative de telechargement via la liste des messages...")
            # Fallback si l'onglet Documents ne s'ouvre pas
            total = scroll_and_download_all(page, already_downloaded)
        else:
            total = scroll_and_download_all(page, already_downloaded)

        log(f"\nTermine ! {total} nouveau(x) PDF(s) telecharge(s) dans :")
        log(f"  {MAGAZINES_DIR}")

        final_count = sum(1 for p in MAGAZINES_DIR.iterdir() if p.suffix.lower() == ".pdf")
        log(f"Total dans le dossier : {final_count} PDFs")

        wait(2)
        context.close()


if __name__ == "__main__":
    main()
