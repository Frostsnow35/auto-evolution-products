"""CLI entry point for Semantic FS."""
import importlib.util
import os
import socket
import urllib.parse
import urllib.request

import click
from rich.console import Console
from rich.table import Table

from . import config as cfg
from . import store

console = Console()


@click.group()
def main():
    """🐦 Semantic FS — Find files by meaning, not path."""
    pass


@main.command()
def init():
    """Initialize Semantic FS with default config."""
    config = cfg.load_config()
    cfg.save_config(config)
    db_path = config["db_path"]
    import os
    os.makedirs(os.path.expanduser(db_path), exist_ok=True)
    console.print("[green]✓[/green] Semantic FS initialized!")
    console.print(f"  Config: ~/.semantic-fs/config.json")
    console.print(f"  DB:     {db_path}")
    console.print(f"\nMode: [bold]{config['mode']}[/bold]", end="")
    if config["mode"] == "local":
        console.print(f" (Ollama @ {config['ollama_url']})")
    else:
        console.print()
    console.print("\nRun [bold]sfs index ~[/bold] to start indexing your home directory.")


@main.command()
@click.argument("path", default="~/")
@click.option("--force", is_flag=True, help="Re-index already indexed files")
def index(path, force):
    """Index files under PATH for semantic search."""
    from .indexer import index_path

    console.print(f"[bold]Indexing[/bold] {path} ...")

    indexed_count = [0]

    def progress_cb(fp, current, total):
        if current % 50 == 0 or current == total:
            console.print(f"  [{current}/{total}] {fp[:60]}...")
        indexed_count[0] = current

    try:
        total = index_path(path, progress_cb=progress_cb, force=force)
    except (FileNotFoundError, NotADirectoryError) as e:
        console.print(f"[red]Indexing failed:[/red] {e}")
        return
    config = cfg.load_config()
    chunks = store.count(config["db_path"])
    console.print(f"\n[green]✓[/green] Done. Scanned {total} files, {chunks} chunks in index.")


@main.command()
@click.argument("path", default="~/")
@click.option("--recursive/--no-recursive", default=True, help="Watch subdirectories too")
@click.option("--settle-seconds", default=1.0, show_default=True, help="Debounce window for repeated file events")
def watch(path, recursive, settle_seconds):
    """Watch PATH and incrementally re-index changed files."""
    from .indexer import watch_path

    console.print(f"[bold]Watching[/bold] {path} for file changes...")
    try:
        observer = watch_path(path, recursive=recursive, settle_seconds=settle_seconds)
    except (FileNotFoundError, NotADirectoryError) as e:
        console.print(f"[red]Watch failed:[/red] {e}")
        return
    console.print("[green]✓[/green] Watcher started. Press Ctrl+C to stop.")
    try:
        observer.join()
    except KeyboardInterrupt:
        observer.stop()
        observer.join()
        console.print("[yellow]Watcher stopped.[/yellow]")


@main.command()
@click.argument("query")
@click.option("--top", default=10, help="Number of results")
def search(query, top):
    """Search for files matching QUERY semantically."""
    from .embedder import get_embedder
    from . import store as st

    config = cfg.load_config()
    embedder = get_embedder(config)

    with console.status("Embedding query..."):
        try:
            q_emb = embedder.embed([query])[0]
        except Exception as e:
            console.print(f"[red]Embedding failed:[/red] {e}")
            return

    results = st.search(config["db_path"], q_emb, top_k=top)

    if not results:
        console.print("[yellow]No results found.[/yellow] Have you run [bold]sfs index ~[/bold]?")
        return

    # Deduplicate by file, keep best score
    seen = {}
    for r in results:
        fp = r["file_path"]
        if fp not in seen or r["score"] > seen[fp]["score"]:
            seen[fp] = r

    table = Table(title=f'Results for: "{query}"')
    table.add_column("Score", style="cyan", width=7)
    table.add_column("File", style="bold")
    table.add_column("Preview", style="dim")

    for r in sorted(seen.values(), key=lambda x: -x["score"])[:top]:
        preview = r["chunk"][:80].replace("\n", " ") + "..."
        table.add_row(str(r["score"]), r["file_path"], preview)

    console.print(table)


