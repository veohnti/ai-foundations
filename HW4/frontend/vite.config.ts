import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { viteSingleFile } from 'vite-plugin-singlefile'

// Two builds:
// - dev / normal: the FastAPI backend serves products and images, proxied here.
// - `--mode static`: a self-contained copy for sharing. JS, CSS, fonts, and the
//   banner photos are inlined into one index.html with relative paths, written
//   to ../output/website/ (product photos are copied next to it as images/).
export default defineConfig(({ mode }) => {
  const isStatic = mode === 'static'
  return {
    plugins: isStatic ? [react(), viteSingleFile()] : [react()],
    base: isStatic ? './' : '/',
    define: isStatic ? { 'import.meta.env.VITE_STATIC': JSON.stringify('1') } : {},
    build: isStatic
      ? { outDir: '../output/website', emptyOutDir: true, assetsInlineLimit: 100_000_000 }
      : undefined,
    server: {
      proxy: {
        '/api': 'http://127.0.0.1:8000',
        '/images': 'http://127.0.0.1:8000',
      },
    },
  }
})
