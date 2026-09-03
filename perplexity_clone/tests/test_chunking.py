"""Tests du découpage en chunks (rerank.chunk_text)."""

import rerank


def _words(n: int) -> str:
    return " ".join(f"mot{i}" for i in range(n))


def test_short_text_gives_one_chunk():
    chunks = rerank.chunk_text(_words(100), "http://exemple.fr")
    assert len(chunks) == 1
    assert chunks[0]["url"] == "http://exemple.fr"


def test_text_shorter_than_minimum_is_dropped():
    assert rerank.chunk_text(_words(10), "http://exemple.fr") == []


def test_chunks_overlap():
    chunks = rerank.chunk_text(_words(600), "u", chunk_size=100, overlap=20)
    first = chunks[0]["text"].split()
    second = chunks[1]["text"].split()
    # Le pas est de 80 mots : les 20 derniers mots du chunk 1 ouvrent le chunk 2.
    assert first[-20:] == second[:20]


def test_no_redundant_trailing_chunk():
    """Quand la dernière fenêtre couvre déjà la fin du texte, on s'arrête :
    sinon le dernier chunk est intégralement contenu dans le précédent et
    part au reranker pour rien."""
    chunks = rerank.chunk_text(_words(320), "u", chunk_size=350, overlap=50)
    assert len(chunks) == 1


def test_every_word_is_covered():
    chunks = rerank.chunk_text(_words(1000), "u", chunk_size=100, overlap=20)
    couverts = set()
    for c in chunks:
        couverts.update(c["text"].split())
    assert len(couverts) == 1000
