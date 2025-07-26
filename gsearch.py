#!/usr/bin/env python

import argparse
import sys
import os
import json
import subprocess
from pathlib import Path
from typing import Optional
from jsoncolor import jprint
from progress_session import ProgressSession
import requests
from rich.console import Console
# from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text
from dotenv import load_dotenv
from rich import traceback as rich_traceback
from licface import CustomRichHelpFormatter 

rich_traceback.install(show_locals=False, theme='fruity', width=os.get_terminal_size()[0])

CONFIG_FILE = Path(os.path.join(os.path.dirname(os.path.realpath(__file__)), "config.json"))
ENV_FILE = Path(".env")
os.environ.update({'SHOW_URL':'1'})

class GoogleSearcher:
    def __init__(self, api_key: str, cse_id: str, browser_path: Optional[str] = None, save_dir: Optional[str] = None):
        self.api_key = api_key
        self.cse_id = cse_id
        self.browser_path = browser_path
        self.console = Console()
        self.base_url = "https://www.googleapis.com/customsearch/v1"
        self.cached_pages = {}
        self.total_pages = 1
        self.total_results = 0
        self.save_dir = Path(save_dir) if save_dir else None
        if self.save_dir:
            self.save_dir.mkdir(parents=True, exist_ok=True)
        self.last_data = None

    def search(self, query: str, page: int = 1, per_page: int = 10):
        if page in self.cached_pages:
            return self.cached_pages[page]

        start = (page - 1) * per_page + 1

        # with Progress(
        #     SpinnerColumn(),
        #     TextColumn("[progress.description]{task.description}"),
        #     transient=True,
        # ) as progress:
        with ProgressSession() as session:
            # progress.add_task(f"Fetching page {page}...", total=None)

            params = {
                "key": self.api_key,
                "cx": self.cse_id,
                "q": query,
                "start": start,
                "num": per_page,
            }

            response = session.get(self.base_url, params=params, text=f"Fetching page {page}...")
            data = response.json()

            if "items" not in data:
                self.console.print("[bold red]❌ No any result found or API error.[/bold red]")
                data = self.last_data
                # jprint(data)
                # return []

            if page == 1:
                self.total_results = int(data["searchInformation"]["totalResults"])
                self.total_pages = min((self.total_results + per_page - 1) // per_page, 10)
                self.console.print(f"\n[bold cyan]🔎 Total Result:[/bold cyan] [red on yellow]{self.total_results:,}[/]")
                self.console.print(f"[bold #FFFF00]📄 Total Page:[/] [blue on #AAFF00]{self.total_pages}[/]\n")

            items = data.get("items", [])
            self.cached_pages[page] = items

            if self.save_dir:
                self.save_to_file(query, page, items)
            self.last_data = data
            # jprint(items)
            return items

    def print_results(self, items, page):
        if not items:
            self.console.print("[white on red blink]No any result found !.[/]")
            return

        self.console.rule(f"[black on white][blue on white]Page[/] [red on white]{page}[/] / [#55007F on white]{self.total_pages}[/][/]")

        table = Table(show_header=True, header_style="bold magenta", width=os.get_terminal_size()[0])
        table.add_column("#", style="dim", width=3)
        table.add_column("Title", style="#00FFFF")
        table.add_column("Link", style="#00FF00", overflow="fold")

        for i, item in enumerate(items, start=1):
            # jprint(item)
            title = f"🔗 {item['title']}"
            table.add_row(str(i).zfill(2), title, item['link'])

        self.console.print(table)
        self.console.print(f"[bold #AAAAFF]Page[/] [white on red]{page}[/] [#FFFF00]/[/] [white on blue]{self.total_pages}[/]")

    def open_in_browser(self, url: str):
        if not self.browser_path:
            self.console.print("[red]❌ Path to browser if exists (--browser or .env)[/red]")
            return
        try:
            subprocess.Popen([self.browser_path, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.console.print(f"[green]🌐 Opening:[/green] {url}")
        except Exception as e:
            self.console.print(f"[red]Failed open Browser:[/red] {e}")

    def save_to_file(self, query: str, page: int, items: list):
        fname = self.save_dir / f"{query.replace(' ', '_')}_page{page}.txt"
        with open(fname, "w", encoding="utf-8") as f:
            for item in items:
                f.write(f"{item['title']}\n{item['link']}\n\n")
        self.console.print(f"[dim]📁 Save to:[/dim] {fname}")


def load_config() -> dict:
    config = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                config.update(json.load(f))
        except Exception as e:
            Console().print(f"[red]⚠️ Failed read from config.json:[/red] {e}")

    if ENV_FILE.exists():
        load_dotenv(dotenv_path=ENV_FILE)

    config.setdefault("api_key", os.getenv("GOOGLE_API_KEY"))
    config.setdefault("cse_id", os.getenv("GOOGLE_CSE_ID"))
    config.setdefault("browser_bin_path", os.getenv("BROWSER_BIN_PATH"))

    return config


def main():
    parser = argparse.ArgumentParser(
        description="🔍 Google Search CLI",
        formatter_class=CustomRichHelpFormatter,
    )
    parser.add_argument("query", help="Search for", nargs='*')
    parser.add_argument("--max", type=int, default=10, help="Number max of results (default: 10, maks: 100)")
    parser.add_argument("--apikey", help="Google API key")
    parser.add_argument("--cseid", help="Google Custom Search Engine ID")
    parser.add_argument("--save", help="Folder to save to file (optional)")
    parser.add_argument("--browser", help="Path to executable browser (ex: /usr/bin/firefox)")

    if len(sys.argv) == 1:
        parser.print_help()
        exit(0)

    args = parser.parse_args()
    if args.max > 100:
        print("⚠️ Maximum results is 100 cause limit of Google API.")
        args.max = 100

    config = load_config()

    api_key = args.apikey or config.get("api_key")
    cse_id = args.cseid or config.get("cse_id")
    browser_bin_path = args.browser or config.get("browser_bin_path")

    if not api_key or not cse_id:
        Console().print("[bold red]❌ API key and CSE ID not given.Use argument or config.json / .env[/bold red]")
        return

    query_str = " ".join(args.query)
    per_page = min(10, args.max)
    searcher = GoogleSearcher(api_key, cse_id, browser_path=browser_bin_path, save_dir=args.save)

    page = 1
    while True:
        items = searcher.search(query_str, page=page, per_page=per_page)
        if not items:
            break

        searcher.print_results(items, page)

        text = "\n[bold yellow]Navigasi:[/bold yellow] "
        text += rf"[black on #00FFFF]\[n][/][#00FFFF]ext[/] "
        text += rf"[black on #FFAA00]\[p][/][#FFAA00]revious[/] "
        text += rf"[white on #5500FF]\[g][/][#5500FF]oto[/] "
        text += rf"[white on red]\[q\|x][/][#FFAAFF]uit or [#FFAAFF]e[/][white on #FFAAFF]x[/][#FFAAFF]it[/] "
        text += rf"[bold #ffff00]select number to go[/]"
        searcher.console.print(text)
        cmd = searcher.console.input("> ").strip().lower()
        # print(f"cmd: {cmd}")
        if cmd == "n" and page < searcher.total_pages:
            page += 1
        elif cmd == "p" and page > 1:
            page -= 1
        elif cmd.startswith("g"):
            try:
                goto = int(cmd.split()[1]) if len(cmd.split()) > 1 else int(input("Goto page: "))
                if 1 <= goto <= searcher.total_pages:
                    page = goto
                else:
                    print("Page not Found.")
            except Exception:
                print("Invalid Format. Use 'g 3' or type number.")
        elif cmd.lower() in ["q", 'quit', 'e', 'exit']:
            break
        elif cmd.isdigit():
            idx = int(cmd)
            if 1 <= idx <= len(items):
                url = items[idx - 1]['link']
                searcher.open_in_browser(url)
            else:
                print("Invalid Number.")
        else:
            if cmd: 
                query_str = cmd
                searcher = GoogleSearcher(api_key, cse_id, browser_path=browser_bin_path, save_dir=args.save)
            else:
                print("Unknown Command.")


if __name__ == "__main__":
    main()
