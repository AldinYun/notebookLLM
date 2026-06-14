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

## Server Deployment

The current MVP can run as two containers with one persistent Docker volume:

- `frontend`: Next.js standalone server on port `3000`
- `backend`: FastAPI API on port `8000`
- `notebookllm-data`: SQLite database and uploaded source files

On a Linux server with Docker and the Compose plugin installed:

```bash
git clone https://github.com/AldinYun/notebookLLM.git
cd notebookLLM
cp .env.deploy.example .env
chmod +x deploy.sh
./deploy.sh
```

Open `http://SERVER_IP:3000`. API health and documentation are available at
`http://SERVER_IP:8000/health` and `http://SERVER_IP:8000/docs`.

Useful operations:

```bash
docker compose --env-file .env -f compose.deploy.yml logs -f
docker compose --env-file .env -f compose.deploy.yml pull
docker compose --env-file .env -f compose.deploy.yml up -d --build
docker compose --env-file .env -f compose.deploy.yml down
```

`down` preserves the named data volume. Do not add `-v` unless the stored notebooks and uploads
should be deleted.

### Model Server

Run an OpenAI-compatible chat model and embedding model separately, then register each connection in
the Models panel with its `Chat model` or `Embedding model` capability. When a model runs directly on
the same Linux host as Docker, use a base URL such as:

```text
http://host.docker.internal:8001/v1
```

When it runs on another machine, use `http://MODEL_SERVER_IP:PORT/v1`. The model endpoint must be
reachable from the backend container; it does not need to be publicly reachable from the browser.

When an embedding connection is selected, new document chunks are embedded during ingestion and
vector or hybrid searches embed the query through the same connection. Existing documents can be
re-embedded with the network button next to each document. Without a selected embedding connection,
the vector mode retains its lexical compatibility fallback. The current MVP stores vectors in SQLite
and calculates cosine similarity in the API process; OpenSearch remains the next scaling step.

PostgreSQL, OpenSearch, and S3-compatible storage in `infra/docker-compose.yml` are architecture
targets and are not required by this deployment yet.

For an internet-facing installation, place a TLS reverse proxy such as Caddy, Nginx, or Traefik in
front of port `3000`, and restrict direct access to port `8000` with the server firewall.

This MVP does not include login or authorization yet. Keep it on a private network or behind an
authenticated reverse proxy while evaluating it; do not expose it as a public multi-user service.
