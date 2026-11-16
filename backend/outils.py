"""Petites fonctions communes : adresse IP du visiteur, date du moment, texte de recherche sans accents."""
from __future__ import annotations

import hashlib
import unicodedata
from datetime import datetime, timezone

from fastapi import Request

from config import get_settings


def maintenant() -> datetime:
    return datetime.now(timezone.utc)


def iso() -> str:
    """Date et heure du moment, au format ISO (UTC = heure de Ouagadougou)."""
    return maintenant().isoformat()


def adresse_ip(request: Request) -> str:
    """Adresse IP du visiteur : derrière Render, c'est la première adresse de l'en-tête X-Forwarded-For."""
    transmis = request.headers.get("x-forwarded-for", "")
    if transmis:
        return transmis.split(",")[0].strip()
    return request.client.host if request.client else ""


def origine_anonyme(request: Request) -> str:
    """Empreinte de l'adresse IP (jamais l'adresse elle-même en base) : sert à ne compter qu'un téléchargement par jour et par origine."""
    return hashlib.sha256((get_settings().jwt_secret + "|" + adresse_ip(request)).encode()).hexdigest()[:24]


def sans_accents(texte: str) -> str:
    """Texte en minuscules sans accents : la recherche « telephone » trouve « Téléphone »."""
    decompose = unicodedata.normalize("NFD", str(texte or "").lower())
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn")
