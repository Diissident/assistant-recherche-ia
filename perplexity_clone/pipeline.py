"""
pipeline.py
-----------
Orchestrateur principal : enchaîne recherche -> scraping -> chunking ->
reranking -> génération. C'est le point d'entrée à utiliser depuis un
agent IA ou en ligne de commande.

Toutes les étapes bloquantes (appel LLM, inférence du cross-encoder) sont
déportées dans un thread : `run_pipeline` est une coroutine, et exécuter du
code CPU/réseau synchrone dedans gèlerait la boucle d'événements — donc
sérialiserait aussi les requêtes concurrentes du serveur HTTP.

Le paramètre `on_progress` permet de suivre l'avancement en temps réel
(étapes franchies et fragments de réponse au fil de leur génération) ; c'est
ce qui alimente l'affichage en streaming de l'interface.
"""

import asyncio
import logging
import time
from typing import Callable, Optional

import generate
import rerank
import search
from config import ENABLE_QUERY_DECOMPOSITION, MAX_CHUNKS_TO_RERANK, MAX_TOTAL_PAGES
from scraper import scrape_many

logger = logging.getLogger(__name__)

# Callback d'avancement. Il doit être **thread-safe** : les événements de type
# "token" sont émis depuis le thread de génération, pas depuis la boucle
# d'événements (cf. api.py, qui passe par loop.call_soon_threadsafe).
ProgressCallback = Optional[Callable[[dict], None]]

STEPS = ("decompose", "search", "scrape", "chunk", "rerank", "generate")


def _merge_chunks_by_source(chunks: list[dict]) -> list[dict]:
    """
    Regroupe en une seule source citable les chunks issus d'une même page.

    Sans ça, deux extraits de la même URL deviennent [Source 1] et [Source 2] :
    le modèle croit s'appuyer sur deux sources indépendantes, et l'interface
    affiche deux fois le même lien. Les chunks arrivent triés par pertinence,
    donc la page la mieux classée conserve le numéro 1.

    Paramètres:
        chunks (list[dict]): chunks triés, avec 'text' et 'url'

    Retour:
        list[dict]: une entrée {'text', 'url'} par URL distincte
    """
    by_url: dict[str, list[str]] = {}
    for chunk in chunks:
        by_url.setdefault(chunk["url"], []).append(chunk["text"])

    return [
        {"url": url, "text": "\n[…]\n".join(texts)}
        for url, texts in by_url.items()
    ]


def _select_chunks(per_page_chunks: list[list[dict]], budget: int) -> list[dict]:
    """
    Répartit équitablement le budget de chunks entre les pages (round-robin)
    plutôt que de tout prendre sur les premières pages — une page très longue
    (article de fond) ne doit pas à elle seule saturer le budget envoyé au
    reranker et faire exploser le temps de traitement.

    Paramètres:
        per_page_chunks: chunks groupés par page
        budget (int): nombre maximum de chunks à retenir au total

    Retour:
        list[dict]: chunks sélectionnés
    """
    selected: list[dict] = []
    idx = 0
    longest = max((len(pc) for pc in per_page_chunks), default=0)

    while idx < longest and len(selected) < budget:
        for page_chunks in per_page_chunks:
            if idx < len(page_chunks):
                selected.append(page_chunks[idx])
                if len(selected) >= budget:
                    break
        idx += 1

    return selected


