"""Mesure de la durée de chaque appel au serveur (règle 7 : « mesurer d'abord »).

Chaque route note ses durées en mémoire (les 50 dernières) ; l'administration affiche « Appels les plus lents » : moyenne, 5 derniers,
dernier, maximum. Aucune écriture en base : la mesure ne ralentit pas l'appel.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Request

_durees: dict = defaultdict(lambda: deque(maxlen=50))
_maximum: dict = defaultdict(float)


async def mesurer(request: Request, suite):
    """Intergiciel : chronomètre l'appel et range la durée sous le modèle de la route (ex. « GET /api/apps/{reference} »)."""
    debut = time.perf_counter()
    reponse = await suite(request)
    duree = (time.perf_counter() - debut) * 1000
    if request.method == "OPTIONS":                               # demandes techniques du navigateur (CORS) : sans intérêt pour la mesure
        return reponse
    route = request.scope.get("route")
    cle = f"{request.method} {getattr(route, 'path', request.url.path)}"
    _durees[cle].append(duree)
    _maximum[cle] = max(_maximum[cle], duree)
    return reponse


def appels_lents(nombre: int = 30) -> list[dict]:
    """Routes classées de la plus lente à la plus rapide (moyenne des 50 derniers appels), durées en millisecondes."""
    lignes = []
    for cle, d in _durees.items():
        valeurs = list(d)
        if valeurs:
            lignes.append({"route": cle, "appels": len(valeurs), "moyenne_ms": round(sum(valeurs) / len(valeurs)),
                           "cinq_derniers_ms": [round(v) for v in valeurs[-5:]], "dernier_ms": round(valeurs[-1]), "maximum_ms": round(_maximum[cle])})
    return sorted(lignes, key=lambda x: -x["moyenne_ms"])[:nombre]
