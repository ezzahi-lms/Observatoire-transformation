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
BORDEAUX = RGBColor(139, 26, 26)    # #8B1A1A
GRIS_FONCE = RGBColor(45, 45, 45)  # #2D2D2D
GRIS_CLAIR = RGBColor(245, 245, 245)  # #F5F5F5
BLANC = RGBColor(255, 255, 255)
VERT_KPI = RGBColor(39, 174, 96)   # #27AE62
POLICE = "Arial"

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


def _footer(slide, nom_mission, entreprise_cible):
    """Ajoute le footer confidentiel LMS."""
    footer_text = f"Confidentiel — {nom_mission} · LMS ORH"
    _add_textbox(
        slide,
        left=Cm(0), top=Cm(18.3), width=SLIDE_W, height=Cm(0.7),
        text=footer_text, font_size=8, color=GRIS_FONCE, align=PP_ALIGN.CENTER,
    )


def _content_slide(prs, titre, col_gauche_text, col_droite_text, so_what_text,
                   mission_config, col_gauche_items=None):
    """
    Crée une slide de contenu standard :
    - barre bordeaux haut
    - barre bordeaux verticale gauche
    - 2 colonnes : gauche (analyse) / droite (benchmark)
    - encadré bordeaux bas (so_what)
    - footer
    """
    nom_mission = mission_config.get("nom_mission", "Mission")
    entreprise_cible = mission_config.get("entreprise_cible", "Entreprise")

    slide_layout = prs.slide_layouts[6]  # blank
    slide = prs.slides.add_slide(slide_layout)
    # Supprimer les placeholders résiduels s'il en existe (layout non strictement vide)
    sp_tree = slide.shapes._spTree
    if len(sp_tree) > 2:
        sp_tree.remove(sp_tree[2])

    # Barre bordeaux haut (titre en textbox décalé pour marge interne propre)
    barre_h = Cm(1.8)
    _add_rect(slide, Cm(0), Cm(0), SLIDE_W, barre_h, fill_color=BORDEAUX)
    _add_textbox(
        slide, Cm(0.5), Cm(0.25), SLIDE_W - Cm(1.0), barre_h - Cm(0.25),
        titre, font_size=18, bold=True, color=BLANC,
    )

    # Barre bordeaux verticale gauche
    _add_rect(slide, Cm(0), barre_h, Cm(0.4), SLIDE_H - barre_h - Cm(2.5), fill_color=BORDEAUX)

    # Zone contenu (de y=1.8 à y=16.5)
    content_top = barre_h + Cm(0.2)
    content_h = Cm(14.5)
    col_l_w = SLIDE_W * 0.58
    col_r_w = SLIDE_W * 0.38
    gap = Cm(0.5)
    col_l_left = Cm(0.6)
    col_r_left = col_l_left + col_l_w + gap

    # Colonne gauche
    if col_gauche_items:
        _add_bullet_textbox(
            slide, col_l_left, content_top, col_l_w, content_h,
            col_gauche_items, font_size=10, color=GRIS_FONCE,
            title=col_gauche_text, title_size=11,
        )
    else:
        _add_textbox(
            slide, col_l_left, content_top, col_l_w, content_h,
            col_gauche_text, font_size=10, color=GRIS_FONCE,
        )

    # Colonne droite
    _add_textbox(
        slide, col_r_left, content_top, col_r_w, content_h,
        col_droite_text, font_size=10, color=GRIS_FONCE,
    )

    # Encadré bordeaux bas (so_what)
    so_what_top = Cm(16.5)
    so_what_h = Cm(1.8)
    rect_sw = _add_rect(slide, Cm(0), so_what_top, SLIDE_W, so_what_h, fill_color=BORDEAUX)
    sw_label = f"So what ? pour {entreprise_cible} : "
    _add_textbox(
        slide, Cm(0.3), so_what_top, SLIDE_W - Cm(0.3), so_what_h,
        sw_label + so_what_text, font_size=10, color=BLANC,
    )

    _footer(slide, nom_mission, entreprise_cible)
    return slide


# ─────────────────────────────────────────────────────────────────────────────
#  SLIDES SPÉCIFIQUES
# ─────────────────────────────────────────────────────────────────────────────

