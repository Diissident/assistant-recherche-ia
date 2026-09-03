# scraper.py — Documentation

## Rôle
Télécharge et nettoie le contenu textuel des pages web trouvées par
`search.py`. Utilise `trafilatura`, une librairie open-source spécialisée
dans l'extraction de texte "principal" (sans menus, publicités, scripts).

Les URLs traitées ici viennent d'un moteur de recherche, donc d'une **source
non maîtrisée**. Le module applique trois garde-fous avant d'extraire quoi que
ce soit : filtre d'adresses, plafond de taille, vérification du type de contenu.

## Fonctions

### `_is_public_host(host: str) -> bool` / `is_url_allowed(url: str) -> bool`
Garde-fou SSRF. `is_url_allowed` vérifie que le schéma est `http(s)` puis, sauf
si `ALLOW_PRIVATE_ADDRESSES` est activé, résout le nom d'hôte et refuse toute
adresse non publique : loopback, plages privées (`10/8`, `192.168/16`…),
lien-local (`169.254/16`, qui inclut **l'endpoint de métadonnées des principaux
clouds**), réservée ou multicast.

Sans ce filtre, une page de résultats piégée pourrait faire interroger le réseau
local de la machine par le scraper. La résolution DNS est déportée dans un
thread pour ne pas bloquer la boucle d'événements.

`ALLOW_PRIVATE_ADDRESSES = True` existe pour un usage légitime (scraper un wiki
interne) ; la vérification du schéma reste appliquée même dans ce mode.

### `fetch_html(session, url: str) -> str | None`
Télécharge le HTML brut d'une page.

- **Paramètre** `session` : session `aiohttp.ClientSession` partagée
  (réutilise les connexions TCP, plus rapide que d'en ouvrir une par page)
- **Paramètre** `url` : URL cible
- **Retour** : HTML brut en texte, ou `None` en cas d'échec/timeout
  (`aiohttp.ClientTimeout(total=SCRAPE_TIMEOUT)`)
- **Rejets supplémentaires** :
  - **redirection** sortant vers une adresse privée (la destination réelle est
    revérifiée, pas seulement l'URL de départ)
  - **type de contenu** hors `ALLOWED_CONTENT_TYPES` : inutile de passer un PDF
    ou une image à trafilatura
  - **taille** au-delà de `MAX_PAGE_BYTES`, vérifiée sur l'en-tête
    `Content-Length` *et* à la lecture. Lire la réponse d'un coup chargerait en
    mémoire un document de plusieurs centaines de Mo servi sans `Content-Length`.

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
- **Cache** : les échecs sont mémorisés avec un TTL court
  (`CACHE_FAILURE_TTL_HOURS`) et non les 48h du cache normal — un timeout est
  souvent transitoire, et condamner la page deux jours serait excessif.
- **Extraction dans un thread** : `trafilatura` est du calcul CPU pur (parsing
  HTML + heuristiques). Sans `asyncio.to_thread`, chaque extraction gèlerait la
  boucle d'événements et **sérialiserait les téléchargements censés être
  parallèles**.

### `scrape_many(urls: list[str]) -> list[dict]`
Scrape une liste d'URLs en parallèle.

- **Paramètre** `urls` : URLs à scraper (issues de `search.py`)
- **Retour** : liste des pages réussies uniquement (les échecs sont filtrés
  et journalisés, une page en erreur n'interrompt pas les autres)

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
