"""
Générateur de présentations PowerPoint LMS ORH.
Utilise python-pptx pour créer un benchmark RH mission au format LMS.

Fonction principale : generate_lms_ppt(analysis, mission_config, output_path) -> str
"""
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

try:
    from pptx import Presentation
    from pptx.util import Cm, Pt, Emu
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Inches
except ImportError as _e:
    raise ImportError(
        "python-pptx n'est pas installé. Exécutez : pip install python-pptx>=1.0.0"
    ) from _e

# ─────────────────────────────────────────────────────────────────────────────
#  CONSTANTES VISUELLES LMS ORH
# ─────────────────────────────────────────────────────────────────────────────
BORDEAUX = RGBColor(139, 26, 26)      # #8B1A1A
BORDEAUX_CLAIR = RGBColor(200, 170, 170)  # texte secondaire sur fond bordeaux
GRIS_FONCE = RGBColor(45, 45, 45)    # #2D2D2D
GRIS_CLAIR = RGBColor(245, 245, 245) # #F5F5F5
GRIS_SEP = RGBColor(229, 229, 229)   # #E5E5E5 — séparateur vertical
BLANC = RGBColor(255, 255, 255)
VERT_KPI = RGBColor(39, 174, 96)     # #27AE62
POLICE = "Arial"

# Dimensions layout slides de contenu
HEADER_H = Cm(2.4)     # 12.6% de 19.05cm — bandeau titre bordeaux
FOOTER_H = Cm(2.5)     # 13.1% de 19.05cm — bandeau footer bordeaux (so what + confidentiel)
BAR_V_W  = Cm(0.18)    # barre verticale bordeaux gauche (~6px)

# Dimensions 16:9 widescreen
SLIDE_W = Cm(33.87)
SLIDE_H = Cm(19.05)

# Assets — cherche plusieurs variantes de noms de fichiers
_HERE = Path(__file__).parent
_ASSETS = _HERE / "assets"

def _find_asset(*candidates) -> Path | None:
    for name in candidates:
        p = _ASSETS / name
        if p.exists():
            return p
    return None

LOGO_PATH   = _find_asset("logo_lms.png", "Logo LMS.png", "logo_lms.jpg", "Logo LMS.jpg")
MOSAIC_PATH = _find_asset("mosaic_lms.jpg", "mosaic_lms.png", "photo mosaïque.png",
                           "photo mosaique.png", "mosaic_lms.png")


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _add_rect(slide, left, top, width, height, fill_color=None, line_color=None):
    """Ajoute un rectangle coloré."""
    shape = slide.shapes.add_shape(
        1,  # MSO_SHAPE_TYPE.RECTANGLE
        left, top, width, height
    )
    if fill_color:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill_color
    else:
        shape.fill.background()
    if line_color:
        shape.line.color.rgb = line_color
    else:
        shape.line.fill.background()
    return shape


def _as_dict(val) -> dict:
    """Retourne val si c'est un dict, sinon {} — protège contre un LLM qui renvoie une string."""
    return val if isinstance(val, dict) else {}


def _as_list(val) -> list:
    """Retourne val si c'est une list, sinon [] — protège contre un LLM qui renvoie autre chose."""
    return val if isinstance(val, list) else []


