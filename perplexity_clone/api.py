"""
api.py
------
Serveur HTTP local exposant le pipeline de recherche à l'interface React
(frontend/index.html), avec sauvegarde des conversations dans une base
SQLite locale (fichier conversations.db, créé automatiquement).

Lancement:
    uvicorn api:app --reload
"""

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import pipeline

DB_PATH = "conversations.db"

app = FastAPI(title="Assistant de recherche IA — API locale")

# CORS ouvert : l'interface tourne dans le navigateur (fichier local ou
# artifact), on autorise toutes origines puisque tout reste sur la machine
# de l'utilisateur — aucune donnée ne transite par un tiers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@contextmanager
def get_db():
    """
    Context manager pratique pour ouvrir/fermer une connexion SQLite avec
    commit automatique en sortie sans erreur.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """
    Crée les tables 'conversations' et 'messages' si elles n'existent pas
    encore. Appelée une fois au démarrage du serveur.
    """
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                sources TEXT,
                timings TEXT,
                created_at REAL NOT NULL,
                FOREIGN KEY(conversation_id) REFERENCES conversations(id)
            )
        """)


init_db()


class AskRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None


class ConversationCreate(BaseModel):
    title: Optional[str] = None


@app.post("/conversations")
def create_conversation(payload: ConversationCreate):
    """Crée une nouvelle conversation vide et retourne son identifiant."""
    conv_id = str(uuid.uuid4())
    title = payload.title or "Nouvelle recherche"
    with get_db() as conn:
        conn.execute(
            "INSERT INTO conversations (id, title, created_at) VALUES (?, ?, ?)",
            (conv_id, title, time.time()),
        )
    return {"id": conv_id, "title": title, "created_at": time.time()}


@app.get("/conversations")
def list_conversations():
    """Liste toutes les conversations sauvegardées, les plus récentes d'abord."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, title, created_at FROM conversations ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/conversations/{conv_id}/messages")
def get_messages(conv_id: str):
    """Retourne l'historique complet des messages d'une conversation."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT role, content, sources, timings, created_at FROM messages "
            "WHERE conversation_id = ? ORDER BY created_at ASC",
            (conv_id,),
        ).fetchall()

    messages = []
    for r in rows:
        m = dict(r)
        m["sources"] = json.loads(m["sources"]) if m["sources"] else []
        m["timings"] = json.loads(m["timings"]) if m["timings"] else {}
        messages.append(m)
    return messages


@app.delete("/conversations/{conv_id}")
def delete_conversation(conv_id: str):
    """Supprime une conversation et tous ses messages."""
    with get_db() as conn:
        conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
        conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
    return {"deleted": conv_id}


@app.post("/ask")
def ask(payload: AskRequest):
    """
    Point d'entrée principal : exécute le pipeline de recherche pour la
    question posée, sauvegarde la question et la réponse dans la
    conversation (existante ou nouvellement créée), et retourne le
    résultat complet.
    """
    conv_id = payload.conversation_id

    with get_db() as conn:
        if not conv_id:
            conv_id = str(uuid.uuid4())
            title = payload.query[:60]
            conn.execute(
                "INSERT INTO conversations (id, title, created_at) VALUES (?, ?, ?)",
                (conv_id, title, time.time()),
            )
        else:
            exists = conn.execute(
                "SELECT 1 FROM conversations WHERE id = ?", (conv_id,)
            ).fetchone()
            if not exists:
                raise HTTPException(404, "Conversation introuvable")

        conn.execute(
            "INSERT INTO messages (id, conversation_id, role, content, sources, timings, created_at) "
            "VALUES (?, ?, 'user', ?, NULL, NULL, ?)",
            (str(uuid.uuid4()), conv_id, payload.query, time.time()),
        )

    result = pipeline.ask(payload.query)

    with get_db() as conn:
        conn.execute(
            "INSERT INTO messages (id, conversation_id, role, content, sources, timings, created_at) "
            "VALUES (?, ?, 'assistant', ?, ?, ?, ?)",
            (
                str(uuid.uuid4()), conv_id, result["answer"],
                json.dumps(result["sources"]), json.dumps(result["timings"]),
                time.time(),
            ),
        )

    return {
        "conversation_id": conv_id,
        "answer": result["answer"],
        "sources": result["sources"],
        "timings": result["timings"],
    }


@app.get("/health")
def health():
    """Vérification rapide que le serveur tourne (utilisé par le frontend)."""
    return {"status": "ok"}
