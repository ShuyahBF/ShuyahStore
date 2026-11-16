"""Envoi d'e-mails par SMTP (fournisseur au choix du propriétaire : Brevo, Gmail avec mot de passe d'application, OVH…).

Les réglages viennent des variables d'environnement SMTP_* (voir config.py) : aucun secret dans le code. L'envoi se fait dans un fil séparé
(smtplib est synchrone) pour ne jamais bloquer le serveur. Si SMTP n'est pas configuré, `configure()` est faux et rien n'est tenté.

Pour un développeur WinDev : l'équivalent d'une procédure « EmailEnvoie » appelée depuis un thread.
"""
from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, parseaddr

from config import get_settings

log = logging.getLogger("shuyahstore.email")


def configure() -> bool:
    s = get_settings()
    return bool(s.smtp_host and (s.smtp_from or s.smtp_user))


def _expediteur() -> str:
    s = get_settings()
    brut = s.smtp_from or s.smtp_user
    nom, adresse = parseaddr(brut)
    return formataddr((nom or "ShuyahStore", adresse or brut))


def _envoyer_sync(destinataire: str, sujet: str, texte: str, html: str) -> None:
    s = get_settings()
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = sujet, _expediteur(), destinataire
    msg.set_content(texte)
    if html:
        msg.add_alternative(html, subtype="html")
    contexte = ssl.create_default_context()
    if s.smtp_starttls:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as serveur:
            serveur.starttls(context=contexte)
            if s.smtp_user:
                serveur.login(s.smtp_user, s.smtp_password)
            serveur.send_message(msg)
    else:
        with smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=15, context=contexte) as serveur:
            if s.smtp_user:
                serveur.login(s.smtp_user, s.smtp_password)
            serveur.send_message(msg)


async def envoyer(destinataire: str, sujet: str, texte: str, html: str = "") -> bool:
    """Envoie un e-mail ; rend vrai si le serveur SMTP l'a accepté. Aucune exception ne sort (le journal ne contient ni adresse ni secret)."""
    if not configure():
        return False
    try:
        await asyncio.to_thread(_envoyer_sync, destinataire, sujet, texte, html)
        return True
    except Exception as exc:  # noqa: BLE001 — un envoi raté ne doit jamais faire tomber la requête
        log.warning("E-mail non envoyé (%s)", type(exc).__name__)
        return False
