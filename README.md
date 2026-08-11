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
├── pipeline.py     # orchestrateur : point d'entrée du projet
├── requirements.txt
├── docs/           # documentation détaillée de chaque module
│   ├── config.md
│   ├── cache.md
│   ├── search.md
│   ├── scraper.md
│   ├── rerank.md
│   ├── generate.md
│   └── pipeline.md
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
git clone assistant-recherche-ia
cd assistant-ia-perplexity/perplexity_clone
python3 -m venv venv
source venv/bin/activate      # sous Windows : venv\Scripts\activate
```

### Étape 3 — Installer les dépendances

```bash
python -m pip install -r requirements.txt
```

Toutes ces librairies sont gratuites et open-source, aucune clé API n'est
nécessaire à ce stade.

### Étape 4 — Installer un LLM gratuit

**Option A (recommandée) : Ollama en local — coût 0€ garanti**

1. Télécharger Ollama sur https://ollama.com (Mac, Windows, Linux)
2. Lancer le service : `ollama serve` (souvent lancé automatiquement)
3. Télécharger un modèle :
   ```bash
   ollama pull llama3.1:8b
   ```
4. Rien d'autre à faire : `config.py` est déjà réglé sur `LLM_BACKEND = "ollama"`

Attention : ce modèle nécessite environ 8 Go de RAM libre (16 Go
recommandés pour un usage confortable). Si ta machine est trop limitée,
utilise l'option B.

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
python pipeline.py "Ma requête"
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
    "query": "...",           # la question posée
    "answer": "...",          # la réponse générée, avec citations [Source N]
    "sources": ["url1", ...], # les URLs effectivement utilisées
    "timings": {...}          # temps (secondes) de chaque étape du pipeline
}
```

## 4. Personnalisation

Tous les réglages (nombre de sources, taille des chunks, modèle utilisé,
timeouts...) se trouvent dans `config.py`. Voir `docs/config.md` pour le
détail de chaque paramètre.

## 5. Limites à connaître

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

## 6. Aller plus loin

- Décomposer une question complexe en plusieurs sous-requêtes avant la
  recherche (fonction `search.search_multiple` déjà prête, pas encore
  branchée dans `pipeline.py` par défaut)
- Ajouter un mode "conversation" en gardant l'historique des échanges
- Exposer le pipeline via une petite API locale (FastAPI, gratuit) pour
  le brancher à une interface web ou à un autre agent
