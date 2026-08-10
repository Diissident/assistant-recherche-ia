"""
cache.py
--------
Cache disque très simple (JSON) pour éviter de refaire une recherche
ou un scraping identique dans un court laps de temps. Gratuit, aucune
dépendance externe (pas de Redis, pas de base de données).
"""

import hashlib
import json
import os
import time

from config import CACHE_DIR, CACHE_TTL_HOURS


def _key_to_path(key: str) -> str:
    """
    Transforme une clé texte (ex: une requête utilisateur) en un chemin
    de fichier unique et stable, via un hash MD5.
    """
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()
    return os.path.join(CACHE_DIR, f"{digest}.json")


def get(key: str):
    """
    Récupère une valeur en cache si elle existe et n'a pas expiré.

    Paramètres:
        key (str): identifiant unique de la donnée (ex: requête normalisée)

    Retour:
        La valeur stockée (any JSON-serializable), ou None si absente/expirée.
    """
    path = _key_to_path(key)
    if not os.path.exists(path):
        return None

    with open(path, "r", encoding="utf-8") as f:
        entry = json.load(f)

    age_hours = (time.time() - entry["timestamp"]) / 3600
    if age_hours > CACHE_TTL_HOURS:
        os.remove(path)
        return None

    return entry["value"]


def set(key: str, value) -> None:
    """
    Stocke une valeur en cache avec un horodatage.

    Paramètres:
        key (str): identifiant unique de la donnée
        value: donnée sérialisable en JSON (dict, list, str...)
    """
    path = _key_to_path(key)
    entry = {"timestamp": time.time(), "value": value}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entry, f, ensure_ascii=False)
