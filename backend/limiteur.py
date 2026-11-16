"""Limitation du nombre d'appels publics par adresse IP (catalogue, téléchargements, signalements).

Pour un développeur WinDev : c'est un tableau associatif en mémoire (clé = adresse IP, valeur = heures d'appel de la dernière minute),
vidé au redémarrage du serveur, ce qui suffit ici.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import HTTPException, Request, status

from config import get_settings
from outils import adresse_ip


class Limiteur:
    """Fenêtre glissante : au plus `maximum` appels par `fenetre` secondes et par clé."""

    def __init__(self, maximum: int, fenetre: float = 60.0):
        self.maximum = maximum
        self.fenetre = fenetre
        self._appels: Dict[str, Deque[float]] = defaultdict(deque)

    def autoriser(self, cle: str, moment: float | None = None) -> bool:
        moment = time.monotonic() if moment is None else moment
        file = self._appels[cle]
        while file and moment - file[0] >= self.fenetre:          # on oublie les appels sortis de la fenêtre
            file.popleft()
        if len(file) >= self.maximum:
            return False
        file.append(moment)
        if len(self._appels) > 10_000:                            # protection mémoire
            self._appels.clear()
        return True

    def vider(self) -> None:
        self._appels.clear()


limiteur_ecriture = Limiteur(get_settings().limite_publique_par_minute)
limiteur_lecture = Limiteur(get_settings().limite_publique_par_minute * 5)   # beaucoup de téléphones partagent une même adresse IP


async def limiter_appels_publics(request: Request) -> None:
    """Dépendance FastAPI : refuse (429) au-delà de la limite par minute et par adresse IP."""
    limiteur = limiteur_lecture if request.method == "GET" else limiteur_ecriture
    if not limiteur.autoriser(adresse_ip(request) or "inconnue"):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Trop de requêtes : réessayez dans une minute")
