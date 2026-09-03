"""
api.py
------
Serveur HTTP local exposant le pipeline de recherche à l'interface
(frontend/index.html), avec sauvegarde des conversations dans une base
SQLite locale (fichier conversations.db, créé automatiquement).

Deux points d'entrée pour poser une question :

- POST /ask         : réponse complète en une fois (pratique pour un script)
- POST /ask/stream  : flux SSE émettant l'avancement réel du pipeline puis la
                      réponse au fil de sa génération (utilisé par l'interface)

Lancement:
    uvicorn api:app --reload
"""

import asyncio
import json
import logging
import sqlite3
import threading
import time
import uuid
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncIterator, Iterator, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

import pipeline
import rerank
from config import LOG_LEVEL, MAX_QUERY_LENGTH, WARMUP_RERANKER
from generate import LLMError

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

DB_PATH = "conversations.db"
# Délai d'attente si une autre connexion tient le verrou d'écriture. FastAPI
# sert les routes synchrones depuis un pool de threads : sans ce timeout, deux
# écritures simultanées lèvent immédiatement "database is locked".
DB_TIMEOUT = 15.0


@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
    """
    Context manager pratique pour ouvrir/fermer une connexion SQLite avec
    commit automatique en sortie sans erreur, et rollback en cas d'exception.
    """
    conn = sqlite3.connect(DB_PATH, timeout=DB_TIMEOUT)
    conn.row_factory = sqlite3.Row
    # SQLite n'applique les clés étrangères que si on le demande, et le réglage
    # est propre à chaque connexion.
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """
    Crée les tables 'conversations' et 'messages' si elles n'existent pas
    encore, ainsi que l'index de lecture. Appelée une fois au démarrage.
    """
    with get_db() as conn:
        # WAL : lectures et écriture peuvent avancer en parallèle, ce qui
        # évite l'essentiel des "database is locked" quand une requête longue
        # tourne pendant que l'interface rafraîchit la liste des conversations.
        conn.execute("PRAGMA journal_mode = WAL")
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
        # Sans cet index, relire une conversation impose un parcours complet
        # de la table des messages.
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_conversation
            ON messages(conversation_id, created_at)
        """)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise la base et précharge le reranker au démarrage du serveur."""
    init_db()
    if WARMUP_RERANKER:
        # En tâche de fond : le serveur répond immédiatement, et le modèle est
        # généralement prêt avant la première question.
        threading.Thread(target=rerank.warmup, name="reranker-warmup", daemon=True).start()
    yield


app = FastAPI(title="Assistant de recherche IA — API locale", lifespan=lifespan)

# CORS ouvert : l'interface tourne dans le navigateur (fichier local ou
# artifact), on autorise toutes origines puisque tout reste sur la machine
# de l'utilisateur — aucune donnée ne transite par un tiers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=MAX_QUERY_LENGTH)
    conversation_id: Optional[str] = None

    @field_validator("query")
    @classmethod
    def _strip_query(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("La question ne peut pas être vide.")
        return v


class ConversationCreate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)


# --------------------------------------------------------------------------
# Persistance
# --------------------------------------------------------------------------

def _resolve_conversation(conv_id: Optional[str]) -> tuple[str, bool]:
    """
    Détermine la conversation cible d'une question.

    Retour:
        tuple[str, bool]: (identifiant, s'agit-il d'une nouvelle conversation)

    Lève:
        HTTPException 404 si un identifiant est fourni mais inconnu.
    """
    if not conv_id:
        return str(uuid.uuid4()), True

    with get_db() as conn:
        exists = conn.execute(
            "SELECT 1 FROM conversations WHERE id = ?", (conv_id,)
        ).fetchone()
    if not exists:
        raise HTTPException(404, "Conversation introuvable")
    return conv_id, False


def _persist_turn(conv_id: str, is_new: bool, query: str, result: dict) -> None:
    """
    Enregistre la question et sa réponse en une seule transaction.

    Écrire les deux messages à la fin (plutôt que la question avant de lancer
    le pipeline) garantit qu'un échec de génération ne laisse jamais une
    question orpheline, ni une conversation vide, dans l'historique.
    """
    now = time.time()
    with get_db() as conn:
        if is_new:
            conn.execute(
                "INSERT INTO conversations (id, title, created_at) VALUES (?, ?, ?)",
                (conv_id, query[:60], now),
            )
        conn.execute(
            "INSERT INTO messages (id, conversation_id, role, content, sources, timings, created_at) "
            "VALUES (?, ?, 'user', ?, NULL, NULL, ?)",
            (str(uuid.uuid4()), conv_id, query, now),
        )
        conn.execute(
            "INSERT INTO messages (id, conversation_id, role, content, sources, timings, created_at) "
            "VALUES (?, ?, 'assistant', ?, ?, ?, ?)",
            (
                str(uuid.uuid4()), conv_id, result["answer"],
                json.dumps(result["sources"]), json.dumps(result["timings"]),
                now,
            ),
        )


# --------------------------------------------------------------------------
# Conversations
# --------------------------------------------------------------------------

