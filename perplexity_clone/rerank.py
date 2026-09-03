"""
rerank.py
---------
Découpe les textes scrapés en chunks, puis classe ces chunks par pertinence
par rapport à la question de l'utilisateur, via un reranker cross-encoder
open-source (gratuit, tourne en local sur CPU).
"""

import logging
import math
import threading

from sentence_transformers import CrossEncoder

from config import (CHUNK_OVERLAP, CHUNK_SIZE, MIN_RERANK_SCORE,
                    RERANKER_MODEL, TOP_K_CHUNKS)

logger = logging.getLogger(__name__)

# Le modèle est chargé une seule fois au niveau module (coûteux à instancier).
# Le verrou évite que deux requêtes simultanées ne déclenchent deux
# chargements concurrents du même modèle au premier appel.
_model: CrossEncoder | None = None
_model_lock = threading.Lock()


def _get_model() -> CrossEncoder:
    """
    Charge (une seule fois) et retourne le modèle de reranking.
    Chargement paresseux pour ne pas ralentir l'import du module.
    """
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                logger.info("Chargement du reranker %s…", RERANKER_MODEL)
                _model = CrossEncoder(RERANKER_MODEL)
                logger.info("Reranker prêt.")
    return _model


def warmup() -> None:
    """
    Force le chargement du modèle en amont de la première question.

    Appelée au démarrage du serveur (en tâche de fond) : sans ça, la toute
    première recherche paie 10 à 20 secondes de chargement de modèle sans
    aucun retour visible dans l'interface.
    """
    try:
        _get_model()
    except Exception as exc:
        # Un échec de préchargement ne doit pas empêcher le serveur de
        # démarrer : le chargement sera retenté à la première question.
        logger.warning("Préchargement du reranker impossible : %s", exc)


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
        if len(chunk_words) >= 20:  # ignore les chunks résiduels trop courts
            chunks.append({"text": " ".join(chunk_words), "url": source_url})
        # La fenêtre atteint la fin du texte : continuer produirait un dernier
        # chunk entièrement contenu dans celui-ci (pur doublon envoyé au
        # reranker).
        if i + chunk_size >= len(words):
            break

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
        list[dict]: nouveaux dicts triés par pertinence décroissante, avec les
                     clés 'score' (score brut) et 'score_norm' (0-1) ajoutées.
                     Les dicts passés en entrée ne sont pas modifiés.
    """
    if not chunks:
        return []

    model = _get_model()
    pairs = [(query, c["text"]) for c in chunks]
    scores = model.predict(pairs)

    scored = []
    for chunk, score in zip(chunks, scores):
        score = float(score)
        scored.append({
            **chunk,
            "score": score,
            # Le cross-encoder retourne un score brut non borné (logit) ; on le
            # ramène entre 0 et 1 avec une sigmoïde pour avoir un seuil lisible.
            "score_norm": 1 / (1 + math.exp(-score)),
        })

    ranked = sorted(scored, key=lambda c: c["score"], reverse=True)
    filtered = [c for c in ranked if c["score_norm"] >= min_score]

    if not filtered:
        # Si le filtre élimine tout (question très pointue, sources
        # imparfaites), on garde quand même le meilleur chunk disponible
        # plutôt que de retourner un pipeline complètement vide.
        filtered = ranked[:1]

    return filtered[:top_k]
