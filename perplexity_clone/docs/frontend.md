# frontend/index.html — Documentation

## Rôle
Interface graphique du projet. Fichier HTML unique et **100% autonome** —
aucune installation Node.js/npm, aucune étape de build, **et aucune
dépendance à un CDN externe** (ni React, ni Babel, ni aucune librairie
chargée depuis Internet). Seule requête réseau : les appels à l'API
locale (`api.py`) sur `http://localhost:8000`.

## Fichiers

L'interface est répartie en trois fichiers, dans `frontend/` :

- **`index.html`** — structure de la page uniquement (balises, zones
  vides que le JS remplit dynamiquement). Charge `style.css` et `app.js`.
- **`style.css`** — toute la mise en forme (couleurs, typographie,
  disposition). Les couleurs sont centralisées en variables CSS (`:root`)
  en haut du fichier.
- **`app.js`** — toute la logique : état de l'application, appels à
  l'API, fonctions de rendu qui réécrivent le HTML des zones concernées.

## Pourquoi pas React ?
La première version utilisait React + Babel via CDN (unpkg.com). Si ce
CDN est bloqué (pare-feu d'entreprise, antivirus, filtrage réseau), la
page reste blanche sans rien afficher. Cette version reconstruit la même
interface et les mêmes fonctionnalités **en JavaScript natif** (DOM API
standard), ce qui élimine complètement ce risque : la page fonctionne
même sans aucun accès Internet, tant que l'API locale tourne.

L'architecture reste organisée par "composants" — une fonction de rendu
par section de l'interface — dans le même esprit que la version React,
mais sans la librairie.

## Fonctionnement général
Un objet `state` unique contient tout l'état de l'application
(conversations, messages, chargement en cours...). Chaque action
(envoyer une question, changer de conversation...) modifie `state` puis
appelle `render()`, qui réécrit le contenu HTML des zones concernées.
C'est un pattern de rendu volontairement simple (pas de diff virtuel),
largement suffisant pour la taille de cette interface.

## Fonctions de rendu principales

- **`renderSidebar()`** : liste des conversations sauvegardées, bouton de
  suppression par conversation (affiché au survol)
- **`renderLedger()`** — l'élément signature de l'interface : pendant
  qu'une question est traitée, affiche en direct les étapes du pipeline
  (décomposition, recherche, lecture des pages, tri par pertinence,
  rédaction) **avec leur durée mesurée**. Ces états proviennent des
  événements `step` du flux SSE : c'est l'avancement réel du serveur, pas
  une animation minutée côté navigateur.
- **`renderMessage(m, idx)`** : affiche un tour de conversation ; pour les
  réponses de l'assistant, ajoute les temps réels par étape
  (`timing-row`) et les sources citées (`sources`), avec des numéros
  `[N]` qui correspondent exactement aux `[Source N]` utilisés dans le
  texte généré
- **`linkCitations(text, idx)`** : transforme chaque `[Source N]` du texte en
  lien vers l'entrée correspondante de la liste des sources (clic → défilement
  + surbrillance). Le texte est **échappé d'abord** ; la notation ne contenant
  aucun caractère HTML, elle survit intacte à l'échappement.
- **`patchStreaming()`** : mises à jour ciblées pendant le streaming (corps du
  message + lignes du registre uniquement), throttlées par
  `requestAnimationFrame`. Réécrire tout le fil à chaque fragment reçu
  détruirait la sélection de texte et ferait ramer la page.
- **`render()`** : orchestre le rendu complet, appelée aux changements d'état
  structurels (envoi, fin de réponse, changement de conversation)

## Fonctions d'action (appels API)

- **`checkHealth()`** : ping `/health`, affiche un avertissement rouge si
  l'API locale n'est pas jointe, puis **retente toutes les 5 s** tant qu'elle
  est absente — l'avertissement disparaît tout seul dès qu'uvicorn démarre.
- **`loadConversations()`** / **`selectConversation(id)`** /
  **`deleteConversation(id)`** : gestion de l'historique
- **`readEventStream(response, onEvent)`** : découpe le flux HTTP en événements
  SSE et appelle `onEvent` pour chacun. `EventSource`, l'API navigateur dédiée
  au SSE, ne conviendrait pas : elle ne sait émettre que des `GET`, or la
  question part en `POST`.
- **`errorDetail(response)`** : extrait un message lisible d'une réponse en
  erreur (FastAPI renvoie `{detail: "..."}`, ou une liste pour les erreurs de
  validation)
- **`send()`** : envoie la question à `/ask/stream`, met à jour le registre au
  fil des étapes, affiche la réponse fragment par fragment, puis les sources
- **`stop()`** : interrompt la requête en cours via `AbortController`. Le
  serveur annule alors sa tâche et l'échange n'est pas enregistré.

## Lancement

1. Démarrer l'API (voir `docs/api.md`) :
   ```bash
   uvicorn api:app --reload
   ```
2. Ouvrir `frontend/index.html` directement dans un navigateur
   (double-clic, ou `start frontend\index.html` sous Windows).

## Personnalisation
- **Adresse de l'API** : constante `API` en haut de `app.js`.
- **Palette de couleurs** : variables CSS dans `:root`, en haut de `style.css`.
- La police (IBM Plex Mono / Source Serif 4) est chargée depuis Google
  Fonts par confort visuel, mais n'est pas requise au fonctionnement — si
  elle ne charge pas (pas d'accès Internet), le navigateur retombe
  automatiquement sur les polices système déclarées en repli
  (`ui-monospace`, `Georgia`...).

## Limites connues
- **Un seul utilisateur** : la base SQLite n'est pas conçue pour un accès
  concurrent multi-utilisateurs ; pour un usage personnel, ce n'est pas
  un problème.
- **Rendu "full re-render"** hors streaming : les changements structurels
  réécrivent le HTML des zones concernées plutôt que de ne modifier que ce qui
  a changé (pas de diff virtuel façon React). Le streaming, lui, passe par des
  mises à jour ciblées (`patchStreaming`). Sans impact perceptible à cette
  échelle (quelques dizaines de messages), mais à garder en tête si
  l'interface grossit beaucoup.
- **Arrêt côté serveur** : « Arrêter » annule la tâche asyncio, donc la réponse
  n'est ni affichée ni enregistrée — mais la génération déjà lancée dans son
  thread continue jusqu'à son terme côté Ollama (Python ne sait pas tuer un
  thread). L'interface est libérée immédiatement ; la machine, non.
- **Pas de rendu Markdown** : la réponse est affichée en texte brut
  (`white-space: pre-wrap`), seules les citations `[Source N]` sont enrichies.
