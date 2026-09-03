"""Tests de l'orchestrateur : sélection des chunks, dédoublonnage des
sources, événements d'avancement, dégradation en l'absence de résultats."""

import asyncio

import pipeline


# --- Sélection round-robin ------------------------------------------------

def test_select_chunks_spreads_budget_across_pages():
    """Une page très longue ne doit pas monopoliser le budget de chunks."""
    longue = [{"text": f"L{i}", "url": "a"} for i in range(50)]
    courte = [{"text": "C0", "url": "b"}]
    moyenne = [{"text": f"M{i}", "url": "c"} for i in range(3)]

    selected = pipeline._select_chunks([longue, courte, moyenne], budget=6)

    assert len(selected) == 6
    urls = [c["url"] for c in selected]
    # Le premier tour prend un chunk de chaque page avant d'en reprendre.
    assert urls[:3] == ["a", "b", "c"]


def test_select_chunks_respects_budget_and_handles_empty():
    assert pipeline._select_chunks([], budget=10) == []
    assert pipeline._select_chunks([[], []], budget=10) == []


# --- Dédoublonnage des sources -------------------------------------------

def test_merge_chunks_by_source_deduplicates_urls():
    """Deux extraits d'une même page ne doivent pas devenir deux sources
    distinctes : ni pour le modèle, ni dans la liste affichée."""
    chunks = [
        {"text": "extrait 1", "url": "http://a.fr"},
        {"text": "extrait 2", "url": "http://b.fr"},
        {"text": "extrait 3", "url": "http://a.fr"},
    ]
    merged = pipeline._merge_chunks_by_source(chunks)

    assert [m["url"] for m in merged] == ["http://a.fr", "http://b.fr"]
    assert "extrait 1" in merged[0]["text"] and "extrait 3" in merged[0]["text"]


# --- Pipeline complet, dépendances externes simulées ----------------------

def _install_fakes(monkeypatch, *, results=None, pages=None, answer="Réponse [Source 1]"):
    monkeypatch.setattr(pipeline, "ENABLE_QUERY_DECOMPOSITION", False)

    async def fake_search(queries):
        return {q: (results if results is not None else
                    [{"href": "http://a.fr"}, {"href": "http://b.fr"}]) for q in queries}

    async def fake_scrape(urls):
        if pages is not None:
            return pages
        return [{"url": u, "text": "texte " * 300} for u in urls]

    def fake_rerank(query, chunks, *args, **kwargs):
        return chunks[:4]

    def fake_generate(query, chunks, on_token=None):
        if on_token:
            for part in answer.split(" "):
                on_token(part + " ")
        return answer

    monkeypatch.setattr(pipeline.search, "search_multiple", fake_search)
    monkeypatch.setattr(pipeline, "scrape_many", fake_scrape)
    monkeypatch.setattr(pipeline.rerank, "rerank", fake_rerank)
    monkeypatch.setattr(pipeline.generate, "generate_answer", fake_generate)


def test_run_pipeline_returns_answer_and_sources(monkeypatch):
    _install_fakes(monkeypatch)
    result = asyncio.run(pipeline.run_pipeline("question"))

    assert result["answer"] == "Réponse [Source 1]"
    assert [s["n"] for s in result["sources"]] == [1, 2]
    assert {s["url"] for s in result["sources"]} == {"http://a.fr", "http://b.fr"}
    assert "total" in result["timings"]


def test_sources_are_numbered_without_duplicates(monkeypatch):
    """Une seule page scrapée découpée en plusieurs chunks => une seule source."""
    _install_fakes(monkeypatch, pages=[{"url": "http://seul.fr", "text": "texte " * 2000}])
    result = asyncio.run(pipeline.run_pipeline("question"))

    assert result["sources"] == [{"n": 1, "url": "http://seul.fr"}]


def test_progress_events_cover_every_step_in_order(monkeypatch):
    _install_fakes(monkeypatch)
    events = []
    asyncio.run(pipeline.run_pipeline("question", on_progress=events.append))

    starts = [e["step"] for e in events if e["type"] == "step" and e["status"] == "start"]
    assert starts == ["search", "scrape", "chunk", "rerank", "generate"]

    # Chaque étape démarrée est aussi terminée, avec une durée mesurée.
    dones = [e for e in events if e["type"] == "step" and e["status"] == "done"]
    assert [e["step"] for e in dones] == starts
    assert all(isinstance(e["duration"], float) for e in dones)

    # La réponse a bien été streamée fragment par fragment.
    tokens = [e["text"] for e in events if e["type"] == "token"]
    assert "".join(tokens).strip() == "Réponse [Source 1]"


def test_no_tokens_emitted_without_progress_callback(monkeypatch):
    """Sans callback, generate_answer doit être appelé sans on_token (pas de
    streaming inutile côté /ask)."""
    recu = {}

    def fake_generate(query, chunks, on_token=None):
        recu["on_token"] = on_token
        return "ok"

    _install_fakes(monkeypatch)
    monkeypatch.setattr(pipeline.generate, "generate_answer", fake_generate)
    asyncio.run(pipeline.run_pipeline("question"))

    assert recu["on_token"] is None


def test_empty_scrape_degrades_gracefully(monkeypatch):
    _install_fakes(monkeypatch, pages=[])
    result = asyncio.run(pipeline.run_pipeline("question"))

    assert result["sources"] == []
    assert "Aucune source exploitable" in result["answer"]


def test_empty_search_gives_a_specific_message(monkeypatch):
    _install_fakes(monkeypatch, results=[], pages=[])
    result = asyncio.run(pipeline.run_pipeline("question"))

    assert "aucun résultat" in result["answer"]
