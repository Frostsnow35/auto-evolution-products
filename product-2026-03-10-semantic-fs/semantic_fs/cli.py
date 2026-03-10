"""CLI entry point for Semantic FS."""
import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint

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

    total = index_path(path, progress_cb=progress_cb, force=force)
    config = cfg.load_config()
    chunks = store.count(config["db_path"])
    console.print(f"\n[green]✓[/green] Done. Scanned {total} files, {chunks} chunks in index.")


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
