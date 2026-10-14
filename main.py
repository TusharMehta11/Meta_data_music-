"""LLm_music command line.

    python main.py doctor                     check Ollama, model, FTP login and web sources
    python main.py scan [--source URL|DIR]    find metadata + covers (never modifies audio files)
    python main.py review                     open the local review page
    python main.py apply [--dry-run]          write approved tags/covers (with backups)
    python main.py export --out review.csv    CSV dump of everything
"""
import argparse
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for _stream in (sys.stdout, sys.stderr):  # show progress immediately, even when piped to a log file
    try:
        _stream.reconfigure(line_buffering=True, errors="replace")
    except Exception:
        pass
sys.path.insert(0, str(HERE))

from llm_music.util import load_env  # noqa: E402

load_env(HERE / ".env")


def cmd_doctor(args, store):
    from llm_music.files import open_source
    from llm_music.judge import LLM
    from llm_music.sources import Http, deezer, itunes, musicbrainz, youtube_music

    llm = LLM(model=args.model)
    problem = llm.check()
    print(f"LLM      {llm.model} @ {llm.url}: {'OK' if not problem else problem}")
    http = Http(store)
    for name, fn in [("musicbrainz", lambda: musicbrainz(http, text="Bohemian Rhapsody Queen")),
                     ("youtube_music", lambda: youtube_music(http, "Bohemian Rhapsody Queen")),
                     ("itunes", lambda: itunes(http, "Bohemian Rhapsody Queen")),
                     ("deezer", lambda: deezer(http, "Bohemian Rhapsody Queen"))]:
        try:
            n = len(fn())
            print(f"{name:<14}{'OK' if n else 'EMPTY (blocked in your region?)'} ({n} results)")
        except Exception as e:
            print(f"{name:<14}FAILED: {e}")
    if args.source:
        try:
            src = open_source(args.source, store.dir / "backups")
            files = src.list()
            src.close()
            print(f"source       OK: {len(files)} audio files in {args.source}")
        except Exception as e:
            print(f"source       FAILED: {e}")


def main():
    p = argparse.ArgumentParser(description="Fix music metadata and cover art using web sources + a local LLM.")
    p.add_argument("--data", default=str(HERE / "data"), help="Folder for the database, covers and local backups")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("doctor", help="Check that everything is reachable")
    d.add_argument("--source", default=os.getenv("MUSIC_SOURCE"))
    d.add_argument("--model")

    s = sub.add_parser("scan", help="Find metadata and covers; never modifies audio files")
    s.add_argument("--source", default=os.getenv("MUSIC_SOURCE"),
                   help="Local folder or ftp://host:port/path (default: MUSIC_SOURCE in .env)")
    s.add_argument("--limit", type=int, help="Scan at most N new files (try 20 first)")
    s.add_argument("--rescan", action="store_true", help="Re-scan files that were already scanned")
    s.add_argument("--llm", choices=["auto", "all", "off"], default="auto",
                   help="auto = only unclear matches go to the LLM (default); all = every file; off = heuristic only")
    s.add_argument("--model", help="Ollama model (default LLM_MODEL in .env or qwen3:4b)")
    s.add_argument("--auto-approve", type=int, metavar="CONF",
                   help="Pre-approve matches with confidence >= CONF, 2+ agreeing sources and length within 5s")
    s.add_argument("--sources", default=os.getenv("SOURCES", "musicbrainz,youtube_music,itunes"),
                   help="Comma-separated: musicbrainz,youtube_music,itunes,deezer (Deezer returns empty "
                        "results in some countries, e.g. India, so it is off by default)")

    r = sub.add_parser("review", help="Open the local review page")
    r.add_argument("--port", type=int, default=8765)
    r.add_argument("--no-browser", action="store_true")

    a = sub.add_parser("apply", help="Write approved tags and covers (backs up originals first)")
    a.add_argument("--dry-run", action="store_true", help="Test the writes on temporary copies only")
    a.add_argument("--no-covers", action="store_true", help="Write tags only, keep existing covers")

    e = sub.add_parser("export", help="Export all results to CSV")
    e.add_argument("--out", default=str(HERE / "data" / "review.csv"))

    args = p.parse_args()
    from llm_music.storage import Store
    store = Store(Path(args.data) / "llm_music.sqlite3")
    try:
        if args.cmd == "doctor":
            cmd_doctor(args, store)
        elif args.cmd == "scan":
            if not args.source:
                p.error("pass --source or set MUSIC_SOURCE in .env")
            from llm_music.pipeline import scan
            scan(store, args.source, limit=args.limit, rescan=args.rescan, llm_mode=args.llm, model=args.model,
                 auto_approve=args.auto_approve, sources=[x.strip() for x in args.sources.split(",") if x.strip()])
        elif args.cmd == "review":
            from llm_music.review import serve
            serve(store, args.port, not args.no_browser)
        elif args.cmd == "apply":
            from llm_music.pipeline import apply
            apply(store, dry_run=args.dry_run, covers=not args.no_covers)
        elif args.cmd == "export":
            from llm_music.pipeline import export_csv
            export_csv(store, args.out)
    except Exception as ex:
        print("ERROR:", ex, file=sys.stderr)
        sys.exit(1)
    finally:
        store.close()


if __name__ == "__main__":
    main()
