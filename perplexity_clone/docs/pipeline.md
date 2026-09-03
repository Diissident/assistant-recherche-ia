# pipeline.py — Documentation

## Rôle
Point d'entrée principal du projet. Enchaîne toutes les étapes :
recherche → scraping → chunking → reranking → génération, et mesure le
temps de chaque étape.

## Fonctions

### `run_pipeline(query, verbose=False, on_progress=None) -> dict` *(async)*
Exécute le pipeline complet.

- **Paramètre** `query` : question en langage naturel
- **Paramètre** `verbose` : si `True`, affiche dans la console le temps
  pris par chaque étape (utile en ligne de commande ; le serveur passe par
  le logger à la place)
- **Paramètre** `on_progress` : callback recevant des événements
  `{'type': 'step'|'token', ...}` au fil de l'exécution. **Il doit être
  thread-safe** : les événements `token` sont émis depuis le thread de
  génération, pas depuis la boucle d'événements (`api.py` passe par
  `loop.call_soon_threadsafe`).
- **Retour** : dict avec les clés :
  - `query` (str) : la question d'origine
  - `answer` (str) : la réponse générée, avec citations
  - `sources` (list[dict]) : `{'n', 'url'}`, une entrée par page distincte
  - `timings` (dict) : durée en secondes de chaque étape (`decompose`,
    `search`, `scrape`, `chunk`, `rerank`, `generate`, `total`)
- **Lève** : `generate.LLMError` si le modèle est injoignable. Les autres
  étapes dégradent silencieusement — une recherche ou une page en échec est
  simplement ignorée.
- **Comportement particulier** : si aucune page n'a pu être scrapée avec
  succès, retourne directement un message d'échec sans appeler le LLM
  (évite un appel inutile et coûteux en temps)

### `ask(query, on_progress=None) -> dict`
Wrapper synchrone autour de `run_pipeline`, pour un usage simple depuis
un script classique ou un agent qui n'est pas conçu en `async`.

- **Retour** : identique à `run_pipeline`

## Fonctions internes

### `_select_chunks(per_page_chunks, budget) -> list[dict]`
Répartit le budget de chunks entre les pages en **round-robin** plutôt que de
tout prendre sur les premières. Une page très longue (article de fond) ne doit
pas saturer à elle seule le budget envoyé au reranker et faire exploser le
temps de traitement.

### `_merge_chunks_by_source(chunks) -> list[dict]`
Regroupe en une seule source citable les chunks issus d'une même page.

Sans ce regroupement, deux extraits de la même URL deviennent `[Source 1]` et
`[Source 2]` : le modèle croit s'appuyer sur deux sources indépendantes, et
l'interface affiche deux fois le même lien. Les chunks arrivant triés par
pertinence, la page la mieux classée conserve le numéro 1.

## Note sur l'asynchronisme
`run_pipeline` est une coroutine, mais trois étapes sont intrinsèquement
bloquantes : l'appel au LLM (`decompose`, `generate`) et l'inférence du
cross-encoder (`rerank`). Elles sont déportées dans un thread via
`asyncio.to_thread`. Les exécuter directement gèlerait la boucle d'événements
et sérialiserait aussi les requêtes concurrentes du serveur HTTP — y compris
le flux SSE censé rendre compte de l'avancement.

## Utilisation en ligne de commande
Le fichier peut être exécuté directement :

```bash
python pipeline.py "Quelle est la capitale de l'Australie ?"
```

Affiche la réponse et la liste des sources utilisées.

## Intégration dans un agent IA
Pour brancher ce pipeline dans un agent (ex: comme "outil" de recherche) :

```python
from pipeline import ask

def outil_recherche_web(question: str) -> str:
    resultat = ask(question)
    return resultat["answer"]
```

Cette fonction peut ensuite être enregistrée comme "tool" dans n'importe
quel framework d'agent (LangChain, un agent fait maison, etc.).
