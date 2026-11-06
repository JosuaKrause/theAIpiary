# theAIpiary client

The web client: a React, TypeScript and Redux app built with
[Vite](https://vite.dev/), tested with [Vitest](https://vitest.dev/) and
linted with ESLint and Prettier. It needs Node 22 (22.22.2 or newer) and
yarn 1. The Makefile targets at the root of the repository (`make install-ts`,
`run-ts`, `lint-ts`, `test-ts`, `ts-build`, `ts-unused`) run the scripts
below from there.

## Scripts

In this directory:

- `yarn start` runs the dev server on http://localhost:3000. It reloads on
  edits and forwards `/api` to the server on port 8080 (`server.proxy` in
  `vite.config.ts`), so start the server first (`make run-server` at the root
  does both).
- `yarn build` type-checks the app and writes the production build to
  `build/`, which the server serves (`UI_PATH`). `yarn preview` serves that
  build locally, without the API.
- `yarn test` runs the tests in watch mode; `yarn testall` runs them once with
  a coverage report and `yarn testwall` watches with coverage.
- `yarn lint` runs ESLint (`eslint.config.js`), including Prettier's
  formatting check; `yarn nice` formats every file with Prettier.
- `yarn unused` lists exports that nothing imports.

## Layout

- `index.html` is the page the app mounts into; Vite injects the bundles.
- `src/` holds the app. `src/index.tsx` is the entry point.
- `public/` is copied into `build/` unchanged and served at the root
  (`/robots.txt`, `/docs/faq.md`, `/scripts/run-worker.sh`, ...). The
  `@@NAME@@` placeholders in some of these files are filled in by the server
  when they are requested (`src/swai_server/app/public_files.py`), and the
  `<appName>` and `<backLink>` ones in `public/docs/` by the app, so Prettier
  leaves `public/` alone.