@app.post("/conversations")
async def create_conversation(payload: ConversationCreate):
    """Crée une nouvelle conversation vide et retourne son identifiant."""
    conv_id = str(uuid.uuid4())
    title = (payload.title or "").strip() or "Nouvelle recherche"
    # Un seul appel à time.time() : la valeur renvoyée au client est
    # exactement celle qui a été enregistrée.
    created_at = time.time()

    def write() -> None:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO conversations (id, title, created_at) VALUES (?, ?, ?)",
                (conv_id, title, created_at),
            )

    await asyncio.to_thread(write)
    return {"id": conv_id, "title": title, "created_at": created_at}


@app.get("/conversations")
async def list_conversations(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """Liste les conversations sauvegardées, les plus récentes d'abord."""

    def read() -> list[dict]:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT id, title, created_at FROM conversations "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [dict(r) for r in rows]

    return await asyncio.to_thread(read)


@app.get("/conversations/{conv_id}/messages")
async def get_messages(conv_id: str):
    """Retourne l'historique complet des messages d'une conversation."""

    def read() -> list[dict]:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT role, content, sources, timings, created_at FROM messages "
                "WHERE conversation_id = ? ORDER BY created_at ASC, rowid ASC",
                (conv_id,),
            ).fetchall()

        messages = []
        for r in rows:
            m = dict(r)
            # `created_at` étant identique pour la question et sa réponse
            # (même transaction), c'est `rowid` qui garantit l'ordre.
            m["sources"] = json.loads(m["sources"]) if m["sources"] else []
            m["timings"] = json.loads(m["timings"]) if m["timings"] else {}
            messages.append(m)
        return messages

    return await asyncio.to_thread(read)


@app.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    """Supprime une conversation et tous ses messages."""

    def write() -> int:
        with get_db() as conn:
            conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
            cur = conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
            return cur.rowcount

    deleted = await asyncio.to_thread(write)
    if not deleted:
        raise HTTPException(404, "Conversation introuvable")
    return {"deleted": conv_id}


# --------------------------------------------------------------------------
# Interrogation du pipeline
# --------------------------------------------------------------------------

@app.post("/ask")
async def ask(payload: AskRequest):
    """
    Exécute le pipeline et retourne la réponse complète en une fois.

    Variante sans streaming, pratique pour un script ou un agent. L'interface
    utilise /ask/stream pour afficher l'avancement réel.
    """
    conv_id, is_new = await asyncio.to_thread(_resolve_conversation, payload.conversation_id)

    try:
        result = await pipeline.run_pipeline(payload.query)
    except LLMError as exc:
        # Rien n'a été écrit en base : la conversation reste propre.
        logger.warning("Génération impossible : %s", exc)
        raise HTTPException(502, str(exc)) from exc

    await asyncio.to_thread(_persist_turn, conv_id, is_new, payload.query, result)

    return {
        "conversation_id": conv_id,
        "answer": result["answer"],
        "sources": result["sources"],
        "timings": result["timings"],
    }


def _sse(event: dict) -> str:
    """Formate un événement en message Server-Sent Events."""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@app.post("/ask/stream")
async def ask_stream(payload: AskRequest):
    """
    Exécute le pipeline en streaming (Server-Sent Events).

    Types d'événements émis :
        {"type": "start",  "conversation_id": str}
        {"type": "step",   "step": str, "status": "start"|"done", "duration": float}
        {"type": "token",  "text": str}
        {"type": "done",   "answer": str, "sources": list, "timings": dict}
        {"type": "error",  "message": str}

    Le flux se termine toujours par un événement "done" ou "error".
    """
    conv_id, is_new = await asyncio.to_thread(_resolve_conversation, payload.conversation_id)

    async def event_stream() -> AsyncIterator[str]:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        done = object()

        def on_progress(event: dict) -> None:
            # Les événements "token" sont émis depuis le thread de génération :
            # call_soon_threadsafe est le seul moyen sûr de réveiller la boucle
            # depuis un autre thread. Il préserve l'ordre d'émission.
            loop.call_soon_threadsafe(queue.put_nowait, event)

        async def run() -> None:
            try:
                result = await pipeline.run_pipeline(
                    payload.query, on_progress=on_progress
                )
                await asyncio.to_thread(_persist_turn, conv_id, is_new, payload.query, result)
                on_progress({
                    "type": "done",
                    "conversation_id": conv_id,
                    "answer": result["answer"],
                    "sources": result["sources"],
                    "timings": result["timings"],
                })
            except asyncio.CancelledError:
                raise
            except LLMError as exc:
                logger.warning("Génération impossible : %s", exc)
                on_progress({"type": "error", "message": str(exc)})
            except Exception as exc:
                logger.exception("Échec du pipeline")
                on_progress({
                    "type": "error",
                    "message": f"Erreur inattendue du pipeline : {exc}",
                })
            finally:
                # Sentinelle envoyée par le même canal, donc toujours après les
                # événements déjà en attente.
                on_progress(done)

        task = asyncio.create_task(run())
        yield _sse({"type": "start", "conversation_id": conv_id})

        try:
            while True:
                event = await queue.get()
                if event is done:
                    break
                yield _sse(event)
        finally:
            # Déconnexion du client en cours de route : on arrête le pipeline
            # au lieu de le laisser tourner dans le vide.
            if not task.done():
                task.cancel()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # désactive le buffering d'un éventuel proxy
        },
    )


@app.get("/health")
def health():
    """Vérification rapide que le serveur tourne (utilisé par le frontend)."""
    return {"status": "ok"}
