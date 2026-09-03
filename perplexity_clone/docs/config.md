# config.py — Documentation

## Rôle
Centralise tous les paramètres réglables du projet. Aucune fonction ici,
uniquement des constantes, pour éviter d'avoir des "valeurs magiques"
dispersées dans le code.

## Paramètres

| Paramètre | Type | Description |
|---|---|---|
| `SEARCH_ENGINE` | str | Nom du moteur de recherche utilisé (informatif) |
| `MAX_SEARCH_RESULTS` | int | Nombre de résultats de recherche récupérés par sous-requête |
| `MAX_TOTAL_PAGES` | int | Plafond global de pages retenues, toutes sous-requêtes confondues |
| `MAX_CHUNKS_TO_RERANK` | int | Plafond de chunks envoyés au reranker (borne le temps de traitement) |
| `SEARCH_TIMEOUT` | int | Timeout (s) pour une requête de recherche |
| `SCRAPE_TIMEOUT` | int | Timeout (s) pour le téléchargement d'une page |
| `MAX_CONCURRENT_SCRAPES` | int | Nombre de pages scrapées en parallèle (limite la charge réseau/CPU) |
| `MIN_TEXT_LENGTH` | int | Longueur minimale (caractères) pour qu'une page soit gardée |
| `MAX_PAGE_BYTES` | int | Taille max du HTML téléchargé ; au-delà la page est abandonnée |
| `ALLOWED_CONTENT_TYPES` | tuple | Types MIME acceptés au scraping (le reste est ignoré) |
| `ALLOW_PRIVATE_ADDRESSES` | bool | `False` = refuse localhost et les IP privées (garde-fou SSRF) |
| `CHUNK_SIZE` | int | Taille cible d'un chunk de texte, en mots |
| `CHUNK_OVERLAP` | int | Chevauchement entre deux chunks consécutifs, en mots |
| `RERANKER_MODEL` | str | Nom du modèle Hugging Face utilisé pour le reranking |
| `TOP_K_CHUNKS` | int | Nombre de chunks conservés après reranking, envoyés au LLM |
| `MIN_RERANK_SCORE` | float | Score normalisé (0-1) minimum pour qu'un chunk soit gardé |
| `WARMUP_RERANKER` | bool | Précharge le cross-encoder au démarrage du serveur |
| `ENABLE_QUERY_DECOMPOSITION` | bool | Décompose les questions complexes en sous-requêtes |
| `MAX_SUBQUERIES` | int | Nombre max de sous-requêtes générées |
| `LLM_BACKEND` | str | `"ollama"` (local, gratuit) ou `"groq"` (cloud, tier gratuit) |
| `OLLAMA_MODEL` | str | Nom du modèle Ollama à utiliser localement |
| `OLLAMA_HOST` | str | URL du serveur Ollama local |
| `OLLAMA_TIMEOUT` | int | Timeout (s) Ollama ; en streaming, porte sur l'attente entre deux fragments |
| `GROQ_MODEL` | str | Nom du modèle Groq à utiliser |
| `GROQ_API_KEY` | str | Clé API Groq, lue depuis la variable d'environnement du même nom |
| `GROQ_TIMEOUT` | int | Timeout (s) pour un appel Groq |
| `MAX_ANSWER_TOKENS` | int | Longueur max de la réponse générée (`num_predict` côté Ollama) |
| `MAX_SUBQUERY_TOKENS` | int | Budget de tokens pour la décomposition (sortie très courte) |
| `MAX_QUERY_LENGTH` | int | Longueur max acceptée pour une question ; au-delà, `422` |
| `CACHE_DIR` | str | Dossier où sont stockés les fichiers de cache |
| `CACHE_TTL_HOURS` | int | Durée de vie (heures) d'une entrée de cache avant expiration |
| `CACHE_FAILURE_TTL_HOURS` | int | TTL plus court pour les échecs de scraping (souvent transitoires) |
| `LOG_LEVEL` | str | Niveau de journalisation, surchargeable par la variable d'environnement `LOG_LEVEL` |

## Pourquoi ces choix
- **Aucune clé API obligatoire** : le backend par défaut (`ollama`) tourne
  entièrement en local, donc coût = 0€ tant que tu as une machine capable
  de faire tourner un modèle 7-8B (16 Go de RAM recommandés, GPU optionnel).
- **Groq en alternative** : si ta machine est trop limitée pour Ollama,
  Groq propose un tier gratuit sans carte bancaire à l'inscription — à
  vérifier régulièrement sur leur site, les conditions peuvent changer.
