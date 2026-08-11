"""
pipeline.py
-----------
Orchestrateur principal : enchaîne recherche -> scraping -> chunking ->
reranking -> génération. C'est le point d'entrée à utiliser depuis un
agent IA ou en ligne de commande.
"""

import asyncio
import time

import generate
import rerank
import search
from scraper import scrape_many


async def run_pipeline(query: str, verbose: bool = True) -> dict:
    """
    Exécute le pipeline complet pour une question donnée.

    Paramètres:
        query (str): question de l'utilisateur, en langage naturel
        verbose (bool): si True, affiche les temps de chaque étape (utile
                         pour identifier les goulots d'étranglement)

    Retour:
        dict: {
            'query': str,
            'answer': str,
            'sources': list[str],
            'timings': dict[str, float]
        }
    """
    timings = {}
    t0 = time.time()

    # 1. Recherche web (une seule requête ici ; extensible à plusieurs
    #    sous-requêtes via search.search_multiple si besoin)
    results = await search.search_async(query)
    urls = [r["href"] for r in results if "href" in r]
    timings["search"] = time.time() - t0

    # 2. Scraping des pages trouvées
    t1 = time.time()
    scraped = await scrape_many(urls)
    timings["scrape"] = time.time() - t1

    if not scraped:
        return {
            "query": query,
            "answer": "Aucune source exploitable trouvée pour cette question.",
            "sources": [],
            "timings": timings,
        }

    # 3. Chunking de chaque page scrapée
    t2 = time.time()
    all_chunks = []
    for page in scraped:
        all_chunks.extend(rerank.chunk_text(page["text"], page["url"]))
    timings["chunk"] = time.time() - t2

    # 4. Reranking : on garde les chunks les plus pertinents
    t3 = time.time()
    top_chunks = rerank.rerank(query, all_chunks)
    timings["rerank"] = time.time() - t3

    # 5. Génération de la réponse finale avec citations
    t4 = time.time()
    answer = generate.generate_answer(query, top_chunks)
    timings["generate"] = time.time() - t4

    timings["total"] = time.time() - t0

    if verbose:
        print("--- Temps par étape (secondes) ---")
        for step, duration in timings.items():
            print(f"{step}: {duration:.2f}s")

    sources = [{"n": i + 1, "url": c["url"]} for i, c in enumerate(top_chunks)]

    return {
        "query": query,
        "answer": answer,
        "sources": sources,
        "timings": timings,
    }


def ask(query: str) -> dict:
    """
    Wrapper synchrone pratique pour appeler le pipeline depuis un script
    ou un agent qui ne gère pas nativement l'async.

    Paramètres:
        query (str): question de l'utilisateur

    Retour:
        dict: identique à run_pipeline
    """
    return asyncio.run(run_pipeline(query))


if __name__ == "__main__":
    import sys

    question = " ".join(sys.argv[1:]) or "Quelles sont les dernières nouvelles sur l'IA ?"
    result = ask(question)
    print("\n=== RÉPONSE ===")
    print(result["answer"])
    print("\n=== SOURCES ===")
    for s in result["sources"]:
        print(f"[Source {s['n']}] {s['url']}")
