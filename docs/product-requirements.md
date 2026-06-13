# Product Requirements

## Product

**Insight Notebook** is a multi-tenant SaaS platform for document-grounded LLM workflows. Users upload documents and images, test different retrieval strategies, save RAG profiles, and use those profiles for chat, analysis, and visual outputs.

## Core Principles

- Basic user workflows should be free by default.
- Admin-provided models may have usage limits.
- Users can register their own SaaS API keys or private sLLM endpoints.
- Documents and search indexes are isolated by tenant, workspace, notebook, and document.
- Document-grounded answers must provide evidence.
- If evidence is insufficient, the system should say that instead of guessing.
- Retrieval behavior and RAG execution details must be inspectable by users.
- The system should avoid hard dependency on one LLM, embedding model, or storage provider.

## User Roles

### User

- Sign in with Google, Kakao, or email fallback.
- Create notebooks and upload documents.
- Test retrieval methods in a search lab.
- Configure RAG profiles.
- Chat with uploaded documents.
- Register personal model connections.
- Manage prompts, search settings, and exports.

### Admin

- Manage users, usage limits, and storage limits.
- Register shared LLMs, embedding models, and evaluation models.
- Configure default prompts and RAG profiles.
- Monitor document processing jobs.
- Inspect model cost, latency, error rates, and Self-Corrective RAG impact.

## Domain Model

- Workspace: top-level user or team space.
- Notebook: a collection of documents, conversations, and analysis results.
- Source: uploaded file or image.
- Document: parsed representation of a source.
- Chunk: searchable unit used by retrieval and RAG.
- Search Profile: saved retrieval settings.
- RAG Profile: end-to-end retrieval, evaluation, augmentation, and generation settings.
- Conversation: chat session using a selected RAG profile.
- Artifact: generated summary, mind map, report, chart, FAQ, or analysis.
- Model Connection: admin or user supplied OpenAI-compatible endpoint.

## Functional Requirements

### Authentication

- Support OIDC-based authentication.
- Support Google login for MVP.
- Design for Kakao and email fallback.
- Separate user and admin authorization.
- Delete user documents, indexes, storage, and API keys on account deletion.

### Notebook and File Management

- Users can create multiple notebooks.
- A notebook owns documents, saved profiles, conversations, and artifacts.
- Support notebook duplication, archive, delete, and tags.
- Support drag-and-drop and multi-file upload.
- Show upload progress and processing status.
- Detect duplicate files by hash, while allowing forced upload.
- Show file name, type, size, page count, upload time, and processing errors.

### Supported Inputs

MVP formats:

- PDF
- DOCX
- PPTX
- XLSX
- CSV and TSV
- TXT and Markdown
- HTML
- JSON and XML
- PNG, JPG, JPEG, WEBP, and TIFF

Later formats:

- HWPX
- ODT, ODS, and ODP
- EML and MSG
- VTT and SRT
- BMP
- EPUB

### Document Processing

Pipeline:

```text
upload -> validation -> parsing/OCR -> structure extraction -> chunking -> embedding -> OpenSearch indexing -> verification
```

- Store each processing stage and status.
- Re-run from failed stages.
- Store original files separately from parsed output.
- Preserve document title, sections, tables, images, pages, and coordinates where possible.
- Support parser, chunker, embedding, and index versioning.
- Support re-embedding and re-indexing when models change.

### Parsing and OCR

- Use Docling as the primary document parser.
- Prefer embedded text layers before OCR.
- Apply OCR selectively per page.
- Prefer PaddleOCR for Korean and multilingual OCR.
- Use Apache Tika or extension-specific parsers as fallbacks.
- Preserve layout hierarchy as much as possible.
- Store OCR confidence and applied pages.

### Storage

- Store source files in S3-compatible object storage.
- Use SeaweedFS by default for local/self-hosted deployments.
- Allow MinIO or external S3-compatible storage.
- Access storage through a common storage adapter.
- Isolate storage paths by tenant and workspace.
- Serve source files through authenticated signed URLs.

