"""
rerank.py
---------
Découpe les textes scrapés en chunks, puis classe ces chunks par pertinence
par rapport à la question de l'utilisateur, via un reranker cross-encoder
open-source (gratuit, tourne en local sur CPU).
"""

import math

from sentence_transformers import CrossEncoder

from config import (CHUNK_OVERLAP, CHUNK_SIZE, MIN_RERANK_SCORE,
                     RERANKER_MODEL, TOP_K_CHUNKS)

# Le modèle est chargé une seule fois au niveau module (coûteux à instancier).
_model = None


def _get_model() -> CrossEncoder:
    """
    Charge (une seule fois) et retourne le modèle de reranking.
    Chargement paresseux pour ne pas ralentir l'import du module.
    """
    global _model
    if _model is None:
        _model = CrossEncoder(RERANKER_MODEL)
    return _model


def chunk_text(text: str, source_url: str, chunk_size: int = CHUNK_SIZE,
               overlap: int = CHUNK_OVERLAP) -> list[dict]:
    """
    Découpe un texte long en chunks de taille approximative fixe,
    avec un léger chevauchement pour ne pas couper une idée en deux.

    Paramètres:
        text (str): texte source
        source_url (str): URL d'origine, conservée pour la citation
        chunk_size (int): taille cible d'un chunk, en mots (proxy de tokens)
        overlap (int): nombre de mots partagés entre deux chunks consécutifs

    Retour:
        list[dict]: liste de {'text': str, 'url': str}
    """
    words = text.split()
    chunks = []
    step = max(chunk_size - overlap, 1)

    for i in range(0, len(words), step):
        chunk_words = words[i:i + chunk_size]
        if len(chunk_words) < 20:  # ignore les chunks résiduels trop courts
            continue
        chunks.append({"text": " ".join(chunk_words), "url": source_url})

    return chunks


def rerank(query: str, chunks: list[dict], top_k: int = TOP_K_CHUNKS,
           min_score: float = MIN_RERANK_SCORE) -> list[dict]:
    """
    Classe les chunks par pertinence par rapport à la question, filtre ceux
    jugés hors-sujet, et retourne les meilleurs restants.

    Paramètres:
        query (str): question de l'utilisateur
        chunks (list[dict]): chunks candidats (issus de chunk_text)
        top_k (int): nombre de chunks à conserver après tri/filtrage
        min_score (float): score minimum (0-1, après normalisation sigmoïde
                            du score brut du cross-encoder) pour qu'un chunk
                            soit conservé

    Retour:
        list[dict]: chunks triés par pertinence décroissante, avec les clés
                     'score' (score brut) et 'score_norm' (0-1) ajoutées
    """
    if not chunks:
        return []

    model = _get_model()
    pairs = [(query, c["text"]) for c in chunks]
    scores = model.predict(pairs)

    for chunk, score in zip(chunks, scores):
        chunk["score"] = float(score)
        # Le cross-encoder retourne un score brut non borné (logit) ; on le
        # ramène entre 0 et 1 avec une sigmoïde pour avoir un seuil lisible.
        chunk["score_norm"] = 1 / (1 + math.exp(-chunk["score"]))

    ranked = sorted(chunks, key=lambda c: c["score"], reverse=True)
    filtered = [c for c in ranked if c["score_norm"] >= min_score]

    if not filtered:
        # Si le filtre élimine tout (question très pointue, sources
        # imparfaites), on garde quand même le meilleur chunk disponible
        # plutôt que de retourner un pipeline complètement vide.
        filtered = ranked[:1]

    return filtered[:top_k]
