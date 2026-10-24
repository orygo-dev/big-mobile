import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import fs from "node:fs";
import { createRequire } from "node:module";

// Host PDF.js fonts/decoders on this origin; no external CDN or new aaPanel service.
function pdfAssets() {
  const require = createRequire(import.meta.url);
  const root = path.dirname(require.resolve('pdfjs-dist/package.json'));
  const { version } = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'));
  const prefix = `pdfjs/${version}/`;
  return { name: 'private-pdf-assets',
    generateBundle() {
      for (const directory of ['cmaps', 'standard_fonts', 'wasm']) {
        for (const file of fs.readdirSync(path.join(root, directory))) {
          if (file.endsWith('.LICENSE') || !fs.statSync(path.join(root, directory, file)).isFile()) continue;
          this.emitFile({ type: 'asset', fileName: prefix + directory + '/' + file, source: fs.readFileSync(path.join(root, directory, file)) });
        }
      }
    },
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const relative = req.url?.split('?')[0]?.slice(1);
        if (!relative?.startsWith(prefix)) return next();
        const rest = relative.slice(prefix.length);
        if (!/^(cmaps|standard_fonts|wasm)\/[A-Za-z0-9_.-]+$/.test(rest)) { res.statusCode = 404; return res.end(); }
        const target = path.join(root, rest);
        if (!fs.existsSync(target)) { res.statusCode = 404; return res.end(); }
        res.setHeader('Content-Type', rest.endsWith('.wasm') ? 'application/wasm' : 'application/octet-stream');
        fs.createReadStream(target).pipe(res);
      });
    },
  };
}

export default defineConfig(({mode}) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [react(), pdfAssets()],
    resolve: {alias: {"@": path.resolve(import.meta.dirname, "src")}},
    define: {"process.env.REACT_APP_BACKEND_URL": JSON.stringify(mode === "test" ? "" : env.REACT_APP_BACKEND_URL || "")},
    // aaPanel can place a protected .user.ini in the site's output directory.
    build: {outDir: "build", emptyOutDir: false, sourcemap: false,
      rollupOptions: {output: {assetFileNames: asset => asset.names?.some(name => name.endsWith('.mjs')) ? 'assets/[name]-[hash].js' : 'assets/[name]-[hash][extname]'}},
    },
    server: {strictPort: true, proxy: {"/api": "http://127.0.0.1:8000"}},
    test: {globals: true, environment: "jsdom", setupFiles: ["./src/test-setup.js"], maxWorkers: 1, pool: "threads", isolate: false},
  };
});
