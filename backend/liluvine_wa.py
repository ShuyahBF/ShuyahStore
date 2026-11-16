"""WhatsApp par la « Transmission WA Universelle » Liluvine (service de SAWALI) : codes de connexion (OTP) et rapports PDF.

Même protocole que les autres plateformes du propriétaire (sawali-bfmobility, auRor) :
    POST {LILUVINE_WA_URL}
    en-têtes  X-Emetteur, X-Timestamp (epoch s), X-Signature = hex(HMAC-SHA256(clé, "<horodatage>.<corps brut>"))
    corps     {"id": uuid, "to": "+226…", "message": "…", "source": "shuyahstore", "media": {...} (facultatif)}
    média     {"type": "document", "contenu_base64": "…", "nom_fichier": "rapport.pdf", "mime": "application/pdf", "legende": "…"} (10 Mo au plus)
Délai 15 s ; UN SEUL nouvel essai (même id, nouvelle signature) sur erreur réseau ou réponse 5xx ; jamais de nouvel essai sur 4xx ;
409 = destinataire désinscrit (il a répondu STOP) : échec définitif.

Sécurité : la clé HMAC n'est JAMAIS journalisée ni renvoyée ; le texte des messages (qui contient un code) n'est jamais journalisé,
seulement sa longueur. Aucune exception ne sort : le résultat est toujours { ok, erreur, desinscrit? }.

Pour un développeur WinDev : l'équivalent d'une procédure globale « EnvoieWhatsApp(numero, message, fichier) » qui rend un booléen et un message d'erreur.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import re
import time
import uuid
from typing import Optional

import httpx

from config import get_settings

log = logging.getLogger("shuyahstore.liluvine")

DELAI_SECONDES = 15                       # imposé par le protocole
LONGUEUR_MAX = 4096                       # longueur maximale d'un message
MEDIA_TAILLE_MAX = 10 * 1024 * 1024       # 10 Mo au plus avant encodage

# Transport HTTP de remplacement : None en production ; les tests y placent un httpx.MockTransport (aucun appel réseau réel)
_transport: Optional[httpx.AsyncBaseTransport] = None

_ERREURS = {
    400: "Liluvine : requête refusée (données invalides)", 401: "Liluvine : signature refusée (clé HMAC ou émetteur incorrect)",
    403: "Liluvine : émetteur non autorisé", 404: "Liluvine : adresse du service introuvable (LILUVINE_WA_URL)",
    409: "Ce numéro s'est désinscrit des messages WhatsApp (réponse STOP)", 429: "Liluvine : trop de messages, réessayez dans un instant",
}


def configure() -> bool:
    """Vrai si la Transmission universelle est utilisable (adresse ET clé saisies dans Render)."""
    s = get_settings()
    return bool((s.liluvine_wa_url or "").strip() and (s.liluvine_wa_hmac or "").strip())


def normaliser_numero(numero: str) -> Optional[str]:
    """Numéro au format international « +22670123456 », ou None s'il est invalide.
    Accepte « +226 70 12 34 56 », « 00226… », « 226… » ; un numéro LOCAL de 8 chiffres reçoit l'indicatif par défaut."""
    brut = str(numero or "").strip()
    chiffres = re.sub(r"\D", "", brut)
    if chiffres.startswith("00"):
        chiffres = chiffres[2:]
    elif not brut.startswith("+") and 0 < len(chiffres) <= 8:
        chiffres = f"{get_settings().indicatif_defaut}{chiffres}"
    # Norme E.164 : 8 à 15 chiffres, sans zéro de tête (l'indicatif d'un pays ne commence jamais par 0)
    if not re.fullmatch(r"[1-9]\d{7,14}", chiffres):
        return None
    return f"+{chiffres}"


def masquer_numero(numero: str) -> str:
    """« +22670123456 » → « +226 •••• 56 » : on montre l'indicatif et les deux derniers chiffres, jamais le numéro entier."""
    n = str(numero or "")
    return f"{n[:4]} •••• {n[-2:]}" if len(n) >= 8 else "•••"


