"""
mailer.py — Envoi des rapports innovation RH aux consultants et clients.

Fonctions :
  send_to_consultant(report_id, html_interne, meta, cfg)
  send_to_client(report_id, html_infographie, client_cfg, meta, cfg)
  preview_email(html) → retourne le HTML brut pour affichage Streamlit

Configuration requise dans Streamlit Secrets / os.environ :
  SMTP_HOST       : ex. smtp.gmail.com
  SMTP_PORT       : ex. 587
  SMTP_USER       : adresse expéditeur
  SMTP_PASSWORD   : mot de passe ou app-password
  EMAIL_FROM_NAME : ex. LMS ORH — Veille Innovation (optionnel, défaut: LMS ORH)
"""
import logging
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  CONFIGURATION SMTP
# ─────────────────────────────────────────────────────────────────────────────

def _get_smtp_config() -> Dict:
    cfg = {
        "host":      os.environ.get("SMTP_HOST", ""),
        "port":      int(os.environ.get("SMTP_PORT", "587")),
        "user":      os.environ.get("SMTP_USER", ""),
        "password":  os.environ.get("SMTP_PASSWORD", ""),
        "from_name": os.environ.get("EMAIL_FROM_NAME", "LMS ORH — Veille Innovation"),
    }
    if not cfg["host"] or not cfg["user"] or not cfg["password"]:
        raise ValueError(
            "Configuration SMTP incomplète. "
            "Vérifiez SMTP_HOST, SMTP_USER, SMTP_PASSWORD dans les secrets Streamlit."
        )
    return cfg


