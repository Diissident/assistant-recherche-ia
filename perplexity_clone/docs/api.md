# api.py — Documentation

## Rôle
Serveur HTTP local (FastAPI) qui expose le pipeline de recherche à
l'interface React (`frontend/index.html`), et sauvegarde l'historique des
conversations dans une base SQLite locale (`conversations.db`, créée
automatiquement au premier lancement — aucune installation de base de
données requise, SQLite est intégré à Python).

## Lancement

```bash
uvicorn api:app --reload
```

Le serveur écoute par défaut sur `http://localhost:8000`. `--reload`
relance automatiquement le serveur si tu modifies le code (pratique en
développement, à retirer en usage courant).

## Schéma de la base de données

- **`conversations`** : `id`, `title`, `created_at`
- **`messages`** : `id`, `conversation_id`, `role` (`user`/`assistant`),
  `content`, `sources` (JSON), `timings` (JSON), `created_at`
- **`idx_messages_conversation`** : index sur `(conversation_id, created_at)`.
  Sans lui, relire une conversation impose un parcours complet de la table.

Réglages appliqués à la base :

- **`PRAGMA journal_mode = WAL`** : lectures et écriture peuvent avancer en
  parallèle. Sans ça, rafraîchir la liste des conversations pendant qu'une
  recherche écrit sa réponse peut lever `database is locked`.
- **`PRAGMA foreign_keys = ON`** (par connexion) : SQLite n'applique les clés
  étrangères que si on le demande explicitement.
- **`timeout=15s`** sur chaque connexion : FastAPI sert les routes depuis un
  pool de threads, donc deux écritures peuvent se croiser.

La question et sa réponse sont écrites **dans une seule transaction, à la fin
du pipeline**. Elles partagent donc le même `created_at` ; c'est `rowid` qui
départage l'ordre à la relecture (`ORDER BY created_at, rowid`).

## Endpoints

### `POST /conversations`
Crée une conversation vide.
- **Corps** : `{"title": "..." }` (optionnel)
- **Retour** : `{"id", "title", "created_at"}`

### `GET /conversations`
Liste les conversations, triées de la plus récente à la plus ancienne.
- **Paramètres** : `limit` (1-500, défaut 100), `offset` (défaut 0)
- **Retour** : liste de `{"id", "title", "created_at"}`

### `GET /conversations/{conv_id}/messages`
Retourne l'historique complet d'une conversation.
- **Retour** : liste de `{"role", "content", "sources", "timings", "created_at"}`

### `DELETE /conversations/{conv_id}`
Supprime une conversation et tous ses messages.
- **Retour** : `{"deleted": conv_id}`, ou `404` si la conversation est inconnue.

### `POST /ask`
Exécute le pipeline complet et retourne la réponse **en une seule fois**.
Variante pratique pour un script ou un agent ; l'interface utilise
`/ask/stream`.
- **Corps** : `{"query": "...", "conversation_id": "..." | null}`
  - `query` : 1 à `MAX_QUERY_LENGTH` caractères, espaces rognés. Une question
    vide ou trop longue est rejetée en `422`.
  - Si `conversation_id` est `null`, une nouvelle conversation est créée
    automatiquement (titre = les 60 premiers caractères de la question)
  - Si un `conversation_id` inconnu est fourni : `404`
- **Retour** : `{"conversation_id", "answer", "sources", "timings"}`
- **Erreur** : `502` avec un message explicite si le modèle est injoignable
  (Ollama arrêté, clé Groq manquante…)
- **Comportement** : rien n'est écrit en base tant que le pipeline n'a pas
  abouti. Question et réponse sont enregistrées ensemble, dans une seule
  transaction — un échec de génération ne laisse donc jamais une question
  orpheline ni une conversation vide dans l'historique.

### `POST /ask/stream`
Même traitement, mais en flux **Server-Sent Events** : l'interface peut
afficher l'étape réellement en cours puis la réponse au fil de sa génération.
- **Corps** : identique à `/ask`
- **Type de réponse** : `text/event-stream`, un événement JSON par bloc
  `data: {...}`

| Événement | Charge utile |
|---|---|
| `start` | `conversation_id` — disponible immédiatement |
| `step` | `step`, `status` (`start`/`done`), `duration` (sur `done`) |
| `token` | `text` : fragment de réponse |
| `done` | `conversation_id`, `answer`, `sources`, `timings` |
| `error` | `message` lisible par l'utilisateur |

Le flux se termine toujours par `done` **ou** `error`. Si le client se
déconnecte (bouton « Arrêter » de l'interface), la tâche serveur est annulée
et l'échange n'est pas enregistré.

> Le `POST` est délibéré : `EventSource`, l'API navigateur dédiée au SSE, ne
> sait émettre que des `GET`. Le frontend lit donc le flux à la main via
> `fetch` + `ReadableStream` (`readEventStream` dans `app.js`).

### `GET /health`
Vérification simple que le serveur répond (utilisé par le frontend pour
afficher un avertissement si l'API n'est pas lancée).

## Démarrage du serveur
Au lancement (`lifespan`), l'API crée les tables et l'index, puis précharge le
reranker **dans un thread de fond** si `WARMUP_RERANKER` est actif. Sans ce
préchargement, la toute première question paie 10 à 20 secondes de chargement
de modèle sans aucun retour visible.

## Sécurité / CORS
Le CORS est ouvert à toutes les origines (`allow_origins=["*"]`). C'est
volontaire et sans risque ici : tout tourne en local sur ta machine,
aucune donnée ne sort vers un tiers. Si un jour tu exposes ce serveur au
delà de `localhost` (déconseillé sans authentification), il faudra
restreindre ce réglage.

## Bibliographie / dépendances
- **FastAPI** (PyPI, open-source, licence MIT) : framework web Python
  léger, génère automatiquement une documentation interactive consultable
  sur `http://localhost:8000/docs` une fois le serveur lancé.
- **uvicorn** (PyPI, open-source) : serveur ASGI utilisé pour exécuter
  FastAPI.
- **sqlite3** : module intégré à la bibliothèque standard Python, aucune
  installation séparée nécessaire.
