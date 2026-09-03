# search.py — Documentation

## Rôle
Effectue les recherches web via DuckDuckGo, sans clé API. S'appuie sur la
librairie open-source `duckduckgo-search`.

## Fonctions

### `search_sync(query: str, max_results: int = MAX_SEARCH_RESULTS) -> list[dict]`
Recherche synchrone (bloquante).

- **Paramètre** `query` : texte de la requête de recherche
- **Paramètre** `max_results` : nombre max de résultats souhaités
- **Retour** : liste de dicts, chacun avec les clés `title`, `href` (URL),
  `body` (extrait de la page)
- **Comportement** : vérifie d'abord le cache avant d'appeler DuckDuckGo.
  **Seules les recherches fructueuses sont mises en cache** : une liste vide
  vient presque toujours d'un rate-limit passager, et la mémoriser 48h
  condamnerait la requête bien après le retour à la normale.
- **Lève** : les exceptions de DDGS (réseau, rate-limit). Les appelants
  asynchrones les attrapent.

### `search_async(query: str, max_results: int = MAX_SEARCH_RESULTS) -> list[dict]`
Version asynchrone de `search_sync`, exécutée dans un thread séparé
(`asyncio.to_thread`) car `duckduckgo-search` n'a pas d'API native async.

- **Retour** : les résultats, ou une **liste vide** en cas d'échec. Une
  sous-requête qui échoue ne doit pas priver le pipeline des autres.

### `search_multiple(queries: list[str]) -> dict[str, list[dict]]`
Lance plusieurs recherches en parallèle — utile si la question initiale
est décomposée en plusieurs sous-requêtes (ex: une question complexe
transformée en 2-3 recherches ciblées).

- **Paramètre** `queries` : liste de requêtes à exécuter
- **Retour** : dict associant chaque requête à ses résultats ; une sous-requête
  en échec est présente avec une liste vide
- **Détail** : `asyncio.gather(..., return_exceptions=True)`. Sans ce réglage,
  une seule sous-requête rate-limitée par DuckDuckGo ferait échouer **toute**
  la phase de recherche.

## Bibliographie / dépendance
- `duckduckgo-search` (PyPI) : wrapper Python non-officiel pour DuckDuckGo,
  gratuit, sans clé API, respecte les CGU d'usage raisonnable de DDG.
  Attention : un usage très intensif peut entraîner un blocage temporaire
  par rate-limiting côté DuckDuckGo — c'est géré en amont par le cache.