def _clean_slide_text(text: str) -> str:
    """Nettoie le texte avant affichage PPT : supprime marqueurs internes et citations."""
    import re
    # Marqueurs de certitude internes (jamais visibles dans un livrable client)
    text = re.sub(r'\[confirm[eé]\]|\[probable\]|\[[àa]\s*v[eé]rifier\]', '', text, flags=re.IGNORECASE)
    # Citations numériques [N] ou groupes [N][M]
    text = re.sub(r'(\[\d+\])+', '', text)
    # Espaces parasites avant ponctuation (après suppression des [N])
    text = re.sub(r'\s+([.,;:!?])', r'\1', text)
    # Doubles espaces et sauts de ligne excessifs
    text = re.sub(r'  +', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _add_textbox(slide, left, top, width, height, text, font_size=12, bold=False,
                 color=None, align=PP_ALIGN.LEFT, wrap=True):
    """Ajoute une zone de texte simple."""
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = wrap
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.name = POLICE
    run.font.size = Pt(font_size)
    run.font.bold = bold
    if color:
        run.font.color.rgb = color
    return txBox


def _set_rect_text(shape, text, font_size=12, bold=False, color=None,
                   align=PP_ALIGN.LEFT, word_wrap=True):
    """Insère du texte dans un rectangle (shape avec text_frame)."""
    tf = shape.text_frame
    tf.word_wrap = word_wrap
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.name = POLICE
    run.font.size = Pt(font_size)
    run.font.bold = bold
    if color:
        run.font.color.rgb = color


def _add_bullet_textbox(slide, left, top, width, height, items, font_size=10,
                        color=None, title=None, title_size=11):
    """Ajoute une zone de texte avec liste à puces."""
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    first = True
    if title:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        run = p.add_run()
        run.text = title
        run.font.name = POLICE
        run.font.size = Pt(title_size)
        run.font.bold = True
        if color:
            run.font.color.rgb = color
    for item in items:
        p = tf.paragraphs[0] if (first and not title) else tf.add_paragraph()
        first = False
        p.level = 1
        run = p.add_run()
        run.text = f"• {item}"
        run.font.name = POLICE
        run.font.size = Pt(font_size)
        if color:
            run.font.color.rgb = color
    return txBox


def _content_slide(prs, titre, col_gauche_text, col_droite_text, so_what_text,
                   mission_config, col_gauche_items=None, titre_droite=None):
    """
    Slide de contenu standard — layout LMS ORH :
    ┌──────────────────────────────────────────┐
    │ HEADER BORDEAUX (2.4cm) — titre slide    │
    ├─┬────────────────────┬───────────────────┤
    │▌│ Colonne gauche 57% │ Colonne droite 38%│  ← fond blanc, barre bordeaux 6px gauche
    │ │                    │   séparateur gris │
    ├─┴────────────────────┴───────────────────┤
    │ FOOTER BORDEAUX (2.5cm)                  │
    │  So what ? pour [entreprise] :  [texte]  │
    │  Confidentiel — [mission] · LMS ORH      │
    └──────────────────────────────────────────┘
    """
    # Nettoyage : supprime [confirmé]/[probable]/[à vérifier] et citations [N]
    col_gauche_text = _clean_slide_text(col_gauche_text or "")
    col_droite_text = _clean_slide_text(col_droite_text or "")
    so_what_text    = _clean_slide_text(so_what_text or "")
    if col_gauche_items:
        col_gauche_items = [_clean_slide_text(i) for i in col_gauche_items]

    nom_mission = mission_config.get("nom_mission", "Mission")
    entreprise_cible = mission_config.get("entreprise_cible", "Entreprise")

    slide_layout = prs.slide_layouts[6]  # blank
    slide = prs.slides.add_slide(slide_layout)
    sp_tree = slide.shapes._spTree
    if len(sp_tree) > 2:
        sp_tree.remove(sp_tree[2])

    # ── HEADER bordeaux ─────────────────────────────────────────────────────
    _add_rect(slide, Cm(0), Cm(0), SLIDE_W, HEADER_H, fill_color=BORDEAUX)
    _add_textbox(
        slide, Cm(0.5), Cm(0.3), SLIDE_W - Cm(1.0), HEADER_H - Cm(0.3),
        titre, font_size=18, bold=True, color=BLANC,
    )

    # ── ZONE CONTENU — fond blanc explicite ─────────────────────────────────
    content_top = HEADER_H
    content_h = SLIDE_H - HEADER_H - FOOTER_H
    _add_rect(slide, Cm(0), content_top, SLIDE_W, content_h, fill_color=BLANC)

    # Barre bordeaux verticale gauche (mince, ~6px)
    _add_rect(slide, Cm(0), content_top, BAR_V_W, content_h, fill_color=BORDEAUX)

    # Layout 2 colonnes
    col_left_x = BAR_V_W + Cm(0.35)
    col_l_w    = SLIDE_W * 0.555
    sep_x      = col_left_x + col_l_w + Cm(0.2)
    col_r_x    = sep_x + Cm(0.2)
    col_r_w    = SLIDE_W - col_r_x - Cm(0.3)
    content_inner_h = content_h - Cm(0.3)

    # Séparateur vertical gris clair
    _add_rect(slide, sep_x, content_top + Cm(0.2), Cm(0.05), content_h - Cm(0.4), fill_color=GRIS_SEP)

    # Titre colonne gauche (en bordeaux, Arial 11pt bold)
    titre_g = "Analyse" if not col_gauche_items else "Observations clés"
    _add_textbox(
        slide, col_left_x, content_top + Cm(0.2), col_l_w, Cm(0.55),
        titre_g, font_size=11, bold=True, color=BORDEAUX,
    )
    col_g_top = content_top + Cm(0.85)
    col_g_h   = content_inner_h - Cm(0.85)

    if col_gauche_items:
        _add_bullet_textbox(
            slide, col_left_x, col_g_top, col_l_w, col_g_h,
            col_gauche_items, font_size=10, color=GRIS_FONCE,
            title=col_gauche_text, title_size=10,
        )
    else:
        _add_textbox(
            slide, col_left_x, col_g_top, col_l_w, col_g_h,
            col_gauche_text, font_size=10, color=GRIS_FONCE,
        )

    # Titre colonne droite
    t_droite = titre_droite or "Benchmark sectoriel"
    _add_textbox(
        slide, col_r_x, content_top + Cm(0.2), col_r_w, Cm(0.55),
        t_droite, font_size=11, bold=True, color=BORDEAUX,
    )
    _add_textbox(
        slide, col_r_x, content_top + Cm(0.85), col_r_w, content_inner_h - Cm(0.85),
        col_droite_text, font_size=10, color=GRIS_FONCE,
    )

    # ── FOOTER bordeaux — So what ? + confidentiel ──────────────────────────
    footer_top = SLIDE_H - FOOTER_H
    _add_rect(slide, Cm(0), footer_top, SLIDE_W, FOOTER_H, fill_color=BORDEAUX)

    # Ligne 1 — So what ?
    sw_h = Cm(1.4)
    _add_textbox(
        slide, Cm(0.4), footer_top + Cm(0.1), SLIDE_W - Cm(0.5), sw_h,
        f"▶ So what ? pour {entreprise_cible} : {so_what_text}",
        font_size=10, bold=False, color=BLANC,
    )

    # Ligne 2 — Confidentiel + logo zone
    conf_top = footer_top + sw_h + Cm(0.05)
    conf_h   = FOOTER_H - sw_h - Cm(0.1)
    _add_textbox(
        slide, Cm(0.4), conf_top, SLIDE_W * 0.7, conf_h,
        f"Confidentiel — {nom_mission}  ·  LMS ORH",
        font_size=8, color=BORDEAUX_CLAIR,
    )

    # Logo LMS dans footer (à droite)
    if LOGO_PATH:
        try:
            logo_w  = Cm(3.2)
            logo_h  = Cm(1.0)
            logo_left = SLIDE_W - logo_w - Cm(0.3)
            logo_top  = footer_top + (FOOTER_H - logo_h) / 2
            slide.shapes.add_picture(str(LOGO_PATH), logo_left, logo_top, logo_w, logo_h)
        except Exception:
            pass

    return slide


# ─────────────────────────────────────────────────────────────────────────────
#  SLIDES SPÉCIFIQUES
# ─────────────────────────────────────────────────────────────────────────────

def _slide_cover(prs, analysis, mission_config):
    """
    Slide 1 — Couverture
    ┌──────────────────┬───────────────────────────────────┐
    │  Mosaïque LMS    │  BENCHMARK RH  (BORDEAUX bold)    │
    │  (35% largeur)   │  Nom de la mission                │
    │  fond bordeaux   │  Entreprise cible  (bordeaux)     │
    │  si pas d'image  │  Secteur | Géographie  (gris)     │
    │                  │  Date                             │
    │                  │  [Logo LMS]                       │
    └──────────────────┴───────────────────────────────────┘
    """
    nom_mission = mission_config.get("nom_mission", "Mission RH")
    entreprise_cible = mission_config.get("entreprise_cible", "Entreprise")
    secteur = mission_config.get("secteur", "")
    geographie = mission_config.get("geographie", "")
    concurrent = mission_config.get("concurrent_reference", "") or ""

    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)

    # ── Panneau gauche 35% ───────────────────────────────────────────────────
    panneau_w = SLIDE_W * 0.35   # ~11.85cm
    _add_rect(slide, Cm(0), Cm(0), panneau_w, SLIDE_H, fill_color=BORDEAUX)

    if MOSAIC_PATH:
        try:
            slide.shapes.add_picture(str(MOSAIC_PATH), Cm(0), Cm(0), panneau_w, SLIDE_H)
        except Exception:
            pass

    # Bandeau bordeaux semi-transparent en bas du panneau gauche (sur mosaïque)
    _add_rect(slide, Cm(0), SLIDE_H - Cm(2.5), panneau_w, Cm(2.5), fill_color=BORDEAUX)
    _add_textbox(
        slide, Cm(0.3), SLIDE_H - Cm(2.3), panneau_w - Cm(0.4), Cm(2.0),
        "LMS ORH", font_size=14, bold=True, color=BLANC, align=PP_ALIGN.CENTER,
    )

    # ── Zone droite fond blanc ───────────────────────────────────────────────
    right_x = panneau_w + Cm(0.1)
    right_w = SLIDE_W - right_x - Cm(0.5)
    _add_rect(slide, panneau_w, Cm(0), SLIDE_W - panneau_w, SLIDE_H, fill_color=BLANC)

    # Type de livrable (petite étiquette bordeaux)
    _bench_type_label = mission_config.get("type", "RH").upper()
    _add_textbox(
        slide, right_x, Cm(1.5), right_w, Cm(0.7),
        f"BENCHMARK {_bench_type_label} — MISSION CONSULTANT",
        font_size=10, bold=True, color=BORDEAUX,
    )

    # Titre mission (Arial Black 24pt)
    _add_textbox(
        slide, right_x, Cm(2.5), right_w, Cm(2.2),
        nom_mission, font_size=24, bold=True, color=GRIS_FONCE,
    )

    # Entreprise cible (bordeaux, 20pt)
    _add_textbox(
        slide, right_x, Cm(5.0), right_w, Cm(1.3),
        entreprise_cible, font_size=20, bold=True, color=BORDEAUX,
    )

    # Secteur | Géographie
    sect_geo = f"{secteur}  |  {geographie}" if geographie else secteur
    _add_textbox(
        slide, right_x, Cm(6.5), right_w, Cm(0.8),
        sect_geo, font_size=12, bold=False, color=GRIS_FONCE,
    )

    # Référence comparative (si renseignée)
    if concurrent:
        _add_textbox(
            slide, right_x, Cm(7.5), right_w, Cm(0.7),
            f"Référence : {concurrent}", font_size=11, bold=False, color=RGBColor(100, 100, 100),
        )
        date_top = Cm(8.4)
    else:
        date_top = Cm(7.5)

    # Date
    date_str = datetime.now().strftime("%d %B %Y")
    _add_textbox(
        slide, right_x, date_top, right_w, Cm(0.7),
        date_str, font_size=11, bold=False, color=GRIS_FONCE,
    )

    # Mention confidentielle
    _add_textbox(
        slide, right_x, SLIDE_H - Cm(2.0), right_w, Cm(0.6),
        "Document confidentiel — LMS ORH",
        font_size=9, bold=False, color=RGBColor(150, 150, 150),
    )

    # Logo LMS
    if LOGO_PATH:
        try:
            logo_w = Cm(4.5)
            logo_h = Cm(1.8)
            slide.shapes.add_picture(
                str(LOGO_PATH),
                SLIDE_W - logo_w - Cm(0.5), SLIDE_H - logo_h - Cm(0.3),
                logo_w, logo_h,
            )
        except Exception:
            pass

    return slide


