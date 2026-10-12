import { defineConfig } from 'vite';
import { viteSingleFile } from 'vite-plugin-singlefile';

// One self-contained HTML file per view: AGNT5 serves it inline from the MCP
// server's resources/read, so it needs no CDN and no CSP domains. The built
// file is committed, so a deploy needs no Node build step; rebuild it with
// `npm run build` after changing anything here.
export default defineConfig({
  plugins: [viteSingleFile()],
  build: {
    target: 'es2022',
    outDir: '../src/agnt5_mcp_server/views',
    emptyOutDir: false,
    reportCompressedSize: false,
    rollupOptions: { input: 'order.html' },
  },
});
