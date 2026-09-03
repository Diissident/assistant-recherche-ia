"""Tests du cache disque : TTL, valeurs None, tolérance à la corruption."""

import json
import os
import time


def test_set_get_roundtrip(temp_cache):
    temp_cache.set("k", {"a": [1, 2, 3]})
    assert temp_cache.get("k") == {"a": [1, 2, 3]}


def test_absent_key_returns_default(temp_cache):
    assert temp_cache.get("jamais-vu") is None
    assert temp_cache.get("jamais-vu", "défaut") == "défaut"


def test_none_is_a_storable_value(temp_cache):
    """scraper.py met en cache les échecs sous forme de None : `has` doit
    distinguer « échec mémorisé » de « pas encore essayé »."""
    assert temp_cache.has("url") is False
    temp_cache.set("url", None)
    assert temp_cache.has("url") is True
    assert temp_cache.get("url") is None


def test_expired_entry_is_dropped(temp_cache):
    temp_cache.set("vieux", "valeur", ttl_hours=0)
    time.sleep(0.01)
    assert temp_cache.get("vieux") is None
    assert temp_cache.has("vieux") is False


def test_per_entry_ttl_is_independent(temp_cache):
    temp_cache.set("court", "x", ttl_hours=0)
    temp_cache.set("long", "y", ttl_hours=48)
    assert temp_cache.get("court") is None
    assert temp_cache.get("long") == "y"


def test_corrupted_file_is_treated_as_a_miss(temp_cache):
    """Un JSON tronqué ne doit jamais faire échouer le pipeline."""
    temp_cache.set("k", "valeur")
    path = temp_cache._key_to_path("k")
    with open(path, "w", encoding="utf-8") as f:
        f.write('{"timestamp": 123, "value": ')  # JSON incomplet

    assert temp_cache.get("k") is None
    # L'entrée illisible est nettoyée au passage.
    assert not os.path.exists(path)


def test_legacy_entry_without_ttl_field(temp_cache):
    """Les entrées écrites par la version précédente (sans champ ttl_hours)
    restent lisibles : elles retombent sur le TTL global."""
    path = temp_cache._key_to_path("ancien")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"timestamp": time.time(), "value": "ok"}, f)

    assert temp_cache.get("ancien") == "ok"


def test_unserializable_value_does_not_raise(temp_cache):
    temp_cache.set("bad", object())          # ne doit pas lever
    assert temp_cache.get("bad") is None
    # Aucun fichier temporaire ne doit rester derrière.
    assert not [f for f in os.listdir(temp_cache.CACHE_DIR) if f.startswith(".tmp-")]
