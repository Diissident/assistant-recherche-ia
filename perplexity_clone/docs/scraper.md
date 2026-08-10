# scraper.py — Documentation

## Rôle
Télécharge et nettoie le contenu textuel des pages web trouvées par
`search.py`. Utilise `trafilatura`, une librairie open-source spécialisée
dans l'extraction de texte "principal" (sans menus, publicités, scripts).

## Fonctions

### `fetch_html(session, url: str) -> str | None`
Télécharge le HTML brut d'une page.

- **Paramètre** `session` : session `aiohttp.ClientSession` partagée
  (réutilise les connexions TCP, plus rapide que d'en ouvrir une par page)
- **Paramètre** `url` : URL cible
- **Retour** : HTML brut en texte, ou `None` en cas d'échec/timeout
  (timeout défini par `SCRAPE_TIMEOUT` dans `config.py`)

### `extract_text(html: str, url: str) -> str | None`
Extrait le texte principal d'une page HTML.

- **Paramètre** `html` : contenu HTML brut
- **Paramètre** `url` : URL d'origine (utile à `trafilatura` pour le contexte)
- **Retour** : texte nettoyé, ou `None` si le texte extrait est trop court
  (seuil `MIN_TEXT_LENGTH`) ou si l'extraction échoue
- **Paramètre interne** `favor_recall=True` : configuration de trafilatura
  qui privilégie la quantité de texte récupéré plutôt que la précision
  stricte — pertinent pour du RAG où on préfère avoir trop de contexte
  que pas assez.

### `scrape_one(session, semaphore, url: str) -> dict | None`
Scrape une seule page, avec cache et limitation de concurrence.

- **Paramètre** `semaphore` : `asyncio.Semaphore` limitant le nombre de
  scrapes simultanés (`MAX_CONCURRENT_SCRAPES`), pour ne pas saturer la
  connexion réseau ni se faire bloquer par les sites visités
- **Retour** : `{'url': str, 'text': str}` ou `None`

### `scrape_many(urls: list[str]) -> list[dict]`
Scrape une liste d'URLs en parallèle.

- **Paramètre** `urls` : URLs à scraper (issues de `search.py`)
- **Retour** : liste des pages réussies uniquement (les échecs sont filtrés)

## Bibliographie / dépendances
- `trafilatura` (PyPI, open-source, licence Apache 2.0) : extraction de
  texte principal, développé pour la recherche en humanités numériques.
- `aiohttp` (PyPI, open-source) : client HTTP asynchrone, permet le
  parallélisme sans multi-threading lourd.

## Points d'attention
- Certains sites bloquent le scraping automatisé (protection anti-bot,
  Cloudflare...). Le `User-Agent` personnalisé aide un peu mais ne
  contourne pas les protections avancées — dans ce cas la page est
  simplement ignorée (retour `None`), sans faire planter le pipeline.