def _slide_contexte(prs, analysis, mission_config):
    """Slide 2 — Contexte & Angle RH."""
    ctx = analysis.get("contexte_mission", {})
    texte = ctx.get("texte", "")
    angle = ctx.get("angle_rh", "")
    angle_strategique = mission_config.get("angle_strategique_rh", "")
    geographie = mission_config.get("geographie", "")
    concurrent = mission_config.get("concurrent_reference", "") or ""

    droite_parts = []
    if angle:
        droite_parts.append(f"Angle RH central :\n{angle}")
    if geographie:
        droite_parts.append(f"Périmètre géographique :\n{geographie}")
    if concurrent:
        droite_parts.append(f"Référence comparative :\n{concurrent}")
    droite_text = "\n\n".join(droite_parts) if droite_parts else angle

    so_what = (
        f"Question centrale : {angle_strategique}"
        if angle_strategique else angle or "Voir angle RH central."
    )
    return _content_slide(
        prs,
        titre="Contexte & Angle RH",
        col_gauche_text=texte,
        col_droite_text=droite_text,
        so_what_text=so_what,
        mission_config=mission_config,
        titre_droite="Cadrage de la mission",
    )


def _slide_business_model(prs, analysis, mission_config):
    """Slide 3 — Business Model — Lecture RH."""
    bm = _as_dict(analysis.get("business_model_rh"))
    analyse = bm.get("analyse", "")
    emergentes = _as_list(bm.get("competences_emergentes"))
    obsoletes = _as_list(bm.get("competences_obsoletes"))
    so_what = bm.get("so_what", "")

    col_g = analyse
    col_g_items = None
    if emergentes or obsoletes:
        col_g_items = (
            [f"[Émergentes] {c}" for c in emergentes]
            + [f"[Obsolètes] {c}" for c in obsoletes]
        )

    droite = "Compétences clés identifiées :\n"
    if emergentes:
        droite += "\nÉmergentes : " + " · ".join(emergentes[:4])
    if obsoletes:
        droite += "\n\nObsolètes : " + " · ".join(obsoletes[:4])

    return _content_slide(
        prs,
        titre="Business Model — Lecture RH",
        col_gauche_text=analyse,
        col_droite_text=droite,
        so_what_text=so_what,
        mission_config=mission_config,
        col_gauche_items=col_g_items if col_g_items else None,
    )