def _slide_cover(prs, analysis, mission_config):
    """Slide 1 — Couverture."""
    nom_mission = mission_config.get("nom_mission", "Mission RH")
    entreprise_cible = mission_config.get("entreprise_cible", "Entreprise")
    secteur = mission_config.get("secteur", "")

    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)

    # Panneau gauche bordeaux (8cm de large)
    panneau_w = Cm(8)
    rect_left = _add_rect(slide, Cm(0), Cm(0), panneau_w, SLIDE_H, fill_color=BORDEAUX)

    # Si mosaïque disponible, l'afficher par-dessus
    if MOSAIC_PATH:
        try:
            slide.shapes.add_picture(
                str(MOSAIC_PATH), Cm(0), Cm(0), panneau_w, SLIDE_H
            )
        except Exception:
            pass  # fallback bordeaux uni

    # Zone droite
    right_left = panneau_w + Cm(0.8)
    right_w = SLIDE_W - panneau_w - Cm(1.2)

    # Titre BENCHMARK RH
    _add_textbox(
        slide, right_left, Cm(3), right_w, Cm(1.8),
        "BENCHMARK RH", font_size=28, bold=True, color=BORDEAUX,
    )

    # Nom de la mission
    _add_textbox(
        slide, right_left, Cm(5), right_w, Cm(1.4),
        nom_mission, font_size=22, bold=False, color=GRIS_FONCE,
    )

    # Entreprise cible
    _add_textbox(
        slide, right_left, Cm(6.6), right_w, Cm(1),
        entreprise_cible, font_size=18, bold=False, color=BORDEAUX,
    )

    # Secteur
    _add_textbox(
        slide, right_left, Cm(7.8), right_w, Cm(0.8),
        secteur, font_size=14, bold=False, color=GRIS_FONCE,
    )

    # Date
    date_str = datetime.now().strftime("%d %B %Y")
    _add_textbox(
        slide, right_left, Cm(9), right_w, Cm(0.7),
        date_str, font_size=12, bold=False, color=GRIS_FONCE,
    )

    # Mention cabinet
    _add_textbox(
        slide, right_left, Cm(17.5), right_w, Cm(0.8),
        "LMS ORH — Organisation & Ressources Humaines",
        font_size=11, bold=False, color=GRIS_FONCE,
    )

    # Logo LMS si disponible
    if LOGO_PATH:
        try:
            logo_w = Cm(4)
            logo_left = SLIDE_W - logo_w - Cm(0.5)
            slide.shapes.add_picture(
                str(LOGO_PATH), logo_left, SLIDE_H - Cm(2), logo_w, Cm(1.6)
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
    so_what = (
        f"Question centrale : {angle_strategique}"
        if angle_strategique else angle or "Voir angle RH central."
    )
    return _content_slide(
        prs,
        titre="Contexte & Angle RH",
        col_gauche_text=texte,
        col_droite_text=f"Angle RH central :\n\n{angle}",
        so_what_text=so_what,
        mission_config=mission_config,
    )


def _slide_business_model(prs, analysis, mission_config):
    """Slide 3 — Business Model — Lecture RH."""
    bm = analysis.get("business_model_rh", {})
    analyse = bm.get("analyse", "")
    emergentes = bm.get("competences_emergentes", [])
    obsoletes = bm.get("competences_obsoletes", [])
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
    org = analysis.get("organisation_dimensionnement", {})
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
        col_gauche_items=[f"• {r}" for r in org.get("nouveaux_roles", [])] or None,
    )


def _slide_gouvernance(prs, analysis, mission_config):
    """Slide 5 — Gouvernance RH & Management."""
    gov = analysis.get("gouvernance_rh", {})
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
    inn = analysis.get("innovation_manageriale", {})
    signaux = analysis.get("signaux_faibles", [])

    signaux_text = ""
    for s in signaux[:3]:
        signaux_text += f"• {s.get('signal', '')} ({s.get('horizon', '')})\n"
        signaux_text += f"  → {s.get('implication_rh', '')}\n\n"

    pratiques = inn.get("pratiques_differenciantes", [])
    outils = inn.get("outils_rh", [])
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


def _slide_recommandations(prs, analysis, mission_config):
    """Slide 7 — Recommandations Mission (3 blocs côte à côte)."""
    nom_mission = mission_config.get("nom_mission", "Mission")
    entreprise_cible = mission_config.get("entreprise_cible", "Entreprise")
    recs = analysis.get("recommandations_mission", [])

    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)

    # Barre bordeaux haut
    barre_h = Cm(1.8)
    _add_rect(slide, Cm(0), Cm(0), SLIDE_W, barre_h, fill_color=BORDEAUX)
    _add_textbox(
        slide, Cm(0.4), Cm(0), SLIDE_W, barre_h,
        "Recommandations Mission", font_size=18, bold=True, color=BLANC,
    )

    # 3 blocs côte à côte
    bloc_w = (SLIDE_W - Cm(2)) / 3
    gap = Cm(0.5)
    bloc_top = barre_h + Cm(0.5)
    bloc_h = Cm(13)

    priorite_colors = {"Haute": BORDEAUX, "Moyenne": RGBColor(230, 126, 34), "Faible": GRIS_FONCE}

    for i, rec in enumerate(recs[:3]):
        left = Cm(0.5) + i * (bloc_w + gap)

        # Fond gris clair
        rect_bloc = _add_rect(slide, left, bloc_top, bloc_w, bloc_h, fill_color=GRIS_CLAIR)

        # Titre de la reco (bordeaux)
        action = rec.get("action", f"Recommandation {i+1}")
        _add_textbox(
            slide, left + Cm(0.2), bloc_top + Cm(0.2), bloc_w - Cm(0.4), Cm(1.8),
            action, font_size=11, bold=True, color=BORDEAUX,
        )

        # Justification
        justif = rec.get("justification", "")
        _add_textbox(
            slide, left + Cm(0.2), bloc_top + Cm(2.2), bloc_w - Cm(0.4), Cm(4),
            justif, font_size=9, color=GRIS_FONCE,
        )

        # Priorité
        priorite = rec.get("priorite", "Moyenne")
        p_color = priorite_colors.get(priorite, GRIS_FONCE)
        _add_textbox(
            slide, left + Cm(0.2), bloc_top + Cm(6.5), bloc_w - Cm(0.4), Cm(0.7),
            f"Priorité : {priorite}", font_size=9, bold=True, color=p_color,
        )

        # KPI (vert)
        kpi = rec.get("kpi", "")
        _add_textbox(
            slide, left + Cm(0.2), bloc_top + Cm(7.4), bloc_w - Cm(0.4), Cm(2.5),
            f"KPI : {kpi}", font_size=9, color=VERT_KPI,
        )

        # Horizon
        horizon = rec.get("horizon", "")
        _add_textbox(
            slide, left + Cm(0.2), bloc_top + Cm(10), bloc_w - Cm(0.4), Cm(0.8),
            f"Horizon : {horizon}", font_size=9, color=GRIS_FONCE,
        )

    _footer(slide, nom_mission, entreprise_cible)
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

    # ── 7 slides fixes ────────────────────────────────────────────────────────
    _slide_cover(prs, analysis, mission_config)
    _slide_contexte(prs, analysis, mission_config)
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
