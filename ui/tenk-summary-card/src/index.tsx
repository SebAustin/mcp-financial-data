import { createRoot } from "react-dom/client";

export type CitationPill = {
  claim_text: string;
  document_title: string;
  cited_text: string;
  start_char_index: number;
  end_char_index: number;
  url: string;
};

export type TenKSummaryCardProps = {
  extraction: {
    section: string;
    document_title: string;
    facts: Array<{ text: string; citations: Array<{ cited_text: string }> }>;
    notes: string[];
    model: string;
    input_tokens: number;
    output_tokens: number;
    cost_usd: number;
    latency_ms: number;
  };
  cik: string;
  company_name: string;
};

function Header(props: TenKSummaryCardProps) {
  return (
    <header className="tk-header">
      <h1>{props.company_name}</h1>
      <p>
        CIK {props.cik} · {props.extraction.document_title}
      </p>
    </header>
  );
}

function FactsList({
  facts,
  pills,
}: {
  facts: TenKSummaryCardProps["extraction"]["facts"];
  pills: CitationPill[];
}) {
  return (
    <section className="tk-facts">
      <h2>Facts</h2>
      <ul>
        {facts.map((fact, idx) => (
          <li key={idx}>
            <p>{fact.text}</p>
            <div className="tk-pills">
              {pills
                .filter((p) => p.claim_text === fact.text)
                .map((pill, pidx) => (
                  <a
                    key={pidx}
                    className="tk-pill"
                    href={pill.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    title={pill.cited_text}
                  >
                    {pill.cited_text.slice(0, 48)}
                    {pill.cited_text.length > 48 ? "…" : ""}
                  </a>
                ))}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Footer({ extraction }: { extraction: TenKSummaryCardProps["extraction"] }) {
  return (
    <footer className="tk-footer">
      <span>Model: {extraction.model}</span>
      <span>
        Tokens: {extraction.input_tokens} in / {extraction.output_tokens} out
      </span>
      <span>Cost: ${extraction.cost_usd.toFixed(4)}</span>
      <span>Latency: {extraction.latency_ms.toFixed(1)} ms</span>
    </footer>
  );
}

export function TenKSummaryCardView({
  cardProps,
  pills,
}: {
  cardProps: TenKSummaryCardProps;
  pills: CitationPill[];
}) {
  return (
    <div className="tk-card">
      <Header {...cardProps} />
      <FactsList facts={cardProps.extraction.facts} pills={pills} />
      <Footer extraction={cardProps.extraction} />
    </div>
  );
}

function mountFromGlobals() {
  const host = document.getElementById("tenk-summary-card-root");
  if (!host) return;
  const envelope = (window as unknown as { __TENK_UI_PROPS__?: Record<string, unknown> })
    .__TENK_UI_PROPS__;
  if (!envelope) return;
  const props = envelope.props as TenKSummaryCardProps;
  const pills = (envelope.citationPills ?? []) as CitationPill[];
  createRoot(host).render(<TenKSummaryCardView cardProps={props} pills={pills} />);
}

if (typeof document !== "undefined") {
  mountFromGlobals();
}
