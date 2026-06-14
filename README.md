# Insight Notebook

Insight Notebook is a document-grounded LLM SaaS platform for uploading files, experimenting with retrieval strategies, and running citation-backed RAG chat and analysis.

The product is inspired by NotebookLM, with an emphasis on:

- OpenSearch-based retrieval experiments
- Multi-retriever RAG profiles
- Optional Self-Corrective RAG
- Admin-provided models, user API keys, and private OpenAI-compatible sLLMs
- Sentence-level citations linked to source document positions
- Document analysis features such as summaries, mind maps, knowledge structures, and text mining

## Repository Layout

```text
backend/   FastAPI service skeleton and domain boundaries
frontend/  Next.js app skeleton
infra/     Local and Kubernetes-oriented infrastructure drafts
docs/      Product requirements and architecture notes
```

## MVP Scope

- Google login and role separation
- Notebook and document management
- PDF, Office, text, HTML, JSON/XML, and image ingestion
- Chunk-level OpenSearch indexing with metadata and vectors
- Text, BM25, vector, hybrid, and multi-retriever search
- Search lab for comparing retrieval strategies
- Saved RAG profiles
- Optional Self-Corrective RAG and candidate replenishment
- OpenAI-compatible chat and embedding model connections
- Streaming document-grounded chat
- Sentence-level citations and source viewer
- Kubernetes and Helm deployment baseline

## Local Development

Start local infrastructure:

```bash
docker compose -f infra/docker-compose.yml up -d
```

Run the backend:

```bash
cd backend
python -m uvicorn app.main:app --reload
```

Run the frontend:

```bash
cd frontend
npm install
npm run dev
```

## Implemented MVP Slice

The current backend includes a SQLite-backed local MVP for validating the complete document-to-chat loop before OpenSearch is wired in:

- `POST /notebooks`
- `GET /notebooks`
- `POST /documents/ingest-text`
- `POST /documents/upload`
- `GET /documents`
- `GET /documents/{document_id}/source`
- `DELETE /documents/{document_id}`
- `POST /search`
- `POST /rag/run`
- `POST /rag/stream`
- `GET /rag/executions`
- `GET /conversations`
- `GET /conversations/{conversation_id}/messages`
- `POST /models/connections`
- `POST /models/connections/{connection_id}/test`

This slice supports text and file ingestion, local source storage, paragraph chunking, BM25-like search, vector-like search, hybrid scoring, deduped RAG context selection, Self-Corrective candidate evaluation and replenishment, OpenAI-compatible model generation, SSE token streaming, persistent conversations, recent-message model context, and citation payloads. File parsing currently supports TXT, Markdown, CSV, TSV, JSON, XML, and HTML.

The frontend provides notebook and document management, retrieval comparison, saved RAG profiles, model connections, streamed answers, correction traces, run history, and persistent conversation selection.

Local MVP data is stored in SQLite at `backend/.data/insight.db` by default. Override it with:

```bash
INSIGHT_SQLITE_PATH=/path/to/insight.db
```
