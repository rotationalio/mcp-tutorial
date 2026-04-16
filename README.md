# Real World MCP Tutorial: Augmenting Model Context from Existing Data Sources

Hands-on **learning and demo** material: you run a small Olympic data stack in Docker, expose it through **[Google MCP Toolbox for Databases](https://mcp-toolbox.dev/documentation/introduction/)**, then drive the same tools from a **Python agent** (OpenRouter) and a **notebook**—so you can see the same ideas in the UI, in logs, and in code.

---

## Follow this order

### 1. Start Docker

From the repo root:

```bash
docker compose up --build
```

That brings up **PostgreSQL** and **MongoDB**, runs a **one-shot seed** (downloads public CSV slices from Hugging Face, loads both databases, then exits), and starts **Toolbox** on **`http://127.0.0.1:5050`** (host **5050** → container **5000**). Copy [`.env.example`](.env.example) to `.env` if you want local overrides.

**Detached (no log stream on your terminal):** use **`docker compose up --build -d`**. Containers keep running in the background; follow logs only when you want, e.g. **`docker compose logs -f toolbox`** or **`docker compose logs -f`** for all services. **`docker compose ps`** shows status.

- **Postgres:** `localhost:5432` — default user / password / database: `olympics`.
- **MongoDB:** `localhost:27017` — database `olympics`.
- **Toolbox:** set **`TOOLBOX_BASE_URL=http://127.0.0.1:5050`** for Python (adjust if you change the published port in [`docker-compose.yml`](docker-compose.yml)).

Re-seeding is skipped if data already exists. **Clean slate:** `docker compose down -v` then `docker compose up --build` again.

### 2. Optional: check the databases

With the stack up and seeded:

```bash
bash scripts/tests/test_databases.sh
```

For a full reset plus sample queries: `bash scripts/tests/verify_stack.sh`.

### 3. Python environment

Python **3.12+** recommended. From the **repo root**, create a virtual environment, **activate it** (so the next steps use this interpreter), and install the project in **editable** mode so ``import mcp_tutorial`` works like any other package (no ``PYTHONPATH``):

```bash
python3.12 -m venv .venv
# macOS / Linux:
source .venv/bin/activate
# Windows cmd:        .venv\Scripts\activate.bat
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -U pip
pip install -e .
```

That reads dependencies from [`pyproject.toml`](pyproject.toml) and registers the ``mcp_tutorial`` package in editable mode.

For Jupyter later, register a kernel from this same venv, e.g.
`python -m ipykernel install --user --name=mcp-tutorial --display-name="MCP tutorial"`.

**Leave the venv activated** (same shell, or point your IDE terminal at it) for steps **4** and **5**.

### 4. Run the agent demo (terminal)

With the venv from step **3** still active, set **`OPENROUTER_API_KEY`** (see [`.env.example`](.env.example)) if you have not already, then:

```bash
python scripts/run_agent_demo.py
```

This runs two **cross-database** questions against OpenRouter with Toolbox’s **`combined`** toolset. Watch **INFO** lines for when each chat request and each tool starts and finishes—handy if something feels slow.

### 5. Same story in the notebook

Open [`notebooks/simple_tool_calls.ipynb`](notebooks/simple_tool_calls.ipynb) with the **same venv as the Jupyter kernel**, ``.env`` loaded, and Toolbox still running. Step through the two prompts at your own pace.

---

## What you are looking at

| Piece | Role |
| -------- | ------ |
| [`pyproject.toml`](pyproject.toml) | Declares the installable ``mcp_tutorial`` package (under ``src/mcp_tutorial/``) and its dependencies. |
| [`docker-compose.yml`](docker-compose.yml) | Postgres, Mongo, seed, Toolbox (inline comments describe each service). |
| [`toolbox/config/tools/`](toolbox/config/tools/) | Merged YAML: sources, SQL/Mongo tools, toolsets (`combined`, `postgres_only`, `mongo_only`), prompts. Numbered filenames set merge order. |
| [`src/mcp_tutorial/`](src/mcp_tutorial/) | Tutorial package **`mcp_tutorial`**: **`run_chat_with_tools`**, **`Settings`**. Installed with ``pip install -e .`` in step **3**. |
| [`scripts/run_agent_demo.py`](scripts/run_agent_demo.py) | Terminal walkthrough of two prompts. |
| [`scripts/seed_databases.py`](scripts/seed_databases.py) | Logic the **seed** container uses to fill the DBs. |
| [`db/postgres/`](db/postgres/), [`db/mongo/`](db/mongo/) | Schema and init helpers for the containers. |

**Data (high level):** Postgres holds core Olympic tables (countries, games, athletes, events); Mongo holds biography-style text and wide event rows—both fed from the public dataset [`SVeldman/126-years-olympic-results`](https://huggingface.co/datasets/SVeldman/126-years-olympic-results) during seed.

**Toolbox in the browser:** **`http://127.0.0.1:5050/ui`** — try tools and parameters by hand. **MCP (Streamable HTTP):** **`http://127.0.0.1:5050/mcp`** — e.g. [MCP Inspector quickstart](https://mcp-toolbox.dev/documentation/getting-started/mcp_quickstart/) (`npx @modelcontextprotocol/inspector`). Python uses the **base URL only** (no `/mcp` suffix).

**Cross-database prompts the repo is built around:** relational slice (medals, NOC, year, optional sport fragment) then Mongo biographies by `athlete_id`; or Mongo text search on biographies then Postgres checks for the same athlete.

**Other OpenAI-compatible APIs:** set `OPENROUTER_BASE_URL` and `OPENROUTER_MODEL` instead of OpenRouter defaults (see `.env.example`).

After edits to [`scripts/seed_databases.py`](scripts/seed_databases.py), rebuild the seed image when re-running seed: `docker compose run --build --rm seed`.
