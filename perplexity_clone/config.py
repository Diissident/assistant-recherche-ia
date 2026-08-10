"""
config.py
---------
Configuration centrale du pipeline. Toutes les valeurs sont modifiables
sans toucher au reste du code.
"""

import os

# --- Recherche web ---
SEARCH_ENGINE = "duckduckgo"      # moteur utilisé (gratuit, pas de clé API)
MAX_SEARCH_RESULTS = 10            # nombre de pages candidates par requête
SEARCH_TIMEOUT = 5                # secondes avant abandon d'une requête de recherche

# --- Scraping ---
SCRAPE_TIMEOUT = 3                # secondes avant abandon du scraping d'une page
MAX_CONCURRENT_SCRAPES = 10        # nombre de pages scrapées en parallèle
MIN_TEXT_LENGTH = 200             # caractères minimum pour garder une page

# --- Chunking ---
CHUNK_SIZE = 350                  # taille approx. d'un chunk en tokens
CHUNK_OVERLAP = 50                # chevauchement entre deux chunks consécutifs

# --- Reranking ---
RERANKER_MODEL = "BAAI/bge-reranker-base"  # modèle open-source, gratuit, local
TOP_K_CHUNKS = 10                  # nombre de chunks gardés après reranking

# --- Génération LLM ---
# Deux options gratuites : Ollama en local (aucune clé), ou Groq (clé API gratuite).
LLM_BACKEND = "ollama"            # "ollama" ou "groq"
OLLAMA_MODEL = "llama3.1:8b"      # modèle local via Ollama (gratuit, tourne en local)
OLLAMA_HOST = "http://localhost:11434"

GROQ_MODEL = "llama-3.1-8b-instant"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")  # clé gratuite sur console.groq.com

MAX_ANSWER_TOKENS = 1600

# --- Cache ---
CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache_data")
CACHE_TTL_HOURS = 48              # durée de vie du cache de recherche

os.makedirs(CACHE_DIR, exist_ok=True)
