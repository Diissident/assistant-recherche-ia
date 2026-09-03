"""
scraper.py
----------
Récupère et nettoie le contenu textuel des pages web trouvées par search.py.
Utilise `trafilatura`, gratuit et open-source, spécialisé dans l'extraction
de texte principal (sans menus, pubs, scripts).

Les URLs traitées ici viennent d'un moteur de recherche, donc d'une source
non maîtrisée : le module refuse par défaut les adresses privées (garde-fou
SSRF), plafonne la taille téléchargée et vérifie le type de contenu avant de
lancer l'extraction.
"""

import asyncio
import ipaddress
import logging
import socket
from urllib.parse import urlparse

import aiohttp
import trafilatura

import cache
from config import (ALLOW_PRIVATE_ADDRESSES, ALLOWED_CONTENT_TYPES,
                    CACHE_FAILURE_TTL_HOURS, MAX_CONCURRENT_SCRAPES,
                    MAX_PAGE_BYTES, MIN_TEXT_LENGTH, SCRAPE_TIMEOUT)

logger = logging.getLogger(__name__)


def _is_public_host(host: str) -> bool:
    """
    Résout un nom d'hôte et vérifie qu'il pointe vers une adresse publique.

    Bloque localhost, les plages privées (10/8, 192.168/16…), le lien-local
    (169.254/16, qui inclut l'endpoint de métadonnées des principaux clouds)
    et le loopback. Sans ce filtre, une page de résultats piégée pourrait
    faire interroger le réseau local de la machine par le scraper.

    Retour:
        bool: True si *toutes* les adresses résolues sont publiques.
    """
    try:
        infos = socket.getaddrinfo(host, None)
    except (socket.gaierror, UnicodeError):
        return False

    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            return False
    return True


async def is_url_allowed(url: str) -> bool:
    """
    Vérifie qu'une URL est scrapable : schéma http(s) et hôte public.

    La résolution DNS est déportée dans un thread pour ne pas bloquer la
    boucle d'événements.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    if ALLOW_PRIVATE_ADDRESSES:
        return True
    return await asyncio.to_thread(_is_public_host, parsed.hostname)


async def fetch_html(session: aiohttp.ClientSession, url: str) -> str | None:
    """
    Télécharge le HTML brut d'une URL avec un timeout court.

    Paramètres:
        session: session aiohttp partagée (réutilisation des connexions)
        url (str): URL de la page à récupérer

    Retour:
        str | None: le HTML brut, ou None en cas d'échec/timeout/page rejetée
        (type de contenu non textuel, page trop lourde, redirection vers une
        adresse privée).
    """
    timeout = aiohttp.ClientTimeout(total=SCRAPE_TIMEOUT)
    try:
        async with session.get(url, timeout=timeout) as resp:
            if resp.status != 200:
                logger.debug("HTTP %s sur %s", resp.status, url)
                return None

            # Une redirection peut sortir du domaine d'origine : on revérifie
            # la destination réelle avant de lire le corps.
            if str(resp.url) != url and not await is_url_allowed(str(resp.url)):
                logger.debug("Redirection refusée : %s -> %s", url, resp.url)
                return None

            content_type = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
            if content_type and not content_type.startswith(ALLOWED_CONTENT_TYPES):
                logger.debug("Type de contenu ignoré (%s) sur %s", content_type, url)
                return None

            declared = resp.headers.get("Content-Length")
            if declared and declared.isdigit() and int(declared) > MAX_PAGE_BYTES:
                logger.debug("Page trop lourde (%s octets) : %s", declared, url)
                return None

            # Lecture bornée : `resp.text()` chargerait tout en mémoire, y
            # compris un document de plusieurs centaines de Mo servi sans
            # Content-Length.
            raw = await resp.content.read(MAX_PAGE_BYTES + 1)
            if len(raw) > MAX_PAGE_BYTES:
                logger.debug("Page tronquée au-delà de la limite : %s", url)
                return None

            encoding = resp.charset or "utf-8"
            return raw.decode(encoding, errors="ignore")
    except (aiohttp.ClientError, asyncio.TimeoutError, UnicodeDecodeError, LookupError) as exc:
        logger.debug("Échec de récupération de %s : %s", url, exc)
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
    try:
        text = trafilatura.extract(html, url=url, favor_recall=True)
    except Exception as exc:
        logger.debug("Extraction impossible sur %s : %s", url, exc)
        return None
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
    cache_key = f"scrape::{url}"
    if cache.has(cache_key):
        return cache.get(cache_key)

    if not await is_url_allowed(url):
        logger.debug("URL refusée par le filtre d'adresses : %s", url)
        return None

    async with semaphore:
        html = await fetch_html(session, url)

    if html is None:
        # Échec probablement transitoire (timeout, 503) : TTL court pour
        # laisser sa chance à la page lors d'une prochaine recherche.
        cache.set(cache_key, None, ttl_hours=CACHE_FAILURE_TTL_HOURS)
        return None

    # trafilatura est purement CPU (parsing HTML + heuristiques) : sans
    # `to_thread`, chaque extraction gèlerait la boucle d'événements et
    # sérialiserait les téléchargements censés être parallèles.
    text = await asyncio.to_thread(extract_text, html, url)

    result = {"url": url, "text": text} if text else None
    cache.set(
        cache_key,
        result,
        ttl_hours=None if result else CACHE_FAILURE_TTL_HOURS,
    )
    return result


async def scrape_many(urls: list[str]) -> list[dict]:
    """
    Scrape plusieurs URLs en parallèle (avec limite de concurrence).

    Paramètres:
        urls (list[str]): liste d'URLs à scraper

    Retour:
        list[dict]: liste de {'url', 'text'} pour les pages réussies uniquement
    """
    if not urls:
        return []

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_SCRAPES)
    async with aiohttp.ClientSession(
        headers={"User-Agent": "Mozilla/5.0 (compatible; PersonalResearchBot/1.0)"}
    ) as session:
        tasks = [scrape_one(session, semaphore, url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    pages = []
    for url, result in zip(urls, results):
        if isinstance(result, BaseException):
            logger.warning("Scraping échoué pour %s : %s", url, result)
        elif result is not None:
            pages.append(result)
    return pages
