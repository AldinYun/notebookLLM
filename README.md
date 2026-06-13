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

This initial commit is a scaffold. The next implementation step is choosing concrete package versions and installing dependencies.

```bash
docker compose -f infra/docker-compose.yml up -d
```