def _slide_organisation(prs, analysis, mission_config):
    """Slide 4 — Organisation & Dimensionnement."""
    org = _as_dict(analysis.get("organisation_dimensionnement"))
    return _content_slide(
        prs,
        titre="Organisation & Dimensionnement",
        col_gauche_text=org.get("analyse", ""),
        col_droite_text=(
            f"Tendances effectifs :\n{org.get('tendances_effectifs', '')}\n\n"
            f"Externalisation :\n{org.get('externalisation', '')}"
        ),
        so_what_text=org.get("so_what", ""),
        mission_config=mission_config,
        col_gauche_items=[f"• {r}" for r in _as_list(org.get("nouveaux_roles"))] or None,
    )


def _slide_gouvernance(prs, analysis, mission_config):
    """Slide 5 — Gouvernance RH & Management."""
    gov = _as_dict(analysis.get("gouvernance_rh"))
    return _content_slide(
        prs,
        titre="Gouvernance RH & Management",
        col_gauche_text=gov.get("analyse", ""),
        col_droite_text=(
            f"Instances RH :\n{gov.get('instances_rh', '')}\n\n"
            f"Politiques sociales :\n{gov.get('politiques_sociales', '')}\n\n"
            f"Conformité :\n{gov.get('conformite', '')}"
        ),
        so_what_text=gov.get("so_what", ""),
        mission_config=mission_config,
    )