def signer(cle: str, horodatage: str, corps_brut: str) -> str:
    """Signature du protocole : hex(HMAC-SHA256(clé, "<horodatage>.<corps brut>"))."""
    return hmac.new(cle.encode("utf-8"), f"{horodatage}.{corps_brut}".encode("utf-8"), hashlib.sha256).hexdigest()


def _resultat(ok: bool, erreur: Optional[str] = None, **extra) -> dict:
    return {"ok": ok, "erreur": erreur, **{k: v for k, v in extra.items() if v is not None}}


async def envoyer_whatsapp(numero: str, message: str, *, document: Optional[bytes] = None, nom_fichier: str = "rapport.pdf",
                           mime: str = "application/pdf") -> dict:
    """Envoie `message` (avec, si fourni, un document joint : PDF…) au numéro WhatsApp. Ne lève JAMAIS d'exception.
    Rend { ok, erreur, message_id?, desinscrit? }."""
    try:
        s = get_settings()
        if not configure():
            return _resultat(False, "WhatsApp n'est pas encore configuré sur ce serveur (LILUVINE_WA_URL et LILUVINE_WA_HMAC)")
        destinataire = normaliser_numero(numero)
        texte = (message or "").strip()
        if not destinataire:
            return _resultat(False, "Numéro WhatsApp invalide")
        if not texte:
            return _resultat(False, "Message vide")
        corps = {"id": str(uuid.uuid4()), "to": destinataire, "message": texte[:LONGUEUR_MAX], "source": "ShuyahStore"}
        if document is not None:
            if not document or len(document) > MEDIA_TAILLE_MAX:
                return _resultat(False, "Document vide ou trop volumineux (10 Mo au plus)")        # refusé localement, sans aucun appel
            corps["media"] = {"type": "document", "contenu_base64": base64.b64encode(document).decode("ascii"),
                              "nom_fichier": nom_fichier, "mime": mime, "legende": texte[:1000]}
        # Corps sérialisé UNE SEULE FOIS : c'est exactement ce texte qui est signé et envoyé ; le même (donc le même id) sert au nouvel essai
        brut = json.dumps(corps, ensure_ascii=False, separators=(",", ":"))
        derniere = "Liluvine injoignable"
        for essai in (1, 2):
            horodatage = str(int(time.time()))
            entetes = {"Content-Type": "application/json", "X-Emetteur": (s.liluvine_wa_emetteur or "shuyahstore").strip(),
                       "X-Timestamp": horodatage, "X-Signature": signer(s.liluvine_wa_hmac.strip(), horodatage, brut)}
            try:
                async with httpx.AsyncClient(timeout=DELAI_SECONDES, transport=_transport) as client:
                    r = await client.post(s.liluvine_wa_url.strip(), content=brut.encode("utf-8"), headers=entetes)
            except httpx.HTTPError as exc:
                log.warning("Liluvine : erreur réseau (essai %s) : %s", essai, type(exc).__name__)
                continue
            if r.status_code >= 500:
                log.warning("Liluvine : HTTP %s (essai %s)", r.status_code, essai)
                derniere = f"Liluvine : erreur du service (HTTP {r.status_code})"
                continue
            if r.status_code == 200:
                try:
                    donnees = r.json()
                except ValueError:
                    donnees = {}
                if donnees.get("ok", True):
                    return _resultat(True, None, message_id=donnees.get("message_id"))
                return _resultat(False, "Liluvine : envoi refusé")
            if r.status_code == 409:
                return _resultat(False, _ERREURS[409], desinscrit=True)
            log.warning("Liluvine : refus HTTP %s (message de %s caractères)", r.status_code, len(texte))   # jamais le texte (il peut contenir un code)
            return _resultat(False, _ERREURS.get(r.status_code, f"Liluvine : refus (HTTP {r.status_code})"))
        return _resultat(False, derniere)
    except Exception as exc:                                  # noqa: BLE001 — un envoi raté ne doit jamais faire tomber une requête
        log.warning("Liluvine : erreur inattendue (%s)", type(exc).__name__)
        return _resultat(False, "Envoi WhatsApp impossible")