def _build_message(
    smtp_cfg: Dict,
    to_addresses: List[str],
    subject: str,
    html_body: str,
    text_body: str = "",
) -> MIMEMultipart:
    """Construit le message MIME."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{smtp_cfg['from_name']} <{smtp_cfg['user']}>"
    msg["To"]      = ", ".join(to_addresses)
    msg["X-Mailer"] = "LMS ORH Veille Innovation / Agent v1.2"

    if text_body:
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    return msg


def _send(smtp_cfg: Dict, to_addresses: List[str], msg: MIMEMultipart) -> bool:
    """Envoie le message via SMTP TLS."""
    ctx = ssl.create_default_context()
    try:
        with smtplib.SMTP(smtp_cfg["host"], smtp_cfg["port"], timeout=15) as srv:
            srv.ehlo()
            srv.starttls(context=ctx)
            srv.login(smtp_cfg["user"], smtp_cfg["password"])
            srv.sendmail(smtp_cfg["user"], to_addresses, msg.as_string())
        logger.info(f"Email envoyé à {to_addresses}")
        return True
    except Exception as e:
        logger.error(f"Erreur envoi email à {to_addresses} : {e}")
        raise


# ─────────────────────────────────────────────────────────────────────────────
#  ENVOI AU CONSULTANT
# ─────────────────────────────────────────────────────────────────────────────

def send_to_consultant(
    report_id: str,
    html_interne: str,
    meta: Dict,
    consultant_email: str,
    consultant_nom: str = "Équipe LMS",
) -> bool:
    """
    Envoie le rapport interne (version consultant) à l'adresse indiquée.

    Args:
        report_id        : ex. "pharma_maroc_Juin_2026"
        html_interne     : HTML généré par generate_rapport_interne()
        meta             : dict _meta du rapport (secteur, mois, nb_sources…)
        consultant_email : destinataire
        consultant_nom   : prénom/nom pour la salutation
    """
    smtp_cfg = _get_smtp_config()

    secteur = meta.get("secteur", "")
    mois    = meta.get("mois", "")
    subject = f"[LMS] Rapport interne Veille Innovation — {secteur} — {mois}"

    text_fallback = (
        f"Bonjour {consultant_nom},\n\n"
        f"Veuillez trouver ci-joint (version HTML) le rapport de veille innovation RH "
        f"du mois {mois} pour le secteur {secteur}.\n\n"
        f"Ce rapport est à usage EXCLUSIF des consultants LMS ORH. Ne pas transmettre.\n\n"
        f"Bonne lecture,\nLMS ORH"
    )

    msg = _build_message(
        smtp_cfg=smtp_cfg,
        to_addresses=[consultant_email],
        subject=subject,
        html_body=html_interne,
        text_body=text_fallback,
    )

    return _send(smtp_cfg, [consultant_email], msg)


# ─────────────────────────────────────────────────────────────────────────────
#  ENVOI AU CLIENT
# ─────────────────────────────────────────────────────────────────────────────

def send_to_client(
    report_id: str,
    html_infographie: str,
    client_cfg: Dict,
    meta: Dict,
) -> bool:
    """
    Envoie l'infographie client (version dirigeant) au contact indiqué.

    Args:
        report_id        : ex. "pharma_maroc_Juin_2026"
        html_infographie : HTML généré par generate_infographie_html()
        client_cfg       : dict client (nom, email, contacts…)
        meta             : dict _meta du rapport
    """
    smtp_cfg = _get_smtp_config()

    secteur   = meta.get("secteur", "")
    mois      = meta.get("mois", "")
    nom_client = client_cfg.get("nom", "")
    contacts  = client_cfg.get("contacts", [])

    if not contacts:
        logger.warning(f"Aucun contact pour {nom_client} — email client non envoyé.")
        return False

    subject = f"Veille Innovation RH — {secteur} — {mois}"
    if nom_client:
        subject = f"{subject} | {nom_client}"

    nom_contact = contacts[0].get("prenom", contacts[0].get("nom", ""))
    text_fallback = (
        f"Bonjour{' ' + nom_contact if nom_contact else ''},\n\n"
        f"Chaque mois, LMS ORH sélectionne pour vous l'innovation RH la plus pertinente "
        f"dans votre secteur et 2 signaux faibles à surveiller.\n\n"
        f"Ce mois-ci : {meta.get('secteur', '')} — {mois}.\n\n"
        f"Consultez la version visuelle de ce message ou contactez-nous pour en discuter.\n\n"
        f"Cordialement,\nL'équipe LMS ORH"
    )

    to_addresses = [c["email"] for c in contacts if c.get("email")]
    if not to_addresses:
        logger.warning(f"Aucune adresse email valide pour {nom_client}.")
        return False

    msg = _build_message(
        smtp_cfg=smtp_cfg,
        to_addresses=to_addresses,
        subject=subject,
        html_body=html_infographie,
        text_body=text_fallback,
    )

    return _send(smtp_cfg, to_addresses, msg)


# ─────────────────────────────────────────────────────────────────────────────
#  ENVOI BATCH (tous clients validés d'un rapport)
# ─────────────────────────────────────────────────────────────────────────────

def send_report_to_all_clients(
    report_data: Dict,
    clients: List[Dict],
    progress_callback=None,
) -> Dict[str, bool]:
    """
    Envoie l'infographie à tous les clients de la liste.
    Retourne un dict {nom_client: succès}.
    """
    from agent.client_report import generate_infographie_html

    meta    = report_data.get("_meta", {})
    results = {}

    for cfg_client in clients:
        nom = cfg_client.get("nom", "inconnu")
        try:
            html = generate_infographie_html(report_data, cfg_client)
            ok   = send_to_client(
                report_id=meta.get("report_id", ""),
                html_infographie=html,
                client_cfg=cfg_client,
                meta=meta,
            )
            results[nom] = ok
            if progress_callback:
                progress_callback(f"{'✅' if ok else '❌'} {nom}")
        except Exception as e:
            logger.error(f"Erreur envoi {nom} : {e}")
            results[nom] = False
            if progress_callback:
                progress_callback(f"❌ {nom} — erreur : {e}")

    return results


# ─────────────────────────────────────────────────────────────────────────────
#  NOTIFICATIONS MANAGER
# ─────────────────────────────────────────────────────────────────────────────

def send_manager_notification(
    manager_email: str,
    nb_rapports: int,
    secteurs: List[str],
    manager_nom: str = "Manager",
) -> bool:
    """
    Notifie le manager qu'un ou plusieurs rapports sont en attente de validation.
    Envoyé automatiquement après la génération mensuelle.
    """
    smtp_cfg = _get_smtp_config()
    subject  = f"[LMS] {nb_rapports} rapport(s) Innovation RH en attente de validation"

    secteurs_list = "".join(f"<li>{s}</li>" for s in secteurs)
    html_body = f"""