def _slide_signaux_innovation(prs, analysis, mission_config):
    """Slide 6 — Signaux faibles & Innovations RH."""
    inn = _as_dict(analysis.get("innovation_manageriale"))
    signaux = _as_list(analysis.get("signaux_faibles"))

    signaux_text = ""
    for s in _as_list(signaux)[:3]:
        s = _as_dict(s)
        signaux_text += f"• {s.get('signal', '')} ({s.get('horizon', '')})\n"
        signaux_text += f"  → {s.get('implication_rh', '')}\n\n"

    pratiques = _as_list(inn.get("pratiques_differenciantes"))
    outils = _as_list(inn.get("outils_rh"))
    droite = ""
    if pratiques:
        droite += "Pratiques différenciantes :\n" + "\n".join(f"• {p}" for p in pratiques[:4])
    if outils:
        droite += "\n\nOutils RH :\n" + "\n".join(f"• {o}" for o in outils[:4])

    return _content_slide(
        prs,
        titre="Signaux faibles & Innovations RH",
        col_gauche_text=signaux_text or inn.get("analyse", ""),
        col_droite_text=droite or inn.get("experience_employe", ""),
        so_what_text=inn.get("so_what", ""),
        mission_config=mission_config,
    )


def _slide_modeles_csp(prs, analysis, mission_config):
    """Slide 3 Org — Modèles CSP comparables."""
    csp = _as_dict(analysis.get("modeles_csp"))
    structures = _as_list(csp.get("structures_types"))
    col_g_items = [f"• {s}" for s in structures] if structures else None
    droite = ""
    if csp.get("gouvernance_observee"):
        droite += f"Gouvernance observée :\n{csp['gouvernance_observee']}\n\n"
    if csp.get("perimetre_fonctionnel"):
        droite += f"Périmètre fonctionnel :\n{csp['perimetre_fonctionnel']}"
    return _content_slide(
        prs,
        titre="Modèles CSP — Benchmark comparatif",
        col_gauche_text=csp.get("analyse", ""),
        col_droite_text=droite,
        so_what_text=csp.get("so_what", ""),
        mission_config=mission_config,
        col_gauche_items=col_g_items,
    )


