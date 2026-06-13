import {
  Bot,
  CheckCircle2,
  Database,
  FileSearch,
  FileText,
  Gauge,
  MessageSquareText,
  Network,
  Search,
  Settings2,
} from "lucide-react";

const notebooks = [
  { title: "MVP Research", documents: 4, status: "Indexed", active: true },
  { title: "Model Gateway Notes", documents: 2, status: "Parsing", active: false },
  { title: "Citation QA", documents: 3, status: "Indexed", active: false },
];

const documents = [
  { name: "requirements.md", chunks: 42, status: "Indexed" },
  { name: "opensearch-mapping.json", chunks: 18, status: "Indexed" },
  { name: "architecture.pdf", chunks: 31, status: "OCR queued" },
];

const retrievers = [
  { mode: "BM25", topK: 5, latency: "42 ms", hits: 5 },
  { mode: "Vector", topK: 5, latency: "58 ms", hits: 5 },
  { mode: "Hybrid", topK: 10, latency: "71 ms", hits: 8 },
];

const searchHits = [
  {
    rank: 1,
    source: "requirements.md",
    section: "OpenSearch Requirements",
    score: "12.84",
    text: "Search operates primarily on chunk documents, not whole files. Each chunk keeps tenant, document, location, parsing, and embedding metadata.",
  },
  {
    rank: 2,
    source: "requirements.md",
    section: "Self-Corrective RAG",
    score: "9.76",
    text: "Candidate chunks are evaluated for relevance, irrelevant chunks are excluded, and next-ranked candidates replenish the context.",
  },
  {
    rank: 3,
    source: "architecture.pdf",
    section: "Retrieval Flow",
    score: "8.41",
    text: "Configured retrievers run in parallel before normalization, fusion, deduplication, optional correction, and augmentation.",
  },
];

const workflows = [
  {
    icon: FileSearch,
    title: "Search Lab ready",
    body: "BM25, vector, hybrid, and multi-retriever comparison API is now scaffolded.",
  },
  {
    icon: MessageSquareText,
    title: "RAG run loop",
    body: "Question, retrieval, deduped context, placeholder answer, and citations now share one flow.",
  },
  {
    icon: Network,
    title: "Corrective switch",
    body: "The API accepts a profile-level Self-Corrective toggle and records excluded chunks.",
  },
  {
    icon: Settings2,
    title: "Model gateway next",
    body: "OpenAI-compatible model registration is the next backend slice after persistence.",
  },
];

export default function Home() {
  return (
    <main className="shell">
      <section className="workspace">
        <div className="toolbar">
          <div>
            <p className="eyebrow">Insight Notebook</p>
            <h1>Document RAG workspace</h1>
          </div>
          <div className="toolbarActions">
            <button className="secondaryButton" type="button">
              <Search aria-hidden="true" size={18} />
              Search lab
            </button>
            <button type="button">New notebook</button>
          </div>
        </div>

        <div className="appGrid">
          <aside className="sidebar">
            <div className="sectionHeader">
              <h2>Notebooks</h2>
              <span>3</span>
            </div>
            <div className="notebookList">
              {notebooks.map((notebook) => (
                <button
                  className={`notebookItem ${notebook.active ? "active" : ""}`}
                  key={notebook.title}
                  type="button"
                >
                  <FileText aria-hidden="true" size={18} />
                  <span>
                    <strong>{notebook.title}</strong>
                    <small>
                      {notebook.documents} docs · {notebook.status}
                    </small>
                  </span>
                </button>
              ))}
            </div>

            <div className="documents">
              <div className="sectionHeader">
                <h2>Documents</h2>
                <span>Active</span>
              </div>
              {documents.map((document) => (
                <article className="documentRow" key={document.name}>
                  <div>
                    <strong>{document.name}</strong>
                    <small>{document.chunks} chunks</small>
                  </div>
                  <span>{document.status}</span>
                </article>
              ))}
            </div>
          </aside>

          <section className="mainPanel">
            <div className="queryBar">
              <Search aria-hidden="true" size={20} />
              <input
                aria-label="Search query"
                defaultValue="How should BM25 and vector retrievers be combined?"
              />
              <button type="button">Run</button>
            </div>

            <div className="retrieverGrid">
              {retrievers.map((retriever) => (
                <article className="retrieverCard" key={retriever.mode}>
                  <div>
                    <strong>{retriever.mode}</strong>
                    <small>Top {retriever.topK}</small>
                  </div>
                  <p>{retriever.hits}</p>
                  <span>{retriever.latency}</span>
                </article>
              ))}
            </div>

            <div className="resultsHeader">
              <div>
                <p className="eyebrow">Search Results</p>
                <h2>Compared retrieval evidence</h2>
              </div>
              <span>RRF fusion enabled</span>
            </div>

            <div className="resultList">
              {searchHits.map((hit) => (
                <article className="resultItem" key={`${hit.rank}-${hit.source}`}>
                  <div className="rank">{hit.rank}</div>
                  <div>
                    <div className="resultMeta">
                      <strong>{hit.source}</strong>
                      <span>{hit.section}</span>
                      <span>score {hit.score}</span>
                    </div>
                    <p>{hit.text}</p>
                  </div>
                </article>
              ))}
            </div>
          </section>

          <aside className="rightRail">
            <section className="statusPanel">
              <div className="statusTitle">
                <Bot aria-hidden="true" size={20} />
                <h2>RAG Profile</h2>
              </div>
              <div className="profileRows">
                <span>BM25 Top 5</span>
                <span>Vector Top 5</span>
                <span>Deduplicate chunks</span>
                <span>Self-Corrective on</span>
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
                  Query normalized
                </li>
                <li>
                  <CheckCircle2 aria-hidden="true" size={16} />
                  18 candidates retrieved
                </li>
                <li>
                  <CheckCircle2 aria-hidden="true" size={16} />
                  3 duplicates removed
                </li>
                <li>
                  <CheckCircle2 aria-hidden="true" size={16} />
                  8 citations prepared
                </li>
              </ol>
            </section>

            <section className="statusPanel emphasis">
              <Database aria-hidden="true" size={22} />
              <p className="metric">MVP</p>
              <span>Backend flow now covers notebook, ingestion, search, and RAG run APIs.</span>
            </section>
          </aside>
        </div>

        <section className="workflowGrid">
          {workflows.map((workflow) => {
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
