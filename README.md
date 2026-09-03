# Assistant de recherche IA — Mode d'emploi

Ce projet reproduit le principe de fonctionnement de Perplexity (recherche
web + LLM + citations) avec des outils 100% gratuits et open-source. Coût
total : 0€, à condition d'utiliser le backend LLM local (`ollama`).

## 1. Ce que contient ce dossier

```
perplexity_clone/
├── config.py       # tous les réglages du projet
├── cache.py        # cache disque pour éviter de refaire les mêmes requêtes
├── search.py       # recherche web via DuckDuckGo (gratuit, sans clé API)
├── scraper.py      # téléchargement + nettoyage du texte des pages web
├── rerank.py       # découpage en chunks + classement par pertinence
├── generate.py     # appel au LLM (Ollama local ou Groq cloud gratuit)
├── pipeline.py     # orchestrateur : point d'entrée du projet (CLI)
├── api.py          # serveur HTTP local + sauvegarde des conversations (SQLite)
├── frontend/       # interface web (JS natif, aucune installation Node.js)
│   ├── index.html  # structure de la page
│   ├── style.css   # mise en forme
│   └── app.js      # état, appels API, rendu
├── tests/          # suite pytest (aucun appel réseau ni LLM réel)
├── requirements.txt
├── requirements-dev.txt
├── docs/           # documentation détaillée de chaque module
│   ├── config.md
│   ├── cache.md
│   ├── search.md
│   ├── scraper.md
│   ├── rerank.md
│   ├── generate.md
│   ├── pipeline.md
│   ├── api.md
│   └── frontend.md
└── README.md       # ce fichier
```

## 2. Installation

### Étape 1 — Python
Assure-toi d'avoir Python 3.10 ou plus récent installé.

```bash
python3 --version
```

### Étape 2 — Environnement virtuel (recommandé)

```bash
cd perplexity_clone
python3 -m venv venv
source venv/bin/activate      # sous Windows : venv\Scripts\activate
```

### Étape 3 — Installer les dépendances

```bash
pip install -r requirements.txt
```

Toutes ces librairies sont gratuites et open-source, aucune clé API n'est
nécessaire à ce stade.

### Étape 4 — Installer un LLM gratuit

**Option A (recommandée) : Ollama en local — coût 0€ garanti**

1. Télécharger Ollama sur https://ollama.com (Mac, Windows, Linux)
2. Lancer le service : `ollama serve` (souvent lancé automatiquement)
3. Télécharger le modèle réglé par défaut dans `config.py` :
   ```bash
   ollama pull llama3.2:3b
   ```
4. Rien d'autre à faire : `config.py` est déjà réglé sur `LLM_BACKEND = "ollama"`

Ce modèle 3B tient dans environ 3 Go de RAM et reste utilisable sur un CPU
modeste — c'est le plus gros levier de vitesse du projet. Si ta machine est
confortable (16 Go+), `llama3.1:8b` donne des réponses sensiblement meilleures :
`ollama pull llama3.1:8b`, puis change `OLLAMA_MODEL` dans `config.py`. Si au
contraire la génération reste trop lente, utilise l'option B.

**Option B : Groq (cloud, tier gratuit)**

1. Créer un compte gratuit sur https://console.groq.com
2. Générer une clé API
3. Définir la variable d'environnement :
   ```bash
   export GROQ_API_KEY="ta_clé_ici"      # Mac/Linux
   set GROQ_API_KEY=ta_clé_ici           # Windows (cmd)
   ```
4. Dans `config.py`, changer : `LLM_BACKEND = "groq"`

## 3. Utilisation

### En ligne de commande

```bash
python pipeline.py "Quelles sont les nouveautés en intelligence artificielle cette semaine ?"
```

### Dans du code Python

```python
from pipeline import ask

resultat = ask("Comment fonctionne un panneau solaire ?")
print(resultat["answer"])
print(resultat["sources"])
```