## OpenSearch Requirements

### Chunk Index

Search operates primarily on chunk documents, not whole files.

Required fields include:

- Tenant and ownership metadata: `tenant_id`, `workspace_id`, `notebook_id`, `document_id`, `chunk_id`, `parent_chunk_id`, `source_id`
- File metadata: `file_name`, `original_file_name`, `file_extension`, `mime_type`, `file_size`, `file_hash`, `storage_object_key`
- Document metadata: `document_title`, `document_summary`, `authors`, `created_at`, `uploaded_at`, `language`, `page_count`, `tags`
- Chunk content: `content`, `content_normalized`, `content_type`, `section_title`, `section_path`, `heading_level`, `page_start`, `page_end`, `chunk_order`, `previous_chunk_id`, `next_chunk_id`
- Source location: `bounding_boxes`, `paragraph_index`, `table_index`, `sheet_name`, `slide_number`, `html_selector`
- Parsing metadata: `parser_name`, `parser_version`, `parse_status`, `ocr_applied`, `ocr_confidence`, `chunking_strategy`, `chunk_size`, `chunk_overlap`
- Embedding metadata: `embedding`, `embedding_model`, `embedding_dimension`, `embedding_version`, `embedded_at`
- Search helpers: `keywords`, `named_entities`, `questions`, `chunk_summary`, `access_scope`, `is_active`

### Retrieval Modes

- Simple text matching
- Exact phrase and boolean matching
- Field-specific search for file name, title, content, and tags
- BM25 full-text search with field boosts
- k-NN vector search with filters
- Hybrid search through normalized score fusion or RRF
- Multi-search execution for parallel retrievers

### Search Lab

Users can test retrieval with:

- Query input
- Notebook and document scope
- Retrieval mode selection
- Top K settings
- Metadata filters
- Result comparison view
- Optional RAG execution
- Profile save button

Results must show:

- Retrieval mode
- Rank and score
- Document name
- Page, sheet, or slide
- Section path
- Chunk text
- Matched terms
- Content type
- Latency
- Whether the chunk is included in RAG

Sensitive internals such as raw embeddings, storage paths, tenant IDs, and API credentials must not be shown by default.

## RAG Requirements

### RAG Profile

A RAG profile stores:

- Retriever types
- Per-retriever Top K
- Fields and boosts
- Minimum scores
- Filters
- Embedding model
- Fusion method
- Deduplication method
- Self-Corrective RAG settings
- Final context limits
- Prompt version

Default profiles:

- Fast search: BM25 Top 5
- Semantic search: Vector Top 5
- Balanced search: BM25 Top 5 + Vector Top 5
- Precise search: Hybrid Top 10 + Self-Corrective RAG
- Filename-focused search: boosted filename/title BM25

### Deduplication

Supported policies:

- Remove duplicates
- Keep highest score
- Keep per-retriever representatives
- Add duplicate bonus
- RRF fusion

Final LLM context should avoid repeated identical chunks.

### Self-Corrective RAG

When enabled:

1. Retrieve a larger candidate set than target Top K.
2. Evaluate candidates for question relevance.
3. Exclude irrelevant chunks.
4. Replenish with next-ranked candidates.
5. Repeat until target context count or token budget is reached.
6. Stop at configured iteration and latency limits.

Relevance labels:

- `relevant`
- `partially_relevant`
- `irrelevant`
- `uncertain`

Each evaluation should store score, reason, linked sentences, and inclusion decision as validated JSON.

### RAG Execution Trace

Store:

- User question
- Search profile
- Per-retriever request conditions
- Raw retrieval results
- Score normalization and fusion output
- Deduplication output
- Self-Corrective evaluation output
- Excluded and replenished chunks
- Final augmentor chunks
- Model and prompt versions
- Retrieval, evaluation, and generation latency
- Input and output tokens
- Final citations

## Model Connections

Use OpenAI-compatible APIs as the common protocol:

