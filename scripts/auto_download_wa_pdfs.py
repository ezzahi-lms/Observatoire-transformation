"""
auto_download_wa_pdfs.py
------------------------
Telecharge automatiquement TOUS les PDFs du groupe WhatsApp "Biblio Observ Transfo".

Strategie : copie la session WhatsApp de Chrome vers un profil Playwright isole.
- Chrome n'a pas besoin d'etre ferme
- Aucun QR code (session deja active dans Chrome)
- Pas de limite de 25 fichiers
- Ignore les PDFs deja presents dans Magazines

Usage :
    py -3 scripts/auto_download_wa_pdfs.py
"""

import os
import sys
import time
import shutil
import subprocess
from pathlib import Path

MAGAZINES_DIR  = Path(r"C:\Users\LMS\OneDrive - LMS ORH\Bureau\LMS-Orga\Observatoire Transformation\Magazines")
CHROME_PROFILE = Path(r"C:\Users\LMS\AppData\Local\Google\Chrome\User Data\Default")
AUTH_DIR       = Path.home() / ".wa_playwright_session"
GROUP_NAME     = "Biblio Observ Transfo"


def log(msg):
    print(f"[WA] {msg}", flush=True)


def wait(s):
    time.sleep(s)


# ---------------------------------------------------------------------------
# Copier la session WhatsApp Web depuis Chrome
# ---------------------------------------------------------------------------
def copy_whatsapp_session():
    """
    Copie les donnees de session WhatsApp Web depuis Chrome vers le profil Playwright.
    Playwright (Chromium) et Chrome utilisent le meme format LevelDB — compatible.
    """
    dst = AUTH_DIR / "Default"
    dst.mkdir(parents=True, exist_ok=True)

    # Dossiers qui stockent la session WhatsApp Web
    session_folders = [
        "IndexedDB/https_web.whatsapp.com_0.indexeddb.leveldb",
        "Local Storage/leveldb",
        "Session Storage",
    ]

    copied = 0
    for folder in session_folders:
        src = CHROME_PROFILE / folder
        dst_folder = dst / folder
        if src.exists():
            try:
                if dst_folder.exists():
                    shutil.rmtree(dst_folder)
                dst_folder.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(str(src), str(dst_folder))
                copied += 1
                log(f"  Session copiee : {folder}")
            except Exception as e:
                log(f"  Avertissement copie {folder} : {e}")

    if copied == 0:
        log("Aucune donnee de session trouvee dans Chrome.")
        log("Vous devrez scanner le QR code lors de la premiere execution.")
    else:
        log(f"{copied} dossier(s) de session copie(s) depuis Chrome.")


# ---------------------------------------------------------------------------
# Helpers WhatsApp Web
# ---------------------------------------------------------------------------
def wait_for_whatsapp(page):
    from playwright.sync_api import TimeoutError as PWTimeout

    log("Chargement WhatsApp Web...")
    try:
        page.wait_for_selector(
            '[data-testid="qrcode"], [data-testid="chat-list"], #side, canvas',
            timeout=30_000,
        )
    except PWTimeout:
        log("WhatsApp Web ne repond pas — verifiez votre connexion internet.")
        sys.exit(1)

    # Si QR code, attendre scan
    qr = page.query_selector('[data-testid="qrcode"], canvas')
    if qr:
        log("QR code affiche. Scannez avec WhatsApp sur votre telephone :")
        log("  WhatsApp > Menu > Appareils connectes > Connecter un appareil")
        log("Attente (5 minutes max)...")
        try:
            page.wait_for_selector('[data-testid="chat-list"], #side', timeout=300_000)
        except PWTimeout:
            log("QR non scanne — relancez le script.")
            sys.exit(1)

    log("WhatsApp Web connecte !")


def find_group(page):
    from playwright.sync_api import TimeoutError as PWTimeout
    log(f"Recherche du groupe '{GROUP_NAME}'...")

    # Clic sur la barre de recherche
    for sel in ['[data-testid="search"]', '[aria-label*="Rechercher"]', '[aria-label*="Search"]']:
        try:
            page.click(sel, timeout=5_000)
            break
        except PWTimeout:
            continue

    wait(1)
    page.keyboard.type(GROUP_NAME)
    wait(2)

    results = page.query_selector_all('[data-testid="cell-frame-container"]')
    for r in results:
        title = r.query_selector('[data-testid="cell-frame-title"]')
        if title and GROUP_NAME.lower() in title.inner_text().lower():
            r.click()
            log(f"Groupe trouve et ouvert.")
            wait(2)
            return True

    log(f"ERREUR : groupe '{GROUP_NAME}' introuvable dans les resultats.")
    log("Groupes visibles :")
    for r in results[:8]:
        t = r.query_selector('[data-testid="cell-frame-title"]')
        if t:
            log(f"  - {t.inner_text()}")
    return False


