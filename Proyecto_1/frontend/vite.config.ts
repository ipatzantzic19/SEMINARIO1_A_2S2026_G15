import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The SPA is served from the root of the S3/CloudFront origin. Relative asset
// paths break when a user refreshes a nested BrowserRouter route.
export default defineConfig({ plugins: [react()], base: '/' })
