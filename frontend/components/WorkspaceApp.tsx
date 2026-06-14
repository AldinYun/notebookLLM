"use client";

import {
  Bot,
  CheckCircle2,
  Download,
  FilePlus2,
  FileSearch,
  FileText,
  Gauge,
  Loader2,
  MessageSquareText,
  Network,
  Search,
  Settings2,
  Trash2,
  Upload,
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

type Notebook = {
  notebook_id: string;
  title: string;
  description: string;
  document_count: number;
};

type DocumentItem = {
  document_id: string;
  notebook_id: string;
  file_name: string;
  title: string;
  status: string;
  chunk_count: number;
  mime_type: string;
  file_size: number;
  file_hash: string;
  storage_object_key: string;
  tags: string[];
};

type RetrieverMode = "bm25" | "vector" | "hybrid" | "text";

type RetrieverConfig = {
  mode: RetrieverMode;
  top_k: number;
  weight: number;
};

type SearchHit = {
  chunk_id: string;
  document_id: string;
  document_title: string;
  retriever: RetrieverMode;
  rank: number;
  score: number;
  page_start: number;
  section_title: string;
  snippet: string;
  matched_terms: string[];
};

type SearchResponse = {
  query: string;
  elapsed_ms: number;
  hits: SearchHit[];
  retriever_summaries: Record<string, number>;
};

type Citation = {
  citation_id: string;
  document_title: string;
  page_start: number;
  section_title: string;
  quote: string;
};

type RagResponse = {
  rag_execution_id: string;
  question: string;
  standalone_query: string;
  answer: string;
  citations: Citation[];
  search: SearchResponse;
  self_corrective_enabled: boolean;
  excluded_chunk_ids: string[];
  elapsed_ms: number;
};

type RagExecution = RagResponse & {
  notebook_id: string;
  created_at: string;
};

type SearchProfile = {
  profile_id: string;
  notebook_id: string;
  name: string;
  retrievers: RetrieverConfig[];
  self_corrective_enabled: boolean;
  final_context_limit: number;
};

type ModelConnection = {
  connection_id: string;
  name: string;
  provider: string;
  base_url: string;
  model_id: string;
  api_key_hint: string;
  capabilities: string[];
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const defaultRetrievers: RetrieverConfig[] = [
  { mode: "bm25", top_k: 5, weight: 1 },
  { mode: "vector", top_k: 5, weight: 1 },
  { mode: "hybrid", top_k: 10, weight: 1 },
];

const workflowCards = [
  {
    icon: FileSearch,
    title: "Search Lab",
    body: "Run BM25, vector, hybrid, and multi-retriever comparisons against ingested chunks.",
  },
  {
    icon: MessageSquareText,
    title: "RAG Loop",
    body: "Use the selected retrievers to build context, generate a placeholder answer, and return citations.",
  },
  {
    icon: Network,
    title: "Correction",
    body: "Toggle Self-Corrective RAG plumbing for candidate filtering and trace visibility.",
  },
  {
    icon: Settings2,
    title: "Next Slice",
    body: "Persistence, OpenSearch wiring, and OpenAI-compatible model gateway can build on this flow.",
  },
];

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function WorkspaceApp() {
  const [notebooks, setNotebooks] = useState<Notebook[]>([]);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedNotebookId, setSelectedNotebookId] = useState("");
  const [notebookTitle, setNotebookTitle] = useState("MVP Research");
  const [documentTitle, setDocumentTitle] = useState("Insight Notebook Requirements");
  const [fileName, setFileName] = useState("requirements.md");
  const [documentContent, setDocumentContent] = useState(
    "OpenSearch enables BM25, vector, and hybrid retrieval.\nSelf-Corrective RAG evaluates candidate chunks and replenishes context.\nEvery grounded answer should expose citations."
  );
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [query, setQuery] = useState("How should BM25 and vector retrievers be combined?");
  const [selfCorrectiveEnabled, setSelfCorrectiveEnabled] = useState(true);
  const [searchProfiles, setSearchProfiles] = useState<SearchProfile[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState("");
  const [profileName, setProfileName] = useState("Balanced Debug");
  const [modelConnections, setModelConnections] = useState<ModelConnection[]>([]);
  const [modelName, setModelName] = useState("Local vLLM");
  const [modelBaseUrl, setModelBaseUrl] = useState("http://localhost:8001/v1");
  const [modelId, setModelId] = useState("local-model");
  const [apiKey, setApiKey] = useState("");
  const [searchResult, setSearchResult] = useState<SearchResponse | null>(null);
  const [ragResult, setRagResult] = useState<RagResponse | null>(null);
  const [ragExecutions, setRagExecutions] = useState<RagExecution[]>([]);
  const [statusMessage, setStatusMessage] = useState("Ready");
  const [isBusy, setIsBusy] = useState(false);

  const selectedNotebook = notebooks.find((notebook) => notebook.notebook_id === selectedNotebookId);
  const selectedDocuments = documents.filter(
    (document) => document.notebook_id === selectedNotebookId
  );
  const selectedProfile = searchProfiles.find((profile) => profile.profile_id === selectedProfileId);
  const activeRetrievers = selectedProfile?.retrievers ?? defaultRetrievers;
  const activeFinalContextLimit = selectedProfile?.final_context_limit ?? 8;

  const retrieverSummaries = useMemo(() => {
    return activeRetrievers.map((retriever) => ({
      ...retriever,
      label: retriever.mode.toUpperCase(),
      hits: searchResult?.retriever_summaries[retriever.mode] ?? 0,
      latency: searchResult ? `${searchResult.elapsed_ms} ms` : "not run",
    }));
  }, [activeRetrievers, searchResult]);

  useEffect(() => {
    void refreshWorkspace();
  }, []);

  async function refreshWorkspace(nextNotebookId?: string) {
    try {
      const [nextNotebooks, nextDocuments] = await Promise.all([
        requestJson<Notebook[]>("/notebooks"),
        requestJson<DocumentItem[]>("/documents"),
      ]);
      await refreshModelConnections();
      setNotebooks(nextNotebooks);
      setDocuments(nextDocuments);
      const fallbackNotebookId = nextNotebookId || selectedNotebookId || nextNotebooks[0]?.notebook_id || "";
      setSelectedNotebookId(fallbackNotebookId);
      if (fallbackNotebookId) {
        await refreshSearchProfiles(fallbackNotebookId);
        await refreshRagExecutions(fallbackNotebookId);
      }
      setStatusMessage(`Connected to ${API_BASE_URL}`);
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "Could not connect to backend API");
    }
  }

  async function refreshRagExecutions(notebookId = selectedNotebookId) {
    if (!notebookId) {
      setRagExecutions([]);
      return;
    }
    const executions = await requestJson<RagExecution[]>(
      `/rag/executions?notebook_id=${encodeURIComponent(notebookId)}`
    );
    setRagExecutions(executions);
  }

  async function refreshSearchProfiles(notebookId = selectedNotebookId) {
    if (!notebookId) {
      setSearchProfiles([]);
      setSelectedProfileId("");
      return;
    }
    const profiles = await requestJson<SearchProfile[]>(
      `/profiles/search?notebook_id=${encodeURIComponent(notebookId)}`
    );
    setSearchProfiles(profiles);
    const nextProfile = profiles.find((profile) => profile.profile_id === selectedProfileId) ?? profiles[0];
    setSelectedProfileId(nextProfile?.profile_id ?? "");
    if (nextProfile) {
      setSelfCorrectiveEnabled(nextProfile.self_corrective_enabled);
    }
  }

  async function refreshModelConnections() {
    const connections = await requestJson<ModelConnection[]>("/models/connections");
    setModelConnections(connections);
  }

  async function createModelConnection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsBusy(true);
    try {
      const connection = await requestJson<ModelConnection>("/models/connections", {
        method: "POST",
        body: JSON.stringify({
          name: modelName,
          provider: "openai-compatible",
          base_url: modelBaseUrl,
          model_id: modelId,
          api_key: apiKey,
          capabilities: ["chat", "embedding"],
        }),
      });
      setApiKey("");
      await refreshModelConnections();
      setStatusMessage(`Registered model connection ${connection.name}`);
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "Model connection failed");
    } finally {
      setIsBusy(false);
    }
  }

  async function createSearchProfile() {
    if (!selectedNotebookId) {
      setStatusMessage("Create or select a notebook first");
      return;
    }

    setIsBusy(true);
    try {
      const profile = await requestJson<SearchProfile>("/profiles/search", {
        method: "POST",
        body: JSON.stringify({
          notebook_id: selectedNotebookId,
          name: profileName,
          retrievers: activeRetrievers,
          self_corrective_enabled: selfCorrectiveEnabled,
          final_context_limit: activeFinalContextLimit,
        }),
      });
      await refreshSearchProfiles(selectedNotebookId);
      setSelectedProfileId(profile.profile_id);
      setStatusMessage(`Saved search profile ${profile.name}`);
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "Search profile save failed");
    } finally {
      setIsBusy(false);
    }
  }

  async function createNotebook(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsBusy(true);
    try {
      const notebook = await requestJson<Notebook>("/notebooks", {
        method: "POST",
        body: JSON.stringify({ title: notebookTitle, description: "Created from the MVP workspace" }),
      });
      setNotebookTitle("");
      await refreshWorkspace(notebook.notebook_id);
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "Notebook creation failed");
    } finally {
      setIsBusy(false);
    }
  }

  async function ingestDocument(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedNotebookId) {
      setStatusMessage("Create or select a notebook first");
      return;
    }

    setIsBusy(true);
    try {
      await requestJson<DocumentItem>("/documents/ingest-text", {
        method: "POST",
        body: JSON.stringify({
          notebook_id: selectedNotebookId,
          file_name: fileName,
          title: documentTitle,
          content: documentContent,
          tags: ["mvp", "rag"],
        }),
      });
      await refreshWorkspace(selectedNotebookId);
      setStatusMessage("Document ingested and chunked");
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "Document ingestion failed");
    } finally {
      setIsBusy(false);
    }
  }

  async function uploadDocument(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedNotebookId || !selectedFile) {
      setStatusMessage("Select a notebook and file first");
      return;
    }

    setIsBusy(true);
    try {
      const params = new URLSearchParams({
        notebook_id: selectedNotebookId,
        title: documentTitle || selectedFile.name,
        file_name: selectedFile.name,
        tags: "upload,mvp",
      });
      const response = await fetch(`${API_BASE_URL}/documents/upload?${params.toString()}`, {
        method: "POST",
        headers: {
          "Content-Type": selectedFile.type || "application/octet-stream",
        },
        body: await selectedFile.arrayBuffer(),
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const document = (await response.json()) as DocumentItem;
      setSelectedFile(null);
      await refreshWorkspace(selectedNotebookId);
      setStatusMessage(`Uploaded ${document.file_name} as ${document.chunk_count} chunks`);
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "File upload failed");
    } finally {
      setIsBusy(false);
    }
  }

  async function deleteDocument(documentId: string) {
    setIsBusy(true);
    try {
      const response = await fetch(`${API_BASE_URL}/documents/${documentId}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      await refreshWorkspace(selectedNotebookId);
      setSearchResult(null);
      setRagResult(null);
      setStatusMessage("Document and indexed chunks deleted");
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "Document deletion failed");
    } finally {
      setIsBusy(false);
    }
  }

  async function runSearch() {
    if (!selectedNotebookId) {
      setStatusMessage("Create or select a notebook first");
      return;
    }

    setIsBusy(true);
    try {
      const result = await requestJson<SearchResponse>("/search", {
        method: "POST",
        body: JSON.stringify({
          notebook_id: selectedNotebookId,
          query,
          retrievers: activeRetrievers.map((retriever) => ({
            mode: retriever.mode,
            top_k: retriever.top_k,
            weight: retriever.weight,
          })),
        }),
      });
      setSearchResult(result);
      setStatusMessage(`Search returned ${result.hits.length} hits`);
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "Search failed");
    } finally {
      setIsBusy(false);
    }
  }

  async function runRag() {
    if (!selectedNotebookId) {
      setStatusMessage("Create or select a notebook first");
      return;
    }

    setIsBusy(true);
    try {
      const result = await requestJson<RagResponse>("/rag/run", {
        method: "POST",
        body: JSON.stringify({
          notebook_id: selectedNotebookId,
          question: query,
          retrievers: [
            ...activeRetrievers.map((retriever) => ({
              mode: retriever.mode,
              top_k: retriever.top_k,
              weight: retriever.weight,
            })),
          ],
          self_corrective_enabled: selfCorrectiveEnabled,
          final_context_limit: activeFinalContextLimit,
        }),
      });
      setRagResult(result);
      setSearchResult(result.search);
      await refreshRagExecutions(selectedNotebookId);
      setStatusMessage(
        `RAG ${result.rag_execution_id} prepared ${result.citations.length} citations`
      );
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "RAG run failed");
    } finally {
      setIsBusy(false);
    }
  }

  return (
    <main className="shell">
      <section className="workspace">
        <div className="toolbar">
          <div>
            <p className="eyebrow">Insight Notebook</p>
            <h1>Document RAG workspace</h1>
          </div>
          <div className="toolbarActions">
            <button className="secondaryButton" onClick={() => void refreshWorkspace()} type="button">
              {isBusy ? <Loader2 aria-hidden="true" className="spin" size={18} /> : <Search aria-hidden="true" size={18} />}
              Refresh
            </button>
            <button onClick={() => void runRag()} type="button">
              <Bot aria-hidden="true" size={18} />
              Run RAG
            </button>
          </div>
        </div>

        <p className="statusLine">{statusMessage}</p>

        <div className="appGrid">
          <aside className="sidebar">
            <div className="sectionHeader">
              <h2>Notebooks</h2>
              <span>{notebooks.length}</span>
            </div>

            <form className="inlineForm" onSubmit={(event) => void createNotebook(event)}>
              <input
                aria-label="Notebook title"
                onChange={(event) => setNotebookTitle(event.target.value)}
                placeholder="Notebook title"
                value={notebookTitle}
              />
              <button disabled={isBusy || !notebookTitle.trim()} type="submit">
                <FilePlus2 aria-hidden="true" size={16} />
              </button>
            </form>

            <div className="notebookList">
              {notebooks.map((notebook) => (
                <button
                  className={`notebookItem ${notebook.notebook_id === selectedNotebookId ? "active" : ""}`}
                  key={notebook.notebook_id}
                  onClick={() => {
                    setSelectedNotebookId(notebook.notebook_id);
                    setSearchResult(null);
                    setRagResult(null);
                    void refreshRagExecutions(notebook.notebook_id);
                    void refreshSearchProfiles(notebook.notebook_id);
                  }}
                  type="button"
                >
                  <FileText aria-hidden="true" size={18} />
                  <span>
                    <strong>{notebook.title}</strong>
                    <small>
                      {notebook.document_count} docs - {notebook.description || "No description"}
                    </small>
                  </span>
                </button>
              ))}
            </div>

            <div className="documents">
              <div className="sectionHeader">
                <h2>Documents</h2>
                <span>{selectedDocuments.length}</span>
              </div>
              {selectedDocuments.map((document) => (
                <article className="documentRow" key={document.document_id}>
                  <div>
                    <strong>{document.title}</strong>
                    <small>
                      {document.file_name} - {document.chunk_count} chunks - {document.file_size} bytes
                    </small>
                  </div>
                  <div className="documentActions">
                    <button
                      aria-label={`Download ${document.title}`}
                      className="iconButton secondaryButton"
                      onClick={() =>
                        window.open(
                          `${API_BASE_URL}/documents/${document.document_id}/source`,
                          "_blank",
                          "noopener,noreferrer"
                        )
                      }
                      title="Download source"
                      type="button"
                    >
                      <Download aria-hidden="true" size={16} />
                    </button>
                    <button
                      aria-label={`Delete ${document.title}`}
                      className="iconButton dangerButton"
                      disabled={isBusy}
                      onClick={() => void deleteDocument(document.document_id)}
                      title="Delete document"
                      type="button"
                    >
                      <Trash2 aria-hidden="true" size={16} />
                    </button>
                  </div>
                </article>
              ))}
              {selectedDocuments.length === 0 && <p className="emptyState">No documents indexed yet.</p>}
            </div>
          </aside>

          <section className="mainPanel">
            <form className="uploadPanel" onSubmit={(event) => void uploadDocument(event)}>
              <label className="filePicker">
                <Upload aria-hidden="true" size={20} />
                <span>{selectedFile?.name ?? "Choose TXT, MD, CSV, TSV, JSON, XML, or HTML"}</span>
                <input
                  accept=".txt,.md,.csv,.tsv,.json,.xml,.html,.htm"
                  onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
                  type="file"
                />
              </label>
              <button disabled={isBusy || !selectedNotebookId || !selectedFile} type="submit">
                Upload file
              </button>
            </form>

            <form className="ingestPanel" onSubmit={(event) => void ingestDocument(event)}>
              <div className="twoColumn">
                <input
                  aria-label="Document title"
                  onChange={(event) => setDocumentTitle(event.target.value)}
                  placeholder="Document title"
                  value={documentTitle}
                />
                <input
                  aria-label="File name"
                  onChange={(event) => setFileName(event.target.value)}
                  placeholder="File name"
                  value={fileName}
                />
              </div>
              <textarea
                aria-label="Document content"
                onChange={(event) => setDocumentContent(event.target.value)}
                value={documentContent}
              />
              <button disabled={isBusy || !selectedNotebookId || !documentContent.trim()} type="submit">
                <FilePlus2 aria-hidden="true" size={18} />
                Ingest text
              </button>
            </form>

            <div className="queryBar">
              <Search aria-hidden="true" size={20} />
              <input
                aria-label="Search query"
                onChange={(event) => setQuery(event.target.value)}
                value={query}
              />
              <button disabled={isBusy || !query.trim()} onClick={() => void runSearch()} type="button">
                Run
              </button>
            </div>

            <div className="retrieverGrid">
              {retrieverSummaries.map((retriever) => (
                <article className="retrieverCard" key={retriever.mode}>
                  <div>
                    <strong>{retriever.label}</strong>
                    <small>Top {retriever.top_k}</small>
                  </div>
                  <p>{retriever.hits}</p>
                  <span>{retriever.latency}</span>
                </article>
              ))}
            </div>

            <div className="resultsHeader">
              <div>
                <p className="eyebrow">Search Results</p>
                <h2>{selectedNotebook?.title ?? "Select a notebook"}</h2>
              </div>
              <span>{searchResult ? `${searchResult.hits.length} hits` : "not run"}</span>
            </div>

            <div className="resultList">
              {searchResult?.hits.map((hit) => (
                <article className="resultItem" key={`${hit.retriever}-${hit.chunk_id}`}>
                  <div className="rank">{hit.rank}</div>
                  <div>
                    <div className="resultMeta">
                      <strong>{hit.document_title}</strong>
                      <span>{hit.retriever}</span>
                      <span>{hit.section_title}</span>
                      <span>score {hit.score}</span>
                    </div>
                    <p>{hit.snippet}</p>
                  </div>
                </article>
              ))}
              {!searchResult && <p className="emptyState">Run search after ingesting a document.</p>}
            </div>
          </section>

          <aside className="rightRail">
            <section className="statusPanel">
              <div className="statusTitle">
                <Settings2 aria-hidden="true" size={20} />
                <h2>Models</h2>
              </div>
              <form className="modelForm" onSubmit={(event) => void createModelConnection(event)}>
                <input
                  aria-label="Model connection name"
                  onChange={(event) => setModelName(event.target.value)}
                  value={modelName}
                />
                <input
                  aria-label="Model base URL"
                  onChange={(event) => setModelBaseUrl(event.target.value)}
                  value={modelBaseUrl}
                />
                <input
                  aria-label="Model ID"
                  onChange={(event) => setModelId(event.target.value)}
                  value={modelId}
                />
                <input
                  aria-label="API key"
                  onChange={(event) => setApiKey(event.target.value)}
                  placeholder="API key"
                  type="password"
                  value={apiKey}
                />
                <button disabled={isBusy || !modelName.trim() || !modelBaseUrl.trim() || !modelId.trim()} type="submit">
                  Register
                </button>
              </form>
              <div className="modelList">
                {modelConnections.map((connection) => (
                  <article key={connection.connection_id}>
                    <strong>{connection.name}</strong>
                    <span>{connection.model_id}</span>
                    <small>{connection.api_key_hint}</small>
                  </article>
                ))}
                {modelConnections.length === 0 && <p className="emptyState">No model connections yet.</p>}
              </div>
            </section>

            <section className="statusPanel">
              <div className="statusTitle">
                <Bot aria-hidden="true" size={20} />
                <h2>RAG Profile</h2>
              </div>
              <div className="profileSelectList">
                {searchProfiles.map((profile) => (
                  <button
                    className={`profileSelect ${profile.profile_id === selectedProfileId ? "active" : ""}`}
                    key={profile.profile_id}
                    onClick={() => {
                      setSelectedProfileId(profile.profile_id);
                      setSelfCorrectiveEnabled(profile.self_corrective_enabled);
                    }}
                    type="button"
                  >
                    <strong>{profile.name}</strong>
                    <small>
                      {profile.retrievers.map((retriever) => retriever.mode).join(" + ")}
                    </small>
                  </button>
                ))}
              </div>
              <label className="toggleRow">
                <input
                  checked={selfCorrectiveEnabled}
                  onChange={(event) => setSelfCorrectiveEnabled(event.target.checked)}
                  type="checkbox"
                />
                Self-Corrective RAG
              </label>
              <div className="profileRows">
                {activeRetrievers.map((retriever) => (
                  <span key={`${retriever.mode}-${retriever.top_k}`}>
                    {retriever.mode.toUpperCase()} Top {retriever.top_k}
                  </span>
                ))}
                <span>Deduplicate chunks</span>
                <span>{selfCorrectiveEnabled ? "Correction on" : "Correction off"}</span>
              </div>
              <div className="profileSave">
                <input
                  aria-label="Profile name"
                  onChange={(event) => setProfileName(event.target.value)}
                  value={profileName}
                />
                <button disabled={isBusy || !profileName.trim()} onClick={() => void createSearchProfile()} type="button">
                  Save
                </button>
              </div>
            </section>

            <section className="statusPanel">
              <div className="statusTitle">
                <Gauge aria-hidden="true" size={20} />
                <h2>Run Trace</h2>
              </div>
              <ol className="traceList">
                <li>
                  <CheckCircle2 aria-hidden="true" size={16} />
                  {ragResult ? `Standalone query: ${ragResult.standalone_query}` : "Waiting for RAG run"}
                </li>
                <li>
                  <CheckCircle2 aria-hidden="true" size={16} />
                  {ragResult ? `${ragResult.search.hits.length} candidates retrieved` : "No candidates yet"}
                </li>
                <li>
                  <CheckCircle2 aria-hidden="true" size={16} />
                  {ragResult ? `${ragResult.excluded_chunk_ids.length} chunks excluded` : "No correction trace"}
                </li>
                <li>
                  <CheckCircle2 aria-hidden="true" size={16} />
                  {ragResult ? `${ragResult.citations.length} citations prepared` : "No citations yet"}
                </li>
              </ol>
            </section>

            <section className="statusPanel">
              <div className="statusTitle">
                <Gauge aria-hidden="true" size={20} />
                <h2>Recent Runs</h2>
              </div>
              <div className="runList">
                {ragExecutions.slice(0, 5).map((execution) => (
                  <button
                    className="runItem"
                    key={execution.rag_execution_id}
                    onClick={() => {
                      setRagResult(execution);
                      setSearchResult(execution.search);
                    }}
                    type="button"
                  >
                    <strong>{execution.rag_execution_id}</strong>
                    <span>{execution.citations.length} citations</span>
                    <small>{execution.question}</small>
                  </button>
                ))}
                {ragExecutions.length === 0 && <p className="emptyState">No RAG runs recorded yet.</p>}
              </div>
            </section>

            <section className="statusPanel emphasis">
              <MessageSquareText aria-hidden="true" size={22} />
              <p className="answerText">
                {ragResult?.answer ??
                  "Run RAG to generate a citation-backed placeholder answer from retrieved chunks."}
              </p>
              <div className="citationList">
                {ragResult?.citations.map((citation) => (
                  <article key={citation.citation_id}>
                    <strong>{citation.citation_id}</strong>
                    <span>
                      {citation.document_title}, page {citation.page_start}
                    </span>
                    <p>{citation.quote}</p>
                  </article>
                ))}
              </div>
            </section>
          </aside>
        </div>

        <section className="workflowGrid">
          {workflowCards.map((workflow) => {
            const Icon = workflow.icon;
            return (
              <article className="workflow" key={workflow.title}>
                <Icon aria-hidden="true" size={22} />
                <h3>{workflow.title}</h3>
                <p>{workflow.body}</p>
              </article>
            );
          })}
        </section>
      </section>
    </main>
  );
}