@main.command()
@click.argument("question")
@click.option("--top", default=5, help="Number of context chunks")
def ask(question, top):
    """Ask a question answered from your indexed files."""
    from .qa import ask as qa_ask

    with console.status("Thinking..."):
        try:
            answer, sources = qa_ask(question, top_k=top)
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            return

    console.print(f"\n[bold green]Answer:[/bold green]\n{answer}\n")

    if sources:
        console.print("[dim]Sources:[/dim]")
        seen = set()
        for s in sources:
            fp = s["file_path"]
            if fp not in seen:
                seen.add(fp)
                console.print(f"  [dim]• {fp} (score: {s['score']})[/dim]")


@main.command("project-view")
@click.argument("query")
@click.option("--top", default=8, help="Number of candidate files to analyze")
def project_view(query, top):
    """Show a lightweight project-oriented semantic view for QUERY."""
    from .project_view import build_project_view

    with console.status("Building project view..."):
        try:
            view = build_project_view(query, top_k=top)
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            return

    console.print(f"\n[bold green]Project View:[/bold green] {view['query']}")
    console.print(f"\n[bold]Overview[/bold]\n{view['summary']}")

    if view["keywords"]:
        console.print(f"\n[bold]Themes[/bold]\n- " + "\n- ".join(view["keywords"][:8]))

    if view["key_files"]:
        table = Table(title="Key Files")
        table.add_column("Score", style="cyan", width=7)
        table.add_column("File", style="bold")
        table.add_column("Preview", style="dim")
        for item in view["key_files"]:
            table.add_row(str(item["score"]), item["file_path"], item["preview"] + "...")
        console.print(table)

    if view["recent_changes"]:
        console.print("\n[bold]Recent Changes[/bold]")
        for item in view["recent_changes"]:
            console.print(f"- {item['updated_at']} | {item['file_path']} (score: {item['score']})")

    if view["risks"]:
        console.print("\n[bold]Risks / Gaps[/bold]")
        for risk in view["risks"]:
            console.print(f"- {risk}")


@main.command()
def status():
    """Show index status."""
    config = cfg.load_config()
    db_path = config["db_path"]
    chunks = store.count(db_path)
    files = store.get_indexed_files(db_path)

    console.print(f"[bold]Semantic FS Status[/bold]")
    console.print(f"  Mode:      {config['mode']}")
    console.print(f"  DB path:   {db_path}")
    console.print(f"  Files:     {len(files)}")
    console.print(f"  Chunks:    {chunks}")
    if config["mode"] == "local":
        console.print(f"  Embed model: {config['ollama_model']}")
        console.print(f"  LLM:         {config['ollama_llm']}")
    else:
        console.print(f"  Embed model: {config['api_embed_model']}")
        console.print(f"  LLM:         {config['api_llm_model']}")


def _diagnose_ollama(url: str) -> tuple[bool, str, list[str]]:
    tips: list[str] = []
    if importlib.util.find_spec("chromadb") is None:
        tips.append("当前 Python 环境缺少 chromadb；本地索引功能会受影响")

    if not os.environ.get("PATH"):
        os.environ["PATH"] = "/usr/local/bin:/usr/bin:/bin"

    ollama_in_path = bool(os.popen("command -v ollama 2>/dev/null").read().strip())
    if not ollama_in_path:
        tips = [
            "本机尚未安装 Ollama，所以现在不能直接启动本地模型服务",
            "Ubuntu 可先安装：sudo snap install ollama",
            f"安装完成后运行：ollama serve",
            f"然后用：sfs config set ollama_url {url}（如果不是默认地址再修改）",
        ]
        return False, "ollama command not found", tips

    try:
        with urllib.request.urlopen(f"{url.rstrip('/')}/api/tags", timeout=3) as resp:
            ok = resp.status == 200
        detail = f"{url} responded successfully"
        return ok, detail, tips
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", e)
        if isinstance(reason, ConnectionRefusedError):
            tips = [
                "Ollama 已安装，但服务似乎没有启动；可先运行：ollama serve",
                f"如果 Ollama 不在默认地址，请执行：sfs config set ollama_url {url}",
                "若已启动仍失败，检查端口 11434 是否被占用或被防火墙拦截",
            ]
            return False, f"{url} connection refused", tips
        if isinstance(reason, socket.timeout):
            tips = [
                f"{url} 响应超时；检查服务是否卡住或地址是否可达",
                "若服务在远程主机，确认网络和防火墙允许访问",
            ]
            return False, f"{url} timed out", tips
        tips = [
            "检查 ollama_url 配置是否正确",
            "确认 /api/tags 接口可访问",
        ]
        return False, f"{url} ({reason})", tips
    except Exception as e:
        tips = [
            "检查 Ollama 服务状态",
            "检查本地网络与 URL 配置",
        ]
        return False, f"{url} ({e})", tips


