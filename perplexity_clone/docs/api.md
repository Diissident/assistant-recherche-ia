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

## Endpoints

### `POST /conversations`
Crée une conversation vide.
- **Corps** : `{"title": "..." }` (optionnel)
- **Retour** : `{"id", "title", "created_at"}`

### `GET /conversations`
Liste toutes les conversations, triées de la plus récente à la plus ancienne.
- **Retour** : liste de `{"id", "title", "created_at"}`

### `GET /conversations/{conv_id}/messages`
Retourne l'historique complet d'une conversation.
- **Retour** : liste de `{"role", "content", "sources", "timings", "created_at"}`

### `DELETE /conversations/{conv_id}`
Supprime une conversation et tous ses messages.

### `POST /ask`
Point d'entrée principal : exécute le pipeline complet pour la question
posée.
- **Corps** : `{"query": "...", "conversation_id": "..." | null}`
  - Si `conversation_id` est `null`, une nouvelle conversation est créée
    automatiquement (titre = les 60 premiers caractères de la question)
  - Si un `conversation_id` est fourni, la question est ajoutée à la
    conversation existante
- **Retour** : `{"conversation_id", "answer", "sources", "timings"}`
- **Comportement** : la question de l'utilisateur ET la réponse générée
  sont sauvegardées en base avant de retourner le résultat — l'historique
  est donc toujours à jour même si l'interface plante ou se ferme.

### `GET /health`
Vérification simple que le serveur répond (utilisé par le frontend pour
afficher un avertissement si l'API n'est pas lancée).

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