def _slide_processus_douaniers(prs, analysis, mission_config):
    """Slide 4 Org — Processus douaniers & import/export."""
    pd = _as_dict(analysis.get("processus_douaniers"))
    pratiques = _as_list(pd.get("bonnes_pratiques"))
    col_g_items = [f"• {p}" for p in pratiques] if pratiques else None
    outils = _as_list(pd.get("outils_systemes"))
    risques = _as_list(pd.get("risques_frequents"))
    droite = ""
    if outils:
        droite += "Outils & systèmes :\n" + "\n".join(f"• {o}" for o in outils[:4])
    if risques:
        droite += "\n\nRisques fréquents :\n" + "\n".join(f"• {r}" for r in risques[:3])
    return _content_slide(
        prs,
        titre="Processus douaniers — Best practices",
        col_gauche_text=pd.get("analyse", ""),
        col_droite_text=droite,
        so_what_text=pd.get("so_what", ""),
        mission_config=mission_config,
        col_gauche_items=col_g_items,
    )


def _slide_interface_filiale_siege(prs, analysis, mission_config):
    """Slide 5 Org — Interface filiale/siège."""
    iface = _as_dict(analysis.get("interface_filiale_siege"))
    return _content_slide(
        prs,
        titre="Interface Filiale / Siège",
        col_gauche_text=iface.get("analyse", ""),
        col_droite_text=(
            f"Modèles de délégation :\n{iface.get('modeles_delegation', '')}\n\n"
            f"Protocoles de validation :\n{iface.get('protocoles_validation', '')}\n\n"
            f"Reporting :\n{iface.get('reporting_type', '')}"
        ),
        so_what_text=iface.get("so_what", ""),
        mission_config=mission_config,
    )


