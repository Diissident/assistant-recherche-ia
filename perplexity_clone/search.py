"""
search.py
---------
Recherche web gratuite, sans clé API, via la librairie `duckduckgo-search`.
Retourne une liste d'URLs candidates pour une requête donnée.
"""

import asyncio
import logging

from ddgs import DDGS

import cache
from config import MAX_SEARCH_RESULTS, SEARCH_TIMEOUT

logger = logging.getLogger(__name__)


def search_sync(query: str, max_results: int = MAX_SEARCH_RESULTS) -> list[dict]:
    """
    Recherche synchrone sur DuckDuckGo.

    Paramètres:
        query (str): la requête de recherche
        max_results (int): nombre max de résultats à retourner

    Retour:
        list[dict]: liste de résultats, chaque dict a les clés
                     'title', 'href' (URL), 'body' (extrait)

    Lève:
        Toute exception remontée par DDGS (réseau, rate-limit…). Les appelants
        asynchrones l'attrapent, cf. search_async.
    """
    cache_key = f"search::{query}::{max_results}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    results = []
    with DDGS(timeout=SEARCH_TIMEOUT) as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            results.append(r)

    # On ne met en cache que les recherches fructueuses : une liste vide vient
    # presque toujours d'un rate-limit passager, et la mémoriser 48h
    # condamnerait la requête bien après le retour à la normale.
    if results:
        cache.set(cache_key, results)
    return results


async def search_async(query: str, max_results: int = MAX_SEARCH_RESULTS) -> list[dict]:
    """
    Version asynchrone de search_sync, pour paralléliser plusieurs
    requêtes de recherche (sous-requêtes générées à partir de la
    question initiale).

    Une sous-requête en échec retourne une liste vide plutôt que de lever :
    les autres sous-requêtes restent exploitables, et le pipeline peut
    continuer avec les résultats disponibles.

    Paramètres identiques à search_sync.
    """
    try:
        return await asyncio.to_thread(search_sync, query, max_results)
    except Exception as exc:
        logger.warning("Recherche échouée pour %r : %s", query, exc)
        return []


async def search_multiple(queries: list[str]) -> dict[str, list[dict]]:
    """
    Lance plusieurs recherches en parallèle.

    Paramètres:
        queries (list[str]): liste de sous-requêtes

    Retour:
        dict[str, list[dict]]: mapping requête -> résultats. Une sous-requête
        en échec est présente avec une liste vide.
    """
    if not queries:
        return {}

    results = await asyncio.gather(
        *(search_async(q) for q in queries), return_exceptions=True
    )

    out: dict[str, list[dict]] = {}
    for query, result in zip(queries, results):
        if isinstance(result, BaseException):
            logger.warning("Recherche échouée pour %r : %s", query, result)
            out[query] = []
        else:
            out[query] = result
    return out
