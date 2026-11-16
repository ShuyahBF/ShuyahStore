// Configuration de Vite (outil de compilation du site ShuyahStore)
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import path from 'node:path'
import { execSync } from 'node:child_process'

// Hash court du commit compilé (affiché avec la version sur les pages d'administration) :
// sur Render, RENDER_GIT_COMMIT ; en local, git ; sinon « dev ».
function hashCommitCourt() {
  if (process.env.RENDER_GIT_COMMIT) return process.env.RENDER_GIT_COMMIT.slice(0, 7)
  try { return execSync('git rev-parse --short=7 HEAD', { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim() } catch { return 'dev' }
}

export default defineConfig({
  plugins: [react()],
  // Alias "@" = dossier src (imports plus lisibles : "@/lib/api")
  resolve: { alias: { '@': path.resolve(import.meta.dirname, './src') } },
  // Valeurs calculées à CHAQUE compilation (lues par src/version.js) : impossible d'oublier de les mettre à jour
  define: { __COMMIT__: JSON.stringify(hashCommitCourt()), __DATE_BUILD__: JSON.stringify(new Date().toISOString()) },
  server: { host: true, port: 5173 },
})
