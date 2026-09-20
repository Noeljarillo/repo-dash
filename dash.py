#!/usr/bin/env python3
"""repo-dash — a tiny local dashboard for your git repos.

Usage:  python3 dash.py [ROOT ...]      (default root: your home folder)
Env:    DASH_PORT=7777  DASH_DEPTH=3
"""
import json, os, platform, subprocess, sys, time, webbrowser
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOTS = [Path(p).expanduser().resolve() for p in sys.argv[1:]] or [Path.home()]
PORT = int(os.environ.get("DASH_PORT", 7777))
DEPTH = int(os.environ.get("DASH_DEPTH", 3))
SKIP = {"node_modules", "Library", "Applications", "vendor", "venv", ".venv", "dist", "build"}
LANGS = {".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript", ".js": "JavaScript", ".jsx": "JavaScript",
         ".go": "Go", ".rs": "Rust", ".swift": "Swift", ".sol": "Solidity", ".java": "Java", ".kt": "Kotlin",
         ".cs": "C#", ".cpp": "C++", ".c": "C", ".rb": "Ruby", ".php": "PHP", ".dart": "Dart", ".vue": "Vue",
         ".svelte": "Svelte", ".html": "HTML", ".sh": "Shell", ".ipynb": "Notebook"}
# (label, markers) — a marker is a top-level file name or a word found in the manifest
STACK = [("Next.js", ['"next"']), ("React", ['"react"']), ("Vue", ['"vue"']), ("Svelte", ['"svelte"']),
         ("Vite", ['"vite"']), ("Electron", ['"electron"']), ("Tailwind", ['"tailwindcss"']), ("Express", ['"express"']),
         ("Prisma", ["prisma"]), ("FastAPI", ["fastapi"]), ("Flask", ["flask"]), ("Django", ["django"]),
         ("PyTorch", ["torch"]), ("MLX", ["mlx"]), ("Telegram", ["telegram", "telegraf", "grammy"]),
         ("Ethers", ["ethers", "viem", "web3"]), ("Anthropic", ["anthropic"]), ("OpenAI", ['openai']),
         ("Docker", ["Dockerfile", "docker-compose.yml", "compose.yml"]), ("Foundry", ["foundry.toml"]),
         ("Hardhat", ["hardhat.config.js", "hardhat.config.ts"]), ("Xcode", ["Package.swift"])]
MAC = platform.system() == "Darwin"
NAMED_HOSTS = {"github.com": "GitHub", "gitlab.com": "GitLab", "bitbucket.org": "Bitbucket",
               "codeberg.org": "Codeberg", "git.sr.ht": "SourceHut", "dev.azure.com": "Azure DevOps"}


def browse_url(url):
    """Turn any git remote (ssh, git://, https, with or without credentials) into a URL
    you can open in a browser. Works for self-hosted Gitea/GitLab/Forgejo too."""
    url = url.strip()
    if not url or url.startswith(("/", ".", "file:")) or "://" not in url and ":" not in url:
        return ""                                               # local path or bare name
    scheme = "https"
    if url.startswith(("http://", "https://", "git://", "ssh://")):
        scheme, _, rest = url.partition("://")
        if scheme in ("git", "ssh"):
            scheme = "https"
    elif "@" in url and ":" in url:                              # git@host:owner/repo.git
        rest = url.split("@", 1)[1].replace(":", "/", 1)
    else:
        return ""
    rest = rest.split("@")[-1]                                   # drop any user:password@
    host, _, path = rest.partition("/")
    host = host.split(":")[0] if host.count(":") and not host.endswith(":") else host
    if not host or not path:
        return ""
    local = host in ("localhost", "127.0.0.1") or host.endswith(".local") or "." not in host \
        or host.replace(".", "").isdigit()
    if local:
        scheme = "http"                                          # LAN servers rarely have TLS
    return f"{scheme}://{host}/{path.removesuffix('.git').strip('/')}"


def host_label(web_url):
    host = web_url.split("://", 1)[1].split("/")[0]
    if host in NAMED_HOSTS:
        return NAMED_HOSTS[host]
    bare = host.removeprefix("www.")
    if "gitea" in bare or "forgejo" in bare:
        return "Gitea"
    if "gitlab" in bare:
        return "GitLab"
    return bare


def find_repos():
    found = []
    def walk(d, depth):
        try:
            entries = list(os.scandir(d))
        except OSError:
            return
        if any(e.name == ".git" for e in entries):
            found.append(Path(d)); return  # don't descend into repos (skips vendored sub-repos)
        if depth == 0:
            return
        for e in entries:
            if e.is_dir(follow_symlinks=False) and not e.name.startswith(".") and e.name not in SKIP:
                walk(e.path, depth - 1)
    for r in ROOTS:
        walk(r, DEPTH)
    return found


def git(repo, *args):
    try:
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return ""


def sync_state(repo, remote, branch):
    """How far the current branch is from this remote, using refs already fetched
    (never touches the network). 'missing' means the branch isn't on that remote at all."""
    if not branch:
        return {"push": 0, "pull": 0, "missing": False}
    ref = f"{remote}/{branch}"
    if not git(repo, "rev-parse", "--verify", "--quiet", ref).strip():
        ahead = git(repo, "rev-list", "--count", "HEAD").strip()
        return {"push": int(ahead or 0), "pull": 0, "missing": True}
    counts = git(repo, "rev-list", "--left-right", "--count", f"{ref}...HEAD").split()
    pull, push = (int(counts[0]), int(counts[1])) if len(counts) == 2 else (0, 0)
    return {"push": push, "pull": pull, "missing": False}