async def run_pipeline(query: str, verbose: bool = False,
                       on_progress: ProgressCallback = None) -> dict:
    """
    Exécute le pipeline complet pour une question donnée.

    Paramètres:
        query (str): question de l'utilisateur, en langage naturel
        verbose (bool): si True, affiche les temps de chaque étape sur la
                         sortie standard (pratique en ligne de commande ;
                         le serveur passe par le logger à la place)
        on_progress: callback thread-safe recevant des événements
                      {'type': 'step'|'token', ...} au fil de l'exécution

    Retour:
        dict: {
            'query': str,
            'answer': str,
            'sources': list[dict],
            'timings': dict[str, float]
        }

    Lève:
        generate.LLMError: si le modèle de génération est injoignable ou
            refuse la requête. Les autres étapes dégradent silencieusement
            (une recherche ou une page en échec est simplement ignorée).
    """
    timings: dict[str, float] = {}
    t0 = time.time()

    def emit(event: dict) -> None:
        if on_progress is not None:
            on_progress(event)

    async def step(name: str, action):
        """Chronomètre une étape et notifie son début/sa fin."""
        emit({"type": "step", "step": name, "status": "start"})
        started = time.time()
        result = await action()
        timings[name] = time.time() - started
        emit({"type": "step", "step": name, "status": "done",
              "duration": timings[name]})
        return result

    # 1. Décomposition éventuelle de la question en sous-requêtes, puis
    #    recherche web sur chacune d'elles (en parallèle).
    if ENABLE_QUERY_DECOMPOSITION:
        subqueries = await step(
            "decompose",
            lambda: asyncio.to_thread(generate.decompose_query, query),
        )
    else:
        subqueries = [query]
        timings["decompose"] = 0.0

    results_by_query = await step(
        "search", lambda: search.search_multiple(subqueries)
    )

    # Fusion des résultats de toutes les sous-requêtes, en dédupliquant
    # les URLs déjà vues (une même page peut ressortir sur plusieurs
    # sous-requêtes).
    urls = []
    seen = set()
    for sub_results in results_by_query.values():
        for r in sub_results:
            href = r.get("href")
            if href and href not in seen:
                seen.add(href)
                urls.append(href)

    # Plafond global : quel que soit le nombre de sous-requêtes générées,
    # on ne scrape/reranke jamais plus de MAX_TOTAL_PAGES pages au total.
    urls = urls[:MAX_TOTAL_PAGES]

    # 2. Scraping des pages trouvées
    scraped = await step("scrape", lambda: scrape_many(urls))

    if not scraped:
        timings["total"] = time.time() - t0
        message = (
            "Aucune source exploitable trouvée pour cette question."
            if urls else
            "La recherche web n'a renvoyé aucun résultat. Vérifie ta connexion "
            "ou reformule la question."
        )
        emit({"type": "token", "text": message})
        return {
            "query": query,
            "answer": message,
            "sources": [],
            "timings": timings,
        }

    # 3. Chunking de chaque page scrapée
    async def do_chunk():
        per_page = [rerank.chunk_text(page["text"], page["url"]) for page in scraped]
        return _select_chunks(per_page, MAX_CHUNKS_TO_RERANK)

    all_chunks = await step("chunk", do_chunk)

    # 4. Reranking : on garde les chunks les plus pertinents. L'inférence du
    #    cross-encoder est du calcul CPU pur, donc dans un thread.
    top_chunks = await step(
        "rerank", lambda: asyncio.to_thread(rerank.rerank, query, all_chunks)
    )

    # Une même page peut fournir plusieurs des meilleurs chunks : on les
    # regroupe pour que la numérotation des citations corresponde aux pages.
    merged_sources = _merge_chunks_by_source(top_chunks)

    # 5. Génération de la réponse finale avec citations
    def on_token(fragment: str) -> None:
        emit({"type": "token", "text": fragment})

    answer = await step(
        "generate",
        lambda: asyncio.to_thread(
            generate.generate_answer,
            query,
            merged_sources,
            on_token if on_progress is not None else None,
        ),
    )

    timings["total"] = time.time() - t0

    summary = ", ".join(f"{k}={v:.2f}s" for k, v in timings.items())
    logger.info("Pipeline terminé (%s)", summary)
    if verbose:
        print("--- Temps par étape (secondes) ---")
        for step_name, duration in timings.items():
            print(f"{step_name}: {duration:.2f}s")

    sources = [{"n": i + 1, "url": c["url"]} for i, c in enumerate(merged_sources)]

    return {
        "query": query,
        "answer": answer,
        "sources": sources,
        "timings": timings,
    }


def ask(query: str, on_progress: ProgressCallback = None) -> dict:
    """
    Wrapper synchrone pratique pour appeler le pipeline depuis un script
    ou un agent qui ne gère pas nativement l'async.

    Paramètres:
        query (str): question de l'utilisateur
        on_progress: callback d'avancement optionnel (cf. run_pipeline)

    Retour:
        dict: identique à run_pipeline
    """
    return asyncio.run(run_pipeline(query, on_progress=on_progress))


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    question = " ".join(sys.argv[1:]) or "Quelles sont les dernières nouvelles sur l'IA ?"
    result = asyncio.run(run_pipeline(question, verbose=True))
    print("\n=== RÉPONSE ===")
    print(result["answer"])
    print("\n=== SOURCES ===")
    for s in result["sources"]:
        print(f"[Source {s['n']}] {s['url']}")
