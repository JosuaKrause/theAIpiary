# theAIpiary

theAIpiary is a swarm-based "inverse cloud" for running machine learning models.
The only part that runs in the cloud is a small server that hosts the website,
keeps track of users and chats, and hands out tasks. The models themselves run
on volunteers' own GPUs: anyone with an account can start a *worker bee* on their
machine, which then picks up tasks from everyone in the swarm. The swarm serves
one model, a Llama 3.1 chat assistant that calls itself Beatrix Buzz.

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
  The accounts can be kept in Postgres instead (see
  [Keeping the accounts in Postgres](#keeping-the-accounts-in-postgres)).
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
- **Client** (`src/swai_client`). A React TypeScript/Redux app, built with
  Vite, with the chat, login, password reset, FAQ and profile pages. The
  profile page lists workers and creates worker tokens. For users allowed to
  it also creates accounts and manages them: it can send a password reset,
  log a user out everywhere, change their capabilities, or delete them.
- **Shared code** (`src/swai`): the API response types, the authorization header
  format, and the Llama prompt and session handling used by both sides.
- **Postgres** (optional). `src/swai_server/system/user/db.py` is a user
  manager that keeps the accounts, sessions, reset tokens, capabilities and
  worker tokens in Postgres (SQLAlchemy). Chats and the task queue stay in
  Redis either way.

## Prerequisites

- Python 3.12 or newer (`sh/install.sh` refuses older versions)
- Node 22 (22.22.2 or newer) and yarn 1 (classic)
- Redis (`redis-server` on the `PATH`; the local scripts start their own instances)
- A C/C++ compiler and CMake, to build llama-cpp-python (on Linux without a GPU
  also `libopenblas-dev` and `pkg-config`)
- Docker, for building images and for running a worker bee the way volunteers do
- A GPU is optional for development. `make install` builds llama-cpp-python for
  Metal on Apple silicon, for CUDA if PyTorch sees one, and for the CPU (with
  OpenBLAS) otherwise. Volunteer worker images need an NVIDIA GPU with CUDA.

## Local setup

1. **Install the dependencies.**

   ```
   make install PYTHON=python3.12   # or whichever python is 3.12+
   make install-ts
   ```

   `make install` installs PyTorch, `requirements.txt`, `requirements.dev.txt`
   and llama-cpp-python. Because `deploy/devmode.conf` sets `DEVMODE=1`, it then
   replaces quick_server, redipy and scattermind with their GitHub versions (or
   with editable installs of `../quick_server`, `../redipy` and `../scattermind`
   if you have those checkouts next to this one).

2. **Get a model.** Llama weights are not part of this repository (see
   [Models](#models)). Download the Q4_K_M GGUF build of Llama 3.1 8B Instruct
   (4.9 GB) into `models/` at the root of the repository:

   ```
   mkdir -p models
   curl -fL -o models/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf \
     https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF/resolve/main/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf
   ```

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
   the Vite dev server (`make run-ts`) in the foreground. Open
   http://localhost:3000. The dev server forwards API calls (`/api`) to port
   8080 (`server.proxy` in `src/swai_client/vite.config.ts`). The server's log
   is in `userdata/server/swai/`. Stopping the dev server leaves the server and
   Redis running; stop them with `pkill -f 'swai_server --dedicated'` and
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
images for your machine's architecture and writes their names to
`deploy/default.server.dev.env`, and `make compose-server` starts them with
`deploy/docker-compose.server.yml` on http://localhost:8080, with
`userdata/server` as the data directory (and so the same
`userdata/server/swai/server.env`).

## Checks

The Python checks are the Makefile targets that CI runs:

```
make lint-all lint-x-imports PYTHON=python
make pytest PYTHON=python
```

`make lint-type-check` (part of `lint-all`) reports the `llama_cpp` module as
missing unless llama-cpp-python is installed in the same environment.

The user manager tests run against Redis (in memory) and Postgres. The
Postgres half needs a server and `TEST_POSTGRES_URL`; without it those tests
are skipped locally (CI provides a server and fails without one). Each test
works in a schema of its own and drops it afterwards. With Docker:

```
docker run -d --name swai-test-pg -e POSTGRES_PASSWORD=pw -p 5432:5432 postgres:17
TEST_POSTGRES_URL=postgresql+psycopg2://postgres:pw@localhost:5432/postgres \
    make pytest PYTHON=python
docker rm -fv swai-test-pg
```

The client checks:

```
make install-ts lint-ts test-ts ts-build ts-unused
```

## Deploying your own swarm

A deployment has two halves: the server images, which you run on a host of your
own, and the provider images, which volunteers pull from a public registry.

The server is a single stateful instance: Redis, the chat blobs on disk and the
task cleaner thread inside the server process belong together, so it does not
scale horizontally. The supported way to run it is Docker Compose on one host
with `deploy/docker-compose.server.yml`; [Kubernetes](#kubernetes) has a short
example for people who already run a cluster.

1. **Choose the registries.** Copy `system.env.sample` to `system.env` and set
   `PROVIDER_REGISTRY` (public, e.g. your Docker Hub user or `ghcr.io/you`) and
   `SERVER_REGISTRY` (can be private), plus `DOCKER_USER` and `DOCKER_TOKEN`
   unless you are already logged in with `docker login`. Values in the
   environment take precedence over the file.

2. **Choose the model.** The worker image runs `deploy/graphs/graph_llama.json`,
   which loads `/models/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf` with a context
   of 16384 tokens (`model_path` and `n_ctx`). Volunteers' `userdata/models/`
   folder is mounted at `/models/`, and `run-worker.sh` downloads the model into
   it from `MODEL_URL` (step 5), so the file name at the end of `MODEL_URL` has
   to match `model_path`. `server.env.sample` sets `MODEL_URL` to the default
   model on Hugging Face,
   `https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF/resolve/main/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf`;
   keep it, host the file yourself, or leave `MODEL_URL` empty and tell
   volunteers which file to place there. To serve a different model, change
   `model_path` (and `n_ctx`) before building the image.

3. **Build and push.**

   ```
   make deploy-provider   # build-provider + dockerpush-provider
   make deploy-server     # build-server + dockerpush-server + show-server-env
   ```

   Provider images are pushed as `<PROVIDER_REGISTRY>/aipiary-<name>` with the
   version tag and `latest`; server images as
   `<SERVER_REGISTRY>/aipiary-server-api` and
   `<SERVER_REGISTRY>/aipiary-server-rserver` with their own tags. The images
   are built for `linux/amd64`. The api's tag comes from `git describe --tags`,
   so the checkout needs the repository's version tags; the rserver tag is
   `REDIS_DOCKER_VERSION` in `deploy/redis.version` (with `-devmode` while
   `deploy/devmode.conf` sets `DEVMODE`). `make build-server` writes
   `SERVER_REGISTRY` and both tags to `deploy/default.server.env`
   (git-ignored), and `make show-server-env` prints them: these are the lines
   the host's `.env` needs in step 4.

   To skip the registry, run `make build-server` with an empty
   `SERVER_REGISTRY` on the host itself (it needs this checkout, Docker with
   buildx, Python and Node 22 with yarn) and leave `SERVER_REGISTRY` empty in
   the host's `.env` too; the compose file then uses the local image names.

4. **Prepare the host.** Any Linux host with Docker Engine and the compose
   plugin will do; the server needs no GPU. Make a directory for the
   deployment, copy two files from `deploy/` into it, and create the data
   directory:

   ```
   /srv/aipiary/
   ├── docker-compose.yml   # deploy/docker-compose.server.yml
   ├── Caddyfile            # deploy/Caddyfile (only for the TLS profile)
   ├── .env                 # from deploy/server.compose.env.sample
   └── data/                # AIPIARY_DATA
       ├── swai/server.env  # the server's settings (step 5)
       ├── session/         # chat blobs and session cache
       ├── rserver/         # Redis snapshot (users, chats, task queue)
       └── caddy/           # certificates (only with the TLS profile)
   ```

   In `.env`, set `AIPIARY_DATA` to the data directory and paste the lines
   from `make show-server-env` (`SERVER_REGISTRY`, `AIPIARY_VERSION`,
   `AIPIARY_REDIS_VERSION`). Docker Compose reads `.env` from the directory of
   the compose file. If `SERVER_REGISTRY` is private, run `docker login` for
   it on the host. Only `swai/server.env` has to exist before the first
   start; Docker creates the other directories.

5. **Configure the server.** Copy `server.env.sample` to
   `data/swai/server.env`; the server reads it from `/swai/server.env` in the
   container. Every variable is explained in the sample. Besides the admin
   account (`make create-admin-pw` prints the two lines) and the email
   settings, set:

   - `OWN_URL`: the public URL, e.g. `https://chat.example.com`, used in
     emails, `robots.txt`, `sitemap.xml` and the worker script. If it is on a
     `www.` subdomain, the bare domain redirects to it.
   - `PROVIDER_REGISTRY`: the same value as in `system.env`, so that
     volunteers pull your worker images.
   - `MODEL_URL`: where volunteers download the model from (step 2).

   The server fills these into `/robots.txt`, `/sitemap.xml` and
   `/scripts/run-worker.sh` when they are requested (`@@NAME@@` placeholders in
   `src/swai_client/public/`). The file is read at startup, so restart the
   api (`docker compose restart api`) after changing it.

6. **Start it.** In the deployment directory:

   ```
   docker compose up -d
   docker compose ps                         # wait for api to be healthy
   curl http://localhost:8080/api/version    # "error": null
   docker compose logs -f api
   ```

   The api listens on port 8080 of the host; Redis is only reachable from the
   api. Both restart unless you stop them. The api's health check fails when
   the server could not start (for example because of a broken setting) and
   fell back to a minimal server that only reports the error; the reason is in
   the `error` field of `/api/version` and in the log.
   Log in at `/login/` as the admin and create the first users from the
   profile page.

7. **Put TLS in front of it.** Either start the bundled Caddy reverse proxy
   or use your own:

   - **Caddy.** Point the domain's DNS at the host, open ports 80 and 443, and
     add `COMPOSE_PROFILES=tls` and `AIPIARY_DOMAIN=chat.example.com` to
     `.env` (for a `www.` `OWN_URL`, `AIPIARY_DOMAIN=www.example.com,
     example.com`). `docker compose up -d` then also starts Caddy, which gets
     and renews a Let's Encrypt certificate by itself and keeps it in
     `data/caddy/`.
   - **Your own proxy.** Forward to `http://<host>:8080`, allow request bodies
     of 120 MiB (the server's upload limit) and a read timeout above 60
     seconds (workers long-poll `/api/task/bid` for a minute).

   Either way port 8080 stays published, so block it from the internet in
   your provider's firewall. Ports that Docker publishes bypass host firewalls
   such as ufw.

8. **Upgrade and back up.** To upgrade, build and push the new version, set
   `AIPIARY_VERSION` (and `AIPIARY_REDIS_VERSION` if `make show-server-env`
   prints a new one) in `.env`, and run `docker compose pull` and
   `docker compose up -d`. All state is in the data directory, so a backup is
   a copy of it taken while the stack is stopped:

   ```
   docker compose stop
   tar -czf aipiary-$(date +%F).tar.gz -C /srv/aipiary data
   docker compose start
   ```

   Restore by unpacking the archive in place of `data/` before
   `docker compose up -d`. Redis writes its snapshot
   (`data/rserver/dump.rdb`) when it is stopped and on its own in between: an
   hour after a change at the latest, every few minutes when it is busy.

9. **Volunteers run the workers.** They follow the instructions on the
   profile page: on Linux or WSL with Docker, CUDA and the NVIDIA container
   toolkit, they download `run-worker.sh` from your server, which asks for
   their email address and worker token, downloads the compose file and the
   model, and starts the provider and worker containers. To add a GPU of your
   own to the swarm, do the same on that machine with an account of your own.

10. **Or let CI build the images.** The `build_pipeline` job in
    `.github/workflows/app.yaml` runs on `v*` tags. Set the repository
    variables `PROVIDER_REGISTRY` and/or `SERVER_REGISTRY` and the secrets
    `DOCKER_USER` and `DOCKER_TOKEN`; each half runs only when its registry is
    set, and the job is skipped when neither is. `make publish` tags the next
    minor version on a clean `main` and pushes the tag. The image tags are the
    git tag and `REDIS_DOCKER_VERSION` as above.

### Kubernetes

`deploy/k8s/` is a kustomize example for running the server in a cluster you
already have: a namespace, the rserver Redis and the api as Deployments with
persistent volumes, a Secret generated from `server.env`, Services and an
Ingress (with optional cert-manager TLS). Copy `server.env.sample` to
`deploy/k8s/server.env`, set the image names and tags in
`deploy/k8s/kustomization.yaml` and the host in `deploy/k8s/ingress.yaml`,
then run `kubectl apply -k deploy/k8s`.

The api has to stay at `replicas: 1` with the `Recreate` strategy: the chat
blobs live on its volume and the task cleaner runs inside the process, so a
second pod would not see the first one's blobs and would run a second cleaner.
Kubernetes buys you scheduling and restarts here, not scaling.

### Keeping the accounts in Postgres

By default the accounts live in Redis next to everything else. To keep them
in Postgres instead, add to `server.env`:

```
USER_STORE=postgres
PGHOST=postgres.example.com
PGPORT=5432
PGUSER=aipiary
PGPASSWORD=...
PGDATABASE=aipiary
```

(`USER_STORE` overrides the `user_mng` entry of the config file, which is
built into the image; outside of Docker you can also set
`"user_mng": {"name": "postgres"}` there, optionally with a `"schema"`.) The
server creates its tables in the `public` schema when it starts if they do
not exist yet (`users`, `user_capabilities`, `user_reset_tokens`,
`user_sessions`, `user_worker_tokens`); there is no separate migration step.
The database user needs to be allowed to create tables for the first start.
Existing accounts are not copied over from Redis: switching stores starts with
no users besides the admin.

With Compose, the `postgres` profile starts a Postgres container next to the
api (data in `data/postgres/`). Add `COMPOSE_PROFILES=postgres` (or
`tls,postgres`) and `AIPIARY_PG_PASSWORD=...` to `.env`, and to `server.env`:

```
USER_STORE=postgres
PGHOST=postgres
PGUSER=aipiary
PGPASSWORD=<the same as AIPIARY_PG_PASSWORD>
PGDATABASE=aipiary
```

Back it up with the rest of the data directory (stop the stack first, as in
step 8). On Kubernetes, put the same `PG*` lines and `USER_STORE=postgres`
into `deploy/k8s/server.env` and point `PGHOST` at a Postgres you run in or
next to the cluster.

A fork should also change `src/swai_client/public/docs/contact.md`, which points
to this repository's issues, and the footer of the welcome page
(`src/swai_client/src/general/Welcome.tsx`).

## Project status

Experimental. The deployment this was written for is offline and the community
it served was invite-only. The pytest suite covers the auction queue, user
management (on Redis and Postgres), permission checks and the user endpoints
without needing Redis; the chat endpoints, the provider and the scattermind
graphs are not tested. Known bugs
are recorded as `xfail` tests and as GitHub issues. Expect rough edges, and read
the code before relying on it.

## Models

No model weights are included. Both graphs, `deploy/graphs/graph_llama.json`
(the worker image) and `local/graphs/graph_llama.json`, load
`Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf`, a 4-bit GGUF quantization of Meta's
Llama 3.1 8B Instruct, with a context of 16384 tokens. The file is 4.9 GB and
the context needs about 2 GB of GPU memory on top. The download URL above is
[bartowski/Meta-Llama-3.1-8B-Instruct-GGUF](https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF)
on Hugging Face, a community conversion that needs no Hugging Face login. The
model is under the
[Llama 3.1 Community License](https://www.llama.com/llama3_1/license/) and its
[Acceptable Use Policy](https://www.llama.com/llama3_1/use-policy/), no matter
where it is downloaded from. Anyone who downloads, hosts or runs it, including
operators who set `MODEL_URL` and volunteers who run a worker, has to accept
the license and the policy.

## Assets

The Beatrix Buzz persona images in `logo/` (`beatrix_*.jpeg`) are AI-generated.
`src/swai_client/public/discord-mark-white.png` is Discord's logo, a trademark
of Discord Inc.; the profile page shows it only as a link to the Discord server
set in `DISCORD_URL`.

## License

Apache License 2.0; see [LICENSE](LICENSE). quick_server, redipy and scattermind
are separate projects under the same license.