def _slide_formalisation_audit(prs, analysis, mission_config):
    """Slide 6 Org — Formalisation & Audit-readiness + signaux faibles."""
    fau = _as_dict(analysis.get("formalisation_audit_readiness"))
    signaux = _as_list(analysis.get("signaux_faibles"))
    referentiels = _as_list(fau.get("referentiels_utilises"))
    criteres = _as_list(fau.get("criteres_audit_groupe"))
    col_g_items = (
        [f"Référentiel : {r}" for r in referentiels[:3]]
        + [f"Critère audit : {c}" for c in criteres[:3]]
    ) or None

    signaux_text = ""
    for s in signaux[:3]:
        s = _as_dict(s)
        signaux_text += f"• {s.get('signal', '')} ({s.get('horizon', '')})\n"
        impl = s.get("implication_organisationnelle") or s.get("implication_rh", "")
        if impl:
            signaux_text += f"  → {impl}\n\n"

    return _content_slide(
        prs,
        titre="Formalisation & Audit-readiness",
        col_gauche_text=fau.get("analyse", ""),
        col_droite_text=signaux_text or fau.get("niveaux_maturite", ""),
        so_what_text=fau.get("so_what", ""),
        mission_config=mission_config,
        col_gauche_items=col_g_items,
        titre_droite="Signaux faibles & maturité",
    )


def _slide_recommandations(prs, analysis, mission_config):
    """Slide 7 — Recommandations Mission (3 blocs côte à côte)."""
    nom_mission = mission_config.get("nom_mission", "Mission")
    entreprise_cible = mission_config.get("entreprise_cible", "Entreprise")
    recs = _as_list(analysis.get("recommandations_mission"))

    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)

    # ── Header bordeaux ──────────────────────────────────────────────────────
    _add_rect(slide, Cm(0), Cm(0), SLIDE_W, HEADER_H, fill_color=BORDEAUX)
    _add_textbox(
        slide, Cm(0.5), Cm(0.3), SLIDE_W - Cm(1), HEADER_H - Cm(0.3),
        "Recommandations Mission", font_size=18, bold=True, color=BLANC,
    )

    # Fond blanc zone contenu
    content_h_reco = SLIDE_H - HEADER_H - FOOTER_H
    _add_rect(slide, Cm(0), HEADER_H, SLIDE_W, content_h_reco, fill_color=BLANC)

    # 3 blocs côte à côte
    bloc_w = (SLIDE_W - Cm(2)) / 3
    gap = Cm(0.5)
    bloc_top = HEADER_H + Cm(0.4)
    bloc_h = content_h_reco - Cm(0.6)

    priorite_colors = {"Haute": BORDEAUX, "Moyenne": RGBColor(230, 126, 34), "Faible": GRIS_FONCE}

    for i, rec in enumerate(recs[:3]):
        rec = _as_dict(rec)
        left = Cm(0.5) + i * (bloc_w + gap)

        # Fond gris clair + bordure bordeaux gauche du bloc
        _add_rect(slide, left, bloc_top, bloc_w, bloc_h, fill_color=GRIS_CLAIR)
        _add_rect(slide, left, bloc_top, Cm(0.15), bloc_h, fill_color=BORDEAUX)

        # Numéro de reco
        _add_textbox(
            slide, left + Cm(0.35), bloc_top + Cm(0.15), bloc_w - Cm(0.5), Cm(0.6),
            f"RECOMMANDATION {i+1}", font_size=8, bold=True, color=BORDEAUX,
        )

        # Titre de la reco (bordeaux)
        action = rec.get("action", f"Recommandation {i+1}")
        _add_textbox(
            slide, left + Cm(0.35), bloc_top + Cm(0.75), bloc_w - Cm(0.5), Cm(1.8),
            action, font_size=11, bold=True, color=GRIS_FONCE,
        )

        # Justification
        justif = rec.get("justification", "")
        _add_textbox(
            slide, left + Cm(0.35), bloc_top + Cm(2.6), bloc_w - Cm(0.5), Cm(4.5),
            justif, font_size=9, color=GRIS_FONCE,
        )

        # Priorité
        priorite = rec.get("priorite", "Moyenne")
        p_color = priorite_colors.get(priorite, GRIS_FONCE)
        _add_textbox(
            slide, left + Cm(0.35), bloc_top + Cm(7.3), bloc_w - Cm(0.5), Cm(0.65),
            f"● Priorité : {priorite}", font_size=9, bold=True, color=p_color,
        )

        # KPI
        kpi = rec.get("kpi", "")
        _add_textbox(
            slide, left + Cm(0.35), bloc_top + Cm(8.1), bloc_w - Cm(0.5), Cm(2.0),
            f"KPI : {kpi}", font_size=9, color=VERT_KPI,
        )

        # Horizon
        horizon = rec.get("horizon", "")
        _add_textbox(
            slide, left + Cm(0.35), bloc_top + bloc_h - Cm(1.1), bloc_w - Cm(0.5), Cm(0.8),
            f"Horizon : {horizon}", font_size=9, bold=False, color=GRIS_FONCE,
        )

    # Footer bordeaux
    footer_top = SLIDE_H - FOOTER_H
    _add_rect(slide, Cm(0), footer_top, SLIDE_W, FOOTER_H, fill_color=BORDEAUX)
    _add_textbox(
        slide, Cm(0.4), footer_top + Cm(0.7), SLIDE_W * 0.7, FOOTER_H - Cm(0.8),
        f"Confidentiel — {nom_mission}  ·  LMS ORH",
        font_size=8, color=BORDEAUX_CLAIR,
    )
    if LOGO_PATH:
        try:
            logo_w, logo_h = Cm(3.2), Cm(1.0)
            slide.shapes.add_picture(
                str(LOGO_PATH),
                SLIDE_W - logo_w - Cm(0.3),
                footer_top + (FOOTER_H - logo_h) / 2,
                logo_w, logo_h,
            )
        except Exception:
            pass
    return slide