def info(repo):
    root = next((r for r in ROOTS if repo == r or r in repo.parents), repo.parent)
    rel = repo.relative_to(root)
    status = git(repo, "status", "-sb", "--porcelain").splitlines()
    head = status[0] if status else ""
    last = git(repo, "log", "-1", "--format=%ct%x00%s").split("\x00")
    now = time.time()
    weeks = [0] * 12
    for t in git(repo, "log", "--all", f"--since={12 * 7} days ago", "--format=%ct").split():
        w = int((now - int(t)) // (7 * 86400))
        if w < 12: weeks[11 - w] += 1
    exts = {}
    for f in git(repo, "ls-files").splitlines():
        lang = LANGS.get(os.path.splitext(f)[1].lower())
        if lang: exts[lang] = exts.get(lang, 0) + 1
    log = git(repo, "log", "--all", "-300", "--format=%an %ae %b").lower()
    names = {e.name for e in os.scandir(repo)}
    branch = head[3:].split("...")[0].replace("No commits yet on ", "") if head.startswith("## ") else ""
    remotes = []
    for line in git(repo, "remote", "-v").splitlines():
        if not line.endswith("(fetch)"):
            continue
        name, _, url = line.partition("\t")
        if any(r["name"] == name for r in remotes):
            continue
        web = browse_url(url.rsplit(" ", 1)[0])
        remotes.append({"name": name, "url": web, "host": host_label(web) if web else name,
                        **sync_state(repo, name, branch)})
    remotes.sort(key=lambda r: r["name"] != "origin")   # origin first
    unsynced = [r for r in remotes if r["push"] or r["missing"]]
    readme = next((repo / n for n in ("README.md", "readme.md", "Readme.md", "README") if n in names), None)
    text = readme.read_text(errors="ignore") if readme else ""
    desc = ""
    for line in text.splitlines():
        t = line.strip().lstrip("#>").strip()
        if t and not t.startswith(("!", "[", "<", "```", "|", "---")) and t.lower() != repo.name.lower():
            desc = t[:160]; break
    manifest = ""
    for m in ("package.json", "pyproject.toml", "Cargo.toml", "requirements.txt", "go.mod", "Package.swift", "composer.json"):
        if m in names:
            try: manifest += (repo / m).read_text(errors="ignore")[:20000].lower()
            except OSError: pass
    if not desc and '"description"' in manifest:
        desc = manifest.split('"description"')[1].split('"')[1][:160]
    stack = [label for label, keys in STACK if any(k in names or k in manifest for k in keys)]
    total = sum(exts.values()) or 1
    langs = sorted(exts.items(), key=lambda kv: -kv[1])[:5]
    tree = sorted((e.name + "/" if e.is_dir() else e.name for e in os.scandir(repo) if not e.name.startswith(".")),
                  key=lambda n: (not n.endswith("/"), n.lower()))
    body = [l for l in text.splitlines() if not l.strip().startswith(("<", "![", "[!["))]
    return {
        "name": repo.name,
        "path": str(repo),
        "group": str(rel.parent) if str(rel.parent) != "." else "",
        "branch": branch,
        "ahead": int(head.split("ahead ")[1].split("]")[0].split(",")[0]) if "ahead " in head else 0,
        "behind": int(head.split("behind ")[1].split("]")[0]) if "behind " in head else 0,
        "dirty": len(status) - 1 if status else 0,
        "last": int(last[0]) if last[0].strip() else 0,
        "msg": last[1].strip() if len(last) > 1 else "",
        "weeks": weeks,
        "lang": max(exts, key=exts.get) if exts else "",
        "claude": "claude" in log or "CLAUDE.md" in names or ".claude" in names,
        "hermes": "hermes" in log or ".hermes" in names,
        "remotes": remotes,
        "unsynced": len(unsynced),
        "desc": desc,
        "langs": [[k, round(v * 100 / total)] for k, v in langs],
        "stack": stack[:6],
        "tree": tree[:24],
        "readme": "\n".join(body).strip()[:2500],
    }


def open_with(path, app):
    if app == "finder":
        cmd = ["open", path] if MAC else ["xdg-open", path]
    elif app == "terminal":
        cmd = ["open", "-a", "iTerm" if Path("/Applications/iTerm.app").exists() else "Terminal", path] if MAC \
            else ["x-terminal-emulator", "--working-directory", path]
    elif app in ("cursor", "code"):
        name = {"cursor": "Cursor", "code": "Visual Studio Code"}[app]
        cmd = ["open", "-a", name, path] if MAC else [app, path]
    else:
        return
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class Handler(BaseHTTPRequestHandler):
    known = set()

    def send(self, code, body, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(body if isinstance(body, bytes) else body.encode())

    def do_GET(self):
        if self.path == "/":
            self.send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/repos":
            with ThreadPoolExecutor(16) as ex:
                repos = list(ex.map(info, find_repos()))
            Handler.known = {r["path"] for r in repos}
            self.send(200, json.dumps({"roots": [str(r) for r in ROOTS], "repos": repos}))
        else:
            self.send(404, "{}")

    def do_POST(self):
        if self.headers.get("Origin", "").split("//")[-1] != self.headers.get("Host"):
            return self.send(403, "{}")  # only our own page may trigger "open"
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or "{}")
        if self.path == "/api/open" and body.get("path") in Handler.known:
            open_with(body["path"], body.get("app"))
            return self.send(200, "{}")
        self.send(400, "{}")

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    url = f"http://127.0.0.1:{PORT}"
    print(f"repo-dash → {url}   scanning: {', '.join(map(str, ROOTS))}")
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:
        print(f"Port {PORT} is busy, so repo-dash is probably already running. Opening {url}")
        webbrowser.open(url)
        sys.exit(0)
    if not os.environ.get("DASH_NO_BROWSER"):
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
