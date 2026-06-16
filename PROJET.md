# Observatoire de la Transformation — Agent Veille Stratégique
## Résumé du projet pour nouvelle conversation Claude Code

---

## 1. Contexte

**Cabinet :** LMS ORH — conseil en transformation RH & organisationnelle, Maroc & Afrique  
**Projet :** Plateforme de veille stratégique automatisée + rapports d'innovation RH clients  
**Utilisateur :** Responsable Observatoire de la Transformation (non-développeur)  
**Déploiement :** Streamlit Cloud (app web) + exécution locale Windows

---

## 2. Architecture générale

```
agent-veille/
├── app.py                    # Interface Streamlit (point d'entrée web)
├── main.py                   # CLI (run / schedule / list / sectors)
├── mailer.py                 # Envoi emails SMTP (validation + relances)
├── agent/
│   ├── collector.py          # Collecte RSS + Web + PDF magazines
│   ├── pdf_collector.py      # Extraction PDF multilingue (FR/EN/IT/AR/ES)
│   ├── analyzer.py           # Analyse veille (Claude/Groq/Gemini)
│   ├── analyzer_mission.py   # Benchmark mission consultant
│   ├── client_report.py      # Rapports Innovation RH clients (Solution 3)
│   └── reporter.py           # Génération DOCX + HTML rapports veille
├── config/
│   ├── sectors.yaml          # Secteurs + clients + validation manager
│   ├── settings.yaml         # Paramètres globaux (LLM, formats, chemins)
│   └── users.yaml            # Utilisateurs Streamlit (mots de passe bcrypt)
├── templates/
│   └── report.html           # Template Jinja2 rapport HTML
├── reports/
│   └── innovation/           # Rapports Innovation générés (_raw.json, HTML)
└── scripts/
    ├── auto_download_wa_pdfs.py   # Téléchargement PDFs WhatsApp (Playwright)
    ├── download_magazines.ps1     # Lanceur PowerShell du script Python
    ├── install_shortcut.ps1       # Crée raccourci Ctrl+Alt+M
    └── lancer_download_wa.bat     # BAT double-cliquable (debug)
```

---

## 3. Fonctionnalités implémentées

### A. Veille Stratégique (Onglet 1)
- Collecte RSS + DuckDuckGo + **PDFs magazines locaux**
- Analyse Claude/Groq/Gemini (3 appels, benchmark RH sectoriel)
- Génération DOCX + HTML avec **section Sources/Références** numérotées
- 5 secteurs : pharma, banque_finance, santé, industrie, RH_digital

### B. Benchmark Mission Consultant (Onglet 2)
- Saisie : nom mission, entreprise cible, secteur, géographie, angle stratégique
- Mode rapide (1 appel) ou Approfondi (3 appels, slides optionnelles)
- Export DOCX professionnel

### C. Rapports Innovation RH Clients — Solution 3 (Onglet 3)
**CDC v2 complet :**
- `indice_maturite` : ●/●●/●●● (Émergent / En adoption / Mature)
- `score_urgence` : cette_semaine / ce_mois / prochain_trimestre
- `question_amorce` : question spécifique générée par Claude
- Rapport interne consultant + Infographie client personnalisée par HTML
- Workflow validation manager : J+1 / J+2 relances email
- Sous-onglet **Feedback** : RDV (Oui/En cours/Non), notes, synthèse

### D. Sources PDF — Magazines
- Dossier : `C:\Users\LMS\OneDrive - LMS ORH\Bureau\LMS-Orga\Observatoire Transformation\Magazines`
- **64 PDFs** actuellement (FR/EN/IT/AR/ES)
- Extraction via `pymupdf` (priorité) + `pdfplumber` (fallback)
- Gestion mojibake WhatsApp, déduplication contenu + chemin
- Inclus automatiquement dans toutes les collectes si `collection.magazines_dir` configuré
- **URLs PDFs masquées** dans les rapports (confidentialité chemin local)
- Badges dans les sources : `Directe` (RSS) · `PDF · Presse` (pdf) · `Contextuelle` (web)

### E. Téléchargement automatique WhatsApp (en cours de débogage)
- Groupe : **"Biblio Observ Transfo"** sur WhatsApp Web
- Script Python : `scripts/auto_download_wa_pdfs.py` via Playwright
- Raccourci : **Ctrl+Alt+M** (installé sur Bureau + Start Menu)
- **Statut actuel** : script fonctionnel mais pb lancement navigateur depuis sandbox Claude
  - La copie de session Chrome → Playwright fonctionne ✓
  - Le navigateur doit être lancé directement par l'utilisateur (pas via Claude sandbox)
  - **À tester** : double-clic sur `scripts/lancer_download_wa.bat`
  - Dernier PDF dans Magazines : **10/06/2026** → ne télécharger que les PDFs postérieurs

---

## 4. Stack technique

