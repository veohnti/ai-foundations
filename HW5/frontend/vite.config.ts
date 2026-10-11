import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The backend (http://localhost:8000) allows this exact origin, so keep the port fixed.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true },
})
