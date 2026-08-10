"""
scraper.py
----------
Récupère et nettoie le contenu textuel des pages web trouvées par search.py.
Utilise `trafilatura`, gratuit et open-source, spécialisé dans l'extraction
de texte principal (sans menus, pubs, scripts).
"""

import asyncio

import aiohttp
import trafilatura

import cache
from config import MAX_CONCURRENT_SCRAPES, MIN_TEXT_LENGTH, SCRAPE_TIMEOUT


async def fetch_html(session: aiohttp.ClientSession, url: str) -> str | None:
    """
    Télécharge le HTML brut d'une URL avec un timeout court.

    Paramètres:
        session: session aiohttp partagée (réutilisation des connexions)
        url (str): URL de la page à récupérer

    Retour:
        str | None: le HTML brut, ou None en cas d'échec/timeout
    """
    try:
        async with session.get(url, timeout=SCRAPE_TIMEOUT) as resp:
            if resp.status != 200:
                return None
            return await resp.text(errors="ignore")
    except Exception:
        return None


def extract_text(html: str, url: str) -> str | None:
    """
    Extrait le texte principal d'une page HTML (sans navigation, pub, etc.).

    Paramètres:
        html (str): contenu HTML brut
        url (str): URL d'origine (utilisée pour le contexte d'extraction)

    Retour:
        str | None: texte nettoyé, ou None si extraction impossible/trop courte
    """
    text = trafilatura.extract(html, url=url, favor_recall=True)
    if not text or len(text) < MIN_TEXT_LENGTH:
        return None
    return text


async def scrape_one(session: aiohttp.ClientSession, semaphore: asyncio.Semaphore, url: str) -> dict | None:
    """
    Scrape et nettoie une seule page, avec cache et limitation de concurrence.

    Paramètres:
        session: session aiohttp partagée
        semaphore: limite le nombre de scrapes simultanés
        url (str): URL cible

    Retour:
        dict | None: {'url': str, 'text': str} ou None si échec
    """
    cached = cache.get(f"scrape::{url}")
    if cached is not None:
        return cached if cached else None

    async with semaphore:
        html = await fetch_html(session, url)

    if html is None:
        cache.set(f"scrape::{url}", None)
        return None

    text = extract_text(html, url)
    result = {"url": url, "text": text} if text else None
    cache.set(f"scrape::{url}", result)
    return result


async def scrape_many(urls: list[str]) -> list[dict]:
    """
    Scrape plusieurs URLs en parallèle (avec limite de concurrence).

    Paramètres:
        urls (list[str]): liste d'URLs à scraper

    Retour:
        list[dict]: liste de {'url', 'text'} pour les pages réussies uniquement
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_SCRAPES)
    async with aiohttp.ClientSession(
        headers={"User-Agent": "Mozilla/5.0 (compatible; PersonalResearchBot/1.0)"}
    ) as session:
        tasks = [scrape_one(session, semaphore, url) for url in urls]
        results = await asyncio.gather(*tasks)

    return [r for r in results if r is not None]