<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
  <div style="background:#8B1A1A;padding:20px 28px;">
    <span style="color:white;font-size:18px;font-weight:bold;">LMS ORH — Veille Innovation RH</span>
  </div>
  <div style="padding:24px 28px;background:#FFFFFF;border:1px solid #E5E5E5;">
    <p style="font-size:15px;">Bonjour {manager_nom},</p>
    <p style="font-size:14px;line-height:1.6;">
      <strong>{nb_rapports} rapport(s)</strong> de veille innovation RH ont été générés
      ce mois-ci et sont en attente de votre validation avant envoi aux clients.
    </p>
    <p style="font-size:13px;color:#595959;">Secteurs concernés :</p>
    <ul style="font-size:13px;color:#2D2D2D;line-height:1.8;">{secteurs_list}</ul>
    <p style="font-size:14px;margin-top:20px;">
      Connectez-vous à l'application pour relire, ajuster et valider chaque rapport
      avant diffusion.
    </p>
    <hr style="border:none;border-top:1px solid #E5E5E5;margin:20px 0;"/>
    <p style="font-size:11px;color:#9A9A9A;">
      Ce message est généré automatiquement par l'Observatoire Transformation — LMS ORH.<br/>
      Aucune action immédiate requise — les rapports restent en attente jusqu'à validation.
    </p>
  </div>
</div>"""

    text_body = (
        f"Bonjour {manager_nom},\n\n"
        f"{nb_rapports} rapport(s) de veille innovation sont en attente de validation.\n"
        f"Secteurs : {', '.join(secteurs)}\n\n"
        f"Connectez-vous à l'application pour valider.\n\nLMS ORH"
    )

    msg = _build_message(
        smtp_cfg=smtp_cfg,
        to_addresses=[manager_email],
        subject=subject,
        html_body=html_body,
        text_body=text_body,
    )
    return _send(smtp_cfg, [manager_email], msg)


def send_validation_reminder(
    report_id: str,
    manager_email: str,
    day: int,
    secteur: str = "",
    manager_nom: str = "Manager",
) -> bool:
    """
    Envoie une relance J+1 ou J+2 si le rapport n'est toujours pas validé.

    Args:
        report_id     : identifiant du rapport
        manager_email : email du manager
        day           : 1 ou 2 (J+1 ou J+2)
        secteur       : nom du secteur pour le contexte
        manager_nom   : prénom du manager
    """
    smtp_cfg = _get_smtp_config()
    subject  = f"[LMS] Relance J+{day} — Rapport Innovation {secteur} en attente"

    html_body = f"""
<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
  <div style="background:#8B1A1A;padding:20px 28px;">
    <span style="color:white;font-size:18px;font-weight:bold;">LMS ORH — Relance validation</span>
  </div>
  <div style="padding:24px 28px;background:#FFFFFF;border:1px solid #E5E5E5;">
    <p style="font-size:15px;">Bonjour {manager_nom},</p>
    <p style="font-size:14px;line-height:1.6;">
      Rappel : le rapport <strong>{report_id}</strong>
      {f'(secteur : {secteur})' if secteur else ''}
      est en attente de validation depuis {day} jour(s).
    </p>
    <p style="font-size:14px;">
      ⚠️ Aucun envoi ne sera effectué tant que vous n'aurez pas validé ce rapport.
    </p>
    <hr style="border:none;border-top:1px solid #E5E5E5;margin:20px 0;"/>
    <p style="font-size:11px;color:#9A9A9A;">
      Relance automatique J+{day} — LMS ORH Observatoire Transformation
    </p>
  </div>
</div>"""

    text_body = (
        f"Bonjour {manager_nom},\n\n"
        f"Relance J+{day} : le rapport {report_id} est toujours en attente de validation.\n"
        f"Aucun envoi ne sera effectué sans votre validation.\n\nLMS ORH"
    )

    msg = _build_message(
        smtp_cfg=smtp_cfg,
        to_addresses=[manager_email],
        subject=subject,
        html_body=html_body,
        text_body=text_body,
    )
    return _send(smtp_cfg, [manager_email], msg)


# ─────────────────────────────────────────────────────────────────────────────
#  UTILITAIRES
# ─────────────────────────────────────────────────────────────────────────────

def preview_email(html: str) -> str:
    """Retourne le HTML sans modification (pour iframe Streamlit)."""
    return html


def check_smtp_config() -> tuple[bool, str]:
    """Vérifie si la config SMTP est complète. Retourne (ok, message)."""
    try:
        _get_smtp_config()
        return True, "Configuration SMTP complète."
    except ValueError as e:
        return False, str(e)
