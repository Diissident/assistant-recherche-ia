"""
cache.py
--------
Cache disque très simple (JSON) pour éviter de refaire une recherche
ou un scraping identique dans un court laps de temps. Gratuit, aucune
dépendance externe (pas de Redis, pas de base de données).

Deux propriétés importantes pour un cache posé à même le disque :

- les écritures sont **atomiques** (fichier temporaire + `os.replace`), donc
  un crash au milieu d'un `set` ne laisse jamais un JSON tronqué derrière lui ;
- les lectures sont **tolérantes** : un fichier illisible (corrompu par une
  version antérieure, disque plein, antivirus…) est traité comme une absence
  de cache, jamais comme une erreur fatale du pipeline.
"""

import hashlib
import json
import logging
import os
import tempfile
import time

from config import CACHE_DIR, CACHE_TTL_HOURS

logger = logging.getLogger(__name__)

# Sentinelle : permet de distinguer "pas de valeur par défaut fournie" d'un
# `default=None` explicite, puisque None est une valeur mise en cache légitime
# (cf. scraper.py qui met en cache les échecs de scraping).
_MISSING = object()


def _key_to_path(key: str) -> str:
    """
    Transforme une clé texte (ex: une requête utilisateur) en un chemin
    de fichier unique et stable, via un hash MD5.

    MD5 n'est utilisé ici que comme fonction de nommage (aucun enjeu de
    sécurité) : `usedforsecurity=False` l'indique explicitement, ce qui évite
    de faire sonner les audits de sécurité et les builds FIPS.
    """
    digest = hashlib.md5(key.encode("utf-8"), usedforsecurity=False).hexdigest()
    return os.path.join(CACHE_DIR, f"{digest}.json")


def get(key: str, default=None):
    """
    Récupère une valeur en cache si elle existe et n'a pas expiré.

    Paramètres:
        key (str): identifiant unique de la donnée (ex: requête normalisée)
        default: valeur retournée en cas d'absence/expiration (None par défaut)

    Retour:
        La valeur stockée (any JSON-serializable), ou `default` si absente,
        expirée ou illisible.

    Note:
        Comme None est une valeur stockable, utilise `get(key, _MISSING)` —
        ou plus simplement `has(key)` — pour distinguer "absent" de "None".
    """
    path = _key_to_path(key)
    try:
        with open(path, "r", encoding="utf-8") as f:
            entry = json.load(f)
        timestamp = float(entry["timestamp"])
        ttl_hours = float(entry.get("ttl_hours", CACHE_TTL_HOURS))
        value = entry["value"]
    except FileNotFoundError:
        return default
    except (OSError, ValueError, KeyError, TypeError) as exc:
        # JSON corrompu, format d'une version antérieure, droits manquants…
        # On dégrade proprement : le cache est un accélérateur, jamais une
        # dépendance dure du pipeline.
        logger.debug("Entrée de cache illisible (%s) : %s", path, exc)
        _discard(path)
        return default

    if (time.time() - timestamp) / 3600 > ttl_hours:
        _discard(path)
        return default

    return value


def has(key: str) -> bool:
    """Indique si la clé est présente et valide (utile quand None est stockable)."""
    return get(key, _MISSING) is not _MISSING


def set(key: str, value, ttl_hours: float | None = None) -> None:
    """
    Stocke une valeur en cache avec un horodatage.

    Paramètres:
        key (str): identifiant unique de la donnée
        value: donnée sérialisable en JSON (dict, list, str...)
        ttl_hours (float | None): durée de vie propre à cette entrée. None
            applique CACHE_TTL_HOURS. Sert par exemple à ne mémoriser un
            échec de scraping que pendant une heure.

    L'écriture passe par un fichier temporaire renommé ensuite sur la cible :
    `os.replace` est atomique, donc un lecteur concurrent voit soit l'ancienne
    entrée complète, soit la nouvelle — jamais un fichier à moitié écrit.
    """
    path = _key_to_path(key)
    entry = {
        "timestamp": time.time(),
        "ttl_hours": CACHE_TTL_HOURS if ttl_hours is None else ttl_hours,
        "value": value,
    }

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=CACHE_DIR, prefix=".tmp-", delete=False
        ) as f:
            tmp_path = f.name
            json.dump(entry, f, ensure_ascii=False)
        os.replace(tmp_path, path)
    except (OSError, TypeError, ValueError) as exc:
        # Valeur non sérialisable ou disque en défaut : on renonce au cache
        # plutôt que de faire échouer l'appelant.
        logger.debug("Écriture de cache impossible (%s) : %s", path, exc)
        if tmp_path is not None:
            _discard(tmp_path)


def _discard(path: str) -> None:
    """Supprime un fichier de cache en ignorant les erreurs (fichier déjà parti…)."""
    try:
        os.remove(path)
    except OSError:
        pass