def open_documents_tab(page):
    from playwright.sync_api import TimeoutError as PWTimeout
    log("Ouverture de la section Documents...")

    # Clic sur l'en-tete du groupe
    for sel in [
        '[data-testid="conversation-info-header"]',
        'header [data-testid="conversation-header"]',
        'header',
    ]:
        try:
            page.click(sel, timeout=5_000)
            break
        except PWTimeout:
            continue

    wait(2)

    # Chercher l'onglet Documents / Docs
    for sel in ['span:text("Docs")', 'span:text("Documents")', 'button:has-text("Docs")']:
        try:
            page.click(sel, timeout=5_000)
            log("Onglet Documents ouvert.")
            wait(2)
            return True
        except PWTimeout:
            continue

    log("Onglet Documents introuvable — telechargement via messages.")
    return False


def download_visible_pdfs(page, already_downloaded):
    from playwright.sync_api import TimeoutError as PWTimeout
    new_count = 0

    # Chercher les elements PDF dans le panneau
    selectors = [
        '[data-testid="media-item"]',
        '[data-testid="document-thumb"]',
        'div[class*="document"]',
    ]
    doc_items = []
    for sel in selectors:
        items = page.query_selector_all(sel)
        if items:
            doc_items = items
            break

    log(f"  {len(doc_items)} document(s) visible(s).")

    for item in doc_items:
        # Nom du fichier
        fn_el = (
            item.query_selector('[data-testid="media-item-filename"]') or
            item.query_selector('span[title]') or
            item.query_selector('span[class*="filename"]')
        )
        filename = fn_el.inner_text().strip() if fn_el else ""

        if not filename.lower().endswith(".pdf"):
            continue
        if filename in already_downloaded:
            continue

        dest = MAGAZINES_DIR / filename
        if dest.exists():
            already_downloaded.add(filename)
            continue

        # Telecharger
        try:
            dl_btn = (
                item.query_selector('[data-testid="media-download"]') or
                item.query_selector('button[aria-label*="echarger"]') or
                item.query_selector('button[aria-label*="ownload"]')
            )
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
                log(f"  [SKIP] Bouton download absent : {filename}")
        except Exception as e:
            log(f"  [ERREUR] {filename} : {e}")

    return new_count


def scroll_and_download_all(page, already_downloaded):
    total = 0
    no_new = 0
    scroll = 0

    while no_new < 3 and scroll < 100:
        new = download_visible_pdfs(page, already_downloaded)
        total += new
        no_new = 0 if new > 0 else no_new + 1

        if new > 0:
            log(f"  +{new} PDFs | Total session : {total}")
        else:
            log(f"  Aucun nouveau ({no_new}/3) — defilement...")

        # Defiler dans le panneau
        panel = (
            page.query_selector('[data-testid="media-docs-list"]') or
            page.query_selector('[data-testid="media-list"]') or
            page.query_selector('#app')
        )
        if panel:
            panel.evaluate("el => el.scrollTop += el.clientHeight")
        else:
            page.keyboard.press("End")

        wait(2)
        scroll += 1

    return total


# ---------------------------------------------------------------------------
# Point d'entree
# ---------------------------------------------------------------------------
def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("Playwright non installe. Executez :")
        log("  py -3 -m pip install playwright")
        log("  py -3 -m playwright install chromium")
        sys.exit(1)

    MAGAZINES_DIR.mkdir(parents=True, exist_ok=True)
    AUTH_DIR.mkdir(parents=True, exist_ok=True)

    already_downloaded = {
        p.name for p in MAGAZINES_DIR.iterdir() if p.suffix.lower() == ".pdf"
    }
    log(f"{len(already_downloaded)} PDFs deja dans le dossier Magazines.")

    # Copier la session WhatsApp depuis Chrome (sans fermer Chrome)
    log("Copie de la session WhatsApp depuis Chrome...")
    copy_whatsapp_session()

    with sync_playwright() as p:
        log("Lancement du navigateur Playwright...")
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(AUTH_DIR),
            headless=False,
            viewport={"width": 1280, "height": 900},
            accept_downloads=True,
            args=["--no-sandbox"],
        )

        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://web.whatsapp.com", wait_until="domcontentloaded")

        wait_for_whatsapp(page)

        if not find_group(page):
            context.close()
            sys.exit(1)

        opened = open_documents_tab(page)
        total = scroll_and_download_all(page, already_downloaded)

        log(f"\nTermine ! {total} nouveau(x) PDF(s) telecharge(s).")
        final = sum(1 for p in MAGAZINES_DIR.iterdir() if p.suffix.lower() == ".pdf")
        log(f"Total dans Magazines : {final} PDFs.")

        wait(2)
        context.close()


if __name__ == "__main__":
    main()