| Composant | Technologie |
|-----------|-------------|
| LLM principal | Anthropic Claude Sonnet 4.6 |
| LLM alternatifs | Groq (llama-3.3-70b), Gemini 2.5 Flash |
| Interface web | Streamlit + streamlit-authenticator |
| Collecte RSS | feedparser |
| Collecte web | duckduckgo-search |
| Extraction PDF | pymupdf (fitz) + pdfplumber |
| Automatisation navigateur | Playwright (Python) |
| Planification | APScheduler (mensuel + J+1 + J+2) |
| Email | SMTP (Gmail App Password) |
| Rapports | python-docx + Jinja2 HTML |
| Auth | bcrypt (users.yaml) |

---

## 5. Sécurité — règles absolues

- **Clés API** : uniquement dans Streamlit Cloud Secrets UI, jamais dans le chat
- **Mots de passe** : bcrypt dans `config/users.yaml` — safe to commit
- **Envoi auto** : `envoi_auto_si_pas_reponse: false` — hardcodé dans sectors.yaml
- **Chemins PDF** : URL masquée (`""`) dans les rapports — jamais exposée
- **WhatsApp** : interdit d'écrire ou supprimer quoi que ce soit dans le groupe

---

## 6. Configuration clé

### settings.yaml (extrait)
```yaml
collection:
  magazines_dir: "C:/Users/LMS/OneDrive - LMS ORH/Bureau/LMS-Orga/Observatoire Transformation/Magazines"
  pdf_days_back: 40
  pdf_max_chars: 3000
  pdf_min_score: 1
  pdf_max_docs: 15
```

### Variables d'environnement (Streamlit Secrets)
```toml
ANTHROPIC_API_KEY = "..."
GROQ_API_KEY = "..."
GEMINI_API_KEY = "..."
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = "587"
SMTP_USER = "..."
SMTP_PASSWORD = "..."
MAGAZINES_DIR = "..."      # optionnel, surcharge settings.yaml
MANAGER_EMAIL = "..."      # optionnel, surcharge sectors.yaml
```

---

## 7. Problème ouvert — téléchargement WhatsApp

**Contexte :** WhatsApp Web est bloqué par l'extension Claude in Chrome → impossible d'automatiser via les outils MCP. La solution alternative (Playwright) fonctionne logiquement mais le sandbox Claude ne peut pas lancer de navigateur.

**Ce qui fonctionne :**
- Copie session Chrome → profil Playwright ✓
- Identification du groupe et navigation WhatsApp Web ✓ (en théorie)
- Filtrage par date (après 10/06/2026) ✓

**À faire en nouvelle session :**
1. Demander à l'utilisateur de lancer `lancer_download_wa.bat` en double-cliquant
2. Lire le contenu du fichier `wa_log.txt` généré sur le Bureau si erreur persiste
3. Si Playwright ne marche toujours pas → envisager `pywinauto` (automatisation UI Windows) ou demander à l'utilisateur de télécharger manuellement par lots via WA Media Downloader Pro (25 fichiers × N fois)

---

## 8. Commandes utiles

```powershell
# Lancer l'app Streamlit localement
cd "C:\Users\LMS\OneDrive - LMS ORH\Bureau\LMS-Orga\Observatoire Transformation\agent-veille"
streamlit run app.py

# Tester la collecte PDF
py -3 -c "from agent.pdf_collector import collect_pdfs; from agent.collector import load_settings, load_sectors; s=load_settings(); sc=list(load_sectors().values())[0]; r=collect_pdfs(sc,s); print(len(r),'PDFs')"

# Téléchargement WhatsApp (double-clic ou depuis Explorer)
scripts\lancer_download_wa.bat

# Vérifier les PDFs dans Magazines
(Get-ChildItem "C:\Users\LMS\OneDrive - LMS ORH\Bureau\LMS-Orga\Observatoire Transformation\Magazines" -Filter "*.pdf").Count
```

---

## 9. Derniers commits

```
16a9925 fix(scripts): utilise Chrome installe (channel=chrome), date limite dernier PDF
126af0b fix(scripts): refonte complete — copie session Chrome vers Playwright
fb63f3a fix(scripts): import subprocess et urllib.request manquants
5fc7af5 feat(ui): compteur PDF dans collecte veille et innovation
2144806 feat(sources): section References dans tous les rapports generes
b4e8523 feat(scripts): raccourci Ctrl+Alt+M pour telecharger magazines WhatsApp
8cfc952 fix(pdf): deduplication contenu, mojibake WhatsApp
3c94dad feat(pdf): collecte magazines PDF multilingue (FR/EN/IT/AR/ES)
b2f467e feat(solution3): CDC v2 — indice_maturite, score_urgence, question_amorce
f485d1d style(infographie): charte LMS sur structure McKinsey
6ba9c6e feat(solution3): Rapport Innovation RH client — génération, validation, envoi
```
