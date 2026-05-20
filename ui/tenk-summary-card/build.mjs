import * as esbuild from "esbuild";
import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const outDir = join(root, "..", "..", "static", "ui");
mkdirSync(outDir, { recursive: true });

await esbuild.build({
  entryPoints: [join(root, "src", "index.tsx")],
  bundle: true,
  format: "iife",
  globalName: "TenKSummaryCard",
  outfile: join(outDir, "tenk-summary-card.bundle.js"),
  minify: true,
  target: ["es2022"],
  jsx: "automatic",
  loader: { ".tsx": "tsx" },
  define: {
    "process.env.NODE_ENV": '"production"',
  },
});

console.log("wrote static/ui/tenk-summary-card.bundle.js");
