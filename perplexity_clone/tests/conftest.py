"""
Fixtures partagées.

Objectif : aucun test ne doit toucher au cache disque réel (cache_data/) ni à
la base de conversations de l'utilisateur (conversations.db). Tout est
redirigé vers des dossiers temporaires.
"""

import pytest


@pytest.fixture
def temp_cache(tmp_path, monkeypatch):
    """Redirige le cache disque vers un dossier temporaire."""
    import cache

    monkeypatch.setattr(cache, "CACHE_DIR", str(tmp_path / "cache"))
    (tmp_path / "cache").mkdir()
    return cache


@pytest.fixture
def client(tmp_path, monkeypatch):
    """
    Client de test FastAPI branché sur une base SQLite jetable, sans
    préchargement du reranker (inutile et lent dans les tests).
    """
    from fastapi.testclient import TestClient

    import api

    monkeypatch.setattr(api, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(api, "WARMUP_RERANKER", False)

    with TestClient(api.app) as c:
        yield c
