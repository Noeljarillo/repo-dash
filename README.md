# repo-dash

A small local dashboard for all the git repos on your machine: see what each one is, what state it's in, and open it in one click.

It's built for people who start a lot of projects, especially with coding agents like **Claude Code** and **Hermes**, and lose track of what lives where. repo-dash finds your repos and shows each one as a card with a description, languages, stack, git status and recent activity.

- **No install.** Two files, Python 3 standard library only, plus `git`.
- **Local only.** The server listens on `127.0.0.1`, and nothing leaves your machine.
- **Read-only.** It never changes your repos. It only reads git status and files.

## Quick start

```bash
git clone https://github.com/Noeljarillo/repo-dash.git
cd repo-dash
python3 dash.py
```

Your browser opens at **http://127.0.0.1:7777**.

> Open the page through the server, not by double-clicking `index.html`. The page gets its data from `dash.py`.

### Choosing what to scan

By default repo-dash looks through your home folder, 3 levels deep. Folders like `node_modules`, `Library` and hidden folders are skipped. To scan specific folders instead:

```bash
python3 dash.py ~/code ~/agents
```

### Settings

| Variable          | Default | What it does                              |
|-------------------|---------|-------------------------------------------|
| `DASH_PORT`       | `7777`  | Port for the local server                 |
| `DASH_DEPTH`      | `3`     | How many folder levels deep to look       |
| `DASH_NO_BROWSER` | unset   | Set to `1` to skip opening the browser    |
| `DASH_WEB`        | unset   | Web address for a git host, e.g. `nas=http://nas:3000` |

```bash
DASH_PORT=8080 DASH_DEPTH=4 python3 dash.py ~/code
```

If repo-dash is already running, starting it again just opens the page.

## What you see

**Top bar.** Search across names, descriptions, stacks and README text. The counts (Repos, With changes, Claude, Hermes) double as filters. **Sort by** orders the cards by last commit, name, uncommitted changes, commits in the last 12 weeks, or number of files.

**Groups.** Repos are grouped by their parent folder: `~/work/api` and `~/work/web` appear under **work**. To reorganize, move repos into folders.

**Cards.** Each repo shows:
- a one-line description taken from the README, `package.json` or `pyproject.toml`, or the top-level files if there's none
- a language bar with percentages
- detected tools and frameworks: Next.js, React, FastAPI, Docker, PyTorch, Ethers, Anthropic and more
- the branch, uncommitted changes (amber), the state of **each remote**, time since the last commit, and a 12-week activity chart
- **✳ Claude** / **☤ Hermes** marks for repos built with those agents

**Detail panel.** Click a card to open a side panel with the formatted README, the file list and git details, plus buttons to open the repo in **Cursor**, **VS Code**, **Terminal**, **Finder** or on any of its remotes, or to copy its path.

### Several remotes (GitHub, Gitea, GitLab…)

A repo often lives in more than one place — a self-hosted Gitea at the office and GitHub as a mirror. repo-dash reads **every** remote, not just `origin`:

- Each remote is named by its host: GitHub, GitLab, Gitea, Codeberg, or the host itself (with its port) for anything else. A remote you named `gitea` is labelled Gitea too. SSH (`git@host:owner/repo`), `git://` and HTTP remotes all become links you can open; passwords in remote URLs are never shown. Hosts on your LAN (`gitea.local`, an IP address) are linked over `http`, and an HTTP remote keeps its port, so `http://gitea.lan:3000/me/x.git` links to `http://gitea.lan:3000/me/x`.
- **SSH remotes don't carry a web port**, so `ssh://git@nas:2222/me/x.git` can only be guessed at. Give it the real address once:

  ```bash
  DASH_WEB="nas=http://nas:3000" python3 dash.py
  ```

  Separate several hosts with commas: `DASH_WEB="nas=http://nas:3000,git.local=https://git.local"`.
- Each remote gets its **own** sync state: *in sync*, *3 to push*, or *branch not pushed* when the current branch doesn't exist there at all. So a repo pushed to Gitea but never mirrored to GitHub shows up immediately.
- A repo with no remote is marked **local only**.
- The counts come from refs already on disk, so scanning never touches the network. Run `git fetch` if you want fresher "to pull" numbers.
- **Not saved** filters to repos with uncommitted work or anything unpushed to any remote.

**Keyboard.** `/` jumps to search, `Enter` opens the first match in Cursor, and `Esc` clears the search or closes the panel.

### How agent marks are detected

- **Claude:** the repo has a `CLAUDE.md` file or `.claude/` folder, or its recent commit history mentions Claude (e.g. `Co-Authored-By: Claude`).
- **Hermes:** the repo has a `.hermes/` folder, or its recent commit history mentions Hermes.

## Platform notes

- **macOS:** everything works. The Terminal button uses iTerm when it's installed.
- **Linux:** works. The open buttons use `xdg-open`, `x-terminal-emulator` and the `cursor` / `code` commands on your PATH.
- **macOS privacy:** repos inside Desktop, Documents or Downloads may not appear unless your terminal has access to those folders (System Settings → Privacy & Security → Files and Folders or Full Disk Access). You can also pass those folders as arguments.

## How it works

`dash.py` walks the folders you give it and runs a few quick `git` commands per repo, in parallel. It serves the results as JSON along with `index.html`. The open buttons send a request back to the server, which only opens paths it found in the scan and only accepts requests from its own page.

```
dash.py      the scanner, JSON API and file opener (Python standard library)
index.html   the whole UI (plain HTML, CSS and JavaScript, no build step)
```

To add a framework to the stack detection, edit the `STACK` list near the top of `dash.py`.

## License

[MIT](LICENSE)
