# rerank.py — Documentation

## Rôle
Découpe les textes scrapés en fragments ("chunks") exploitables, puis les
classe par pertinence par rapport à la question posée, à l'aide d'un
modèle cross-encoder open-source tournant en local (CPU suffisant).

## Fonctions

### `_get_model() -> CrossEncoder`
Fonction interne. Charge le modèle de reranking une seule fois (le
chargement est coûteux en temps/mémoire) et le garde en mémoire pour les
appels suivants (pattern singleton simple via variable globale `_model`).

### `chunk_text(text, source_url, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP) -> list[dict]`
Découpe un texte long en chunks de taille fixe approximative.

- **Paramètre** `text` : texte source (issu du scraping)
- **Paramètre** `source_url` : URL d'origine, conservée pour la citation finale
- **Paramètre** `chunk_size` : nombre de mots par chunk (proxy simple du
  nombre de tokens ; un mot ≈ 1,3 token en moyenne pour du texte français)
- **Paramètre** `overlap` : nombre de mots partagés entre deux chunks
  consécutifs, pour éviter qu'une idée importante soit coupée pile à la
  frontière entre deux chunks
- **Retour** : liste de `{'text': str, 'url': str}`
- **Détail d'implémentation** : les chunks résiduels de moins de 20 mots
  (souvent en fin de texte) sont ignorés car trop peu informatifs

### `rerank(query, chunks, top_k=TOP_K_CHUNKS) -> list[dict]`
Classe les chunks par pertinence et retourne les meilleurs.

- **Paramètre** `query` : question de l'utilisateur
- **Paramètre** `chunks` : liste de chunks candidats (issus de `chunk_text`)
- **Paramètre** `top_k` : nombre de chunks à garder après tri
- **Retour** : chunks triés par score décroissant, avec une clé `score`
  ajoutée à chaque dict
- **Fonctionnement interne** : le modèle cross-encoder évalue chaque paire
  (question, chunk) et produit un score de pertinence — contrairement à
  une simple similarité d'embeddings, le cross-encoder regarde la question
  et le texte ensemble, ce qui donne un score plus précis (mais plus lent)

## Bibliographie / dépendances
- `sentence-transformers` (PyPI, open-source, Apache 2.0) : librairie
  développée à l'origine par l'UKP Lab, standard pour l'usage de modèles
  d'embeddings et de reranking.
- `BAAI/bge-reranker-base` (Hugging Face, gratuit, licence MIT) : modèle
  développé par le Beijing Academy of Artificial Intelligence, bon
  compromis vitesse/qualité pour du reranking multilingue. Une version
  `bge-reranker-large` existe si tu veux plus de précision au prix d'une
  latence plus élevée.

## Optimisation
Le choix `base` plutôt que `large` est un choix de vitesse : sur CPU, le
gain de précision du modèle `large` ne justifie généralement pas le
temps supplémentaire pour un usage personnel interactif.