- `GET /v1/models`
- `POST /v1/chat/completions`
- `POST /v1/embeddings`
- `stream=true`
- SSE streaming
- Bearer token authentication

Supported model supply paths:

- Admin shared SaaS model
- Admin shared private sLLM
- User-provided SaaS API key
- User-registered private sLLM

vLLM is recommended for private OpenAI-compatible sLLM serving.

## Chat and Citations

- Responses stream in real time.
- Users can stop and regenerate responses.
- Each chat can choose a RAG profile.
- Each answer must expose retrieval method and model used.
- Claims should link to one or more citations.
- Citations show document name, page, section, and sentence.
- Clicking a citation opens the source viewer at the referenced location.
- Unsupported claims should be warned or omitted.

## Memory and Conversation

- Conversations preserve context across follow-up questions.
- Follow-up questions may be rewritten into standalone retrieval queries.
- The original user question must be preserved.
- The rewritten query must be stored separately and shown in debug/search details.
- Older conversation turns are summarized instead of always passed verbatim.
- Previous AI answers cannot be treated as document evidence.
- Users can disable memory, reference selected messages, branch a conversation, and reset memory.

Conversation fields:

- `conversation_id`
- `workspace_id`
- `notebook_id`
- `title`
- `active_rag_profile_id`
- `active_model_id`
- `memory_mode`
- `conversation_summary`
- `summary_updated_at`
- `created_at`
- `updated_at`
- `archived_at`

Message fields:

- `message_id`
- `conversation_id`
- `parent_message_id`
- `branch_id`
- `role`
- `original_content`
- `standalone_query`
- `referenced_message_ids`
- `rag_execution_id`
- `response_version`
- `input_token_count`
- `output_token_count`
- `created_at`

## Analysis Features

MVP analysis artifacts:

- Whole-notebook and per-document summaries
- Mind map
- Knowledge structure
- Document comparison
- Entity and relationship network
- Timeline
- Keyword and frequency analysis
- Text mining
- Recommended questions
- Insights
- FAQ
- Claim/evidence/counterargument structure
- Tables, charts, briefs, and reports

All generated artifacts should connect to source chunks where possible.

## Non-Functional Requirements

### Security

- TLS for all communication.
- Encrypted API key storage.
- No direct OpenSearch access from clients.
- Server-side permission filters for all retrieval.
- MIME and malicious file validation.
- Prompt injection defenses.
- Admin and user audit logs.
- Exclude document text and embeddings from general logs.

### Performance

- General API P95 target under 1 second.
- First chat token target under 3 seconds.
- Parallel execution for multi-retriever search.
- Async document processing jobs.
- Concurrent Self-Corrective evaluation.
- Cache retrieval and embedding queries where safe.

### Scalability

- Kubernetes deployment.
- Independently scalable web, API, worker, and model gateway services.
- Separate OCR and parsing workers.
- Optional GPU workers.
- Helm-based environment configuration.

### Observability

- Trace retrieval, evaluation, replenishment, and generation stages.
- Include request ID, user ID, notebook ID, and RAG execution ID.
- Use OpenTelemetry-compatible logs, metrics, and traces.
- Track accuracy feedback and latency by retrieval mode.

## MVP Acceptance Criteria

1. A user can sign in and create a notebook.
2. A user can upload PDF, DOCX, XLSX, and image files.
3. Documents are parsed, chunked, embedded, and indexed in OpenSearch.
4. The search lab can run the same question through BM25 and vector search.
5. Search results show chunk, document name, page/location, score, and latency.
6. Raw embeddings are not exposed in the default UI.
7. A user can choose BM25 Top 5 + Vector Top 5 for RAG.
8. Retrievers run in parallel and merge candidates by the selected policy.
9. A user can enable Self-Corrective RAG.
10. The system evaluates candidate relevance and replenishes excluded chunks.
11. The final answer streams from the LLM.
12. Answer claims show citations.
13. Clicking a citation opens the source viewer location.
14. RAG stage latency and execution details are inspectable.
15. The system can be deployed to Kubernetes with Helm.

