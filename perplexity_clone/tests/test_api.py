"""Tests de l'API : CRUD des conversations, validation, persistance
transactionnelle et flux SSE."""

import json

import pytest

import api
from generate import LLMError

FAKE_RESULT = {
    "query": "q",
    "answer": "Une réponse [Source 1]",
    "sources": [{"n": 1, "url": "http://a.fr"}],
    "timings": {"search": 0.5, "total": 1.0},
}


@pytest.fixture
def fake_pipeline(monkeypatch):
    """Remplace le pipeline par une version instantanée et déterministe."""
    async def run(query, verbose=False, on_progress=None):
        if on_progress:
            on_progress({"type": "step", "step": "search", "status": "start"})
            on_progress({"type": "step", "step": "search", "status": "done", "duration": 0.5})
            for part in ["Une ", "réponse ", "[Source 1]"]:
                on_progress({"type": "token", "text": part})
        return dict(FAKE_RESULT, query=query)

    monkeypatch.setattr(api.pipeline, "run_pipeline", run)


def _events(client, payload):
    """Consomme un flux SSE et retourne la liste des événements décodés."""
    out = []
    with client.stream("POST", "/ask/stream", json=payload) as r:
        assert r.status_code == 200
        for line in r.iter_lines():
            if line.startswith("data:"):
                out.append(json.loads(line[5:].strip()))
    return out


# --- CRUD ------------------------------------------------------------------

def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_created_at_returned_matches_stored_value(client):
    """La valeur renvoyée doit être exactement celle enregistrée (et non un
    second appel à time.time())."""
    created = client.post("/conversations", json={"title": "Test"}).json()
    listed = client.get("/conversations").json()

    assert listed[0]["created_at"] == created["created_at"]
    assert listed[0]["id"] == created["id"]


def test_blank_title_falls_back_to_default(client):
    assert client.post("/conversations", json={"title": "   "}).json()["title"] == "Nouvelle recherche"


def test_delete_unknown_conversation_returns_404(client):
    assert client.delete("/conversations/inexistante").status_code == 404


def test_delete_removes_conversation_and_messages(client, fake_pipeline):
    conv_id = client.post("/ask", json={"query": "question"}).json()["conversation_id"]
    assert len(client.get(f"/conversations/{conv_id}/messages").json()) == 2

    assert client.delete(f"/conversations/{conv_id}").status_code == 200
    assert client.get("/conversations").json() == []
    assert client.get(f"/conversations/{conv_id}/messages").json() == []


def test_conversations_are_paginated(client):
    for i in range(5):
        client.post("/conversations", json={"title": f"c{i}"})
    assert len(client.get("/conversations?limit=2").json()) == 2
    assert len(client.get("/conversations?limit=2&offset=4").json()) == 1
    assert client.get("/conversations?limit=0").status_code == 422


# --- Validation ------------------------------------------------------------

@pytest.mark.parametrize("payload", [
    {"query": ""},
    {"query": "   "},
    {"query": "x" * 5000},
    {},
])
def test_invalid_queries_are_rejected(client, payload):
    assert client.post("/ask", json=payload).status_code == 422


def test_query_is_stripped(client, fake_pipeline):
    conv_id = client.post("/ask", json={"query": "  ma question  "}).json()["conversation_id"]
    messages = client.get(f"/conversations/{conv_id}/messages").json()
    assert messages[0]["content"] == "ma question"


def test_unknown_conversation_id_returns_404(client, fake_pipeline):
    r = client.post("/ask", json={"query": "q", "conversation_id": "inconnue"})
    assert r.status_code == 404


# --- /ask ------------------------------------------------------------------

def test_ask_persists_question_and_answer_in_order(client, fake_pipeline):
    body = client.post("/ask", json={"query": "question"}).json()
    messages = client.get(f"/conversations/{body['conversation_id']}/messages").json()

    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "question"
    assert messages[1]["content"] == "Une réponse [Source 1]"
    assert messages[1]["sources"] == [{"n": 1, "url": "http://a.fr"}]
    assert messages[1]["timings"]["total"] == 1.0


def test_ask_reuses_existing_conversation(client, fake_pipeline):
    first = client.post("/ask", json={"query": "q1"}).json()["conversation_id"]
    second = client.post("/ask", json={"query": "q2", "conversation_id": first}).json()

    assert second["conversation_id"] == first
    assert len(client.get(f"/conversations/{first}/messages").json()) == 4


def test_llm_failure_leaves_no_orphan_message(client, monkeypatch):
    """Le bug corrigé : la question était écrite avant l'appel au modèle, et
    restait seule en base quand la génération échouait."""
    async def failing(query, verbose=False, on_progress=None):
        raise LLMError("Ollama est injoignable")

    monkeypatch.setattr(api.pipeline, "run_pipeline", failing)

    r = client.post("/ask", json={"query": "question"})
    assert r.status_code == 502
    assert "Ollama est injoignable" in r.json()["detail"]
    # Ni conversation vide, ni question orpheline.
    assert client.get("/conversations").json() == []


# --- /ask/stream -----------------------------------------------------------

def test_stream_emits_start_steps_tokens_then_done(client, fake_pipeline):
    events = _events(client, {"query": "question"})

    assert events[0]["type"] == "start"
    assert events[-1]["type"] == "done"

    types = [e["type"] for e in events]
    assert "step" in types and "token" in types

    tokens = "".join(e["text"] for e in events if e["type"] == "token")
    assert tokens == "Une réponse [Source 1]"

    done = events[-1]
    assert done["answer"] == "Une réponse [Source 1]"
    assert done["sources"] == [{"n": 1, "url": "http://a.fr"}]
    assert done["conversation_id"] == events[0]["conversation_id"]


def test_stream_persists_the_exchange(client, fake_pipeline):
    events = _events(client, {"query": "question"})
    conv_id = events[-1]["conversation_id"]

    messages = client.get(f"/conversations/{conv_id}/messages").json()
    assert [m["role"] for m in messages] == ["user", "assistant"]


def test_stream_reports_llm_failure_as_an_error_event(client, monkeypatch):
    async def failing(query, verbose=False, on_progress=None):
        raise LLMError("Modèle absent")

    monkeypatch.setattr(api.pipeline, "run_pipeline", failing)

    events = _events(client, {"query": "question"})
    assert events[-1] == {"type": "error", "message": "Modèle absent"}
    assert client.get("/conversations").json() == []


def test_stream_reports_unexpected_failure_without_crashing(client, monkeypatch):
    async def boom(query, verbose=False, on_progress=None):
        raise ValueError("cassé")

    monkeypatch.setattr(api.pipeline, "run_pipeline", boom)

    events = _events(client, {"query": "question"})
    assert events[-1]["type"] == "error"
    assert "cassé" in events[-1]["message"]
