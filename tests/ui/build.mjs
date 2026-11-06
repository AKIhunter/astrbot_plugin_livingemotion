import { build } from "esbuild";
import { fileURLToPath } from "node:url";
await build({
  stdin: { contents: 'export { forceSimulation, forceManyBody, forceLink, forceCollide, forceX, forceY } from "d3-force";',
    resolveDir: fileURLToPath(new URL(".", import.meta.url)), sourcefile: "livingemotion-force-entry.mjs" },
  outfile: fileURLToPath(new URL("../../pages/livingemotion/vendor/d3-force.mjs", import.meta.url)),
  bundle: true, format: "esm", platform: "browser", target: "es2022", minify: true,
  legalComments: "inline", banner: { js: "// d3-force 3.0.0; local ESM build. See THIRD_PARTY_NOTICES.md." },
});
