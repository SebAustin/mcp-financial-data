/*! TenKSummaryCard — MCP Apps bundle (esbuild output; rebuild via `make ui-build`) */
(function () {
  "use strict";
  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    if (attrs) {
      Object.entries(attrs).forEach(([k, v]) => {
        if (k === "className") node.className = String(v);
        else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2).toLowerCase(), v);
        else node.setAttribute(k, String(v));
      });
    }
    (children || []).forEach((c) => {
      if (typeof c === "string") node.appendChild(document.createTextNode(c));
      else if (c) node.appendChild(c);
    });
    return node;
  }
  function render(cardProps, pills) {
    const ext = cardProps.extraction;
    const root = el("div", { className: "tk-card" }, [
      el("header", { className: "tk-header" }, [
        el("h1", null, [cardProps.company_name]),
        el("p", null, [`CIK ${cardProps.cik} · ${ext.document_title}`]),
      ]),
      el("section", { className: "tk-facts" }, [
        el("h2", null, ["Facts"]),
        el(
          "ul",
          null,
          ext.facts.map((fact) =>
            el("li", null, [
              el("p", null, [fact.text]),
              el(
                "div",
                { className: "tk-pills" },
                pills
                  .filter((p) => p.claim_text === fact.text)
                  .map((pill, pidx) => {
                    const label =
                      pill.cited_text.length > 48
                        ? pill.cited_text.slice(0, 48) + "…"
                        : pill.cited_text;
                    return el(
                      "a",
                      {
                        className: "tk-pill",
                        href: pill.url,
                        target: "_blank",
                        rel: "noopener noreferrer",
                        title: pill.cited_text,
                      },
                      [label]
                    );
                  })
              ),
            ])
          )
        ),
      ]),
      el("footer", { className: "tk-footer" }, [
        el("span", null, [`Model: ${ext.model}`]),
        el("span", null, [`Tokens: ${ext.input_tokens} in / ${ext.output_tokens} out`]),
        el("span", null, [`Cost: $${Number(ext.cost_usd).toFixed(4)}`]),
      ]),
    ]);
    return root;
  }
  function mount() {
    const host = document.getElementById("tenk-summary-card-root");
    if (!host || !window.__TENK_UI_PROPS__) return;
    const env = window.__TENK_UI_PROPS__;
    host.replaceChildren(render(env.props, env.citationPills || []));
  }
  window.TenKSummaryCard = { mount, render };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount);
  else mount();
})();