def _slide_optionnelle(prs, slide_data, mission_config):
    """Slide optionnelle — format contenu standard."""
    titre = slide_data.get("titre", "Analyse thématique")
    observation = slide_data.get("observation", "")
    benchmark = slide_data.get("benchmark_sectoriel", "")
    so_what = slide_data.get("so_what", "")

    return _content_slide(
        prs,
        titre=titre,
        col_gauche_text=observation,
        col_droite_text=benchmark,
        so_what_text=so_what,
        mission_config=mission_config,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  FONCTION PRINCIPALE
# ─────────────────────────────────────────────────────────────────────────────

def generate_lms_ppt(analysis: Dict[str, Any], mission_config: Dict, output_path: str) -> str:
    """
    Génère un fichier PowerPoint LMS ORH pour un benchmark mission.

    Args:
        analysis      : dict retourné par analyze_mission()
        mission_config: dict de configuration de la mission
        output_path   : chemin absolu du fichier .pptx à créer

    Returns:
        Le chemin du fichier généré (= output_path).

    Raises:
        ImportError si python-pptx n'est pas installé.
    """
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    # S'assurer qu'il y a un layout blank (index 6 dans la plupart des templates)
    # Fallback : utiliser le premier layout
    if len(prs.slide_layouts) <= 6:
        blank_idx = len(prs.slide_layouts) - 1
    else:
        blank_idx = 6
    # Remplacer la référence globale de layout dans les helpers
    # (les helpers utilisent prs.slide_layouts[6] directement)

    # ── Slides fixes (7 slides, axes selon le type de benchmark) ─────────────
    _is_org = mission_config.get("type", "RH").upper() == "ORGANISATIONNEL"
    _slide_cover(prs, analysis, mission_config)
    _slide_contexte(prs, analysis, mission_config)
    if _is_org:
        _slide_modeles_csp(prs, analysis, mission_config)
        _slide_processus_douaniers(prs, analysis, mission_config)
        _slide_interface_filiale_siege(prs, analysis, mission_config)
        _slide_formalisation_audit(prs, analysis, mission_config)
    else:
        _slide_business_model(prs, analysis, mission_config)
        _slide_organisation(prs, analysis, mission_config)
        _slide_gouvernance(prs, analysis, mission_config)
        _slide_signaux_innovation(prs, analysis, mission_config)
    _slide_recommandations(prs, analysis, mission_config)

    # ── Slides optionnelles ───────────────────────────────────────────────────
    slides_opt = analysis.get("slides_optionnelles", [])
    if isinstance(slides_opt, list):
        for slide_data in slides_opt:
            if isinstance(slide_data, dict):
                _slide_optionnelle(prs, slide_data, mission_config)

    # ── Sauvegarde ────────────────────────────────────────────────────────────
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))
    return str(out)
