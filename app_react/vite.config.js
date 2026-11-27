// A tela do Painel (React) é montada aqui e sai pronta em app_ui/v2, que o servidor do Painel abre em "/".
// Os 4 PCs não instalam nada: recebem os arquivos já montados pelo git, como sempre.
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/v2/",
  build: {
    outDir: "../app_ui/v2",
    emptyOutDir: true,
    assetsDir: "assets",
    sourcemap: false,
  },
  server: {
    // npm run dev: a tela em modo de edição conversa com o Painel que estiver aberto neste PC (demonstração ou real)
    proxy: { "/api": "http://127.0.0.1:8765" },
  },
});