### Résultat retourné

```python
{
    "query": "...",   # la question posée
    "answer": "...",  # la réponse générée, avec citations [Source N]
    "sources": [      # une entrée par page distincte, numérotée comme les citations
        {"n": 1, "url": "https://..."},
    ],
    "timings": {...}  # temps (secondes) de chaque étape du pipeline
}
```

## 4. Interface graphique + sauvegarde des conversations

Le projet inclut une interface web (JavaScript natif, aucune installation
Node.js ni CDN externe) et une API locale qui sauvegarde l'historique des
conversations dans un fichier SQLite.

**Étape 1 — Lancer l'API locale**, dans le dossier du projet :
```bash
python -m pip install -r requirements.txt   # inclut FastAPI/uvicorn désormais
uvicorn api:app --reload
```
Laisse cette commande tourner (elle sert le pipeline sur `http://localhost:8000`).

**Étape 2 — Ouvrir l'interface**, dans un second terminal ou simplement
en double-cliquant sur le fichier :
```
frontend/index.html
```
Ça ouvre la page dans ton navigateur par défaut. Tant que l'API tourne,
tu peux poser des questions, suivre les étapes du pipeline **en direct avec
leur durée réelle**, voir la réponse s'écrire au fil de sa génération, cliquer
sur les citations `[Source N]` pour rejoindre la source correspondante, et
retrouver tes conversations précédentes dans la barre latérale. Le bouton
« Arrêter » interrompt une recherche en cours.

Toutes les conversations sont stockées dans `conversations.db` (créé
automatiquement à côté de `api.py`) — rien ne quitte ta machine.

Voir `docs/api.md` et `docs/frontend.md` pour le détail technique.

## 5. Personnalisation

Tous les réglages (nombre de sources, taille des chunks, modèle utilisé,
timeouts...) se trouvent dans `config.py`. Voir `docs/config.md` pour le
détail de chaque paramètre.

## 6. Tests

```bash
pip install -r requirements-dev.txt
pytest
```

La suite ne fait **aucun appel réseau ni appel LLM réel** : recherche,
scraping et génération sont simulés. Elle couvre le cache (TTL, corruption,
valeurs `None`), le découpage en chunks, la sélection et le dédoublonnage des
sources, le garde-fou SSRF du scraper, et l'API (validation, pagination, flux
SSE, absence de message orphelin en cas d'échec du modèle).

## 7. Limites à connaître

- **Pas d'index propriétaire** : contrairement à Perplexity, ce projet
  s'appuie sur DuckDuckGo à chaque requête — plus lent et moins exhaustif
  qu'un index web propriétaire construit sur des années.
- **Scraping parfois bloqué** : certains sites (paywalls, protections
  anti-bot) refuseront le scraping. Le pipeline ignore simplement ces
  pages sans planter.
- **Qualité du LLM local** : un modèle 8B en local est correct mais moins
  performant qu'un modèle propriétaire de dernière génération. Pour plus
  de qualité, on peut essayer un modèle plus gros si la machine le permet
  (`ollama pull llama3.1:70b`, nécessite beaucoup plus de RAM/VRAM).
- **Aucune garantie de gratuité éternelle côté Groq** : c'est un service
  tiers, ses conditions peuvent changer. Ollama en local reste la seule
  option dont le coût ne dépend d'aucune politique commerciale externe.

## 8. Aller plus loin

- Rendre le Markdown de la réponse (titres, listes, gras) plutôt que du texte
  brut
- Envoyer l'historique de la conversation au LLM pour permettre les questions
  de suivi (« et en 2024 ? ») — aujourd'hui chaque question est traitée
  isolément, même à l'intérieur d'une conversation
- Purger automatiquement `cache_data/` (les entrées jamais relues restent sur
  le disque)
- Remplacer DuckDuckGo par plusieurs moteurs en parallèle pour élargir la
  couverture
