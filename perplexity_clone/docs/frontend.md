# frontend/index.html — Documentation

## Rôle
Interface graphique du projet, en React. Fichier HTML unique et autonome —
aucune installation de Node.js, npm, ni étape de build : React et Babel
sont chargés directement depuis un CDN (unpkg), et le JSX est transpilé
dans le navigateur à l'ouverture de la page.

## Fonctionnement général
La page appelle l'API locale (`api.py`, sur `http://localhost:8000`) via
`fetch`. Aucune donnée ne quitte ta machine : le navigateur (côté client)
parle directement au serveur local que tu fais tourner à côté.

## Composants principaux

### `App`
Composant racine. Gère l'état global :
- `conversations` : liste des conversations sauvegardées (chargée au démarrage)
- `activeId` : conversation actuellement affichée
- `messages` : messages de la conversation active
- `input` / `loading` : état du champ de saisie et de la requête en cours
- `apiUp` : résultat du ping `/health`, affiche un avertissement si l'API
  locale n'est pas lancée

### `Sidebar`
Liste des conversations sauvegardées, avec un bouton "Nouvelle recherche"
et un bouton de suppression par conversation (apparaît au survol).

### `Message`
Affiche un tour de conversation (question ou réponse). Les réponses de
l'assistant affichent en plus les temps par étape (`TimingRow`) et les
sources citées (`Sources`).

### `Ledger` — l'élément signature de l'interface
Pendant qu'une question est en cours de traitement, ce composant affiche
en direct les étapes du pipeline (décomposition, recherche, lecture des
pages, tri par pertinence, rédaction) — un reflet honnête de ce qui se
passe réellement côté serveur, plutôt qu'un simple indicateur de
chargement générique. Une fois la réponse reçue, `TimingRow` affiche les
temps réels mesurés pour chaque étape (renvoyés par l'API), donc le
"registre" promis pendant l'attente est ensuite vérifié par des chiffres
concrets.

### `Sources`
Liste numérotée des sources citées par la réponse, avec des liens
cliquables — le numéro correspond exactement au `[Source N]` utilisé dans
le texte généré (grâce au correctif appliqué dans `pipeline.py`).

## Lancement

1. Démarrer l'API (voir `docs/api.md`) :
   ```bash
   uvicorn api:app --reload
   ```
2. Ouvrir `frontend/index.html` directement dans un navigateur (double-clic,
   ou `start frontend\index.html` sous Windows).

Aucun serveur web n'est nécessaire pour servir ce fichier HTML — il
fonctionne en `file://` local, tant que l'API tourne sur `localhost:8000`.

## Personnalisation
- **Adresse de l'API** : modifie la constante `API` en haut du bloc
  `<script type="text/babel">` si tu changes le port d'uvicorn.
- **Palette de couleurs** : variables CSS dans le `<style>` de l'en-tête
  (`:root { --amber: ...; --bg: ...; }`).

## Limites connues
- **Pas de streaming** : la réponse s'affiche d'un coup à la fin de la
  génération, pas mot par mot. Ajouter du streaming nécessiterait de
  faire streamer `generate.py` (Ollama le supporte nativement) et de
  passer l'API en Server-Sent Events ou WebSocket — non implémenté ici
  pour rester simple.
- **Un seul utilisateur** : la base SQLite n'est pas conçue pour un accès
  concurrent multi-utilisateurs ; pour un usage personnel, ce n'est pas un
  problème.

## Bibliographie / dépendances
- **React 18** et **ReactDOM** (via CDN unpkg.com, licence MIT)
- **Babel Standalone** (via CDN unpkg.com, licence MIT) : permet d'écrire
  du JSX directement dans le navigateur, sans étape de compilation
- Police **IBM Plex Mono** (IBM, licence SIL Open Font) et **Source
  Serif 4** (Adobe, licence SIL Open Font), chargées depuis Google Fonts
