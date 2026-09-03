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
MAX_PAGE_BYTES = 2_000_000        # taille max du HTML téléchargé (2 Mo). Au-delà
                                   # on abandonne la page : inutile de charger un
                                   # document géant en mémoire pour en extraire
                                   # quelques paragraphes.
ALLOWED_CONTENT_TYPES = ("text/html", "application/xhtml+xml", "text/plain")
ALLOW_PRIVATE_ADDRESSES = False   # si False, refuse de scraper localhost et les
                                   # plages IP privées / lien-local (garde-fou
                                   # SSRF : une page de résultats malveillante ne
                                   # peut pas faire interroger le réseau local ni
                                   # les endpoints de métadonnées cloud)

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
WARMUP_RERANKER = True            # charge le cross-encoder au démarrage du
                                   # serveur, en tâche de fond : sans ça, la
                                   # toute première question paie ~10-20s de
                                   # chargement de modèle sans aucun retour.

# --- Décomposition de requête ---
ENABLE_QUERY_DECOMPOSITION = True # décompose les questions complexes en
                                   # plusieurs sous-requêtes de recherche
MAX_SUBQUERIES = 3                # nombre max de sous-requêtes générées

# --- Génération LLM ---
# Deux options gratuites : Ollama en local (aucune clé), ou Groq (clé API gratuite).
LLM_BACKEND = "ollama"            # "ollama" ou "groq"
OLLAMA_MODEL = "llama3.2:3b"      # 8B -> 3B : le plus gros levier sur CPU faible
OLLAMA_HOST = "http://localhost:11434"
OLLAMA_TIMEOUT = 180              # secondes. Génération en streaming : le timeout
                                   # porte sur l'attente entre deux fragments, pas
                                   # sur la durée totale de la réponse.

GROQ_MODEL = "llama-3.1-8b-instant"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")  # clé gratuite sur console.groq.com
GROQ_TIMEOUT = 60

MAX_ANSWER_TOKENS = 400
MAX_SUBQUERY_TOKENS = 120         # la décomposition ne produit que 1 à 3 lignes :
                                   # inutile de laisser le modèle partir en
                                   # digression, ça ne fait qu'ajouter de la latence

# --- Requête utilisateur ---
MAX_QUERY_LENGTH = 2000           # garde-fou : au-delà ce n'est plus une question
                                   # de recherche, et ça sature le contexte du LLM

# --- Cache ---
CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache_data")
CACHE_TTL_HOURS = 48              # durée de vie du cache de recherche
CACHE_FAILURE_TTL_HOURS = 1       # durée de vie plus courte pour les échecs de
                                   # scraping : un timeout est souvent transitoire,
                                   # inutile de condamner une page pendant 48h

# --- Journalisation ---
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

os.makedirs(CACHE_DIR, exist_ok=True)
