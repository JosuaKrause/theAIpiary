/**
 * Copyright (C) 2024 Josua Krause
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// NOTE: the API server (`make run-server`) listens on port 8080
const API_SERVER = 'http://127.0.0.1:8080';

export default defineConfig({
  // the app is served from the root of its domain
  base: '/',
  plugins: [react()],
  // NOTE: files in public/ are copied verbatim; the server fills in the
  // `@@NAME@@` placeholders of some of them at request time
  // (see src/swai_server/app/public_files.py)
  publicDir: 'public',
  build: {
    // the server serves the client from build/ (UI_PATH)
    outDir: 'build',
    emptyOutDir: true,
    sourcemap: true,
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: API_SERVER,
        changeOrigin: true,
        secure: false,
        ws: true,
        xfwd: true,
      },
    },
  },
});
