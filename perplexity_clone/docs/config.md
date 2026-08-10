# config.py — Documentation

## Rôle
Centralise tous les paramètres réglables du projet. Aucune fonction ici,
uniquement des constantes, pour éviter d'avoir des "valeurs magiques"
dispersées dans le code.

## Paramètres

| Paramètre | Type | Description |
|---|---|---|
| `SEARCH_ENGINE` | str | Nom du moteur de recherche utilisé (informatif) |
| `MAX_SEARCH_RESULTS` | int | Nombre de résultats de recherche récupérés par requête |
| `SEARCH_TIMEOUT` | int | Timeout (s) pour une requête de recherche |
| `SCRAPE_TIMEOUT` | int | Timeout (s) pour le téléchargement d'une page |
| `MAX_CONCURRENT_SCRAPES` | int | Nombre de pages scrapées en parallèle (limite la charge réseau/CPU) |
| `MIN_TEXT_LENGTH` | int | Longueur minimale (caractères) pour qu'une page soit gardée |
| `CHUNK_SIZE` | int | Taille cible d'un chunk de texte, en mots |
| `CHUNK_OVERLAP` | int | Chevauchement entre deux chunks consécutifs, en mots |
| `RERANKER_MODEL` | str | Nom du modèle Hugging Face utilisé pour le reranking |
| `TOP_K_CHUNKS` | int | Nombre de chunks conservés après reranking, envoyés au LLM |
| `LLM_BACKEND` | str | `"ollama"` (local, gratuit) ou `"groq"` (cloud, tier gratuit) |
| `OLLAMA_MODEL` | str | Nom du modèle Ollama à utiliser localement |
| `OLLAMA_HOST` | str | URL du serveur Ollama local |
| `GROQ_MODEL` | str | Nom du modèle Groq à utiliser |
| `GROQ_API_KEY` | str | Clé API Groq, lue depuis la variable d'environnement du même nom |
| `MAX_ANSWER_TOKENS` | int | Longueur max de la réponse générée |
| `CACHE_DIR` | str | Dossier où sont stockés les fichiers de cache |
| `CACHE_TTL_HOURS` | int | Durée de vie (heures) d'une entrée de cache avant expiration |

## Pourquoi ces choix
- **Aucune clé API obligatoire** : le backend par défaut (`ollama`) tourne
  entièrement en local, donc coût = 0€ tant que tu as une machine capable
  de faire tourner un modèle 7-8B (16 Go de RAM recommandés, GPU optionnel).
- **Groq en alternative** : si ta machine est trop limitée pour Ollama,
  Groq propose un tier gratuit sans carte bancaire à l'inscription — à
  vérifier régulièrement sur leur site, les conditions peuvent changer.
