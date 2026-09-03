# generate.py — Documentation

## Rôle
Génère la réponse finale en langage naturel, avec citations, à partir de
la question et des chunks les plus pertinents. Supporte deux backends
gratuits interchangeables.

## Exceptions

### `LLMError`
Erreur d'appel au modèle, portant un message destiné à l'utilisateur final
(« Ollama est injoignable sur… », « Clé GROQ_API_KEY invalide »…). Elle
distingue un problème explicable et courant — service arrêté, modèle absent,
quota atteint — d'un vrai bug du pipeline. `api.py` la traduit en `502` sur
`/ask` et en événement `error` sur `/ask/stream`.

## Fonctions

### `_call_llm(prompt, *, max_tokens, on_token=None) -> str`
Fonction interne : aiguille vers le backend configuré (`LLM_BACKEND`). Point de
passage unique, pour que les appelants n'aient pas à connaître la liste des
backends ni à dupliquer l'aiguillage.

### `decompose_query(query: str) -> list[str]`
Décompose une question potentiellement complexe en 1 à 3 sous-requêtes de
recherche plus ciblées, via un appel au LLM configuré.

- **Paramètre** `query` : question de l'utilisateur
- **Retour** : liste de 1 à `MAX_SUBQUERIES` sous-requêtes (la question
  d'origine si elle est déjà simple)
- **Coût** : un appel LLM supplémentaire avant la recherche, donc un peu
  de latence en plus — désactivable via `ENABLE_QUERY_DECOMPOSITION` dans
  `config.py`. Le budget de tokens est plafonné à `MAX_SUBQUERY_TOKENS` :
  la sortie attendue tient en 1 à 3 lignes, laisser le modèle digresser
  n'ajouterait que de la latence.
- **En cas d'échec du modèle** : retombe sur la question d'origine plutôt que
  de lever. La décomposition est une optimisation, pas une étape critique.

### `build_prompt(query: str, chunks: list[dict]) -> str`
Construit le prompt final envoyé au LLM.

- **Paramètre** `query` : question de l'utilisateur
- **Paramètre** `chunks` : chunks pertinents (avec `text` et `url`)
- **Retour** : prompt complet, structuré ainsi :
  1. Instruction système (répondre uniquement à partir des sources, citer
     avec la notation `[Source N]`)
  2. La question
  3. Les sources numérotées avec leur URL, encadrées par `<sources>…</sources>`
  4. Une invite finale pour la génération

Le contenu des sources vient de pages web arbitraires. Les délimiteurs
explicites, accompagnés d'une consigne indiquant qu'il s'agit de **données à
citer et non d'instructions à suivre**, réduisent la prise d'une page piégée
(« ignore les instructions précédentes »). Ça n'élimine pas le risque
d'injection de prompt, mais ça le rend nettement moins facile.

### `generate_ollama(prompt, *, max_tokens=MAX_ANSWER_TOKENS, on_token=None) -> str`
Appelle un modèle local via l'API HTTP d'Ollama.

- **Paramètre** `prompt` : prompt complet (construit par `build_prompt`)
- **Paramètre** `max_tokens` : transmis en `options.num_predict`. **Sans ce
  réglage, Ollama ignore complètement le budget de tokens** et peut générer
  jusqu'à saturer son contexte — c'est ce qui rendait le backend local
  incohérent avec Groq.
- **Paramètre** `on_token` : si fourni, la réponse est streamée et le callback
  reçoit chaque fragment
- **Retour** : texte généré par le modèle (complet, même en streaming)
- **Prérequis** : Ollama installé et lancé (`ollama serve`), modèle
  téléchargé au préalable (`ollama pull llama3.2:3b` par exemple)
- **Endpoint utilisé** : `POST /api/generate` sur `OLLAMA_HOST`
- **Coût** : 0€, tout tourne sur ta machine
- **Timeout** : `OLLAMA_TIMEOUT`. En streaming, il porte sur l'attente *entre
  deux fragments*, pas sur la durée totale — une réponse longue sur une machine
  lente n'est donc pas interrompue à tort.

### `generate_groq(prompt, *, max_tokens=MAX_ANSWER_TOKENS, on_token=None) -> str`
Appelle l'API cloud Groq (compatible format OpenAI).

- **Paramètres** : identiques à `generate_ollama`
- **Retour** : texte généré
- **Prérequis** : variable d'environnement `GROQ_API_KEY` définie (clé
  gratuite obtenue sur console.groq.com, sans carte bancaire à l'inscription
  au moment de la rédaction — à vérifier, les offres évoluent)
- **Erreurs traduites** : `401` → clé invalide, `429` → quota atteint

### `generate_answer(query, chunks, on_token=None) -> str`
Point d'entrée principal du module — choisit automatiquement le backend
configuré dans `config.py` (`LLM_BACKEND`).

- **Paramètre** `on_token` : callback appelé pour chaque fragment généré,
  utilisé par `/ask/stream` pour afficher la réponse au fil de l'eau. Laissé à
  `None`, la génération n'est pas streamée.
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
