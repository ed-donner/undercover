# UnderCover dev container

This folder holds a dev container for the UnderCover repo. The container gives you Python 3.12, uv, Node.js 26, and the VS Code Python and Jupyter extensions. The first build runs `uv sync` and `npm install`. The course packages and the dashboard packages are then ready when the container starts.

## Before you start

- Docker Desktop or another Docker runtime
- VS Code with the Dev Containers extension
- An OpenRouter API key

## How to use the container

1. Clone the repo, and open the `community_contributions/artem_koval` folder in VS Code.
2. Run the command **Dev Containers: Reopen in Container**. The first build takes a few minutes.
3. Create a `.env` file in the repo root, and add your key:

   ```
   OPENROUTER_API_KEY=sk-or-v1-...
   ```

   The setup notebook `setup/setup.ipynb` shows how to make the account and the key.
4. Open a lab notebook in `labs/`. Choose the `.venv` kernel.

The container serves the whole repo at `/workspaces/undercover`. The `.env` file is not in git, so it stays when you change branches.

## What the build runs

| Command | Purpose |
|---|---|
| `uv sync` | makes the `.venv` folder with the course packages |
| `npm install` | installs the dashboard packages and the git pre-commit hook |
