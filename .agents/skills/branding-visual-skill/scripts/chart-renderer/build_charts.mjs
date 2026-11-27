// Builds one PPTX slide per *.chart.json from a charts directory.
// Usage:
//   node build_charts.mjs --charts <dir> --tokens <visual-dna/tokens.json> --out <deck.pptx>
//                         [--root <dir>] [--kicker "BRAND / DATA"] [--title "Deck title"]
// --root is the directory data.location is relative to (default: parent of --charts).
// Run validate_chart_spec.py first: the renderer refuses specs whose data hash changed.
import path from "node:path";
import { parseArgs } from "node:util";
import { buildDeck } from "./render_pptx.mjs";

const { values: args } = parseArgs({
  options: {
    charts: { type: "string" },
    tokens: { type: "string" },
    out: { type: "string" },
    root: { type: "string" },
    kicker: { type: "string", default: "" },
    title: { type: "string", default: "Charts" },
  },
});
for (const key of ["charts", "tokens", "out"]) {
  if (!args[key]) {
    console.error(`missing --${key}`);
    process.exit(2);
  }
}
const specsDir = path.resolve(args.charts);
const report = await buildDeck({
  specsDir,
  root: path.resolve(args.root || path.dirname(specsDir)),
  tokensPath: path.resolve(args.tokens),
  out: path.resolve(args.out),
  kicker: args.kicker,
  title: args.title,
});
console.table(report);
console.log(`written: ${path.resolve(args.out)}`);
