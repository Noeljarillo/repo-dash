# repo-dash

A small local dashboard for the git repos you build with Claude and Hermes. It's two files and needs only Python 3 and git.

```bash
python3 dash.py              # scans your home folder (3 levels deep)
python3 dash.py ~/code ~/ai  # or pick the folders to scan
```

It opens http://127.0.0.1:7777.

- **Groups** come from folders. Repos in `~/work/*` show up under "work". Move a repo into a folder to regroup it.
- **Claude / Hermes badges** appear when the repo has `CLAUDE.md` or `.claude/`, or its commit history mentions claude/hermes (e.g. `Co-Authored-By: Claude`).
- **Cards** show a description (from the README, or from `package.json` / `pyproject.toml`; if there's none, the top-level files), a language bar, tool tags (Next.js, FastAPI, Docker…), branch, changed files, ↑ahead/↓behind, last commit and 12 weeks of commits. **README / Files** opens a preview inside the card. The other buttons open the repo in Cursor, VS Code, Terminal, Finder or GitHub.
- **Keys:** `/` to search, `Enter` opens the first match in Cursor, `Esc` clears.

Settings: `DASH_PORT=7777`, `DASH_DEPTH=3`, `DASH_NO_BROWSER=1`.
