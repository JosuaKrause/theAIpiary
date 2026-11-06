# theAIpiary

theAIpiary is a swarm-based "inverse cloud" for running machine learning models.
The only part that runs in the cloud is a small server that hosts the website,
keeps track of users and chats, and hands out tasks. The models themselves run
on volunteers' own GPUs: anyone with an account can start a *worker bee* on their
machine, which then picks up tasks from everyone in the swarm. The swarm serves
one model, a Llama 3 chat assistant that calls itself Beatrix Buzz.

## Architecture

```
 browser ──► server ◄─────────────── provider ─────────► scattermind worker
             (src/swai_server)        (src/swai_provider)  runs the Llama graph
             client + /api            bids for tasks,      with llama.cpp
             auction queue            reports results
               │       ▲                    │                │       │
               ▼       └────────────────────┼────────────────┼───────┘ chat state via /api
             Redis                          ▼                ▼
             (rserver)                    Redis (rmain, rdata, rcache, rbody)
                                          on the volunteer's machine
```

- **Server** (`src/swai_server`, built on [quick_server](https://github.com/JosuaKrause/quick_server)).
  Serves the built client and the JSON API under `/api`: login with a session
  cookie, user management, chats, and the endpoints the providers call, which
  authenticate with a worker token. All state lives in Redis (accessed through
  [redipy](https://github.com/JosuaKrause/redipy)): users, chat sessions
  (scattermind's session store; large blobs go to disk), and the task queue.
- **Auction queue** (`src/swai_server/auction/queue.py`). A chat prompt becomes a
  task in a Redis list per model namespace (currently `llama`). Workers bid for
  work by long-polling `POST /api/task/bid` with the namespaces they can serve;
  the first worker to pop a task gets it. Workers send heartbeats with their
  status (idle, busy, backed up, offline), and a cleaner thread puts tasks back
  in the queue when the worker that took them goes away. Results come back
  through `POST /api/task/finish`, and the client polls `POST /api/chat/response`
  for the generated text.
- **Provider** (`src/swai_provider`). Runs on the volunteer's machine next to a
  [scattermind](https://github.com/JosuaKrause/scattermind) worker. It bids for
  tasks on the server, passes them to the local scattermind worker through
  four local Redis instances, and sends the results back. The worker reads and
  writes chat state through the server's API (the `remote_session_*` plugins)
  rather than keeping it on the volunteer's machine.
- **Worker**. A scattermind worker that executes the graph
  `deploy/graphs/graph_llama.json` (local runs use `local/graphs/`). Its single
  node (`src/swai/smind/nodes/node_llama.py`) runs a GGUF Llama model with
  llama-cpp-python.
- **Client** (`src/swai_client`). A create-react-app TypeScript/Redux app with
  the chat, login, password reset, FAQ and profile pages. The profile page lists
  workers, creates worker tokens and, for users allowed to, creates accounts.
- **Shared code** (`src/swai`): the API response types, the authorization header
  format, and the Llama prompt and session handling used by both sides.
- **Postgres**. `src/swai_server/system/db/` has SQLAlchemy tables and
  `src/swai_server/system/user/db.py` a Postgres-backed user manager, but they are
  not wired in yet: the user manager loader only supports Redis, so Postgres is
  not needed to run anything.

## Prerequisites

- Python 3.11 or newer (`sh/install.sh` refuses older versions)
- Node 22 and yarn 1 (classic)
- Redis (`redis-server` on the `PATH`; the local scripts start their own instances)
- A C/C++ compiler and CMake, to build llama-cpp-python
- Docker, for building images and for running a worker bee the way volunteers do
- A GPU is optional for development. `make install` builds llama-cpp-python for
  Metal on Apple silicon, for CUDA if PyTorch sees one, and for the CPU (with
  OpenBLAS) otherwise. Volunteer worker images need an NVIDIA GPU with CUDA.

## Local setup

1. **Install the dependencies.**

   ```
   make install PYTHON=python3.11   # or whichever python is 3.11+
   make install-ts
   ```

   `make install` installs PyTorch, `requirements.txt`, `requirements.dev.txt`
   and llama-cpp-python. Because `deploy/devmode.conf` sets `DEVMODE=1`, it then
   replaces quick_server, redipy and scattermind with their GitHub versions (or
   with editable installs of `../quick_server`, `../redipy` and `../scattermind`
   if you have those checkouts next to this one).

2. **Get a model.** Llama weights are not part of this repository (see
   [Models](#models)). Download a GGUF build of Meta-Llama-3-8B-Instruct, for
   example from Hugging Face after accepting Meta's license, and save it as
   `models/Meta-Llama-3-8B-Instruct-IQ3_XS.gguf` at the root of the repository.
   That is the path `local/graphs/graph_llama.json` loads (`model_path`, relative
   to `src/`); point it at a different file to use another quantization.
   `models/` is git-ignored.

3. **Configure the server.** Run `make run-server` once. It copies
   `server.env.sample` to `userdata/server/swai/server.env` and stops. Every
   variable is explained in the sample; for a local run you need:

   - `ADMIN_EMAIL` and `ADMIN_PW`: the admin account. Run `make create-admin-pw`,
     type a password twice, and paste the two lines it prints. `ADMIN_EMAIL` is
     the login name (`admin` unless you change it) and `ADMIN_PW` is a bcrypt
     hash, not the password itself.
   - `OWN_URL=http://localhost:3000`, so that the account links in emails point
     at the dev server.
   - The `SMTP_*` and `OWN_EMAIL` variables can stay empty. The server then
     prints every email, including the link to set a new account's password,
     to its log instead of sending it.

   `userdata/` is git-ignored and holds all local state.

4. **Run the server and the client.** `make run-server` starts a Redis instance
   on port 6385 and the server on port 8080, both in the background, then runs
   the CRA dev server (`make run-ts`) in the foreground. Open
   http://localhost:3000. The dev server forwards API calls to port 8080 (the
   `proxy` entry in `src/swai_client/package.json`). The server's log is in
   `userdata/server/swai/`. Stopping the dev server leaves the server and Redis
   running; stop them with `pkill -f 'swai_server --dedicated'` and
   `redis-cli -p 6385 shutdown`.

5. **Create a user.** Log in as the admin, open the profile page and create an
   account with an email address and a display name. The new user gets a link
   to set a password (in the server log if email is not configured).

6. **Run a provider.** Logged in as that user, create a worker token on the
   profile page. Run `make run-provider` once; it copies `provider.env.sample`
   to `userdata/provider/swai/provider.env` and stops. Fill in
   `AIPIARY_WORKER_TOKEN`, `AIPIARY_USER` (the user's email address) and
   `AIPIARY_API_URL` (`http://localhost:8080/` for the local server), then run
   `make run-provider` again. It starts four Redis instances (ports 6381 to
   6384), the scattermind worker and the provider; logs go to
   `userdata/provider/`. `DEVICE=cpu make run-provider` overrides the automatic
   device choice (the value goes to scattermind's `--device`). The worker
   appears in the worker list on the profile page, and chats on
   http://localhost:3000 are answered by it.

The server also runs in Docker locally: `make build-server-dev` builds the
images and writes `docker-compose.server.dev.yml`, and `make compose-server`
starts it on http://localhost:8080 with the same
`userdata/server/swai/server.env`.

## Checks

The Python checks are the Makefile targets that CI runs:

```
make lint-all lint-x-imports PYTHON=python
python -m pytest test
```

`make lint-type-check` (part of `lint-all`) reports the `llama_cpp` module as
missing unless llama-cpp-python is installed in the same environment.

The client checks:

```
make install-ts lint-ts test-ts ts-build ts-unused
```

## Deploying your own swarm

A deployment has two halves: the server images, which you run on a host of your
own, and the provider images, which volunteers pull from a public registry.

1. **Choose the registries.** Copy `system.env.sample` to `system.env` and set
   `PROVIDER_REGISTRY` (public, e.g. your Docker Hub user or `ghcr.io/you`) and
   `SERVER_REGISTRY`, plus `DOCKER_USER` and `DOCKER_TOKEN` unless you are
   already logged in (`docker login`, or `az acr login --name <registry>` on
   Azure). Values in the environment take precedence over the file.

2. **Choose the model.** The worker image runs `deploy/graphs/graph_llama.json`,
   which loads `/models/` plus the file name in its `model_path`. Volunteers'
   `userdata/models/` folder is mounted there, and `run-worker.sh` downloads the
   model into it from `MODEL_URL` (step 4), so the file name at the end of
   `MODEL_URL` has to match `model_path`. Host the GGUF file somewhere
   volunteers can download it from, or leave `MODEL_URL` empty and tell them
   which file to place there.

3. **Build and push.**

   ```
   make deploy-provider   # build-provider + dockerpush-provider
   make deploy-server     # build-server + dockerpush-server, then prints the compose file
   ```

   Provider images are pushed as `<PROVIDER_REGISTRY>/aipiary-<name>` with the
   version tag and `latest`; server images as
   `<SERVER_REGISTRY>/aipiary-server-<name>`. `make build-server` writes
   `docker-compose.server.yml` (git-ignored) with your registry in the image
   names. The image tag comes from `git describe --tags`, so the checkout
   needs the repository's version tags.

4. **Run the server.** On the host, create a directory for the server's data,
   put the server's settings in `<that directory>/swai/server.env` (see
   `server.env.sample`), and start it:

   ```
   WEBAPP_STORAGE_HOME=/srv/aipiary docker compose -f docker-compose.server.yml up -d
   ```

   The server listens on port 8080; put a TLS-terminating reverse proxy in front
   of it. (Azure App Service sets `WEBAPP_STORAGE_HOME` by itself.) Besides the
   admin and email settings, set:

   - `OWN_URL`: the public URL, used in emails, `robots.txt`, `sitemap.xml` and
     the worker script. If it is on a `www.` subdomain, the bare domain
     redirects to it.
   - `PROVIDER_REGISTRY`: the same value as in `system.env`, so that
     volunteers pull your worker images.
   - `MODEL_URL`: where volunteers download the model from (step 2).

   The server fills these into `/robots.txt`, `/sitemap.xml` and
   `/scripts/run-worker.sh` when they are requested (`@@NAME@@` placeholders in
   `src/swai_client/public/`). Volunteers follow the instructions on the profile
   page: on Linux or WSL with Docker, CUDA and the NVIDIA container toolkit,
   they download `run-worker.sh`, which asks for their email address and worker
   token, downloads the compose file and the model, and starts the provider and
   worker containers.

5. **Or let CI build the images.** The `build_pipeline` job in
   `.github/workflows/app.yaml` runs on `v*` tags. Set the repository variables
   `PROVIDER_REGISTRY` and/or `SERVER_REGISTRY` and the secrets `DOCKER_USER`
   and `DOCKER_TOKEN`; each half runs only when its registry is set, and the
   job is skipped when neither is. `make publish` tags the next minor version
   on a clean `main` and pushes the tag.

A fork should also change `src/swai_client/public/docs/contact.md`, which points
to this repository's issues, and the footer of the welcome page
(`src/swai_client/src/general/Welcome.tsx`).

## Project status

Experimental. The deployment this was written for is offline, the community it
served was invite-only, and the test suite is a placeholder: the checks are
linters, type checks and a client build, not tests of the server or the queue.
Expect rough edges, and read the code before relying on it.

## Models

No model weights are included. The graphs reference Meta's Llama models:
`deploy/graphs/graph_llama.json` (the worker image) loads
`Meta-Llama-3.1-8B-Instruct-F16.gguf`, which is under the
[Llama 3.1 Community License](https://www.llama.com/llama3_1/license/) and its
[Acceptable Use Policy](https://www.llama.com/llama3_1/use-policy/), and
`local/graphs/graph_llama.json` loads `Meta-Llama-3-8B-Instruct-IQ3_XS.gguf`,
which is under the [Meta Llama 3 Community License](https://www.llama.com/llama3/license/)
and its [Acceptable Use Policy](https://www.llama.com/llama3/use-policy/).
Anyone who downloads, hosts or runs these models, including operators who set
`MODEL_URL` and volunteers who run a worker, has to accept the license and the
policy of the model they use.

## Assets

The Beatrix Buzz persona images in `logo/` (`beatrix_*.jpeg`) are AI-generated.
`src/swai_client/public/discord-mark-white.png` is Discord's logo, a trademark
of Discord Inc.; the profile page shows it only as a link to the Discord server
set in `DISCORD_URL`.

## License

Apache License 2.0; see [LICENSE](LICENSE). quick_server, redipy and scattermind
are separate projects under the same license.
