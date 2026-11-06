# Installation

The setup steps from the course, day by day. On a PC, the terminal in VS Code is PowerShell, and the PC commands below are for PowerShell.

## Week 1 Day 1

### Install the tools

1. **VS Code**: download it from https://code.visualstudio.com, install it and open it. Open a terminal from the **Terminal** menu with **New Terminal**.

2. **Git**: check whether you have it with `git --version`. If not:
   - PC: `winget install --id Git.Git -e --source winget`
   - Mac: `git --version` offers to install the Command Line Tools, which include Git. Click **Install**.

3. **Node**: use Node.js 24.15.0. With nvm, run `nvm install` and `nvm use` in the repository; `.nvmrc` selects the version. Otherwise, download version 24.15.0 from the Node.js release archive and install the Windows or macOS package for your computer.

4. **uv**:
   - PC: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
   - Mac: `curl -LsSf https://astral.sh/uv/install.sh | sh`

Quit VS Code and open it again so the terminal finds the new tools. Then check each one:

```
git --version
node --version
npm --version
uv --version
```

On a PC, if `npm --version` says running scripts is disabled on this system, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` and try again.

### Add the VS Code extensions

Open the Extensions view (Ctrl+Shift+X on a PC, Cmd+Shift+X on a Mac) and install **Python** and **Jupyter**, both from Microsoft.

### Clone the repo

In the VS Code terminal:

```
mkdir ~/projects
cd ~/projects
git clone https://github.com/ed-donner/undercover
```

Skip the `mkdir` if you already have a projects folder. Keep it out of folders that OneDrive or iCloud sync.

Then choose **File**, **Open Folder** and pick the `undercover` folder. If VS Code asks whether you trust the authors, choose yes.

### Set up the environment

1. In a terminal in the `undercover` folder, run `uv sync`. It installs Python and the packages in a `.venv` folder.
2. Create a file called `.env` in the `undercover` folder with your OpenRouter key:
   ```
   OPENROUTER_API_KEY=sk-or-v1-...
   ```
   Setup parts 1 to 4 in `setup/setup.ipynb` show how to create the OpenRouter account, the key and the `.env` file.
3. Open `setup/setup.ipynb`, click **Select Kernel**, then **Python Environments**, and choose `.venv`.

## Week 1 Day 2

The lab is `labs/week1day2.ipynb`. It calls paid models, so add a little credit to your OpenRouter account at https://openrouter.ai/settings/credits. The lab costs a few cents.

If you'd rather not spend anything, use `labs/week1day2free.ipynb`, which uses free models throughout.

## Week 1 Day 3

### Install a coding agent

Pick one of Claude Code, Codex or OpenCode. I use Claude Code.

**Claude Code** needs a Claude Pro or Max plan, or an Anthropic Console account. Sign up at https://claude.ai, then install it:

- PC: `irm https://claude.ai/install.ps1 | iex`
- Mac: `curl -fsSL https://claude.ai/install.sh | bash`

Run `claude` in the `undercover` folder and sign in with `/login`.

**Codex** comes with a ChatGPT plan such as Plus. Sign up at https://chatgpt.com, then:

```
npm i -g @openai/codex
codex login
codex
```

`codex login` signs you in with your ChatGPT account.

**OpenCode** is the free route. Sign up for OpenCode Zen at https://opencode.ai/auth, then:

```
npm i -g opencode-ai
opencode
```

In OpenCode, run `/connect`, pick OpenCode Zen and paste your Zen API key. `/models` lists the free models.

On a Mac, if `npm i -g` fails with an EACCES permission error, run it again with `sudo` in front.

### Install the project's Node packages

In a terminal in the `undercover` folder:

```
npm install
```

This installs the dashboard's packages, the git pre-commit hook and Playwright's Chromium browser for the end-to-end tests.

### Add the Playwright MCP server

The Playwright MCP server lets the coding agent open the dashboard in a browser. Add it in the `undercover` folder:

- Claude Code: `claude mcp add playwright -- npx -y @playwright/mcp@latest`, then `claude mcp list` to check it
- Codex: `codex mcp add playwright -- npx -y @playwright/mcp@latest`
- OpenCode: `opencode mcp add`

It uses Google Chrome. If you don't have Chrome, install it from https://www.google.com/chrome.
