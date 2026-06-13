import { FileSearch, MessageSquareText, Network, Settings2 } from "lucide-react";

const workflows = [
  {
    icon: FileSearch,
    title: "Search Lab",
    body: "Compare BM25, vector, hybrid, and multi-retriever results before using them in RAG.",
  },
  {
    icon: MessageSquareText,
    title: "Grounded Chat",
    body: "Stream answers with sentence-level citations connected to source document locations.",
  },
  {
    icon: Network,
    title: "Self-Corrective RAG",
    body: "Evaluate candidate chunks, exclude irrelevant evidence, and replenish context automatically.",
  },
  {
    icon: Settings2,
    title: "Model Gateway",
    body: "Use admin models, user API keys, or private OpenAI-compatible sLLM endpoints.",
  },
];

export default function Home() {
  return (
    <main className="shell">
      <section className="workspace">
        <div className="toolbar">
          <div>
            <p className="eyebrow">Insight Notebook</p>
            <h1>Document-grounded LLM workspace</h1>
          </div>
          <button type="button">New notebook</button>
        </div>

        <div className="grid">
          <section className="panel primary">
            <div>
              <p className="eyebrow">MVP Focus</p>
              <h2>Upload, retrieve, correct, cite.</h2>
              <p>
                The first build centers on notebook file management, OpenSearch retrieval experiments,
                configurable RAG profiles, and citation-backed streaming chat.
              </p>
            </div>
          </section>

          <section className="panel compact">
            <p className="metric">4</p>
            <span>retrieval families</span>
          </section>

          <section className="panel compact">
            <p className="metric">15</p>
            <span>MVP acceptance checks</span>
          </section>
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

