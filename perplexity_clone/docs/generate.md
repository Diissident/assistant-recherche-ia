# generate.py — Documentation

## Rôle
Génère la réponse finale en langage naturel, avec citations, à partir de
la question et des chunks les plus pertinents. Supporte deux backends
gratuits interchangeables.

## Fonctions

### `decompose_query(query: str) -> list[str]`
Décompose une question potentiellement complexe en 1 à 3 sous-requêtes de
recherche plus ciblées, via un appel au LLM configuré.

- **Paramètre** `query` : question de l'utilisateur
- **Retour** : liste de 1 à `MAX_SUBQUERIES` sous-requêtes (la question
  d'origine si elle est déjà simple)
- **Coût** : un appel LLM supplémentaire avant la recherche, donc un peu
  de latence en plus — désactivable via `ENABLE_QUERY_DECOMPOSITION` dans
  `config.py`

### `build_prompt(query: str, chunks: list[dict]) -> str`
Construit le prompt final envoyé au LLM.

- **Paramètre** `query` : question de l'utilisateur
- **Paramètre** `chunks` : chunks pertinents (avec `text` et `url`)
- **Retour** : prompt complet, structuré ainsi :
  1. Instruction système (répondre uniquement à partir des sources, citer
     avec la notation `[Source N]`)
  2. La question
  3. Les sources numérotées avec leur URL
  4. Une invite finale pour la génération

### `generate_ollama(prompt: str) -> str`
Appelle un modèle local via l'API HTTP d'Ollama.

- **Paramètre** `prompt` : prompt complet (construit par `build_prompt`)
- **Retour** : texte généré par le modèle
- **Prérequis** : Ollama installé et lancé (`ollama serve`), modèle
  téléchargé au préalable (`ollama pull llama3.1:8b` par exemple)
- **Endpoint utilisé** : `POST /api/generate` sur `OLLAMA_HOST`
- **Coût** : 0€, tout tourne sur ta machine

### `generate_groq(prompt: str) -> str`
Appelle l'API cloud Groq (compatible format OpenAI).

- **Paramètre** `prompt` : prompt complet
- **Retour** : texte généré
- **Prérequis** : variable d'environnement `GROQ_API_KEY` définie (clé
  gratuite obtenue sur console.groq.com, sans carte bancaire à l'inscription
  au moment de la rédaction — à vérifier, les offres évoluent)
- **Paramètre API** `max_tokens` : limite la longueur de la réponse
  (`MAX_ANSWER_TOKENS` dans `config.py`)

### `generate_answer(query: str, chunks: list[dict]) -> str`
Point d'entrée principal du module — choisit automatiquement le backend
configuré dans `config.py` (`LLM_BACKEND`).

- **Paramètres** : identiques à `build_prompt`
- **Retour** : réponse finale générée

## Bibliographie / dépendances
- Ollama (ollama.com, open-source) : moteur d'exécution local pour LLM
  open-weight (Llama, Mistral, Qwen, etc.), gratuit, aucune limite d'usage
  autre que le matériel disponible.
- Groq (groq.com) : fournisseur cloud d'inférence LLM très rapide, tier
  gratuit avec quota (le montant exact évolue — se référer à leur
  documentation officielle avant de dépendre de ce backend en production).

## Point d'attention
Aucun de ces deux backends n'est garanti gratuit indéfiniment ; c'est le
fournisseur qui décide de ses conditions. Pour un coût vraiment nul et
stable dans le temps, `ollama` (local) est la seule option qui ne dépend
d'aucune politique tarifaire externe.
