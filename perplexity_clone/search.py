"""
search.py
---------
Recherche web gratuite, sans clé API, via la librairie `duckduckgo-search`.
Retourne une liste d'URLs candidates pour une requête donnée.
"""

import asyncio

from ddgs import DDGS

import cache
from config import MAX_SEARCH_RESULTS, SEARCH_TIMEOUT


def search_sync(query: str, max_results: int = MAX_SEARCH_RESULTS) -> list[dict]:
    """
    Recherche synchrone sur DuckDuckGo.

    Paramètres:
        query (str): la requête de recherche
        max_results (int): nombre max de résultats à retourner

    Retour:
        list[dict]: liste de résultats, chaque dict a les clés
                     'title', 'href' (URL), 'body' (extrait)
    """
    cached = cache.get(f"search::{query}::{max_results}")
    if cached is not None:
        return cached

    results = []
    with DDGS(timeout=SEARCH_TIMEOUT) as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            results.append(r)

    cache.set(f"search::{query}::{max_results}", results)
    return results


async def search_async(query: str, max_results: int = MAX_SEARCH_RESULTS) -> list[dict]:
    """
    Version asynchrone de search_sync, pour paralléliser plusieurs
    requêtes de recherche (sous-requêtes générées à partir de la
    question initiale).

    Paramètres identiques à search_sync.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, search_sync, query, max_results)


async def search_multiple(queries: list[str]) -> dict[str, list[dict]]:
    """
    Lance plusieurs recherches en parallèle.

    Paramètres:
        queries (list[str]): liste de sous-requêtes

    Retour:
        dict[str, list[dict]]: mapping requête -> résultats
    """
    tasks = {q: search_async(q) for q in queries}
    results = await asyncio.gather(*tasks.values())
    return dict(zip(tasks.keys(), results))
