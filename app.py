"""
Observatoire de la Transformation Organisationnelle — Interface Streamlit
Lancer : streamlit run app.py
"""
import sys
import os
from pathlib import Path
from datetime import datetime

import streamlit as st
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth
from dotenv import dotenv_values

# ── Chemins ───────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

# ── Chargement .env (clé API côté serveur — usage local) ─────────────────────
_env_path = ROOT / ".env"
if _env_path.exists():
    for _k, _v in dotenv_values(_env_path, encoding="utf-8").items():
        if _v and not os.environ.get(_k):
            os.environ[_k] = _v

# ── Streamlit Cloud : injecter st.secrets dans os.environ ────────────────────
# Sur Streamlit Community Cloud, les clés API sont configurées dans l'UI Secrets
# et exposées via st.secrets. Ce bloc les rend disponibles à tous les modules
# qui utilisent os.environ.get("GEMINI_API_KEY"), os.environ.get("LLM_PROVIDER")…
try:
    for _k, _v in st.secrets.items():
        if isinstance(_v, str) and _v and not os.environ.get(_k):
            os.environ[_k] = _v
except Exception:
    pass  # Pas de secrets configurés (normal en local sans secrets.toml)

# ── Configuration de la page ──────────────────────────────────────────────────
st.set_page_config(
    page_title="Observatoire Transformation",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  /* Sidebar */
  section[data-testid="stSidebar"] { background: #1A5F8A !important; }
  section[data-testid="stSidebar"] * { color: white !important; }
  section[data-testid="stSidebar"] .stTextInput input { color: #222 !important; background: white !important; }
  section[data-testid="stSidebar"] .stSelectbox div { color: #222 !important; }

  /* Formulaire de connexion */
  div[data-testid="stForm"] {
    max-width: 420px;
    margin: 80px auto 0;
    padding: 40px 36px;
    border-radius: 14px;
    background: white;
    box-shadow: 0 4px 24px rgba(0,0,0,0.10);
  }
  .login-logo {
    text-align: center;
    font-size: 2.4rem;
    margin-bottom: 6px;
  }
  .login-title {
    text-align: center;
    font-size: 1.2rem;
    font-weight: 700;
    color: #1A5F8A;
    margin-bottom: 4px;
  }
  .login-subtitle {
    text-align: center;
    font-size: 0.85rem;
    color: #888;
    margin-bottom: 24px;
  }

  /* App */
  .block-container { padding-top: 1.5rem; }
  div[data-testid="stTabs"] button { font-size: 14px; font-weight: 600; }
  .badge-green  { background:#27AE60; color:white; padding:2px 10px; border-radius:10px; font-size:11px; font-weight:700; }
  .badge-orange { background:#E67E22; color:white; padding:2px 10px; border-radius:10px; font-size:11px; font-weight:700; }
  .badge-blue   { background:#2E86C1; color:white; padding:2px 10px; border-radius:10px; font-size:11px; font-weight:700; }
</style>
""", unsafe_allow_html=True)


# ── Chargement des configs ─────────────────────────────────────────────────────
def load_settings() -> dict:
    with open(ROOT / "config" / "settings.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)

def save_settings(settings: dict):
    with open(ROOT / "config" / "settings.yaml", "w", encoding="utf-8") as f:
        yaml.dump(settings, f, allow_unicode=True, sort_keys=False)

def load_sectors() -> dict:
    with open(ROOT / "config" / "sectors.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f).get("sectors", {})

def load_users_config() -> dict:
    with open(ROOT / "config" / "users.yaml", encoding="utf-8") as f:
        return yaml.load(f, Loader=SafeLoader)

def save_users_config(config: dict):
    with open(ROOT / "config" / "users.yaml", "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, sort_keys=False)


# ══════════════════════════════════════════════════════════════════════════════
#  AUTHENTIFICATION
# ══════════════════════════════════════════════════════════════════════════════

users_config = load_users_config()

authenticator = stauth.Authenticate(
    credentials=users_config["credentials"],
    cookie_name=users_config["cookie"]["name"],
    cookie_key=users_config["cookie"]["key"],
    cookie_expiry_days=users_config["cookie"].get("expiry_days", 7),
)

# ── Page de connexion ─────────────────────────────────────────────────────────
if not st.session_state.get("authentication_status"):
    st.markdown('<div class="login-logo">🔍</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-title">Observatoire de la Transformation</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-subtitle">LMS ORH · Accès réservé aux membres du projet</div>', unsafe_allow_html=True)

authenticator.login(location="main", key="login_form")

auth_status = st.session_state.get("authentication_status")

if auth_status is False:
    st.error("❌ Identifiant ou mot de passe incorrect.")
    st.stop()

if auth_status is None:
    st.stop()

# ── Utilisateur connecté → affichage de l'app ─────────────────────────────────
current_user = st.session_state.get("name", "")
current_username = st.session_state.get("username", "")
user_role = (
    users_config["credentials"]["usernames"]
    .get(current_username, {})
    .get("role", "user")
)


# ══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR (après connexion)
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🔍 Observatoire\n**Transformation**")
    st.markdown("---")
    st.markdown(f"👤 **{current_user}**")
    st.caption(f"Rôle : {'Administrateur' if user_role == 'admin' else 'Consultant'}")

    if authenticator.logout(button_name="🚪 Déconnexion", location="sidebar"):
        st.rerun()

    st.markdown("---")

    # Statut clé API selon le provider actif
    _provider = os.environ.get("LLM_PROVIDER", load_settings().get("analysis", {}).get("provider", "anthropic")).lower()
    _key_map = {"gemini": "GEMINI_API_KEY", "groq": "GROQ_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}
    _key_name_sidebar = _key_map.get(_provider, "ANTHROPIC_API_KEY")
    _api_key_sidebar = os.environ.get(_key_name_sidebar, "")
    if _api_key_sidebar:
        st.markdown(f"✅ **Clé API {_provider.title()} configurée**")
    else:
        st.warning(f"⚠️ Clé API {_provider.title()} manquante")
        st.caption(f"Ajoutez {_key_name_sidebar} dans les Secrets")

    st.markdown("---")
    settings_sidebar = load_settings()
    sectors_sidebar = load_sectors()
    default = settings_sidebar.get("agent", {}).get("default_sector", "")
    if default and default in sectors_sidebar:
        st.caption(f"Secteur par défaut : **{sectors_sidebar[default]['label']}**")

    sched = settings_sidebar.get("scheduling", {})
    if sched.get("enabled"):
        day = sched.get("day_of_month", 1)
        h = sched.get("hour", 8)
        m = sched.get("minute", 0)
        st.caption(f"📅 Planification active\nLe {day} du mois à {h:02d}h{m:02d}")
    else:
        st.caption("📅 Planification désactivée")

    st.markdown("---")
    st.caption("LMS ORH · Observatoire Transformation\nv1.1.0")


# ══════════════════════════════════════════════════════════════════════════════
#  ONGLETS PRINCIPAUX
# ══════════════════════════════════════════════════════════════════════════════

# Onglet admin uniquement si rôle admin
if user_role == "admin":
    tab_analyse, tab_mission, tab_reports, tab_planning, tab_config, tab_admin = st.tabs([
        "🚀 Nouvelle analyse",
        "🎯 Benchmark Mission",
        "📂 Rapports",
        "📅 Planification",
        "⚙️ Paramètres",
        "👥 Utilisateurs",
    ])
else:
    tab_analyse, tab_mission, tab_reports, tab_planning, tab_config = st.tabs([
        "🚀 Nouvelle analyse",
        "🎯 Benchmark Mission",
        "📂 Rapports",
        "📅 Planification",
        "⚙️ Paramètres",
    ])
    tab_admin = None


# ═══════════════════════════════════════════════════════════════════════════════
# ONGLET 1 — NOUVELLE ANALYSE
# ═══════════════════════════════════════════════════════════════════════════════
with tab_analyse:
    st.header("Lancer une analyse de veille stratégique")

    settings = load_settings()
    sectors = load_sectors()
    _provider_tab = os.environ.get("LLM_PROVIDER", settings.get("analysis", {}).get("provider", "anthropic")).lower()
    _key_map_tab = {"gemini": "GEMINI_API_KEY", "groq": "GROQ_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}
    _key_name_tab = _key_map_tab.get(_provider_tab, "ANTHROPIC_API_KEY")
    api_key = os.environ.get(_key_name_tab, "")

    if not api_key:
        st.error(f"🔑 Clé API {_provider_tab.title()} non configurée ({_key_name_tab} manquante). Contactez l'administrateur.")
        st.stop()

    col_form, col_info = st.columns([1, 1], gap="large")

    with col_form:
        sector_labels = {k: v["label"] for k, v in sectors.items()}
        default_sector = settings.get("agent", {}).get("default_sector", list(sector_labels.keys())[0])
        selected = st.selectbox(
            "Secteur à analyser",
            options=list(sector_labels.keys()),
            format_func=lambda k: sector_labels[k],
            index=list(sector_labels.keys()).index(default_sector)
                  if default_sector in sector_labels else 0,
        )

        formats_available = ["docx", "html", "pdf"]
        formats_default = settings.get("reporting", {}).get("formats", ["docx", "html"])
        formats_selected = st.multiselect(
            "Formats de sortie",
            options=formats_available,
            default=[f for f in formats_default if f in formats_available],
        )

        run_btn = st.button("▶ Lancer l'analyse", type="primary", use_container_width=True)

    with col_info:
        if selected in sectors:
            sc = sectors[selected]
            st.markdown(f"**{sc['label']}**")
            st.caption(f"{len(sc.get('rss_feeds', []))} flux RSS · {len(sc.get('search_queries', []))} requêtes web")
            st.markdown("**Axes analysés :**")
            for fa in sc.get("focus_areas", sc.get("benchmark_axes", []))[:5]:
                label = fa.split(":")[0].replace("FCS ", "").strip() if ":" in fa else fa
                st.markdown(f"- {label[:80]}")

    st.markdown("---")

    if run_btn:
        sector_config = {**sectors[selected], "key": selected}  # injecte la clé YAML pour les tmp
        run_settings = load_settings()
        if formats_selected:
            run_settings["reporting"]["formats"] = formats_selected

        with st.status("⏳ Analyse en cours…", expanded=True) as status:
            st.write("🔎 **Étape 1/3** — Collecte des sources (RSS + Web)…")
            try:
                from agent import collector as col_module
                articles = col_module.collect(sector_config, run_settings)
                rss_c = sum(1 for a in articles if a.get("type") == "rss")
                web_c = sum(1 for a in articles if a.get("type") == "web")
                st.write(f"✅ **{len(articles)} articles collectés** — RSS : {rss_c} · Web : {web_c}")
            except Exception as e:
                status.update(label="❌ Erreur collecte", state="error")
                st.error(f"Erreur lors de la collecte : {e}")
                st.stop()

            st.write("🧠 **Étape 2/3** — Benchmark avec Claude (3 appels, ~5-6 min)…")
            _step_placeholder = st.empty()
            def _progress(step, total, msg):
                _step_placeholder.caption(f"  ↳ {msg}")
            try:
                from agent import analyzer as ana_module
                analysis = ana_module.analyze(sector_config, articles, run_settings,
                                              progress_callback=_progress)
                _step_placeholder.empty()
                nb_fcs  = len(analysis.get("facteurs_cles_succes", []))
                nb_sig  = len(analysis.get("signaux_faibles", []))
                nb_rec  = len(analysis.get("recommandations", []))
                nb_src  = len(analysis.get("index_sources", []))
                fiab    = analysis.get("qualite_sources", {}).get("fiabilite_globale", "—")
                st.write(
                    f"✅ **Benchmark produit** — {nb_fcs} FCS · {nb_sig} signaux · "
                    f"{nb_rec} recommandations · {nb_src} sources · Fiabilité : **{fiab}**"
                )
            except Exception as e:
                status.update(label="❌ Erreur analyse", state="error")
                st.error(f"Erreur lors de l'analyse Claude : {e}")
                st.stop()

            st.write("📝 **Étape 3/3** — Génération des rapports…")
            try:
                from agent import reporter as rep_module
                files = rep_module.generate_reports(analysis, run_settings, str(ROOT))
                for f in files:
                    st.write(f"  📄 `{Path(f).name}`")
            except Exception as e:
                status.update(label="❌ Erreur rapport", state="error")
                st.error(f"Erreur lors de la génération du rapport : {e}")
                st.stop()

            status.update(label="✅ Analyse terminée avec succès !", state="complete")

        st.success(f"Rapports générés le {datetime.now().strftime('%d/%m/%Y à %H:%M')}")
        mime_map = {
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".html": "text/html",
            ".pdf":  "application/pdf",
        }
        icons = {".docx": "📄", ".html": "🌐", ".pdf": "📕"}
        cols = st.columns(len(files)) if files else []
        for i, fpath in enumerate(files):
            p = Path(fpath)
            with open(fpath, "rb") as fp:
                data = fp.read()
            col = cols[i] if cols else st
            col.download_button(
                label=f"{icons.get(p.suffix, '📎')} {p.suffix.upper().lstrip('.')}",
                data=data,
                file_name=p.name,
                mime=mime_map.get(p.suffix, "application/octet-stream"),
                use_container_width=True,
            )


# ═══════════════════════════════════════════════════════════════════════════════
# ONGLET 2 — BENCHMARK MISSION
# ═══════════════════════════════════════════════════════════════════════════════
with tab_mission:
    st.header("🎯 Benchmark Mission — Consultant RH")
    st.caption("Générez un benchmark stratégique personnalisé pour votre mission, livré en PPT LMS.")

    # ── Formulaire de configuration ──
    with st.form("form_mission"):
        st.subheader("Configuration de la mission")

        col1, col2 = st.columns(2)
        with col1:
            nom_mission = st.text_input("Nom de la mission *", placeholder="Ex: Diagnostic RH — BEL Groupe")
            entreprise_cible = st.text_input("Entreprise / Acteur cible *", placeholder="Ex: BEL Groupe, OCP, Marjane…")
            secteur_mission = st.selectbox("Secteur d'activité *", [
                "Agroalimentaire", "Industrie & Manufacturing", "Banque & Finance",
                "Assurance", "Santé & Pharma", "Retail & Distribution",
                "Telecom & Digital", "Énergie & Utilities", "Immobilier & BTP",
                "Transport & Logistique", "Secteur Public & Parapublic", "Autre",
            ])
            geographie = st.selectbox("Géographie prioritaire *", [
                "Maroc", "Maroc & MENA", "Afrique francophone", "France & Europe", "International",
            ])
        with col2:
            mode_analyse = st.radio("Mode d'analyse", ["Rapide (~2 min)", "Approfondi (~6 min)"],
                                    horizontal=True,
                                    help="Rapide : 1 appel LLM, axes fixes. Approfondi : 3 appels, benchmark complet avec chiffres et entreprises nommées.")
            periode = st.selectbox("Période d'analyse",
                ["3 derniers mois", "6 derniers mois", "12 derniers mois", "24 derniers mois"],
                index=1)

        angle_strategique = st.text_area(
            "Angle stratégique RH * (3-4 phrases)",
            placeholder=(
                "Décrivez la question centrale de votre mission.\n"
                "Ex : Comment BEL Groupe structure-t-il ses équipes RH pour accompagner son expansion "
                "en Afrique ? Quelles compétences clés sont en tension ?"
            ),
            max_chars=600, height=110
        )
        concurrent_reference = st.text_input(
            "Concurrent ou référence sectorielle à comparer (optionnel)",
            placeholder="Ex : Nestlé Maroc, Danone, Label'Vie, SABIC…"
        )

        st.markdown("**Sources prioritaires** (optionnel)")
        src_cols = st.columns(3)
        sources_cochees = []
        sources_dispo = [
            ("presse_sectorielle", "Presse sectorielle"),
            ("publications_academiques", "Publications & études"),
            ("rapports_annuels", "Rapports annuels"),
            ("linkedin", "LinkedIn & réseaux pro"),
            ("offres_emploi", "Offres d'emploi"),
            ("sources_arabophones", "Sources arabophones"),
        ]
        for i, (key, label) in enumerate(sources_dispo):
            with src_cols[i % 3]:
                if st.checkbox(label, key=f"src_{key}"):
                    sources_cochees.append(key)

        st.markdown("**Slides thématiques optionnelles**")
        sl_cols = st.columns(4)
        slides_cochees = []
        slides_dispo = [
            ("effectifs_dimensionnement", "Effectifs & dimensionnement"),
            ("recrutement_talent", "Recrutement & talent"),
            ("formation_competences", "Formation & compétences"),
            ("culture_engagement", "Culture & engagement"),
            ("remuneration_social", "Rémunération & social"),
            ("sirh_digitalisation", "SIRH & digitalisation RH"),
            ("diversite_inclusion", "Diversité & inclusion"),
            ("relations_sociales", "Relations sociales"),
        ]
        for i, (key, label) in enumerate(slides_dispo):
            with sl_cols[i % 4]:
                if st.checkbox(label, key=f"sl_{key}"):
                    slides_cochees.append(key)

        submitted = st.form_submit_button("▶ Générer le benchmark mission", type="primary", use_container_width=True)

    if submitted:
        # Validation
        if not nom_mission or not entreprise_cible or not angle_strategique:
            st.error("⚠️ Les champs Nom de la mission, Entreprise cible et Angle stratégique RH sont obligatoires.")
            st.stop()

        mission_config = {
            "nom_mission": nom_mission,
            "entreprise_cible": entreprise_cible,
            "secteur": secteur_mission,
            "geographie": geographie,
            "angle_strategique_rh": angle_strategique,
            "concurrent_reference": concurrent_reference,
            "periode": periode,
            "mode": "Rapide" if "Rapide" in mode_analyse else "Approfondi",
            "sources": sources_cochees,
            "slides_optionnelles": slides_cochees,
        }

        # Réinitialiser les résultats précédents
        st.session_state.pop("mission_result", None)

        settings_m = load_settings()
        sectors_m = load_sectors()
        secteur_map = {
            "Pharma": "pharma_maroc", "Banque": "banque_finance",
            "Industrie": "industrie", "Santé": "sante",
            "Telecom": "telecom_maroc", "Agroalimentaire": "agroalimentaire_maroc",
            "Retail": "distribution_maroc",
        }
        sector_key_m = secteur_map.get(secteur_mission, list(sectors_m.keys())[0])
        sector_config_m = {**sectors_m[sector_key_m], "key": sector_key_m}

        with st.status("⏳ Génération du benchmark mission…", expanded=True) as status_m:

            st.write("🔎 **Étape 1/3** — Collecte des sources…")
            try:
                from agent import collector as col_m
                articles_m = col_m.collect(sector_config_m, settings_m)
                st.write(f"✅ **{len(articles_m)} articles collectés**")
            except Exception as e:
                status_m.update(label="❌ Erreur collecte", state="error")
                st.error(f"Erreur collecte : {e}")
                st.stop()

            st.write(f"🧠 **Étape 2/3** — Analyse Claude ({mission_config['mode']})…")
            _ph = st.empty()
            def _prog_m(step, total, msg): _ph.caption(f"  ↳ {msg}")
            try:
                from agent import analyzer_mission as am
                analysis_m = am.analyze_mission(mission_config, articles_m, settings_m, _prog_m)
                _ph.empty()
                nb_rec_m = len(analysis_m.get("recommandations_mission", []))
                st.write(f"✅ **Benchmark produit** — {nb_rec_m} recommandations · {len(analysis_m.get('signaux_faibles', []))} signaux")
            except Exception as e:
                status_m.update(label="❌ Erreur analyse", state="error")
                st.error(f"Erreur analyse : {e}")
                import traceback; st.code(traceback.format_exc())
                st.stop()

            st.write("📊 **Étape 3/3** — Génération PPT LMS…")
            try:
                import ppt_generator as pptgen
                from datetime import datetime as _dt
                ppt_name = f"Benchmark_LMS_{entreprise_cible.replace(' ', '_')}_{_dt.now().strftime('%Y-%m-%d')}.pptx"
                ppt_path = str(ROOT / "reports" / ppt_name)
                pptgen.generate_lms_ppt(analysis_m, mission_config, ppt_path)
                # Sauvegarder JSON mission
                import json as _json
                json_m_path = ppt_path.replace(".pptx", ".json")
                with open(json_m_path, "w", encoding="utf-8") as fp:
                    _json.dump({**analysis_m, "_mission_config": mission_config}, fp, ensure_ascii=False, indent=2)
                st.write(f"  📊 `{ppt_name}`")
                # Stocker dans session_state pour survivre au rerun
                st.session_state["mission_result"] = {
                    "ppt_path": ppt_path,
                    "ppt_name": ppt_name,
                    "json_path": json_m_path,
                    "nb_slides_opt": len(slides_cochees),
                }
            except ImportError:
                status_m.update(label="❌ python-pptx manquant", state="error")
                st.error("python-pptx non installé. Exécutez : pip install python-pptx")
                st.stop()
            except Exception as e:
                status_m.update(label="❌ Erreur PPT", state="error")
                st.error(f"Erreur génération PPT : {e}")
                import traceback; st.code(traceback.format_exc())
                st.stop()

            status_m.update(label="✅ Benchmark mission généré !", state="complete")

    # ── Boutons téléchargement (persistent via session_state) ─────────────────
    if "mission_result" in st.session_state:
        res = st.session_state["mission_result"]
        nb_opt = res["nb_slides_opt"]
        st.success(f"✅ Présentation générée — 7 slides fixes + {nb_opt} slide(s) optionnelle(s) = {7 + nb_opt} slides au total")
        dl_cols = st.columns(2)
        with dl_cols[0]:
            with open(res["ppt_path"], "rb") as fp:
                st.download_button(
                    "📊 Télécharger le PPT LMS",
                    data=fp.read(),
                    file_name=res["ppt_name"],
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    use_container_width=True,
                    type="primary",
                )
        with dl_cols[1]:
            with open(res["json_path"], "rb") as fp:
                st.download_button(
                    "📋 Données JSON",
                    data=fp.read(),
                    file_name=res["ppt_name"].replace(".pptx", ".json"),
                    mime="application/json",
                    use_container_width=True,
                )


# ═══════════════════════════════════════════════════════════════════════════════
# ONGLET 3 — RAPPORTS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_reports:
    st.header("Rapports générés")

    settings = load_settings()
    reports_dir = ROOT / settings.get("reporting", {}).get("output_dir", "reports")
    reports_dir.mkdir(exist_ok=True)

    files = sorted(
        [f for f in reports_dir.iterdir() if f.suffix in (".docx", ".html", ".pdf")],
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )

    col_refresh, _ = st.columns([1, 5])
    with col_refresh:
        if st.button("🔄 Actualiser", use_container_width=True):
            st.rerun()

    if not files:
        st.info("Aucun rapport généré. Lancez une analyse dans le premier onglet.")
    else:
        groups: dict[str, list] = {}
        for f in files:
            groups.setdefault(f.stem, []).append(f)

        st.caption(f"{len(groups)} analyse(s) · {len(files)} fichier(s)")
        st.markdown("---")

        mime_map = {
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".html": "text/html",
            ".pdf":  "application/pdf",
        }
        icons = {".docx": "📄 Word", ".html": "🌐 HTML", ".pdf": "📕 PDF"}

        for base, group_files in groups.items():
            mtime = max(f.stat().st_mtime for f in group_files)
            date_str = datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M")
            with st.container():
                col_info, *col_btns = st.columns([3] + [1] * len(group_files))
                with col_info:
                    st.markdown(f"**{base}**")
                    st.caption(f"Généré le {date_str}")
                for i, f in enumerate(sorted(group_files, key=lambda x: x.suffix)):
                    with col_btns[i]:
                        with open(f, "rb") as fp:
                            data = fp.read()
                        st.download_button(
                            label=f"{icons.get(f.suffix, '📎')} ({len(data)//1024} KB)",
                            data=data,
                            file_name=f.name,
                            mime=mime_map.get(f.suffix, "application/octet-stream"),
                            use_container_width=True,
                            key=f"dl_{f.name}",
                        )
            st.markdown("---")


# ═══════════════════════════════════════════════════════════════════════════════
# ONGLET 3 — PLANIFICATION
# ═══════════════════════════════════════════════════════════════════════════════
with tab_planning:
    st.header("Planification automatique")

    settings = load_settings()
    sched = settings.get("scheduling", {})
    sectors = load_sectors()

    col_plan, col_status = st.columns([1, 1], gap="large")

    with col_plan:
        st.subheader("Configuration")

        enabled = st.toggle("Activer la planification mensuelle", value=sched.get("enabled", True))

        sector_options = {k: v["label"] for k, v in sectors.items()}
        default_sector = settings.get("agent", {}).get("default_sector", list(sector_options.keys())[0])
        planned_sector = st.selectbox(
            "Secteur planifié",
            options=list(sector_options.keys()),
            format_func=lambda k: sector_options[k],
            index=list(sector_options.keys()).index(default_sector) if default_sector in sector_options else 0,
            key="plan_sector",
        )

        col_day, col_hour = st.columns(2)
        with col_day:
            day_of_month = st.number_input("Jour du mois", min_value=1, max_value=28,
                                           value=sched.get("day_of_month", 1))
        with col_hour:
            hour = st.number_input("Heure (0-23)", min_value=0, max_value=23, value=sched.get("hour", 8))

        if st.button("💾 Enregistrer la planification", type="primary", use_container_width=True):
            settings["scheduling"]["enabled"] = enabled
            settings["scheduling"]["day_of_month"] = int(day_of_month)
            settings["scheduling"]["hour"] = int(hour)
            settings["scheduling"]["minute"] = 0
            settings["agent"]["default_sector"] = planned_sector
            save_settings(settings)
            st.success("✅ Planification enregistrée")
            st.rerun()

    with col_status:
        st.subheader("Statut du scheduler")

        for key in ("scheduler_thread", "scheduler_running", "scheduler_log"):
            if key not in st.session_state:
                st.session_state[key] = None if key == "scheduler_thread" else (False if key == "scheduler_running" else [])

        is_running = (
            st.session_state.scheduler_thread is not None
            and st.session_state.scheduler_thread.is_alive()
        )

        if is_running:
            st.success("🟢 Scheduler actif")
            if st.button("⏹ Arrêter le scheduler", use_container_width=True):
                if "_scheduler_obj" in st.session_state:
                    try:
                        st.session_state._scheduler_obj.shutdown(wait=False)
                    except Exception:
                        pass
                st.session_state.scheduler_running = False
                st.rerun()
        else:
            st.warning("⚪ Scheduler inactif")
            start_btn = st.button("▶ Démarrer le scheduler", use_container_width=True)
            if start_btn:
                from apscheduler.schedulers.background import BackgroundScheduler
                from apscheduler.triggers.cron import CronTrigger

                s = load_settings()
                sc2 = s.get("scheduling", {})
                sec2 = load_sectors()

                def scheduled_job():
                    try:
                        from agent import collector, analyzer, reporter
                        sec_key = s.get("agent", {}).get("default_sector", "pharmaceutique")
                        arts = collector.collect(sec2.get(sec_key, {}), s)
                        ana  = analyzer.analyze(sec2.get(sec_key, {}), arts, s)
                        reporter.generate_reports(ana, s, str(ROOT))
                        msg = f"[{datetime.now().strftime('%d/%m %H:%M')}] ✅ Analyse {sec_key} terminée"
                    except Exception as e:
                        msg = f"[{datetime.now().strftime('%d/%m %H:%M')}] ❌ Erreur : {e}"
                    st.session_state.scheduler_log.append(msg)

                scheduler = BackgroundScheduler(timezone="Europe/Paris")
                scheduler.add_job(
                    scheduled_job,
                    CronTrigger(day=sc2.get("day_of_month", 1), hour=sc2.get("hour", 8), minute=0),
                    id="veille_auto", replace_existing=True,
                )
                scheduler.start()
                st.session_state._scheduler_obj = scheduler
                st.session_state.scheduler_running = True

                next_job = scheduler.get_job("veille_auto")
                if next_job and next_job.next_run_time:
                    st.session_state.scheduler_log.append(
                        f"[{datetime.now().strftime('%d/%m %H:%M')}] ▶ Démarré — "
                        f"Prochain run : {next_job.next_run_time.strftime('%d/%m/%Y à %H:%M')}"
                    )
                st.rerun()

        if is_running and "_scheduler_obj" in st.session_state:
            job = st.session_state._scheduler_obj.get_job("veille_auto")
            if job and job.next_run_time:
                st.info(f"⏰ Prochain run : **{job.next_run_time.strftime('%d/%m/%Y à %H:%M')}**")

        if st.session_state.get("scheduler_log"):
            st.markdown("**Journal :**")
            for msg in reversed(st.session_state.scheduler_log[-10:]):
                st.caption(msg)

    st.markdown("---")
    st.info("💡 Le scheduler tourne tant que cette fenêtre est ouverte. Pour une exécution permanente, utilisez `python main.py schedule` en ligne de commande.")


# ═══════════════════════════════════════════════════════════════════════════════
# ONGLET 4 — PARAMÈTRES
# ═══════════════════════════════════════════════════════════════════════════════
with tab_config:
    st.header("Paramètres de l'agent")

    settings = load_settings()

    col_ana, col_col, col_rep = st.columns(3, gap="large")

    with col_ana:
        st.subheader("🧠 Analyse")
        model_options = ["claude-sonnet-4-6", "claude-opus-4-5", "claude-haiku-4-5"]
        current_model = settings.get("analysis", {}).get("model", "claude-sonnet-4-6")
        model = st.selectbox(
            "Modèle Claude",
            options=model_options,
            index=model_options.index(current_model) if current_model in model_options else 0,
        )
        st.caption("Sonnet : équilibre qualité/coût · Opus : qualité max · Haiku : rapide")
        max_tokens = st.slider(
            "Tokens max par appel",
            min_value=2048, max_value=8192, step=1024,
            value=settings.get("analysis", {}).get("max_tokens", 8192),
        )

    with col_col:
        st.subheader("🔎 Collecte")
        days_back = st.slider("Jours en arrière (RSS)", 7, 90, step=7,
                              value=settings.get("collection", {}).get("days_back", 35))
        max_search = st.slider("Résultats max / requête web", 3, 15,
                               value=settings.get("collection", {}).get("max_search_results", 8))
        max_articles = st.slider("Articles max envoyés à Claude", 20, 100, step=10,
                                 value=settings.get("collection", {}).get("max_articles_total", 60))

    with col_rep:
        st.subheader("📝 Rapports")
        formats_cfg = settings.get("reporting", {}).get("formats", ["docx", "html"])
        fmt_docx = st.checkbox("Word (.docx)", value="docx" in formats_cfg)
        fmt_html = st.checkbox("HTML (.html)", value="html" in formats_cfg)
        fmt_pdf  = st.checkbox("PDF (.pdf — nécessite weasyprint)", value="pdf" in formats_cfg)
        if fmt_pdf:
            st.caption("⚠️ PDF requiert : `pip install weasyprint`")

    st.markdown("---")
    if st.button("💾 Enregistrer les paramètres", type="primary"):
        settings["analysis"]["model"] = model
        settings["analysis"]["max_tokens"] = int(max_tokens)
        settings["collection"]["days_back"] = int(days_back)
        settings["collection"]["max_search_results"] = int(max_search)
        settings["collection"]["max_articles_total"] = int(max_articles)
        new_formats = []
        if fmt_docx: new_formats.append("docx")
        if fmt_html: new_formats.append("html")
        if fmt_pdf:  new_formats.append("pdf")
        settings["reporting"]["formats"] = new_formats
        save_settings(settings)
        st.success("✅ Paramètres enregistrés")
        st.rerun()

    st.markdown("---")
    st.subheader("🗂 Secteurs configurés")
    sectors = load_sectors()
    for key, sc in sectors.items():
        with st.expander(f"**{sc['label']}** — `{key}`"):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Flux RSS :**")
                for f in sc.get("rss_feeds", []):
                    st.caption(f"• {f['name']}")
            with col2:
                st.markdown("**Axes analysés :**")
                for a in sc.get("focus_areas", sc.get("benchmark_axes", []))[:6]:
                    st.caption(f"• {a.split(':')[0].strip()[:70]}")


# ═══════════════════════════════════════════════════════════════════════════════
# ONGLET 5 — GESTION DES UTILISATEURS (admin uniquement)
# ═══════════════════════════════════════════════════════════════════════════════
if tab_admin is not None:
    with tab_admin:
        st.header("Gestion des utilisateurs")
        st.caption("Accessible uniquement aux administrateurs.")

        users_cfg = load_users_config()
        usernames = users_cfg["credentials"]["usernames"]

        # ── Liste des utilisateurs ──
        st.subheader("Comptes actifs")
        col_h1, col_h2, col_h3, col_h4 = st.columns([2, 2, 1, 1])
        col_h1.markdown("**Identifiant**")
        col_h2.markdown("**Nom**")
        col_h3.markdown("**Email**")
        col_h4.markdown("**Rôle**")
        st.markdown("---")

        for uname, udata in usernames.items():
            c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
            c1.code(uname)
            c2.write(udata.get("name", "—"))
            c3.caption(udata.get("email", "—"))
            role_badge = "🔴 Admin" if udata.get("role") == "admin" else "🔵 User"
            c4.write(role_badge)

        st.markdown("---")

        # ── Ajouter un utilisateur ──
        st.subheader("Ajouter un utilisateur")
        with st.form("add_user_form"):
            col_a, col_b = st.columns(2)
            with col_a:
                new_username = st.text_input("Identifiant (ex: prenom.nom)", placeholder="marie.dupont")
                new_name     = st.text_input("Nom complet", placeholder="Marie Dupont")
            with col_b:
                new_email    = st.text_input("Email", placeholder="marie.dupont@lms-orh.com")
                new_role     = st.selectbox("Rôle", ["user", "admin"])
            new_password = st.text_input("Mot de passe", type="password",
                                         help="Min. 8 caractères, avec majuscule et chiffre")
            submitted = st.form_submit_button("➕ Ajouter l'utilisateur", type="primary")

            if submitted:
                if not all([new_username, new_name, new_email, new_password]):
                    st.error("Tous les champs sont obligatoires.")
                elif new_username in usernames:
                    st.error(f"L'identifiant `{new_username}` existe déjà.")
                elif len(new_password) < 8:
                    st.error("Le mot de passe doit contenir au moins 8 caractères.")
                else:
                    import bcrypt
                    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
                    usernames[new_username] = {
                        "name": new_name,
                        "email": new_email,
                        "password": hashed,
                        "role": new_role,
                    }
                    users_cfg["credentials"]["usernames"] = usernames
                    save_users_config(users_cfg)
                    st.success(f"✅ Utilisateur **{new_name}** ajouté avec succès.")
                    st.rerun()

        # ── Supprimer un utilisateur ──
        st.markdown("---")
        st.subheader("Supprimer un utilisateur")
        other_users = [u for u in usernames if u != current_username]
        if other_users:
            del_user = st.selectbox("Sélectionner l'utilisateur à supprimer", other_users,
                                    format_func=lambda u: f"{usernames[u]['name']} ({u})")
            if st.button("🗑 Supprimer cet utilisateur", type="secondary"):
                del usernames[del_user]
                users_cfg["credentials"]["usernames"] = usernames
                save_users_config(users_cfg)
                st.success(f"Utilisateur `{del_user}` supprimé.")
                st.rerun()
        else:
            st.info("Aucun autre utilisateur à supprimer.")
