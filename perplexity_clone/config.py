"""
config.py
---------
Configuration centrale du pipeline. Toutes les valeurs sont modifiables
sans toucher au reste du code.
"""

import os

# --- Recherche web ---
SEARCH_ENGINE = "duckduckgo"      # moteur utilisé (gratuit, pas de clé API)
MAX_SEARCH_RESULTS = 8            # nombre de pages candidates par sous-requête
MAX_TOTAL_PAGES = 8                # plafond global de pages retenues, tous
                                    # les sous-requêtes confondues (évite que
                                    # la décomposition ne multiplie le volume
                                    # envoyé au reranker sans limite)
MAX_CHUNKS_TO_RERANK = 40          # plafond du nombre total de chunks
                                    # envoyés au reranker, indépendamment du
                                    # nombre de pages : des pages longues
                                    # (articles de fond) génèrent beaucoup
                                    # plus de chunks que des pages courtes,
                                    # donc le nombre de pages seul ne suffit
                                    # pas à borner le temps de reranking
SEARCH_TIMEOUT = 5                # secondes avant abandon d'une requête de recherche

# --- Scraping ---
SCRAPE_TIMEOUT = 3                # secondes avant abandon du scraping d'une page
MAX_CONCURRENT_SCRAPES = 8        # nombre de pages scrapées en parallèle
MIN_TEXT_LENGTH = 200             # caractères minimum pour garder une page

# --- Chunking ---
CHUNK_SIZE = 350                  # taille approx. d'un chunk en tokens
CHUNK_OVERLAP = 50                # chevauchement entre deux chunks consécutifs

# --- Reranking ---
RERANKER_MODEL = "BAAI/bge-reranker-base"  # modèle open-source, gratuit, local
TOP_K_CHUNKS = 4                  # nombre de chunks gardés après reranking
MIN_RERANK_SCORE = 0.3            # score minimum (0-1, après normalisation)
                                   # pour qu'un chunk soit gardé. Un chunk
                                   # jugé hors-sujet par le reranker sera
                                   # exclu même si TOP_K_CHUNKS n'est pas
                                   # encore atteint. À ajuster : plus haut
                                   # = plus strict (risque de sources vides
                                   # sur des questions pointues), plus bas
                                   # = plus permissif.

# --- Décomposition de requête ---
ENABLE_QUERY_DECOMPOSITION = True # décompose les questions complexes en
                                   # plusieurs sous-requêtes de recherche
MAX_SUBQUERIES = 3                # nombre max de sous-requêtes générées

# --- Génération LLM ---
# Deux options gratuites : Ollama en local (aucune clé), ou Groq (clé API gratuite).
LLM_BACKEND = "ollama"            # "ollama" ou "groq"
OLLAMA_MODEL = "llama3.2:3b"      # 8B -> 3B : le plus gros levier sur CPU faible      # modèle local via Ollama (gratuit, tourne en local)
OLLAMA_HOST = "http://localhost:11434"

GROQ_MODEL = "llama-3.1-8b-instant"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")  # clé gratuite sur console.groq.com

MAX_ANSWER_TOKENS = 400

# --- Cache ---
CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache_data")
CACHE_TTL_HOURS = 48              # durée de vie du cache de recherche

os.makedirs(CACHE_DIR, exist_ok=True)