@main.command()
def doctor():
    """Run a local health check for Semantic FS."""
    config = cfg.load_config()
    config_path = cfg.CONFIG_PATH
    db_path = os.path.expanduser(config["db_path"])

    rows = []
    suggestions: list[str] = []

    def add(check: str, ok: bool, detail: str):
        rows.append((check, "OK" if ok else "WARN", detail))

    add("config file", config_path.exists(), str(config_path))
    add("db directory", os.path.isdir(db_path), db_path)
    add("chromadb installed", importlib.util.find_spec("chromadb") is not None, "required for local index storage")
    add("watchdog installed", importlib.util.find_spec("watchdog") is not None, "required for sfs watch")

    mode = config.get("mode", "local")
    add("mode", mode in {"local", "api"}, f"current mode: {mode}")

    if mode == "local":
        ollama_url = config.get("ollama_url", "http://localhost:11434").rstrip("/")
        ok, detail, tips = _diagnose_ollama(ollama_url)
        add("ollama reachable", ok, detail)
        suggestions.extend(tips)
        add("embed model set", bool(config.get("ollama_model")), config.get("ollama_model", ""))
        add("llm model set", bool(config.get("ollama_llm")), config.get("ollama_llm", ""))
    else:
        add("api key configured", bool(config.get("api_key")), "set via sfs config set api_key ...")
        add("api base configured", bool(config.get("api_base")), config.get("api_base", ""))
        add("embed model set", bool(config.get("api_embed_model")), config.get("api_embed_model", ""))
        add("llm model set", bool(config.get("api_llm_model")), config.get("api_llm_model", ""))

    table = Table(title="Semantic FS Doctor")
    table.add_column("Check", style="bold")
    table.add_column("Status", width=8)
    table.add_column("Detail")
    for check, status_text, detail in rows:
        style = "green" if status_text == "OK" else "yellow"
        table.add_row(check, f"[{style}]{status_text}[/{style}]", detail)

    ok_count = sum(1 for _, status_text, _ in rows if status_text == "OK")
    warn_count = len(rows) - ok_count
    console.print(table)
    console.print(f"\n[bold]Summary:[/bold] {ok_count} OK, {warn_count} warnings")
    if warn_count:
        console.print("[yellow]Suggestion:[/yellow] fix warnings before large indexing runs.")
        if suggestions:
            console.print("[yellow]Next steps:[/yellow]")
            for tip in dict.fromkeys(suggestions):
                console.print(f"  • {tip}")
    else:
        console.print("[green]Semantic FS looks ready.[/green]")


@main.group()
def config():
    """Manage configuration."""
    pass


@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key, value):
    """Set a config value."""
    cfg.set_value(key, value)
    console.print(f"[green]✓[/green] {key} = {value}")


@config.command("show")
def config_show():
    """Show current config."""
    import json
    c = cfg.load_config()
    # Hide api key
    if c.get("api_key"):
        c["api_key"] = "***"
    console.print_json(json.dumps(c, indent=2))


if __name__ == "__main__":
    main()
