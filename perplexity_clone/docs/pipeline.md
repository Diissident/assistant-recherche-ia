# pipeline.py — Documentation

## Rôle
Point d'entrée principal du projet. Enchaîne toutes les étapes :
recherche → scraping → chunking → reranking → génération, et mesure le
temps de chaque étape.

## Fonctions

### `run_pipeline(query: str, verbose: bool = True) -> dict` *(async)*
Exécute le pipeline complet.

- **Paramètre** `query` : question en langage naturel
- **Paramètre** `verbose` : si `True`, affiche dans la console le temps
  pris par chaque étape (utile pour identifier les lenteurs)
- **Retour** : dict avec les clés :
  - `query` (str) : la question d'origine
  - `answer` (str) : la réponse générée, avec citations
  - `sources` (list[str]) : URLs effectivement utilisées dans la réponse
  - `timings` (dict) : durée en secondes de chaque étape (`search`,
    `scrape`, `chunk`, `rerank`, `generate`, `total`)
- **Comportement particulier** : si aucune page n'a pu être scrapée avec
  succès, retourne directement un message d'échec sans appeler le LLM
  (évite un appel inutile et coûteux en temps)

### `ask(query: str) -> dict`
Wrapper synchrone autour de `run_pipeline`, pour un usage simple depuis
un script classique ou un agent qui n'est pas conçu en `async`.

- **Paramètre** `query` : question de l'utilisateur
- **Retour** : identique à `run_pipeline`

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
