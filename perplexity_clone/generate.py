"""
generate.py
-----------
Génère la réponse finale à partir de la question et des chunks pertinents,
avec citations des sources. Deux backends gratuits supportés :

- "ollama" : modèle open-source tournant 100% en local (aucune clé, aucun coût,
  mais nécessite d'installer Ollama et de télécharger un modèle).
- "groq"   : API cloud avec un tier gratuit généreux (nécessite une clé API
  gratuite, aucune carte bancaire requise à l'inscription).
"""

import json

import requests

from config import (GROQ_API_KEY, GROQ_MODEL, LLM_BACKEND, MAX_ANSWER_TOKENS,
                     OLLAMA_HOST, OLLAMA_MODEL)


def build_prompt(query: str, chunks: list[dict]) -> str:
    """
    Construit le prompt envoyé au LLM : la question + les extraits de sources
    numérotés, avec instruction explicite de citer les sources utilisées.

    Paramètres:
        query (str): question de l'utilisateur
        chunks (list[dict]): chunks pertinents, avec 'text' et 'url'

    Retour:
        str: prompt complet
    """
    sources_block = "\n\n".join(
        f"[Source {i+1} - {c['url']}]\n{c['text']}"
        for i, c in enumerate(chunks)
    )

    return (
        "Tu es un assistant de recherche. Réponds à la question en te basant "
        "UNIQUEMENT sur les sources fournies ci-dessous. Cite systématiquement "
        "tes sources avec la notation [Source N]. Si les sources ne permettent "
        "pas de répondre, dis-le clairement.\n\n"
        f"Question: {query}\n\n"
        f"Sources disponibles:\n{sources_block}\n\n"
        "Réponse (avec citations [Source N]):"
    )


def generate_ollama(prompt: str) -> str:
    """
    Appelle un modèle local via Ollama (gratuit, aucune clé API).
    Nécessite qu'Ollama tourne en local (`ollama serve`) et que le
    modèle configuré ait été téléchargé (`ollama pull <modele>`).

    Paramètres:
        prompt (str): prompt complet à envoyer

    Retour:
        str: réponse générée
    """
    resp = requests.post(
        f"{OLLAMA_HOST}/api/generate",
        json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
        timeout=600,
    )
    resp.raise_for_status()
    return resp.json()["response"]


def generate_groq(prompt: str) -> str:
    """
    Appelle l'API Groq (tier gratuit, clé API requise via console.groq.com).

    Paramètres:
        prompt (str): prompt complet à envoyer

    Retour:
        str: réponse générée
    """
    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY manquante. Définis la variable d'environnement "
            "GROQ_API_KEY avec une clé gratuite obtenue sur console.groq.com"
        )

    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json={
            "model": GROQ_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": MAX_ANSWER_TOKENS,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def generate_answer(query: str, chunks: list[dict]) -> str:
    """
    Point d'entrée principal : construit le prompt et appelle le backend
    LLM configuré dans config.py.

    Paramètres:
        query (str): question de l'utilisateur
        chunks (list[dict]): chunks pertinents triés par rerank.rerank()

    Retour:
        str: réponse finale générée, citations incluses
    """
    prompt = build_prompt(query, chunks)

    if LLM_BACKEND == "ollama":
        return generate_ollama(prompt)
    elif LLM_BACKEND == "groq":
        return generate_groq(prompt)
    else:
        raise ValueError(f"Backend LLM inconnu: {LLM_BACKEND}")
